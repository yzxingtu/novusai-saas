"""
智能体对话执行 Service / Agent Chat Service

编排完整对话流程：创建/续接对话 → 加载历史 → 调 ExecutionDispatcher → 持久化消息
Orchestrates full chat flow: create/resume conversation → load history → call ExecutionDispatcher → persist messages.
"""

import json
import time
from typing import TYPE_CHECKING, Any
from uuid import uuid4

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
from app.configs.service import PLATFORM_TENANT_ID
from app.core.database import async_session_factory
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import (
    AgentExecutionModeEnum,
    AgentStatusEnum,
    ConversationOwnerTypeEnum,
    MemoryChannelEnum,
    MemorySceneEnum,
)
from app.enums.common import UserRoleEnum
from app.exceptions import BusinessException, NotFoundException
from app.repositories.ai.agent_repository import AgentRepository
from app.schemas.ai.agent_chat import AgentChatResponse, PageContext
from app.services.ai.conversation_service import ConversationService
from app.services.ai.session_memory_service import SessionMemoryService

if TYPE_CHECKING:
    from app.models.ai.agent import Agent

logger = LogManager.get_logger("ai.agent_chat_service")


class AgentChatService:
    """
    智能体对话执行 Service / Agent chat execution service.

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
        初始化 / Initialize.

        Args:
            db: 异步数据库会话
            tenant_id: 企业 ID
        """
        self.db = db
        self.tenant_id = tenant_id
        self.conversation_svc = ConversationService(db, tenant_id)

    # ========================================
    # 内部方法：Agent 校验 / Internal: Agent validation
    # ========================================

    async def _validate_agent(self, agent_id: int) -> "Agent":
        """
        加载并校验 Agent（存在性 + 已发布状态）。 / Load and validate agent (existence + published).

        Args:
            agent_id: 智能体 ID

        Returns:
            Agent 实例

        Raises:
            NotFoundException: 智能体不存在
            BusinessException: 智能体未发布
        """
        if self.tenant_id == PLATFORM_TENANT_ID:
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

    async def _sanitize_client_knowledge_base_ids(
        self,
        agent_id: int,
        knowledge_base_ids: list[int] | None,
    ) -> list[int] | None:
        """
        Keep only KB ids bound to the agent (tenant-scoped bindings). None => no narrowing.
        仅保留已绑定到智能体的知识库 ID；None 表示不按客户端列表收窄。
        """
        if not knowledge_base_ids:
            return None
        from app.ai.rag_injector import load_agent_kb_bindings

        bound_ids, _ = await load_agent_kb_bindings(self.db, agent_id, self.tenant_id)
        allowed = set(bound_ids or [])
        filtered = [x for x in knowledge_base_ids if x in allowed]
        dropped = [x for x in knowledge_base_ids if x not in allowed]
        if dropped:
            logger.warning(
                "Dropped knowledge_base_ids not bound to agent_id={}: {}",
                agent_id,
                dropped,
            )
        return filtered or None

    async def _build_billing_context(
        self,
        *,
        agent: "Agent",
        user_id: int | None,
        user_role: str,
        user_role_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Build immutable billing attribution context for the current entrypoint.
        为当前入口构建不可变计费归属上下文。
        """
        if self.tenant_id == PLATFORM_TENANT_ID:
            from app.services.ai.agent_service import AdminAgentService

            return await AdminAgentService(self.db).build_usage_attribution_context(
                agent=agent,
                user_id=user_id,
                user_role=user_role,
                user_role_id=user_role_id,
            )

        from app.services.ai.agent_service import AgentService

        return await AgentService(
            self.db,
            self.tenant_id,
        ).build_usage_attribution_context(
            agent=agent,
            user_id=user_id,
            user_role=user_role,
            user_role_id=user_role_id,
        )

    async def _extract_memory_delta(
        self,
        message: str,
        response: str,
        agent_id: int,
    ) -> dict[str, list[str]]:
        """
        使用 LLM 从本轮对话中提取会话记忆增量 / Extract session memory delta from this turn via LLM.

        相比关键词匹配版本，LLM 能更准确地理解上下文、
        区分重要信息、并生成简洁的摘要式记忆条目。

        使用独立 DB Session 以兼容流式回调场景。
        失败时静默降级返回空 delta，不影响主对话链路。
        """
        empty: dict[str, list[str]] = {
            "preferences": [],
            "constraints": [],
            "task_states": [],
            "verified_facts": [],
        }

        text = (message or "").strip()
        if not text or len(text) < 4:
            return empty

        try:
            async with async_session_factory() as llm_db:
                # 优先使用平台配置的记忆提取专用模型（成本更低）/ Prefer platform memory-extraction model (lower cost)
                from app.configs.service import ConfigService
                cfg = ConfigService(llm_db)
                cfg_provider = await cfg.get_platform_config(
                    "memory_extraction_provider", default="",
                )
                cfg_model = await cfg.get_platform_config(
                    "memory_extraction_model", default="",
                )

                if cfg_provider and cfg_model:
                    provider_code = cfg_provider
                    model_code = cfg_model
                else:
                    # 降级：使用 Agent 自身绑定的模型 / Fallback: use Agent's bound model
                    if self.tenant_id == PLATFORM_TENANT_ID:
                        from app.repositories.ai.agent_repository import AdminAgentRepository
                        agent_repo = AdminAgentRepository(llm_db)
                    else:
                        agent_repo = AgentRepository(llm_db, self.tenant_id)

                    agent = await agent_repo.get_by_id(agent_id)
                    if not agent:
                        return empty

                    model_obj = getattr(agent, "model", None)
                    if not model_obj or not getattr(model_obj, "provider", None):
                        return empty

                    provider_code = model_obj.provider.code
                    model_code = model_obj.code
                    if not provider_code or not model_code:
                        return empty

                extraction_prompt = (
                    "Analyze this conversation turn and extract information worth remembering.\n\n"
                    f"User message:\n{text[:1500]}\n\n"
                    f"Assistant response:\n{(response or '')[:1500]}\n\n"
                    "Extract ONLY genuinely important items into these categories:\n"
                    "- preferences: User's stated preferences, likes, dislikes, preferred formats/tools/styles\n"
                    "- constraints: Explicit restrictions, rules, things to avoid, 'don't do X'\n"
                    "- task_states: Current task progress, todos, next steps, ongoing work\n"
                    "- verified_facts: User's personal facts (name, role, company, tech stack, etc.)\n\n"
                    "Rules:\n"
                    "1. Only extract items the user explicitly stated or strongly implied\n"
                    "2. Summarize each item concisely (1 short sentence max)\n"
                    "3. If nothing worth remembering, return all empty arrays\n"
                    "4. Do NOT extract trivial greetings, acknowledgments, or filler\n"
                    "5. Do NOT repeat what the assistant said unless the user confirmed it as a preference\n\n"
                    'Respond ONLY with valid JSON (no markdown, no explanation):\n'
                    '{"preferences": [], "constraints": [], "task_states": [], "verified_facts": []}'
                )

                gateway = AIGateway(llm_db)
                llm_response = await gateway.chat(
                    provider_code=provider_code,
                    messages=[ChatMessage(role="user", content=extraction_prompt)],
                    model=model_code,
                    temperature=0.1,
                    max_tokens=500,
                    tenant_id=(
                        self.tenant_id
                        if self.tenant_id > PLATFORM_TENANT_ID
                        else None
                    ),
                )

                content = (llm_response.message.content or "").strip()
                # 处理 markdown 代码块包裹 / Strip markdown code block wrapper
                if content.startswith("```"):
                    lines = content.split("\n")
                    content = "\n".join(lines[1:])
                    if content.endswith("```"):
                        content = content[:-3].strip()

                data = json.loads(content)

                result: dict[str, list[str]] = {}
                for key in ("preferences", "constraints", "task_states", "verified_facts"):
                    raw_list = data.get(key) or []
                    result[key] = [
                        str(item).strip()[:300]
                        for item in raw_list
                        if item and str(item).strip()
                    ][:5]

                if any(result.values()):
                    logger.info(
                        "LLM memory extraction: tenant={} agent={} prefs={} constraints={} tasks={} facts={}",
                        self.tenant_id, agent_id,
                        len(result["preferences"]),
                        len(result["constraints"]),
                        len(result["task_states"]),
                        len(result["verified_facts"]),
                    )

                return result

        except Exception as exc:
            logger.warning(
                "LLM memory extraction failed, returning empty: tenant={} agent={} err={}",
                self.tenant_id, agent_id, str(exc),
            )
            return empty

    async def _load_session_memory_context(
        self,
        *,
        request: ExecutionRequest,
    ) -> str:
        """
        读取会话记忆并拼装为可注入 system 的文本 / Read session memory and build system-injectable text.
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
                "Session memory load degraded: tenant={} agent={} user={} conversation={} err={}",
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
                "Session memory context empty: tenant={} agent={} user={} conversation={}",
                self.tenant_id,
                request.agent_id,
                request.user_id,
                request.conversation_id,
            )
            return ""
        logger.info(
            "Session memory context injected: tenant={} agent={} user={} conversation={}",
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
    ) -> dict[str, list[str]] | None:
        """
        将本轮对话增量写入会话记忆 / Persist this turn's memory delta to session memory.

        Returns:
            提取到的 delta dict（有内容时），或 None（无记忆提取）
        """
        if not request.memory_enabled:
            return None
        if not request.conversation_id or not request.user_id:
            return None

        delta = await self._extract_memory_delta(message, response, request.agent_id)
        if not any(delta.values()):
            return None

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
        return delta

    @staticmethod
    def _build_memory_event_id(conversation_id: int) -> str:
        """生成请求级唯一记忆事件 ID / Build a request-scoped unique memory event ID."""
        return f"memevt:{conversation_id}:{uuid4().hex}"

    @staticmethod
    def _resolve_memory_context(
        memory_scene: str,
        memory_channel: str,
        memory_source: str,
    ) -> tuple[str, str, str, bool]:
        """
        解析并归一化会话记忆场景参数 / Parse and normalize session memory scene params.

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
        enabled = scene in (
            MemorySceneEnum.AI_CHAT_PAGE.value,
            MemorySceneEnum.ADMIN_CHAT.value,
        )
        return scene, channel, source, enabled

    async def _resolve_effective_memory_enabled(
        self,
        *,
        agent_id: int,
        scene: str,
        scene_enabled: bool,
    ) -> bool:
        """
        解析运行时最终记忆开关（入口场景 + 三层开关）/ Resolve effective memory enabled (scene + 3-layer toggles).

        规则：
        1) 非 ai_chat_page/admin_chat 场景直接关闭
        2) 允许场景下叠加平台/管理端/企业三层开关
        """
        if not scene_enabled:
            return False

        try:
            if self.tenant_id == PLATFORM_TENANT_ID:
                from app.services.ai.agent_service import AdminAgentService

                config = await AdminAgentService(self.db).get_memory_config(agent_id)
            else:
                from app.services.ai.agent_service import AgentService

                config = await AgentService(self.db, self.tenant_id).get_memory_config(agent_id)

            enabled = bool(config.get("effective_memory_enabled", False))
            logger.info(
                "Session memory switch resolved: tenant={} agent={} scene={} enabled={}",
                self.tenant_id,
                agent_id,
                scene,
                enabled,
            )
            return enabled
        except Exception as exc:
            # 记忆开关解析失败时降级，不影响主对话链路 / Memory switch parse fail: degrade silently, no impact on main flow
            logger.warning(
                "Resolve session memory switch degraded: tenant={} agent={} scene={} err={}",
                self.tenant_id,
                agent_id,
                scene,
                str(exc),
            )
            return False

    # ========================================
    # 非流式对话 / Non-streaming chat
    # ========================================

    async def chat(
        self,
        agent_id: int,
        message: str,
        conversation_id: int | None = None,
        variables: dict[str, Any] | None = None,
        page_context: PageContext | dict[str, Any] | None = None,
        user_id: int | None = None,
        knowledge_base_ids: list[int] | None = None,
        user_role: str = UserRoleEnum.TENANT_ADMIN.value,
        user_role_id: int | None = None,
        permissions: set[str] | None = None,
        consented_actions: list[str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
        memory_scene: str = DEFAULT_MEMORY_SCENE,
        memory_channel: str = MEMORY_CHANNEL_SYSTEM,
        memory_source: str = "",
        page_session_id: str | None = None,
        route_source: str | None = None,
    ) -> AgentChatResponse:
        """
        非流式对话 / Non-streaming chat.

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
        variables = PageContext.normalize_variables(variables, page_context)

        # 0. 加载并校验 Agent（必须已发布）/ Load and validate Agent (must be published)
        agent = await self._validate_agent(agent_id)
        knowledge_base_ids = await self._sanitize_client_knowledge_base_ids(
            agent_id, knowledge_base_ids,
        )

        # 1. 获取或创建对话 / Get or create conversation
        is_new_conversation = conversation_id is None
        conversation_owner_type = ConversationOwnerTypeEnum.from_user_role(user_role)
        conversation = await self.conversation_svc.get_or_create_for_chat(
            agent_id=agent_id,
            conversation_id=conversation_id,
            user_id=user_id,
            owner_type=conversation_owner_type,
            first_message=message,
        )
        memory_event_id = self._build_memory_event_id(conversation.id)

        # 1.5 新对话时递增每日对话计数（用于 conversations_per_day 配额）/ Increment daily conversation count for new convos
        if is_new_conversation:
            await AgentQuotaManager.record_conversation(
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                user_id=user_id,
            )

        # 2. 加载历史消息 → 转换为 ChatMessage（受 agent.context_config 控制）/ Load history and convert to ChatMessage
        ctx_cfg = agent.context_config or {}
        history_messages = await self.conversation_svc.load_chat_history(
            conversation_id=conversation.id,
            max_messages=ctx_cfg.get("max_history_messages", 0),
            max_tokens=ctx_cfg.get("max_history_tokens", 0),
        )

        # 3. 追加新用户消息（含附件）/ Append new user message (with attachments)
        user_msg = ChatMessage(
            role="user", content=message,
            attachments=[a if isinstance(a, dict) else a.model_dump() for a in attachments] if attachments else None,
        )
        all_messages = [*history_messages, user_msg]

        # 3.5 BEFORE_AGENT_CHAT 钩子（插件可修改 messages/注入 system prompt/阻止对话）/ BEFORE_AGENT_CHAT hook
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

        # 4. 构建执行请求 / Build execution request
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
            user_role_id=user_role_id,
            permissions=permissions,
            billing_context=await self._build_billing_context(
                agent=agent,
                user_id=user_id,
                user_role=user_role,
                user_role_id=user_role_id,
            ),
            memory_scene=normalized_scene,
            memory_channel=normalized_channel,
            memory_source=normalized_source,
            memory_enabled=memory_enabled,
            page_session_id=page_session_id,
        )

        # 4.1 会话记忆注入（仅 ai_chat_page 生效）/ Session memory injection (ai_chat_page only)
        mem_text = await self._load_session_memory_context(request=request)
        if mem_text:
            # system 消息优先，其次插入首位 / System message first, else insert at head
            if request.messages and request.messages[0].role == "system":
                request.messages[0].content = f"{request.messages[0].content}\n\n{mem_text}"
            else:
                request.messages.insert(0, ChatMessage(role="system", content=mem_text))

        # 4.2 会话级配额检查（max_turns_per_conversation / max_tokens_per_conversation）/ Conversation-level quota check
        quota_config = AgentQuotaConfig.from_dict(agent.quota_config)
        if quota_config.max_turns_per_conversation > 0 or quota_config.max_tokens_per_conversation > 0:
            current_turns = sum(1 for m in request.messages if m.role == "assistant")
            current_tokens = sum(estimate_tokens(m.content or "") for m in request.messages)
            await AgentQuotaManager.check_conversation_limits(
                config=quota_config,
                current_turns=current_turns,
                current_tokens=current_tokens,
            )

        # 5. 调用分发器（传入已校验的 agent，避免 Dispatcher 内二次 DB 查询）/ Call dispatcher with validated agent
        dispatcher = ExecutionDispatcher(self.db)
        result = await dispatcher.dispatch(request, pre_loaded_agent=agent)

        if not result.success:
            raise BusinessException(message=result.error or _("agent_chat.error.execution_failed"))

        # 5.5 AFTER_AGENT_CHAT 钩子（插件可修改响应/触发后续动作）/ AFTER_AGENT_CHAT hook
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

        # 6. 持久化新消息（用户消息 + 引擎生成的消息）/ Persist new messages (user + engine)
        history_count = len(history_messages)
        tool_calls_collected = await self.conversation_svc.persist_chat_messages(
            conversation=conversation,
            result=result,
            history_count=history_count,
            agent_id=agent_id,
            route_source=route_source,
        )

        # 7. 更新对话统计 + 智能体用量统计 / Update conversation stats and agent usage
        await self.conversation_svc.update_stats(
            conversation,
            result,
            current_agent=agent,
        )
        await AgentStatsManager.record_chat(
            tenant_id=self.tenant_id,
            agent_id=agent_id,
            tokens=result.total_tokens,
        )

        # 7.1 写入会话记忆（非阻塞主流程，失败仅告警）/ Write session memory (non-blocking, fail-safe)
        try:
            memory_delta = await self._persist_session_memory(
                request=request,
                message=message,
                response=result.output or "",
                event_id=memory_event_id,
            )
            if memory_delta:
                await self.conversation_svc.mark_memory_updated(conversation.id)
        except Exception as exc:
            logger.warning(
                "Persist session memory failed: tenant={} conversation={} err={}",
                self.tenant_id,
                conversation.id,
                str(exc),
            )
        await self.db.commit()

        duration_ms = int((time.perf_counter() - start) * 1000)

        logger.info(
            "Chat completed: agent={} conversation={} tokens={} duration={}ms",
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
    # 流式对话（M16-T3-2 实现）/ Streaming chat
    # ========================================

    async def stream_chat(
        self,
        agent_id: int,
        message: str = "",
        messages: list[str] | None = None,
        conversation_id: int | None = None,
        variables: dict[str, Any] | None = None,
        page_context: PageContext | dict[str, Any] | None = None,
        user_id: int | None = None,
        knowledge_base_ids: list[int] | None = None,
        user_role: str = UserRoleEnum.TENANT_ADMIN.value,
        user_role_id: int | None = None,
        permissions: set[str] | None = None,
        consented_actions: list[str] | None = None,
        attachments: list[dict[str, Any]] | None = None,
        image_params: dict[str, Any] | None = None,
        memory_scene: str = DEFAULT_MEMORY_SCENE,
        memory_channel: str = MEMORY_CHANNEL_SYSTEM,
        memory_source: str = "",
        page_session_id: str | None = None,
        route_source: str | None = None,
    ) -> StreamingResponse:
        """
        流式对话（返回 StreamingResponse）/ Streaming chat (returns StreamingResponse).

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
        variables = PageContext.normalize_variables(variables, page_context)

        # 0. 加载并校验 Agent（必须已发布）/ Load and validate Agent (must be published)
        agent = await self._validate_agent(agent_id)
        knowledge_base_ids = await self._sanitize_client_knowledge_base_ids(
            agent_id, knowledge_base_ids,
        )

        # 解析消息：支持单条 message 或批量 messages
        batch = messages if messages else ([message] if message else [])
        first_message = batch[0] if batch else ""

        # 1. 获取或创建对话 / Get or create conversation
        is_new_conversation = conversation_id is None
        conversation_owner_type = ConversationOwnerTypeEnum.from_user_role(user_role)
        conversation = await self.conversation_svc.get_or_create_for_chat(
            agent_id=agent_id,
            conversation_id=conversation_id,
            user_id=user_id,
            owner_type=conversation_owner_type,
            first_message=first_message,
        )
        memory_event_id = self._build_memory_event_id(conversation.id)

        # 1.5 新对话时递增每日对话计数 / 1.5 Increment daily conversation count on new chat
        if is_new_conversation:
            await AgentQuotaManager.record_conversation(
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                user_id=user_id,
            )

        # 1.6 提交对话创建，确保 on_stream_complete 回调的独立 session 能看到它 / Commit conv creation for stream callback
        await self.db.commit()

        # 2. 加载历史消息（使用 agent 的 context_config 窗口控制）/ Load history (agent context_config window)
        ctx_cfg = agent.context_config or {}
        history_messages = await self.conversation_svc.load_chat_history(
            conversation_id=conversation.id,
            max_messages=ctx_cfg.get("max_history_messages", 0),
            max_tokens=ctx_cfg.get("max_history_tokens", 0),
        )

        # 3. 追加新用户消息（支持单条或批量；仅第一条支持附件）/ Append new user messages (single or batch; attachments only on first)
        attach_list = [a if isinstance(a, dict) else a.model_dump() for a in attachments] if attachments else None
        if batch:
            user_msgs = [
                ChatMessage(role="user", content=m, attachments=attach_list if i == 0 else None)
                for i, m in enumerate(batch)
            ]
        else:
            user_msgs = [
                ChatMessage(role="user", content=message, attachments=attach_list),
            ]
        all_messages = [*history_messages, *user_msgs]

        # 3.5 BEFORE_AGENT_CHAT 钩子（插件可修改 messages/注入 system prompt/阻止对话）/ BEFORE_AGENT_CHAT hook
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

        # 4. 构建执行请求 / Build execution request（标记为流式）
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
            user_role_id=user_role_id,
            permissions=permissions,
            billing_context=await self._build_billing_context(
                agent=agent,
                user_id=user_id,
                user_role=user_role,
                user_role_id=user_role_id,
            ),
            memory_scene=normalized_scene,
            memory_channel=normalized_channel,
            memory_source=normalized_source,
            memory_enabled=memory_enabled,
            page_session_id=page_session_id,
        )

        # 4.1 会话记忆注入（仅 ai_chat_page 生效）/ Session memory injection (ai_chat_page only)
        mem_text = await self._load_session_memory_context(request=request)
        if mem_text:
            if request.messages and request.messages[0].role == "system":
                request.messages[0].content = f"{request.messages[0].content}\n\n{mem_text}"
            else:
                request.messages.insert(0, ChatMessage(role="system", content=mem_text))

        # 4.2 会话级配额检查（max_turns_per_conversation / max_tokens_per_conversation）/ Conversation-level quota check
        quota_config = AgentQuotaConfig.from_dict(agent.quota_config)
        if quota_config.max_turns_per_conversation > 0 or quota_config.max_tokens_per_conversation > 0:
            current_turns = sum(1 for m in request.messages if m.role == "assistant")
            current_tokens = sum(estimate_tokens(m.content or "") for m in request.messages)
            await AgentQuotaManager.check_conversation_limits(
                config=quota_config,
                current_turns=current_turns,
                current_tokens=current_tokens,
            )

        # 5. 配额/并发/钩子前置检查（与 dispatcher.dispatch 对等）/ Quota/concurrency/hook pre-check
        lock_token: str = ""

        # 预估输入 Token 以启用原子预扣减（与 dispatcher 一致）/ Estimate input tokens for atomic pre-deduction
        estimated_tokens = max(
            sum(estimate_tokens(m.content or "") for m in all_messages),
            100,  # 至少 100 tokens（system prompt + 生成开销）
        )

        try:
            # 并发控制 / Concurrency control
            if quota_config.max_concurrent > 0 or quota_config.tenant_max_concurrent > 0:
                lock_token = await AgentConcurrencyLimiter.acquire(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    max_concurrent=quota_config.max_concurrent,
                    tenant_max_concurrent=quota_config.tenant_max_concurrent,
                )

            # 配额检查（含原子预扣减，防止并发超限）/ Quota check (atomic pre-deduction)
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

            # 套餐月 API 调用次数配额检查（与 dispatcher 对等）/ Plan monthly API quota check
            if self.tenant_id:
                from app.enums import ErrorCode
                from app.services.tenant.quota_service import QuotaService
                api_check = await QuotaService.check_api_quota_for_tenant_id(
                    self.db, self.tenant_id
                )
                if not api_check.allowed:
                    raise BusinessException(
                        message=api_check.message or _("quota.api_calls_exceeded"),
                        code=ErrorCode.CONFLICT,
                    )

            # BEFORE_EXECUTE 钩子（hook_registry 已在 step 3.5 获取）/ BEFORE_EXECUTE hook
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

            # ExecutionStarted 事件 / ExecutionStarted event
            await BaseEngine._publish_execution_started(request, agent)

        except (AgentQuotaExceeded, AgentConcurrencyExceeded, BusinessException):
            # 释放并发锁后重新抛出 / Release concurrency lock then re-raise
            if lock_token:
                await AgentConcurrencyLimiter.release(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    lock_token=lock_token,
                )
            raise

        # 6. 创建 Gateway / Create Gateway
        gateway = AIGateway(self.db)

        # 6.1 检测是否为生图模型 → 使用 ImageGenerationEngine / Use ImageGenerationEngine for image models
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
            # 解析 Skill（在 Service 层完成，不在 Engine 内部查 DB）/ Resolve Skill in Service layer
            from app.ai.skills.resolver import resolve_for_agent
            try:
                skill_result = await resolve_for_agent(
                    self.db, agent,
                    tenant_id=self.tenant_id,
                    user_role=user_role,
                )
            except Exception as skill_exc:
                logger.error(
                    "Skill resolution failed for agent {}: {}",
                    agent_id, str(skill_exc),
                )
                skill_result = None

            # 读取平台 Toolkit 安全配置 / Read platform Toolkit security config
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
                input_variables=variables or {},
                page_session_id=page_session_id,
            )
            engine = ConversationEngine(
                db=self.db,
                gateway=gateway,
                sandbox=sandbox,
            )

        # 7. 创建持久化回调（流式完成后调用，含配额记录+并发释放+钩子）/ Create persist callback for stream complete
        history_count = len(history_messages)

        async def on_stream_complete(result: ExecutionResult) -> dict[str, Any] | None:
            """流式完成后持久化消息 + 配额记录 + 并发释放 / Persist message + quota + release concurrency on stream complete.

            使用独立 db session，不依赖 DI session 生命周期。
            SSE 生成器在响应体流式传输期间执行此回调，
            DI session 的 commit/close 时机取决于框架版本，
            独立 session 保证写入操作始终可靠。

            Returns:
                Extra data dict to merge into the SSE 'done' event, or None.
            """
            extra: dict[str, Any] = {}
            try:
                # Persist when success OR when we have new messages (partial/interrupted) / 成功时持久化；或中断时如有新消息也持久化
                system_count = sum(
                    1 for m in (result.messages or [])
                    if m.get("role") == "system"
                )
                has_new_messages = (
                    (result.messages or []) and
                    len(result.messages) > system_count + history_count
                )
                if result.success or has_new_messages:
                    # 先提交消息和统计，再做可能较慢的记忆抽取，避免后半段取消导致历史整笔回滚。 / Commit messages and stats first, then slower memory extract to avoid full rollback on late cancel
                    # Commit message persistence first, then run slower memory extraction separately.
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
                                agent_id=agent_id,
                                route_source=route_source,
                            )
                            await cb_conv_svc.update_stats(
                                cb_conv,
                                result,
                                current_agent=agent,
                            )
                            await cb_db.commit()
                        except Exception:
                            await cb_db.rollback()
                            raise

                    await AgentStatsManager.record_chat(
                        tenant_id=self.tenant_id,
                        agent_id=agent_id,
                        tokens=result.total_tokens,
                    )

                    # 写入会话记忆（流式完成后）/ Write session memory after stream complete
                    try:
                        memory_delta = await self._persist_session_memory(
                            request=request,
                            message=message,
                            response=result.output or "",
                            event_id=memory_event_id,
                        )
                        if memory_delta:
                            extra["memory_updated"] = True
                            async with async_session_factory() as mem_db:
                                try:
                                    mem_conv_svc = ConversationService(
                                        mem_db, self.tenant_id,
                                    )
                                    await mem_conv_svc.mark_memory_updated(
                                        conversation.id,
                                    )
                                    await mem_db.commit()
                                except Exception:
                                    await mem_db.rollback()
                                    raise
                    except Exception as mem_exc:
                        logger.warning(
                            "Persist stream session memory failed: tenant={} conversation={} err={}",
                            self.tenant_id,
                            conversation.id,
                            str(mem_exc),
                        )

                # 配额调整：从预估调整为实际（与 dispatcher 对等）/ Adjust quota from estimate to actual
                actual_tokens = result.total_tokens or 0
                await AgentQuotaManager.adjust_usage(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    estimated_tokens=estimated_tokens,
                    actual_tokens=actual_tokens,
                    config=quota_config,
                )

                # 用户级用量记录 / User-level usage record
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

                # AFTER_EXECUTE 钩子 / AFTER_EXECUTE hook
                await hook_registry.trigger(
                    HookPoint.AFTER_EXECUTE,
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    result=result,
                )

                # 发布执行完成/失败事件（流式模式绕过 dispatcher，需手动发布）/ Emit execution complete/fail event
                if result.success:
                    await BaseEngine._publish_execution_completed(
                        request, agent, result,
                    )
                else:
                    await BaseEngine._publish_execution_failed(
                        request, agent, result.error or "",
                    )
            finally:
                # 释放并发锁 / Release concurrency lock
                if lock_token:
                    await AgentConcurrencyLimiter.release(
                        tenant_id=self.tenant_id,
                        agent_id=agent_id,
                        lock_token=lock_token,
                    )
            return extra or None

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
    # 轻量级流式调用（无对话记录）/ Lightweight streaming (no conversation record)
    # ========================================

    async def stream_chat_ephemeral(
        self,
        agent_id: int,
        message: str,
        variables: dict[str, Any] | None = None,
        user_id: int | None = None,
        knowledge_base_ids: list[int] | None = None,
        user_role: str = UserRoleEnum.TENANT_ADMIN.value,
        user_role_id: int | None = None,
        permissions: set[str] | None = None,
    ) -> StreamingResponse:
        """
        轻量级流式调用（无对话记录，无消息持久化）/ Lightweight streaming (no conversation/message persistence).

        适用于富文本写作操作（续写、优化、校对等），不需要对话上下文。
        与 stream_chat 的区别：
        - 不创建 AgentConversation 记录
        - 不保存消息历史
        - 不注入会话记忆
        - 仍保留配额检查和统计
        """
        agent = await self._validate_agent(agent_id)
        knowledge_base_ids = await self._sanitize_client_knowledge_base_ids(
            agent_id, knowledge_base_ids,
        )

        user_msg = ChatMessage(role="user", content=message)
        all_messages = [user_msg]

        request = ExecutionRequest(
            agent_id=agent_id,
            tenant_id=self.tenant_id,
            user_id=user_id,
            messages=all_messages,
            input_variables=variables or {},
            execution_mode=AgentExecutionModeEnum.CONVERSATION.value,
            stream=True,
            conversation_id=0,
            knowledge_base_ids=knowledge_base_ids,
            skip_persistence=True,
            user_role=user_role,
            user_role_id=user_role_id,
            permissions=permissions,
            billing_context=await self._build_billing_context(
                agent=agent,
                user_id=user_id,
                user_role=user_role,
                user_role_id=user_role_id,
            ),
            memory_scene="ephemeral",
            memory_channel=MEMORY_CHANNEL_SYSTEM,
            memory_source="system.ai_writing",
            memory_enabled=False,
        )

        quota_config = AgentQuotaConfig.from_dict(agent.quota_config)
        estimated_tokens = max(estimate_tokens(message), 100)
        lock_token: str = ""

        try:
            if quota_config.max_concurrent > 0 or quota_config.tenant_max_concurrent > 0:
                lock_token = await AgentConcurrencyLimiter.acquire(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    max_concurrent=quota_config.max_concurrent,
                    tenant_max_concurrent=quota_config.tenant_max_concurrent,
                )

            await AgentQuotaManager.check_quota(
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                config=quota_config,
                estimated_tokens=estimated_tokens,
            )

            if self.tenant_id:
                from app.enums import ErrorCode
                from app.services.tenant.quota_service import QuotaService
                api_check = await QuotaService.check_api_quota_for_tenant_id(
                    self.db, self.tenant_id
                )
                if not api_check.allowed:
                    raise BusinessException(
                        message=api_check.message or _("quota.api_calls_exceeded"),
                        code=ErrorCode.CONFLICT,
                    )

        except (AgentQuotaExceeded, AgentConcurrencyExceeded, BusinessException):
            if lock_token:
                await AgentConcurrencyLimiter.release(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    lock_token=lock_token,
                )
            raise

        async def on_stream_complete(result: ExecutionResult) -> dict[str, Any] | None:
            try:
                actual_tokens = result.total_tokens or 0
                await AgentQuotaManager.adjust_usage(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    estimated_tokens=estimated_tokens,
                    actual_tokens=actual_tokens,
                    config=quota_config,
                )
                if user_id and actual_tokens > 0:
                    await AgentQuotaManager.record_user_usage(
                        tenant_id=self.tenant_id,
                        agent_id=agent_id,
                        user_id=user_id,
                        tokens=actual_tokens,
                    )
                await AgentStatsManager.record_chat(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    tokens=result.total_tokens,
                )
            finally:
                if lock_token:
                    await AgentConcurrencyLimiter.release(
                        tenant_id=self.tenant_id,
                        agent_id=agent_id,
                        lock_token=lock_token,
                    )
            return None

        gateway = AIGateway(self.db)
        engine = ConversationEngine(db=self.db, gateway=gateway, sandbox=None)
        return await engine.stream_execute(
            agent=agent,
            request=request,
            on_complete=on_stream_complete,
        )

__all__ = ["AgentChatService"]
