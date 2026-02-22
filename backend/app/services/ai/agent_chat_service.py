"""
智能体对话执行 Service

编排完整对话流程：创建/续接对话 → 加载历史 → 调 ExecutionDispatcher → 持久化消息
"""

import time
from typing import Any

from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.ai.agent_quota import (
    AgentConcurrencyExceeded,
    AgentConcurrencyLimiter,
    AgentQuotaConfig,
    AgentQuotaExceeded,
    AgentQuotaManager,
)
from app.ai.agent_stats import AgentStatsManager
from app.ai.engine.base import BaseEngine
from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.dispatcher import ExecutionDispatcher
from app.ai.utils.token_estimator import estimate_tokens
from app.ai.engine.types import ExecutionRequest, ExecutionResult
from app.ai.events.hooks import HookPoint, get_hook_registry
from app.ai.gateway import AIGateway
from app.ai.tools.sandbox import ToolSandbox
from app.ai.types import ChatMessage
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import (
    AgentExecutionModeEnum,
    AgentStatusEnum,
)
from app.enums.common import UserRoleEnum
from app.exceptions import BusinessException, NotFoundException
from app.repositories.ai.agent_repository import AgentRepository
from app.schemas.ai.agent_chat import AgentChatResponse
from app.services.ai.conversation_service import ConversationService

logger = LogManager.get_logger("ai.agent_chat_service")


