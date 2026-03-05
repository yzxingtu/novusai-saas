"""
智能体对话执行 Service

编排完整对话流程：创建/续接对话 → 加载历史 → 调 ExecutionDispatcher → 持久化消息
"""

import time
from typing import TYPE_CHECKING, Any

from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent_quota import (
    AgentConcurrencyExceeded,
    AgentConcurrencyLimiter,
    AgentQuotaConfig,
    AgentQuotaExceeded,
    AgentQuotaManager,
)
from app.ai.agent_stats import AgentStatsManager
from app.ai.constants import (
    DEFAULT_MEMORY_SCENE,
    MEMORY_CHANNEL_SYSTEM,
)
from app.ai.engine.base import BaseEngine
from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.dispatcher import ExecutionDispatcher
from app.ai.engine.types import ExecutionRequest, ExecutionResult
from app.ai.events.hooks import HookPoint, get_hook_registry
from app.ai.gateway import AIGateway
from app.ai.tools.sandbox import ToolSandbox
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens
from app.core.database import async_session_factory
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import (
    AgentExecutionModeEnum,
    AgentStatusEnum,
    MemoryChannelEnum,
    MemorySceneEnum,
)
from app.enums.common import UserRoleEnum
from app.exceptions import BusinessException, NotFoundException
from app.repositories.ai.agent_repository import AgentRepository
from app.schemas.ai.agent_chat import AgentChatResponse
from app.services.ai.conversation_service import ConversationService
from app.services.ai.session_memory_service import SessionMemoryService

