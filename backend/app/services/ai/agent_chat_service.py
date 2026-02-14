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
from app.ai.engine.output_parser import parse_output
from app.ai.utils.token_estimator import estimate_tokens
from app.ai.engine.types import ExecutionRequest, ExecutionResult
from app.ai.events.hooks import HookPoint, get_hook_registry
from app.ai.gateway import AIGateway
from app.ai.tools.sandbox import ToolSandbox
from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import (
    AgentExecutionModeEnum,
    AgentStatusEnum,
    ConversationStatusEnum,
    MessageRoleEnum,
)
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent_conversation import AgentConversation
from app.models.ai.conversation_message import ConversationMessage
from app.repositories.ai.agent_conversation_repository import AgentConversationRepository
from app.repositories.ai.agent_repository import AgentRepository
from app.repositories.ai.conversation_message_repository import ConversationMessageRepository
from app.schemas.ai.agent_chat import AgentChatResponse

logger = LogManager.get_logger("ai.agent_chat_service")

# 历史消息最大加载条数（兜底默认值）
MAX_HISTORY_MESSAGES = 50

# 历史消息最大 Token 数（兜底默认值，0=不限制）
MAX_HISTORY_TOKENS = 0

# 对话标题最大长度
MAX_TITLE_LENGTH = 100


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
        self.conversation_repo = AgentConversationRepository(db, tenant_id)
        self.message_repo = ConversationMessageRepository(db, tenant_id)

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
        user_role: str = "tenant_admin",
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
        conversation = await self._get_or_create_conversation(
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
        history_messages = await self._load_history_as_chat_messages(
            conversation_id=conversation.id,
            max_messages=ctx_cfg.get("max_history_messages", MAX_HISTORY_MESSAGES),
            max_tokens=ctx_cfg.get("max_history_tokens", MAX_HISTORY_TOKENS),
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
        tool_calls_collected = await self._persist_new_messages(
            conversation=conversation,
            result=result,
            history_count=len(history_messages),
        )

        # 7. 更新对话统计 + 智能体用量统计
        await self._update_conversation_stats(conversation, result)
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
        user_role: str = "tenant_admin",
        permissions: set[str] | None = None,
        consented_actions: list[str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
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
        conversation = await self._get_or_create_conversation(
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
        history_messages = await self._load_history_as_chat_messages(
            conversation_id=conversation.id,
            max_messages=ctx_cfg.get("max_history_messages", MAX_HISTORY_MESSAGES),
            max_tokens=ctx_cfg.get("max_history_tokens", MAX_HISTORY_TOKENS),
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

        # 6. 创建引擎
        gateway = AIGateway(self.db)
        sandbox = ToolSandbox(
            tenant_id=self.tenant_id,
            agent_id=agent_id,
            user_id=user_id,
            user_role=user_role,
            permissions=permissions,
            gateway=gateway,
            db=self.db,
            agent=agent,
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
                            cb_svc = AgentChatService(cb_db, self.tenant_id)
                            cb_conv = await cb_svc.conversation_repo.get_by_id(
                                conversation.id,
                            )
                            await cb_svc._persist_new_messages(
                                conversation=cb_conv,
                                result=result,
                                history_count=history_count,
                            )
                            await cb_svc._update_conversation_stats(
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

        return await engine.stream_execute(
            agent=agent,
            request=request,
            on_complete=on_stream_complete,
        )

    # ========================================
    # 内部方法：对话管理
    # ========================================

    async def _get_or_create_conversation(
        self,
        agent_id: int,
        conversation_id: int | None,
        user_id: int | None,
        first_message: str,
    ) -> AgentConversation:
        """
        获取或创建对话

        Args:
            agent_id: 智能体 ID
            conversation_id: 已有对话 ID（续接时传入）
            user_id: 用户 ID
            first_message: 首条消息（用于生成标题）

        Returns:
            AgentConversation 实例

        Raises:
            NotFoundException: 对话不存在
            BusinessException: 对话已归档
        """
        if conversation_id:
            # 续接已有对话
            conversation = await self.conversation_repo.get_by_id(conversation_id)
            if not conversation:
                raise NotFoundException(message=_("agent_chat.error.conversation_not_found"))

            if conversation.status == ConversationStatusEnum.ARCHIVED.value:
                raise BusinessException(
                    message=_("agent_chat.error.conversation_archived"),
                )

            return conversation

        # 创建新对话
        title = first_message[:MAX_TITLE_LENGTH].strip()
        conversation = await self.conversation_repo.create({
            "tenant_id": self.tenant_id,
            "agent_id": agent_id,
            "user_id": user_id,
            "title": title,
            "status": ConversationStatusEnum.ACTIVE.value,
            "token_count": 0,
            "cost": 0,
        })

        logger.info(
            "Conversation created: id=%d agent=%d tenant=%d",
            conversation.id,
            agent_id,
            self.tenant_id,
        )

        return conversation

    # ========================================
    # 内部方法：消息加载与转换
    # ========================================

    async def _load_history_as_chat_messages(
        self,
        conversation_id: int,
        max_messages: int = MAX_HISTORY_MESSAGES,
        max_tokens: int = MAX_HISTORY_TOKENS,
    ) -> list[ChatMessage]:
        """
        从 ConversationMessage 加载历史消息并转换为 ChatMessage

        支持两级截断：
        1. max_messages: 最多保留最近 N 条消息
        2. max_tokens: 历史消息总 token 不超过 N（从最旧开始移除）

        Args:
            conversation_id: 对话 ID
            max_messages: 最大消息条数
            max_tokens: 最大 token 数（0 = 不限制）

        Returns:
            ChatMessage 列表（不含 system 消息，由引擎构建）
        """
        effective_limit = max_messages if max_messages > 0 else MAX_HISTORY_MESSAGES
        db_messages = await self.message_repo.get_last_n_messages(
            conversation_id=conversation_id,
            n=effective_limit,
        )

        chat_messages: list[ChatMessage] = []
        for msg in db_messages:
            # 跳过 system 消息（由引擎重新构建）
            if msg.role == MessageRoleEnum.SYSTEM.value:
                continue

            # 从 metadata 恢复附件（用于多模态历史消息）
            msg_attachments = None
            if msg.metadata_ and isinstance(msg.metadata_, dict):
                msg_attachments = msg.metadata_.get("attachments")

            chat_messages.append(
                ChatMessage(
                    role=msg.role,
                    content=msg.content or "",
                    tool_calls=msg.tool_calls,
                    tool_call_id=msg.tool_call_id,
                    attachments=msg_attachments,
                ),
            )

        # Token 截断：从最旧消息开始移除，直到总 token 不超过 max_tokens
        if max_tokens > 0 and chat_messages:
            total = sum(estimate_tokens(m.content or "") for m in chat_messages)
            while total > max_tokens and len(chat_messages) > 1:
                removed = chat_messages.pop(0)
                total -= estimate_tokens(removed.content or "")

        # 清理孤立的 tool 消息（前面没有 tool_calls 的 assistant 消息）
        chat_messages = self._sanitize_tool_messages(chat_messages)

        return chat_messages

    @staticmethod
    def _sanitize_tool_messages(
        messages: list[ChatMessage],
    ) -> list[ChatMessage]:
        """清理孤立的 tool/tool_calls 消息，防止 LLM API 400 错误

        规则：
        - role=tool 的消息前面必须有一条带 tool_calls 的 assistant 消息
        - 如果截断导致 assistant(tool_calls) 丢失，相关的 tool 消息也要移除
        - 如果 tool 消息被移除，对应的 assistant(tool_calls) 也要移除
        """
        if not messages:
            return messages

        # 收集所有 assistant 消息中声明的 tool_call id
        declared_tc_ids: set[str] = set()
        for msg in messages:
            if msg.role == "assistant" and msg.tool_calls:
                for tc in msg.tool_calls:
                    tc_id = tc.get("id", "")
                    if tc_id:
                        declared_tc_ids.add(tc_id)

        # 第一遍：移除 tool_call_id 不在声明集合中的 tool 消息
        cleaned: list[ChatMessage] = []
        for msg in messages:
            if msg.role == "tool":
                if msg.tool_call_id and msg.tool_call_id in declared_tc_ids:
                    cleaned.append(msg)
                # else: 孤立的 tool 消息，跳过
            else:
                cleaned.append(msg)

        # 第二遍：收集实际保留的 tool 回复的 id
        answered_tc_ids: set[str] = set()
        for msg in cleaned:
            if msg.role == "tool" and msg.tool_call_id:
                answered_tc_ids.add(msg.tool_call_id)

        # 第三遍：移除 tool_calls 中所有 id 都没有对应 tool 回复的 assistant 消息
        result: list[ChatMessage] = []
        for msg in cleaned:
            if msg.role == "assistant" and msg.tool_calls:
                tc_ids_in_msg = {tc.get("id", "") for tc in msg.tool_calls}
                if tc_ids_in_msg & answered_tc_ids:
                    result.append(msg)
                # else: assistant 的 tool_calls 全部没有 tool 回复，跳过
            else:
                result.append(msg)

        return result

    # ========================================
    # 内部方法：消息持久化
    # ========================================

    async def _persist_new_messages(
        self,
        conversation: AgentConversation,
        result: ExecutionResult,
        history_count: int,
    ) -> list[dict[str, Any]]:
        """
        将执行过程中产生的新消息持久化为 ConversationMessage

        ExecutionResult.messages 结构:
        [system, ...history..., new_user, (assistant+tool_calls, tool, ...,)* final_assistant]

        我们需要持久化 new_user 及之后的所有消息（跳过 system 和 history）。

        Args:
            conversation: 对话实例
            result: 执行结果
            history_count: 历史消息数量（用于计算新消息起始位置）

        Returns:
            收集到的 tool_calls（用于响应）
        """
        # 动态计算前缀 system 消息数（而非硬编码 1）
        system_count = 0
        for msg_dict in result.messages:
            if msg_dict.get("role") == "system":
                system_count += 1
            else:
                break
        new_start = system_count + history_count
        new_messages = result.messages[new_start:]

        if not new_messages:
            return []

        # 构建 tool_call_id → ToolResult 的查找表（用于存储工具执行结果元数据）
        tool_result_map: dict[str, ToolResult] = {}
        if result.tool_results:
            for tr in result.tool_results:
                if tr.tool_call_id:
                    tool_result_map[tr.tool_call_id] = tr

        # 获取下一个 sequence
        next_seq = await self.message_repo.get_next_sequence(conversation.id)
        tool_calls_collected: list[dict[str, Any]] = []

        for i, msg_dict in enumerate(new_messages):
            role = msg_dict.get("role", "")
            content = msg_dict.get("content", "")
            tool_calls = msg_dict.get("tool_calls")
            tool_call_id = msg_dict.get("tool_call_id")
            attachments = msg_dict.get("attachments")

            # 收集 tool_calls 用于响应
            if tool_calls:
                tool_calls_collected.extend(tool_calls)

            # 估算 token 数（CJK 感知，精确值在 LLM 层记录）
            token_estimate = estimate_tokens(content) if content else 0

            # 附件存入 metadata（用于历史消息回显）
            metadata = None
            if attachments:
                metadata = {"attachments": attachments}

            # tool 角色消息：存储工具执行成功/失败状态到 metadata
            if role == "tool" and tool_call_id and tool_call_id in tool_result_map:
                tr = tool_result_map[tool_call_id]
                metadata = metadata or {}
                metadata["tool_success"] = tr.success
                if not tr.success and tr.error:
                    metadata["tool_error"] = tr.error

            await self.message_repo.create({
                "tenant_id": self.tenant_id,
                "conversation_id": conversation.id,
                "role": role,
                "content": content,
                "sequence": next_seq + i,
                "token_count": token_estimate,
                "tool_calls": tool_calls,
                "tool_call_id": tool_call_id,
                "metadata_": metadata,
            })

        # 递增 message_count 冗余计数
        new_message_count = (conversation.message_count or 0) + len(new_messages)
        await self.conversation_repo.update(
            conversation.id,
            {"message_count": new_message_count},
        )

        return tool_calls_collected

    async def _update_conversation_stats(
        self,
        conversation: AgentConversation,
        result: ExecutionResult,
    ) -> None:
        """
        更新对话统计信息，并尝试提取输出变量

        Args:
            conversation: 对话实例
            result: 执行结果
        """
        new_token_count = (conversation.token_count or 0) + result.total_tokens
        new_total_tokens = (conversation.total_tokens or 0) + result.total_tokens

        update_data: dict[str, Any] = {
            "token_count": new_token_count,
            "total_tokens": new_total_tokens,
        }

        # 尝试提取输出变量（如果 agent 配置了 output_schema）
        agent = conversation.agent
        if agent and agent.output_schema and result.output:
            extracted = parse_output(result.output, agent.output_schema)
            if extracted:
                metadata = dict(conversation.metadata_ or {})
                metadata["output_variables"] = extracted
                update_data["metadata_"] = metadata

        await self.conversation_repo.update(
            conversation.id,
            update_data,
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