class AgentChatService:
    """
    智能体对话执行 Service

    职责：
    1. 创建或续接对话（AgentConversation）
    2. 从 ConversationMessage 加载历史消息
    3. 将历史 + 新消息转换为 ChatMessage 列表
    4. 调用 ExecutionDispatcher 完成推理
    5. 将新消息持久化为 ConversationMessage
    6. 更新对话统计信息

    注意：本 Service 不继承 TenantService，因为它不管理单一 CRUD 模型，
    而是编排多个 Repository 和 Engine 完成对话执行。
    """

    def __init__(self, db: AsyncSession, tenant_id: int):
        """
        Args:
            db: 异步数据库会话
            tenant_id: 租户 ID
        """
        self.db = db
        self.tenant_id = tenant_id
        self.conversation_svc = ConversationService(db, tenant_id)

    # ========================================
    # 内部方法：Agent 校验
    # ========================================

    async def _validate_agent(self, agent_id: int) -> "Agent":
        """
        加载并校验 Agent（存在性 + 已发布状态）

        Args:
            agent_id: 智能体 ID

        Returns:
            Agent 实例

        Raises:
            NotFoundException: 智能体不存在
            BusinessException: 智能体未发布
        """
        agent_repo = AgentRepository(self.db, self.tenant_id)
        agent = await agent_repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))
        if agent.status != AgentStatusEnum.PUBLISHED.value:
            raise BusinessException(message=_("agent.error.not_published"))
        return agent

    # ========================================
    # 非流式对话
    # ========================================

    async def chat(
        self,
        agent_id: int,
        message: str,
        conversation_id: int | None = None,
        variables: dict[str, Any] | None = None,
        user_id: int | None = None,
        knowledge_base_ids: list[int] | None = None,
        user_role: str = UserRoleEnum.TENANT_ADMIN.value,
        permissions: set[str] | None = None,
        consented_actions: list[str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
    ) -> AgentChatResponse:
        """
        非流式对话

        完整流程：
        校验 Agent → 获取/创建对话 → 加载历史 → 构建消息 → 调 dispatcher → 持久化 → 返回

        Args:
            agent_id: 智能体 ID
            message: 用户消息
            conversation_id: 对话 ID（续接时传入）
            variables: 输入变量（注入到 system_prompt 占位符）
            user_id: 用户 ID
            user_role: 用户角色（platform_admin / tenant_admin / tenant_user）
            permissions: 用户 RBAC 权限码集合

        Returns:
            AgentChatResponse

        Raises:
            NotFoundException: 智能体或对话不存在
            BusinessException: 智能体未发布、对话已归档、执行失败
        """
        start = time.perf_counter()

        # 0. 加载并校验 Agent（必须已发布）
        agent = await self._validate_agent(agent_id)

        # 1. 获取或创建对话
        is_new_conversation = conversation_id is None
        conversation = await self.conversation_svc.get_or_create_for_chat(
            agent_id=agent_id,
            conversation_id=conversation_id,
            user_id=user_id,
            first_message=message,
        )

        # 1.5 新对话时递增每日对话计数（用于 conversations_per_day 配额）
        if is_new_conversation:
            await AgentQuotaManager.record_conversation(
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                user_id=user_id,
            )

        # 2. 加载历史消息 → 转换为 ChatMessage（受 agent.context_config 控制）
        ctx_cfg = agent.context_config or {}
        history_messages = await self.conversation_svc.load_chat_history(
            conversation_id=conversation.id,
            max_messages=ctx_cfg.get("max_history_messages", 0),
            max_tokens=ctx_cfg.get("max_history_tokens", 0),
        )

        # 3. 追加新用户消息（含附件）
        user_msg = ChatMessage(
            role="user", content=message,
            attachments=[a if isinstance(a, dict) else a.model_dump() for a in attachments] if attachments else None,
        )
        all_messages = [*history_messages, user_msg]

        # 4. 构建执行请求
        request = ExecutionRequest(
            agent_id=agent_id,
            tenant_id=self.tenant_id,
            user_id=user_id,
            messages=all_messages,
            input_variables=variables or {},
            execution_mode=AgentExecutionModeEnum.CONVERSATION.value,
            conversation_id=conversation.id,
            knowledge_base_ids=knowledge_base_ids,
            consented_actions=consented_actions,
            user_role=user_role,
            permissions=permissions,
        )

        # 5. 调用分发器
        dispatcher = ExecutionDispatcher(self.db)
        result = await dispatcher.dispatch(request)

        if not result.success:
            raise BusinessException(message=result.error or _("agent_chat.error.execution_failed"))

        # 6. 持久化新消息（用户消息 + 引擎生成的消息）
        tool_calls_collected = await self.conversation_svc.persist_chat_messages(
            conversation=conversation,
            result=result,
            history_count=len(history_messages),
        )

        # 7. 更新对话统计 + 智能体用量统计
        await self.conversation_svc.update_stats(conversation, result)
        await AgentStatsManager.record_chat(
            tenant_id=self.tenant_id,
            agent_id=agent_id,
            tokens=result.total_tokens,
        )
        await self.db.commit()

        duration_ms = int((time.perf_counter() - start) * 1000)

        logger.info(
            "Chat completed: agent=%d conversation=%d tokens=%d duration=%dms",
            agent_id,
            conversation.id,
            result.total_tokens,
            duration_ms,
        )

        return AgentChatResponse(
            conversation_id=conversation.id,
            message=result.output,
            tool_calls=tool_calls_collected or None,
            total_tokens=result.total_tokens,
            duration_ms=duration_ms,
        )

    # ========================================
    # 流式对话（M16-T3-2 实现）
    # ========================================

    async def stream_chat(
        self,
        agent_id: int,
        message: str,
        conversation_id: int | None = None,
        variables: dict[str, Any] | None = None,
        user_id: int | None = None,
        knowledge_base_ids: list[int] | None = None,
        user_role: str = UserRoleEnum.TENANT_ADMIN.value,
        permissions: set[str] | None = None,
        consented_actions: list[str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
        image_params: dict[str, Any] | None = None,
    ) -> StreamingResponse:
        """
        流式对话（返回 StreamingResponse）

        流程：加载 Agent → 创建/续接对话 → 加载历史 → 通过 engine.stream_execute SSE 推送

        Args:
            agent_id: 智能体 ID
            message: 用户消息
            conversation_id: 对话 ID（续接时传入）
            variables: 输入变量
            user_id: 用户 ID
            user_role: 用户角色（platform_admin / tenant_admin / tenant_user）
            permissions: 用户 RBAC 权限码集合

        Returns:
            StreamingResponse (SSE)
        """
        # 0. 加载并校验 Agent（必须已发布）
        agent = await self._validate_agent(agent_id)

        # 1. 获取或创建对话
        is_new_conversation = conversation_id is None
        conversation = await self.conversation_svc.get_or_create_for_chat(
            agent_id=agent_id,
            conversation_id=conversation_id,
            user_id=user_id,
            first_message=message,
        )

        # 1.5 新对话时递增每日对话计数
        if is_new_conversation:
            await AgentQuotaManager.record_conversation(
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                user_id=user_id,
            )

        # 1.6 提交对话创建，确保 on_stream_complete 回调的独立 session 能看到它
        await self.db.commit()

        # 2. 加载历史消息（使用 agent 的 context_config 窗口控制）
        ctx_cfg = agent.context_config or {}
        history_messages = await self.conversation_svc.load_chat_history(
            conversation_id=conversation.id,
            max_messages=ctx_cfg.get("max_history_messages", 0),
            max_tokens=ctx_cfg.get("max_history_tokens", 0),
        )

        # 3. 追加新用户消息（含附件）
        user_msg = ChatMessage(
            role="user", content=message,
            attachments=[a if isinstance(a, dict) else a.model_dump() for a in attachments] if attachments else None,
        )
        all_messages = [*history_messages, user_msg]

        # 4. 构建执行请求（标记为流式）
        request = ExecutionRequest(
            agent_id=agent_id,
            tenant_id=self.tenant_id,
            user_id=user_id,
            messages=all_messages,
            input_variables=variables or {},
            execution_mode=AgentExecutionModeEnum.CONVERSATION.value,
            stream=True,
            conversation_id=conversation.id,
            knowledge_base_ids=knowledge_base_ids,
            consented_actions=consented_actions,
            user_role=user_role,
            permissions=permissions,
        )

        # 5. 配额/并发/钩子前置检查（与 dispatcher.dispatch 对等）
        quota_config = AgentQuotaConfig.from_dict(agent.quota_config)
        lock_token: str = ""

        # 预估输入 Token 以启用原子预扣减（与 dispatcher 一致）
        estimated_tokens = max(
            sum(estimate_tokens(m.content or "") for m in all_messages),
            100,  # 至少 100 tokens（system prompt + 生成开销）
        )

        try:
            # 并发控制
            if quota_config.max_concurrent > 0 or quota_config.tenant_max_concurrent > 0:
                lock_token = await AgentConcurrencyLimiter.acquire(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    max_concurrent=quota_config.max_concurrent,
                    tenant_max_concurrent=quota_config.tenant_max_concurrent,
                )

            # 配额检查（含原子预扣减，防止并发超限）
            await AgentQuotaManager.check_quota(
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                config=quota_config,
                estimated_tokens=estimated_tokens,
            )
            if user_id:
                await AgentQuotaManager.check_user_quota(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    user_id=user_id,
                    config=quota_config,
                )

            # BEFORE_EXECUTE 钩子
            hook_registry = get_hook_registry()
            hook_context = await hook_registry.trigger(
                HookPoint.BEFORE_EXECUTE,
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                execution_mode=request.execution_mode,
                request=request,
            )
            if hook_context.get("blocked"):
                reason = hook_context.get("block_reason", _("agent.error.blocked_by_hook"))
                raise BusinessException(message=reason)

            # ExecutionStarted 事件
            await BaseEngine._publish_execution_started(request, agent)

        except (AgentQuotaExceeded, AgentConcurrencyExceeded):
            # 释放并发锁后重新抛出
            if lock_token:
                await AgentConcurrencyLimiter.release(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    lock_token=lock_token,
                )
            raise

        # 6. 创建 Gateway
        gateway = AIGateway(self.db)

        # 6.1 检测是否为生图模型 → 使用 ImageGenerationEngine
        model_obj = getattr(agent, "model", None)
        is_image_model = (
            model_obj is not None
            and getattr(model_obj, "type", "") == "image"
        )

        if is_image_model:
            from app.ai.engine.image_generation import ImageGenerationEngine
            engine = ImageGenerationEngine(gateway=gateway)
            skill_result = None
            skill_warnings: list[str] = []
        else:
            # 解析 Skill（在 Service 层完成，不在 Engine 内部查 DB）
            from app.ai.skills.resolver import resolve_for_agent
            skill_warnings = []
            try:
                skill_result = await resolve_for_agent(
                    self.db, agent, tenant_id=self.tenant_id,
                )
                if skill_result and skill_result.warnings:
                    skill_warnings = skill_result.warnings
            except Exception as skill_exc:
                logger.error(
                    "Skill resolution failed for agent %d: %s",
                    agent_id, str(skill_exc),
                )
                skill_result = None
                skill_warnings = [_("agent_chat.skill_load_failed")]

            # 读取平台 Toolkit 安全配置
            from app.configs.service import ConfigService
            _cfg = ConfigService(self.db)
            _toolkit_security_level = await _cfg.get_platform_config(
                "toolkit_security_level", default="normal",
            )
            _toolkit_memory_limit_mb = await _cfg.get_platform_config(
                "toolkit_memory_limit_mb", default=256,
            )

            sandbox = ToolSandbox(
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                user_id=user_id,
                user_role=user_role,
                permissions=permissions,
                gateway=gateway,
                db=self.db,
                agent=agent,
                toolkit_security_level=str(_toolkit_security_level),
                toolkit_memory_limit_mb=int(_toolkit_memory_limit_mb),
            )
            engine = ConversationEngine(
                db=self.db,
                gateway=gateway,
                sandbox=sandbox,
            )

        # 7. 创建持久化回调（流式完成后调用，含配额记录+并发释放+钩子）
        history_count = len(history_messages)

        async def on_stream_complete(result: ExecutionResult) -> None:
            """流式完成后持久化消息 + 配额记录 + 并发释放

            使用独立 db session，不依赖 DI session 生命周期。
            SSE 生成器在响应体流式传输期间执行此回调，
            DI session 的 commit/close 时机取决于框架版本，
            独立 session 保证写入操作始终可靠。
            """
            try:
                if result.success:
                    # 独立 session：不依赖 DI session 生命周期
                    async with async_session_factory() as cb_db:
                        try:
                            cb_conv_svc = ConversationService(cb_db, self.tenant_id)
                            cb_conv = await cb_conv_svc.repo.get_by_id(
                                conversation.id,
                            )
                            await cb_conv_svc.persist_chat_messages(
                                conversation=cb_conv,
                                result=result,
                                history_count=history_count,
                            )
                            await cb_conv_svc.update_stats(
                                cb_conv, result,
                            )
                            await AgentStatsManager.record_chat(
                                tenant_id=self.tenant_id,
                                agent_id=agent_id,
                                tokens=result.total_tokens,
                            )
                            await cb_db.commit()
                        except Exception:
                            await cb_db.rollback()
                            raise

                # 配额调整：从预估调整为实际（与 dispatcher 对等）
                actual_tokens = result.total_tokens or 0
                await AgentQuotaManager.adjust_usage(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    estimated_tokens=estimated_tokens,
                    actual_tokens=actual_tokens,
                    config=quota_config,
                )

                # 用户级用量记录
                if user_id and actual_tokens > 0:
                    await AgentQuotaManager.record_user_usage(
                        tenant_id=self.tenant_id,
                        agent_id=agent_id,
                        user_id=user_id,
                        tokens=actual_tokens,
                    )

                # AFTER_EXECUTE 钩子
                await hook_registry.trigger(
                    HookPoint.AFTER_EXECUTE,
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    result=result,
                )

                # 发布执行完成/失败事件（流式模式绕过 dispatcher，需手动发布）
                if result.success:
                    await BaseEngine._publish_execution_completed(
                        request, agent, result,
                    )
                else:
                    await BaseEngine._publish_execution_failed(
                        request, agent, result.error or "",
                    )
            finally:
                # 释放并发锁
                if lock_token:
                    await AgentConcurrencyLimiter.release(
                        tenant_id=self.tenant_id,
                        agent_id=agent_id,
                        lock_token=lock_token,
                    )

        if is_image_model:
            return await engine.stream_execute(
                agent=agent,
                request=request,
                on_complete=on_stream_complete,
                image_params=image_params,
            )
        else:
            return await engine.stream_execute(
                agent=agent,
                request=request,
                on_complete=on_stream_complete,
                skill_result=skill_result,
            )

    # ========================================
    # 操作确认/取消
    # ========================================

    @staticmethod
    async def cancel_action(confirm_id: str) -> dict[str, str]:
        """
        取消 AI 操作确认

        删除 Redis 中的 confirm_id 记录

        Args:
            confirm_id: 确认 ID

        Returns:
            {"status": "cancelled" | "expired"}
        """
        from app.core.redis import get_redis
        from app.ai.constants import action_confirm_key

        redis = await get_redis()
        key = action_confirm_key(confirm_id)
        deleted_count = await redis.delete(key)

        if deleted_count:
            return {"status": "cancelled"}
        return {"status": "expired"}

    async def confirm_action(
        self,
        confirm_id: str,
        tenant_id: int,
        user_id: int,
    ) -> dict[str, Any]:
        """
        确认并执行 AI 操作

        旧版 ActionExecutor 已废弃，新的 CRUD 工具使用内联确认（confirmed 参数）。
        此方法仅处理遗留的 Redis 确认数据。

        Args:
            confirm_id: 确认 ID
            tenant_id: 租户 ID
            user_id: 用户 ID

        Returns:
            操作执行结果

        Raises:
            BusinessException: 确认已过期
        """
        raise BusinessException(
            message=_("data_intelligence.action.confirm_expired"),
        )


__all__ = ["AgentChatService"]