if TYPE_CHECKING:
    from app.models.ai.agent import Agent

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
        if self.tenant_id == 0:
            from app.repositories.ai.agent_repository import AdminAgentRepository
            agent_repo = AdminAgentRepository(self.db)
        else:
            agent_repo = AgentRepository(self.db, self.tenant_id)
        agent = await agent_repo.get_by_id(agent_id)
        if not agent:
            raise NotFoundException(message=_("agent.error.not_found"))
        if agent.status != AgentStatusEnum.PUBLISHED.value:
            raise BusinessException(message=_("agent.error.not_published"))
        return agent

    @staticmethod
    def _extract_memory_delta(
        message: str,
        response: str,
    ) -> dict[str, list[str]]:
        """
        从本轮对话中提取会话记忆增量（轻量规则版）

        仅提取偏好/约束/任务状态/可验证事实，避免全量污染。
        """
        text = (message or "").strip()
        if not text:
            return {
                "preferences": [],
                "constraints": [],
                "task_states": [],
                "verified_facts": [],
            }

        lowered = text.lower()
        preferences: list[str] = []
        constraints: list[str] = []
        task_states: list[str] = []
        verified_facts: list[str] = []

        # 偏好信号
        pref_markers = ["请用", "以后都用", "prefer", "please use", "use "]
        if any(m in text for m in pref_markers) or any(m in lowered for m in ["prefer", "please use"]):
            preferences.append(text[:300])

        # 约束信号
        constraint_markers = ["不要", "禁止", "必须", "不超过", "must", "do not", "don't", "should not"]
        if any(m in text for m in constraint_markers) or any(m in lowered for m in ["must", "do not", "should not"]):
            constraints.append(text[:300])

        # 任务状态信号
        task_markers = ["继续", "下一步", "待办", "todo", "next step", "continue"]
        if any(m in text for m in task_markers) or any(m in lowered for m in ["todo", "next step", "continue"]):
            task_states.append(text[:300])

        # 可验证事实（首版仅记录用户明确陈述；不做模型推断）
        fact_markers = ["我是", "我们是", "my ", "our ", "我的", "我们"]
        if any(m in text for m in fact_markers) or any(m in lowered for m in ["my ", "our "]):
            verified_facts.append(text[:300])

        # 显式“记住”指令，提高召回价值
        if "记住" in text or "remember" in lowered:
            constraints.append(f"[explicit_remember] {text[:300]}")

        # assistant 响应摘要（任务状态补充）
        resp = (response or "").strip()
        if resp:
            task_states.append(resp[:300])

        return {
            "preferences": preferences[:5],
            "constraints": constraints[:5],
            "task_states": task_states[:5],
            "verified_facts": verified_facts[:5],
        }

    async def _load_session_memory_context(
        self,
        *,
        request: ExecutionRequest,
    ) -> str:
        """
        读取会话记忆并拼装为可注入 system 的文本
        """
        if not request.memory_enabled:
            return ""
        if not request.conversation_id or not request.user_id:
            return ""

        try:
            memory_svc = SessionMemoryService(self.tenant_id)
            _, state = await memory_svc.get_state(
                channel=request.memory_channel,
                source=request.memory_source,
                agent_id=request.agent_id,
                user_id=request.user_id,
                conversation_id=request.conversation_id,
            )
        except Exception as exc:
            logger.warning(
                "Session memory load degraded: tenant=%s agent=%s user=%s conversation=%s err=%s",
                self.tenant_id,
                request.agent_id,
                request.user_id,
                request.conversation_id,
                str(exc),
            )
            return ""

        parts: list[str] = []
        if state.get("constraints"):
            parts.append("Constraints: " + " | ".join(state["constraints"][:6]))
        if state.get("preferences"):
            parts.append("Preferences: " + " | ".join(state["preferences"][:6]))
        if state.get("task_states"):
            parts.append("Task States: " + " | ".join(state["task_states"][:6]))
        if state.get("verified_facts"):
            parts.append("Verified Facts: " + " | ".join(state["verified_facts"][:6]))

        if not parts:
            logger.info(
                "Session memory context empty: tenant=%s agent=%s user=%s conversation=%s",
                self.tenant_id,
                request.agent_id,
                request.user_id,
                request.conversation_id,
            )
            return ""
        logger.info(
            "Session memory context injected: tenant=%s agent=%s user=%s conversation=%s",
            self.tenant_id,
            request.agent_id,
            request.user_id,
            request.conversation_id,
        )
        return "[SESSION MEMORY CONTEXT]\n" + "\n".join(parts)

    async def _persist_session_memory(
        self,
        *,
        request: ExecutionRequest,
        message: str,
        response: str,
        event_id: str,
    ) -> None:
        """
        将本轮对话增量写入会话记忆
        """
        if not request.memory_enabled:
            return
        if not request.conversation_id or not request.user_id:
            return

        delta = self._extract_memory_delta(message, response)
        if not any(delta.values()):
            return

        memory_svc = SessionMemoryService(self.tenant_id)
        await memory_svc.upsert_state(
            channel=request.memory_channel,
            source=request.memory_source,
            agent_id=request.agent_id,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            event_id=event_id,
            delta=delta,
            metadata={"scene": request.memory_scene},
        )

    @staticmethod
    def _resolve_memory_context(
        memory_scene: str,
        memory_channel: str,
        memory_source: str,
    ) -> tuple[str, str, str, bool]:
        """
        解析并归一化会话记忆场景参数。

        Returns:
            (scene, channel, source, enabled)
        """
        scene = (
            memory_scene
            if MemorySceneEnum.has_value(memory_scene)
            else MemorySceneEnum.UNKNOWN.value
        )
        channel = (
            memory_channel
            if MemoryChannelEnum.has_value(memory_channel)
            else MemoryChannelEnum.SYSTEM.value
        )
        source = memory_source or scene
        enabled = scene == MemorySceneEnum.AI_CHAT_PAGE.value
        return scene, channel, source, enabled

    async def _resolve_effective_memory_enabled(
        self,
        *,
        agent_id: int,
        scene: str,
        scene_enabled: bool,
    ) -> bool:
        """
        解析运行时最终记忆开关（入口场景 + 三层开关）

        规则：
        1) 非 ai_chat_page 场景直接关闭
        2) ai_chat_page 场景下叠加平台/管理端/租户三层开关
        """
        if not scene_enabled:
            return False

        try:
            if self.tenant_id == 0:
                from app.services.ai.agent_service import AdminAgentService

                config = await AdminAgentService(self.db).get_memory_config(agent_id)
            else:
                from app.services.ai.agent_service import AgentService

                config = await AgentService(self.db, self.tenant_id).get_memory_config(agent_id)

            enabled = bool(config.get("effective_memory_enabled", False))
            logger.info(
                "Session memory switch resolved: tenant=%s agent=%s scene=%s enabled=%s",
                self.tenant_id,
                agent_id,
                scene,
                enabled,
            )
            return enabled
        except Exception as exc:
            # 记忆开关解析失败时降级，不影响主对话链路
            logger.warning(
                "Resolve session memory switch degraded: tenant=%s agent=%s scene=%s err=%s",
                self.tenant_id,
                agent_id,
                scene,
                str(exc),
            )
            return False

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
        memory_scene: str = DEFAULT_MEMORY_SCENE,
        memory_channel: str = MEMORY_CHANNEL_SYSTEM,
        memory_source: str = "",
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

        # 3.5 BEFORE_AGENT_CHAT 钩子（插件可修改 messages/注入 system prompt/阻止对话）
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.BEFORE_AGENT_CHAT):
            hook_ctx = await hook_registry.trigger(
                HookPoint.BEFORE_AGENT_CHAT,
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                messages=all_messages,
                config={"variables": variables, "knowledge_base_ids": knowledge_base_ids},
            )
            if hook_ctx.get("blocked"):
                raise BusinessException(message=hook_ctx.get("block_reason", _("agent_chat.error.blocked_by_hook")))
            all_messages = hook_ctx.get("messages", all_messages)

        # 4. 构建执行请求
        normalized_scene, normalized_channel, normalized_source, memory_enabled = self._resolve_memory_context(
            memory_scene=memory_scene,
            memory_channel=memory_channel,
            memory_source=memory_source,
        )
        memory_enabled = await self._resolve_effective_memory_enabled(
            agent_id=agent_id,
            scene=normalized_scene,
            scene_enabled=memory_enabled,
        )
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
            memory_scene=normalized_scene,
            memory_channel=normalized_channel,
            memory_source=normalized_source,
            memory_enabled=memory_enabled,
        )

        # 4.1 会话记忆注入（仅 ai_chat_page 生效）
        mem_text = await self._load_session_memory_context(request=request)
        if mem_text:
            # system 消息优先，其次插入首位
            if request.messages and request.messages[0].role == "system":
                request.messages[0].content = f"{request.messages[0].content}\n\n{mem_text}"
            else:
                request.messages.insert(0, ChatMessage(role="system", content=mem_text))

        # 5. 调用分发器（传入已校验的 agent，避免 Dispatcher 内二次 DB 查询）
        dispatcher = ExecutionDispatcher(self.db)
        result = await dispatcher.dispatch(request, pre_loaded_agent=agent)

        if not result.success:
            raise BusinessException(message=result.error or _("agent_chat.error.execution_failed"))

        # 5.5 AFTER_AGENT_CHAT 钩子（插件可修改响应/触发后续动作）
        if hook_registry.has_hooks(HookPoint.AFTER_AGENT_CHAT):
            hook_ctx = await hook_registry.trigger(
                HookPoint.AFTER_AGENT_CHAT,
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                response=result.output,
                total_tokens=result.total_tokens,
            )
            if "response" in hook_ctx and hook_ctx["response"] != result.output:
                result.output = hook_ctx["response"]

        # 6. 持久化新消息（用户消息 + 引擎生成的消息）
        history_count = len(history_messages)
        tool_calls_collected = await self.conversation_svc.persist_chat_messages(
            conversation=conversation,
            result=result,
            history_count=history_count,
        )

        # 7. 更新对话统计 + 智能体用量统计
        await self.conversation_svc.update_stats(conversation, result)
        await AgentStatsManager.record_chat(
            tenant_id=self.tenant_id,
            agent_id=agent_id,
            tokens=result.total_tokens,
        )

        # 7.1 写入会话记忆（非阻塞主流程，失败仅告警）
        try:
            await self._persist_session_memory(
                request=request,
                message=message,
                response=result.output or "",
                event_id=f"{conversation.id}:{history_count}:{int(time.time())}",
            )
        except Exception as exc:
            logger.warning(
                "Persist session memory failed: tenant=%s conversation=%s err=%s",
                self.tenant_id,
                conversation.id,
                str(exc),
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
        memory_scene: str = DEFAULT_MEMORY_SCENE,
        memory_channel: str = MEMORY_CHANNEL_SYSTEM,
        memory_source: str = "",
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

        # 3.5 BEFORE_AGENT_CHAT 钩子（插件可修改 messages/注入 system prompt/阻止对话）
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.BEFORE_AGENT_CHAT):
            hook_ctx = await hook_registry.trigger(
                HookPoint.BEFORE_AGENT_CHAT,
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                messages=all_messages,
                config={"variables": variables, "knowledge_base_ids": knowledge_base_ids},
            )
            if hook_ctx.get("blocked"):
                raise BusinessException(message=hook_ctx.get("block_reason", _("agent_chat.error.blocked_by_hook")))
            all_messages = hook_ctx.get("messages", all_messages)

        # 4. 构建执行请求（标记为流式）
        normalized_scene, normalized_channel, normalized_source, memory_enabled = self._resolve_memory_context(
            memory_scene=memory_scene,
            memory_channel=memory_channel,
            memory_source=memory_source,
        )
        memory_enabled = await self._resolve_effective_memory_enabled(
            agent_id=agent_id,
            scene=normalized_scene,
            scene_enabled=memory_enabled,
        )
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
            memory_scene=normalized_scene,
            memory_channel=normalized_channel,
            memory_source=normalized_source,
            memory_enabled=memory_enabled,
        )

        # 4.1 会话记忆注入（仅 ai_chat_page 生效）
        mem_text = await self._load_session_memory_context(request=request)
        if mem_text:
            if request.messages and request.messages[0].role == "system":
                request.messages[0].content = f"{request.messages[0].content}\n\n{mem_text}"
            else:
                request.messages.insert(0, ChatMessage(role="system", content=mem_text))

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

            # BEFORE_EXECUTE 钩子（hook_registry 已在 step 3.5 获取）
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
        else:
            # 解析 Skill（在 Service 层完成，不在 Engine 内部查 DB）
            from app.ai.skills.resolver import resolve_for_agent
            try:
                skill_result = await resolve_for_agent(
                    self.db, agent, tenant_id=self.tenant_id,
                )
            except Exception as skill_exc:
                logger.error(
                    "Skill resolution failed for agent %d: %s",
                    agent_id, str(skill_exc),
                )
                skill_result = None

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

                            # 写入会话记忆（流式完成后）
                            try:
                                await self._persist_session_memory(
                                    request=request,
                                    message=message,
                                    response=result.output or "",
                                    event_id=f"{conversation.id}:{history_count}:{int(time.time())}",
                                )
                            except Exception as mem_exc:
                                logger.warning(
                                    "Persist stream session memory failed: tenant=%s conversation=%s err=%s",
                                    self.tenant_id,
                                    conversation.id,
                                    str(mem_exc),
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

                # AFTER_AGENT_CHAT 钩子（插件可修改响应/触发后续动作）
                if hook_registry.has_hooks(HookPoint.AFTER_AGENT_CHAT):
                    hook_ctx = await hook_registry.trigger(
                        HookPoint.AFTER_AGENT_CHAT,
                        tenant_id=self.tenant_id,
                        agent_id=agent_id,
                        response=result.output,
                        total_tokens=result.total_tokens,
                    )
                    if "response" in hook_ctx and hook_ctx["response"] != result.output:
                        result.output = hook_ctx["response"]

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
        from app.ai.constants import action_confirm_key
        from app.core.redis import get_redis

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
        确认 AI 操作（兼容接口）

        旧版 ActionExecutor 已废弃，新的确认流程为内联文本触发：
        用户在对话中输入「确认执行」等触发词，引擎自动在消息历史中
        查找待确认的工具调用并注入 confirmed=True 直接执行，
        无需调用此 REST 端点。

        此方法保留以避免旧客户端接收 422，返回 deprecated 状态
        提醒调用方迁移到内联确认流程。

        Args:
            confirm_id: 确认 ID（不再使用）
            tenant_id: 租户 ID
            user_id: 用户 ID

        Returns:
            {"status": "deprecated", "message": "..."}
        """
        logger.warning(
            "confirm_action called via REST endpoint (deprecated): "
            "confirm_id=%s tenant=%d user=%d — "
            "new flow uses inline confirmation text in conversation",
            confirm_id, tenant_id, user_id,
        )
        return {
            "status": "deprecated",
            "message": _("data_intelligence.action.use_inline_confirmation"),
        }



__all__ = ["AgentChatService"]
