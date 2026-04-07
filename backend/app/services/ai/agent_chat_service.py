"""
智能体对话执行 Service / Agent Chat Service

编排完整对话流程：创建/续接对话 → 加载历史 → 调 ExecutionDispatcher → 持久化消息
Orchestrates full chat flow: create/resume conversation → load history → call ExecutionDispatcher → persist messages.
"""

import time
from datetime import datetime, timezone
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
from app.ai.context.long_term_memory import get_long_term_memory_provider
from app.ai.engine.base import BaseEngine
from app.ai.engine.conversation import ConversationEngine
from app.ai.engine.dispatcher import ExecutionDispatcher
from app.ai.engine.types import ExecutionRequest, ExecutionResult
from app.ai.events.hooks import HookPoint, get_hook_registry
from app.ai.gateway import AIGateway
from app.ai.json_safe import normalize_json_safe, normalize_json_safe_dict
from app.ai.tools.sandbox import ToolSandbox
from app.ai.types import ChatMessage
from app.ai.utils.token_estimator import estimate_tokens
from app.configs.service import PLATFORM_TENANT_ID
from app.core.database import async_session_factory
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import (
    ActionLevelEnum,
    AgentExecutionModeEnum,
    AgentStatusEnum,
    ConversationOwnerTypeEnum,
    MemoryChannelEnum,
    MemorySceneEnum,
)
from app.enums.common import UserRoleEnum
from app.exceptions import BusinessException, NotFoundException
from app.repositories.ai.agent_repository import AgentRepository
from app.schemas.ai.agent_chat import AgentChatResponse, InteractionMode, PageContext
from app.services.ai.conversation_service import ConversationService
from app.services.ai.execution_trust_policy_service import (
    ExecutionTrustPolicyService,
)
from app.services.ai.long_term_memory_service import (
    build_memory_capture_payload_from_session_delta,
)
from app.services.ai.memory_extraction_service import MemoryExtractionService
from app.services.ai.session_memory_service import SessionMemoryService

if TYPE_CHECKING:
    from app.models.ai.agent import Agent

logger = LogManager.get_logger("ai.agent_chat_service")
_JSON_SAFE = normalize_json_safe
_JSON_SAFE_DICT = normalize_json_safe_dict
_EXTRACT_TURN_DIAGNOSTICS = ConversationService._extract_turn_diagnostics_from_metadata


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
    # Internal: Agent validation / 内部：Agent 校验
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
    ) -> tuple[list[int] | None, list[int]]:
        """
        Keep only KB ids bound to the agent (tenant-scoped bindings). None => no narrowing.
        仅保留已绑定到智能体的知识库 ID；None 表示不按客户端列表收窄。
        """
        if not knowledge_base_ids:
            return None, []
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
        return filtered or None, dropped

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
        result = await MemoryExtractionService(
            self.tenant_id,
        ).extract_turn_memory(
            agent_id=agent_id,
            message=message,
            response=response,
        )
        return result or empty

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

        _MEMORY_SECTION_KEYS = (
            "constraints",
            "preferences",
            "task_states",
            "verified_facts",
        )
        parts: list[str] = []
        for key in _MEMORY_SECTION_KEYS:
            items = state.get(key)
            if items:
                parts.append(f"{key}: " + " | ".join(items[:6]))

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
        if request.long_term_memory_enabled and request.user_id:
            try:
                payload = build_memory_capture_payload_from_session_delta(delta)
                if any(payload.values()):
                    provider = get_long_term_memory_provider(
                        db=self.db,
                        tenant_id=self.tenant_id,
                    )
                    await provider.capture(
                        agent_id=request.agent_id,
                        user_id=request.user_id,
                        source_kind="conversation_turn",
                        source_ref=f"conversation:{request.conversation_id}:{event_id}",
                        items_by_type=payload,
                    )
            except Exception as exc:
                logger.warning(
                    "Long-term memory capture degraded: tenant={} agent={} user={} conversation={} err={}",
                    self.tenant_id,
                    request.agent_id,
                    request.user_id,
                    request.conversation_id,
                    str(exc),
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

                config = await AgentService(self.db, self.tenant_id).get_memory_config(
                    agent_id
                )

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
            # Memory switch parse fail: degrade silently (no impact on main chat) / 记忆开关解析失败时降级，不影响主链路
            logger.warning(
                "Resolve session memory switch degraded: tenant={} agent={} scene={} err={}",
                self.tenant_id,
                agent_id,
                scene,
                str(exc),
            )
            return False

    async def _resolve_runtime_trust_policy_ref(
        self,
        *,
        conversation_id: int | None,
        agent_id: int,
        operator_id: int | None,
        operator_type: str | None,
        explicit_ref: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Resolve backend trust policy reference with fail-safe degradation / 解析后端 trust policy 引用，失败时静默降级。"""
        if explicit_ref:
            return explicit_ref
        try:
            return await ExecutionTrustPolicyService(
                self.db,
                self.tenant_id,
            ).resolve_runtime_policy(
                conversation_id=conversation_id,
                agent_id=agent_id,
                operator_id=operator_id,
                operator_type=operator_type,
            )
        except Exception as exc:
            logger.warning(
                "Resolve execution trust policy degraded: tenant={} agent={} conversation={} operator={} type={} err={}",
                self.tenant_id,
                agent_id,
                conversation_id,
                operator_id,
                operator_type,
                str(exc),
            )
            return None

    async def _resolve_interaction_mode(
        self,
        *,
        requested_mode: str | None,
        conversation_id: int | None,
        agent_id: int,
        operator_id: int | None,
        operator_type: str | None,
        explicit_trust_policy_ref: dict[str, Any] | None = None,
        interaction_updates: list[dict[str, Any]] | None = None,
    ) -> tuple[InteractionMode, dict[str, Any] | None, str | None]:
        normalized_mode = (
            requested_mode
            if requested_mode in {"confirm", "trusted_auto"}
            else "confirm"
        )
        if normalized_mode != "trusted_auto":
            return normalized_mode, explicit_trust_policy_ref, None

        resolved_ref = await self._resolve_runtime_trust_policy_ref(
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=operator_id,
            operator_type=operator_type,
            explicit_ref=explicit_trust_policy_ref,
        )
        if resolved_ref:
            return "trusted_auto", resolved_ref, None
        interaction_ref = self._build_trust_policy_ref_from_interaction_updates(
            interaction_updates
        )
        if interaction_ref:
            return "trusted_auto", interaction_ref, None
        return "confirm", None, "missing_runtime_trust_policy"

    @staticmethod
    def _build_trust_policy_ref_from_interaction_updates(
        interaction_updates: list[dict[str, Any]] | None,
    ) -> dict[str, Any] | None:
        """Build a temporary trust policy ref from freshly confirmed interaction updates / 基于刚确认的交互更新构建临时信任策略引用。"""
        if not interaction_updates:
            return None

        allowed_tool_names: set[str] = set()
        tool_families: set[str] = set()
        risk_cap = ActionLevelEnum.READ.value

        for update in interaction_updates:
            if not isinstance(update, dict):
                continue
            if bool(update.get("rejected")):
                continue
            if str(update.get("kind") or "") not in {
                "pending_confirmation",
                "pending_consent",
            }:
                continue
            tool_name = str(update.get("tool_name") or "").strip()
            if not tool_name:
                continue
            tool_family = ExecutionTrustPolicyService.tool_family_for_name(tool_name)
            tool_risk = ExecutionTrustPolicyService.tool_risk_level(
                tool_name=tool_name,
                tool_family=tool_family,
            )
            allowed_tool_names.add(tool_name)
            if tool_family and tool_family != "none":
                tool_families.add(tool_family)
            if ExecutionTrustPolicyService._risk_rank(
                tool_risk
            ) > ExecutionTrustPolicyService._risk_rank(risk_cap):
                risk_cap = tool_risk

        if not allowed_tool_names:
            return None

        return {
            "policy_ids": [],
            "allowed_tool_names": sorted(allowed_tool_names),
            "tool_families": sorted(tool_families),
            "risk_level_cap": risk_cap,
        }

    async def _grant_trusted_auto_policies(
        self,
        *,
        conversation_id: int,
        agent_id: int,
        operator_id: int | None,
        operator_type: str | None,
        interaction_updates: list[dict[str, Any]] | None,
        interaction_mode: str,
    ) -> None:
        if interaction_mode != "trusted_auto" or not interaction_updates:
            return

        service = ExecutionTrustPolicyService(self.db, self.tenant_id)
        for update in interaction_updates:
            if str(update.get("kind") or "") not in {
                "pending_consent",
                "pending_confirmation",
            }:
                continue
            if bool(update.get("rejected")):
                continue
            tool_name = str(update.get("tool_name") or "").strip()
            if not tool_name:
                continue
            await service.grant_conversation_tool_trust(
                conversation_id=conversation_id,
                agent_id=agent_id,
                operator_id=operator_id,
                operator_type=operator_type,
                tool_name=tool_name,
                granted_by=operator_id,
                grant_reason="interaction_mode:trusted_auto",
            )

    @staticmethod
    def _extract_turn_meta_from_result(result: ExecutionResult) -> dict[str, Any]:
        return _EXTRACT_TURN_DIAGNOSTICS(
            {
                "turn_record": getattr(result, "turn_record", None),
                "completion_reason": getattr(result, "completion_reason", None),
                "partial": bool(getattr(result, "partial", False)),
                "interrupted": bool(getattr(result, "interrupted", False)),
            }
        )

    @staticmethod
    def _build_context_diagnostics(
        result: ExecutionResult,
        *,
        interaction_mode_effective: str,
    ) -> dict[str, Any]:
        turn_meta = AgentChatService._extract_turn_meta_from_result(result)
        payload: dict[str, Any] = {
            "estimated_tokens": result.total_tokens,
            "context_compacted": bool(result.context_compacted),
            "compact_summary_present": bool(result.context_compacted),
            "memory_recalled": bool(result.memory_recalled),
            "memory_flush_triggered": bool(result.memory_flush_triggered),
            "prune_stats": result.prune_stats,
            "rag_source_kinds": list(result.rag_source_kinds or []),
            "last_interrupted": bool(result.interrupted),
            "interaction_mode_effective": interaction_mode_effective,
            "tool_planner": result.tool_planner,
        }
        if turn_meta.get("turn_outcome"):
            payload["turn_outcome"] = turn_meta["turn_outcome"]
        if turn_meta.get("termination_reason"):
            payload["termination_reason"] = turn_meta["termination_reason"]
        if turn_meta.get("protocol_path"):
            payload["protocol_path"] = turn_meta["protocol_path"]
        if turn_meta.get("selected_tool_names"):
            payload["selected_tool_names"] = turn_meta["selected_tool_names"]
        if turn_meta.get("selected_skill_names"):
            payload["selected_skill_names"] = turn_meta["selected_skill_names"]
        if turn_meta.get("context_sources"):
            payload["context_sources"] = turn_meta["context_sources"]
        if turn_meta.get("contract_breach_type"):
            payload["contract_breach_type"] = turn_meta["contract_breach_type"]
        if turn_meta.get("tool_leak_detected"):
            payload["tool_leak_detected"] = True
        if turn_meta.get("unfinished_intents"):
            payload["unfinished_intents"] = turn_meta["unfinished_intents"]
        if turn_meta.get("leaked_tool_names"):
            payload["leaked_tool_names"] = turn_meta["leaked_tool_names"]
        if turn_meta.get("recovered_via_retry") is not None:
            payload["recovered_via_retry"] = turn_meta["recovered_via_retry"]
        if turn_meta.get("last_tool_name"):
            payload["last_tool_name"] = turn_meta["last_tool_name"]
        if turn_meta.get("last_page_key"):
            payload["last_page_key"] = turn_meta["last_page_key"]
        if turn_meta.get("last_page_op"):
            payload["last_page_op"] = turn_meta["last_page_op"]
        if turn_meta.get("interrupted_stage"):
            payload["interrupted_stage"] = turn_meta["interrupted_stage"]
        if turn_meta.get("tool_loop_progress"):
            payload["tool_loop_progress"] = turn_meta["tool_loop_progress"]
        return payload

    @staticmethod
    def _build_last_run_summary(
        result: ExecutionResult,
        *,
        interaction_mode_effective: str,
        downgrade_reason: str | None,
    ) -> dict[str, Any]:
        turn_meta = AgentChatService._extract_turn_meta_from_result(result)
        payload: dict[str, Any] = {
            "duration_ms": result.duration_ms,
            "interaction_mode_effective": interaction_mode_effective,
            "downgrade_reason": downgrade_reason,
            "runtime_model_name": result.runtime_model_name,
            "runtime_provider_name": result.runtime_provider_name,
            "success": bool(result.success),
            "total_tokens": result.total_tokens,
            "tool_planner": result.tool_planner,
        }
        completion_reason = (
            turn_meta.get("termination_reason")
            or str(getattr(result, "completion_reason", "") or "").strip()
            or None
        )
        if completion_reason:
            payload["completion_reason"] = completion_reason
            payload["termination_reason"] = completion_reason
        if turn_meta.get("turn_outcome"):
            payload["turn_outcome"] = turn_meta["turn_outcome"]
        if turn_meta.get("protocol_path"):
            payload["protocol_path"] = turn_meta["protocol_path"]
        if turn_meta.get("selected_tool_names"):
            payload["selected_tool_names"] = turn_meta["selected_tool_names"]
        if turn_meta.get("selected_skill_names"):
            payload["selected_skill_names"] = turn_meta["selected_skill_names"]
        if turn_meta.get("context_sources"):
            payload["context_sources"] = turn_meta["context_sources"]
        if turn_meta.get("contract_breach_type"):
            payload["contract_breach_type"] = turn_meta["contract_breach_type"]
        if turn_meta.get("tool_leak_detected"):
            payload["tool_leak_detected"] = True
        if turn_meta.get("unfinished_intents"):
            payload["unfinished_intents"] = turn_meta["unfinished_intents"]
        if turn_meta.get("leaked_tool_names"):
            payload["leaked_tool_names"] = turn_meta["leaked_tool_names"]
        if turn_meta.get("recovered_via_retry") is not None:
            payload["recovered_via_retry"] = turn_meta["recovered_via_retry"]
        if turn_meta.get("last_tool_name"):
            payload["last_tool_name"] = turn_meta["last_tool_name"]
        if turn_meta.get("last_page_key"):
            payload["last_page_key"] = turn_meta["last_page_key"]
        if turn_meta.get("last_page_op"):
            payload["last_page_op"] = turn_meta["last_page_op"]
        if turn_meta.get("interrupted_stage"):
            payload["interrupted_stage"] = turn_meta["interrupted_stage"]
        if turn_meta.get("tool_loop_progress"):
            payload["tool_loop_progress"] = turn_meta["tool_loop_progress"]
        return payload

    # ========================================
    # Non-streaming chat / 非流式对话
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
        interaction_updates: list[dict[str, Any]] | None = None,
        trust_policy_ref: dict[str, Any] | None = None,
        interaction_mode: InteractionMode = "confirm",
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

        # 0. Load and validate Agent (must be published) / 0. 加载并校验 Agent（须已发布）
        agent = await self._validate_agent(agent_id)
        (
            knowledge_base_ids,
            dropped_knowledge_base_ids,
        ) = await self._sanitize_client_knowledge_base_ids(
            agent_id,
            knowledge_base_ids,
        )

        # 1. Get or create conversation / 1. 获取或创建对话
        is_new_conversation = conversation_id is None
        conversation_owner_type = ConversationOwnerTypeEnum.from_user_role(user_role)
        (
            interaction_mode_effective,
            resolved_trust_policy_ref,
            interaction_mode_downgrade_reason,
        ) = await self._resolve_interaction_mode(
            requested_mode=interaction_mode,
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=user_id,
            operator_type=conversation_owner_type,
            explicit_trust_policy_ref=trust_policy_ref,
            interaction_updates=interaction_updates,
        )
        conversation = await self.conversation_svc.get_or_create_for_chat(
            agent_id=agent_id,
            conversation_id=conversation_id,
            user_id=user_id,
            owner_type=conversation_owner_type,
            first_message=message,
        )
        conversation_metadata = dict(conversation.metadata_ or {})
        conversation_metadata["interaction_mode"] = interaction_mode_effective
        conversation_metadata["interaction_mode_requested"] = interaction_mode
        if interaction_mode_downgrade_reason:
            conversation_metadata["interaction_mode_downgrade_reason"] = (
                interaction_mode_downgrade_reason
            )
        conversation.metadata_ = conversation_metadata
        if interaction_updates:
            interaction_updates = [
                {
                    **update,
                    "auto_approve_source": (
                        "execution_trust_policy"
                        if interaction_mode_effective == "trusted_auto"
                        else None
                    ),
                    "downgraded_from": (
                        interaction_mode
                        if interaction_mode != interaction_mode_effective
                        else None
                    ),
                    "downgrade_reason": interaction_mode_downgrade_reason,
                    "interaction_mode_effective": interaction_mode_effective,
                }
                for update in interaction_updates
            ]
            await self.conversation_svc.update_last_assistant_interaction_state(
                conversation.id,
                interaction_updates,
                user_id=user_id,
                owner_type=conversation_owner_type,
                interaction_mode_requested=interaction_mode,
                interaction_mode_effective=interaction_mode_effective,
                interaction_mode_downgrade_reason=interaction_mode_downgrade_reason,
            )
            await self._grant_trusted_auto_policies(
                conversation_id=conversation.id,
                agent_id=agent_id,
                operator_id=user_id,
                operator_type=conversation_owner_type,
                interaction_updates=interaction_updates,
                interaction_mode=interaction_mode_effective,
            )
        memory_event_id = self._build_memory_event_id(conversation.id)

        # 1.5 Increment daily conversation count for new chat (conversations_per_day) / 1.5 新对话递增每日计数
        if is_new_conversation:
            await AgentQuotaManager.record_conversation(
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                user_id=user_id,
            )

        # 2. Load history → ChatMessage (context_config) / 2. 加载历史并转 ChatMessage
        ctx_cfg = agent.context_config or {}
        history_messages = await self.conversation_svc.load_chat_history(
            conversation_id=conversation.id,
            max_messages=ctx_cfg.get("max_history_messages", 0),
            max_tokens=ctx_cfg.get("max_history_tokens", 0),
        )

        # 3. Append new user message (with attachments) / 3. 追加用户消息（含附件）
        attach_list = (
            [a if isinstance(a, dict) else a.model_dump() for a in attachments]
            if attachments
            else None
        )
        if message.strip() or attach_list:
            user_msg = ChatMessage(
                role="user",
                content=message,
                attachments=attach_list,
            )
            all_messages = [*history_messages, user_msg]
        else:
            all_messages = list(history_messages)

        # 3.5 BEFORE_AGENT_CHAT hook (messages / system prompt / block) / 3.5 BEFORE_AGENT_CHAT 钩子
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.BEFORE_AGENT_CHAT):
            hook_ctx = await hook_registry.trigger(
                HookPoint.BEFORE_AGENT_CHAT,
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                messages=all_messages,
                config={
                    "variables": variables,
                    "knowledge_base_ids": knowledge_base_ids,
                },
            )
            if hook_ctx.get("blocked"):
                raise BusinessException(
                    message=hook_ctx.get(
                        "block_reason", _("agent_chat.error.blocked_by_hook")
                    )
                )
            all_messages = hook_ctx.get("messages", all_messages)

        # 4. Build execution request / 4. 构建执行请求
        normalized_scene, normalized_channel, normalized_source, memory_enabled = (
            self._resolve_memory_context(
                memory_scene=memory_scene,
                memory_channel=memory_channel,
                memory_source=memory_source,
            )
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
            long_term_memory_enabled=bool(
                ctx_cfg.get("long_term_memory_enabled", False)
            ),
            trust_policy_ref=resolved_trust_policy_ref,
            interaction_mode=interaction_mode_effective,
            page_session_id=page_session_id,
            interaction_updates=interaction_updates,
            knowledge_base_feedback=(
                {
                    "dropped_knowledge_base_ids": dropped_knowledge_base_ids,
                    "effective_knowledge_base_ids": knowledge_base_ids or [],
                }
                if dropped_knowledge_base_ids
                else None
            ),
        )

        # 4.1 Session memory injection (ai_chat_page only) / 4.1 会话记忆注入
        mem_text = await self._load_session_memory_context(request=request)
        if mem_text:
            # Prefer system slot, else prepend / system 位优先，否则插首位
            if request.messages and request.messages[0].role == "system":
                request.messages[
                    0
                ].content = f"{request.messages[0].content}\n\n{mem_text}"
            else:
                request.messages.insert(0, ChatMessage(role="system", content=mem_text))

        # 4.2 Conversation quota (max_turns / max_tokens per conversation) / 4.2 会话级配额
        quota_config = AgentQuotaConfig.from_dict(agent.quota_config)
        if (
            quota_config.max_turns_per_conversation > 0
            or quota_config.max_tokens_per_conversation > 0
        ):
            current_turns = sum(1 for m in request.messages if m.role == "assistant")
            current_tokens = sum(
                estimate_tokens(m.content or "") for m in request.messages
            )
            await AgentQuotaManager.check_conversation_limits(
                config=quota_config,
                current_turns=current_turns,
                current_tokens=current_tokens,
            )

        # 5. Dispatch with pre-validated agent (skip extra DB in Dispatcher) / 5. 调用分发器（已预校验 agent）
        dispatcher = ExecutionDispatcher(self.db)
        result = await dispatcher.dispatch(request, pre_loaded_agent=agent)

        if not result.success:
            raise BusinessException(
                message=result.error or _("agent_chat.error.execution_failed")
            )

        # 5.5 AFTER_AGENT_CHAT hook / 5.5 AFTER_AGENT_CHAT 钩子
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

        # 6. Persist new messages (user + engine) / 6. 持久化新消息
        history_count = len(history_messages)
        context_diagnostics_payload = self._build_context_diagnostics(
            result,
            interaction_mode_effective=interaction_mode_effective,
        )
        last_run_summary_payload = self._build_last_run_summary(
            result,
            interaction_mode_effective=interaction_mode_effective,
            downgrade_reason=interaction_mode_downgrade_reason,
        )
        (
            tool_calls_collected,
            _persisted_message_count,
        ) = await self.conversation_svc.persist_chat_messages(
            conversation=conversation,
            result=result,
            history_count=history_count,
            agent_id=agent_id,
            route_source=route_source,
            context_diagnostics=context_diagnostics_payload,
            last_run_summary=last_run_summary_payload,
        )

        # 7. Update conversation stats + agent usage / 7. 更新对话与智能体用量
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

        # 7.1 Write session memory (non-blocking, fail-safe) / 7.1 写入会话记忆
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

        prune_stats = (
            result.prune_stats if isinstance(result.prune_stats, dict) else None
        )
        rag_source_kinds = (
            result.rag_source_kinds if isinstance(result.rag_source_kinds, list) else []
        )

        return AgentChatResponse(
            conversation_id=conversation.id,
            message=result.output,
            tool_calls=tool_calls_collected or None,
            total_tokens=result.total_tokens,
            duration_ms=duration_ms,
            effective_knowledge_base_ids=knowledge_base_ids,
            dropped_knowledge_base_ids=dropped_knowledge_base_ids or None,
            context_compacted=(
                result.context_compacted
                if isinstance(result.context_compacted, bool)
                else False
            ),
            memory_recalled=(
                result.memory_recalled
                if isinstance(result.memory_recalled, bool)
                else False
            ),
            prune_stats=prune_stats,
            rag_source_kinds=rag_source_kinds,
            interaction_mode_effective=interaction_mode_effective,
            context_diagnostics=context_diagnostics_payload,
            last_run_summary=last_run_summary_payload,
        )

    # ========================================
    # Streaming chat (M16-T3-2) / 流式对话
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
        interaction_updates: list[dict[str, Any]] | None = None,
        trust_policy_ref: dict[str, Any] | None = None,
        interaction_mode: InteractionMode = "confirm",
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

        # 0. Load and validate Agent (must be published) / 0. 加载并校验 Agent（须已发布）
        agent = await self._validate_agent(agent_id)
        (
            knowledge_base_ids,
            dropped_knowledge_base_ids,
        ) = await self._sanitize_client_knowledge_base_ids(
            agent_id,
            knowledge_base_ids,
        )

        # Parse input: single message or batch / 解析消息：单条 message 或批量 messages
        batch = messages if messages else ([message] if message else [])
        first_message = batch[0] if batch else ""

        # 1. Get or create conversation / 1. 获取或创建对话
        is_new_conversation = conversation_id is None
        conversation_owner_type = ConversationOwnerTypeEnum.from_user_role(user_role)
        (
            interaction_mode_effective,
            resolved_trust_policy_ref,
            interaction_mode_downgrade_reason,
        ) = await self._resolve_interaction_mode(
            requested_mode=interaction_mode,
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=user_id,
            operator_type=conversation_owner_type,
            explicit_trust_policy_ref=trust_policy_ref,
            interaction_updates=interaction_updates,
        )
        conversation = await self.conversation_svc.get_or_create_for_chat(
            agent_id=agent_id,
            conversation_id=conversation_id,
            user_id=user_id,
            owner_type=conversation_owner_type,
            first_message=first_message,
        )
        conversation_metadata = dict(conversation.metadata_ or {})
        conversation_metadata["interaction_mode"] = interaction_mode_effective
        conversation_metadata["interaction_mode_requested"] = interaction_mode
        if interaction_mode_downgrade_reason:
            conversation_metadata["interaction_mode_downgrade_reason"] = (
                interaction_mode_downgrade_reason
            )
        conversation.metadata_ = conversation_metadata
        if interaction_updates:
            interaction_updates = [
                {
                    **update,
                    "auto_approve_source": (
                        "execution_trust_policy"
                        if interaction_mode_effective == "trusted_auto"
                        else None
                    ),
                    "downgraded_from": (
                        interaction_mode
                        if interaction_mode != interaction_mode_effective
                        else None
                    ),
                    "downgrade_reason": interaction_mode_downgrade_reason,
                    "interaction_mode_effective": interaction_mode_effective,
                }
                for update in interaction_updates
            ]
            await self.conversation_svc.update_last_assistant_interaction_state(
                conversation.id,
                interaction_updates,
                user_id=user_id,
                owner_type=conversation_owner_type,
                interaction_mode_requested=interaction_mode,
                interaction_mode_effective=interaction_mode_effective,
                interaction_mode_downgrade_reason=interaction_mode_downgrade_reason,
            )
            await self._grant_trusted_auto_policies(
                conversation_id=conversation.id,
                agent_id=agent_id,
                operator_id=user_id,
                operator_type=conversation_owner_type,
                interaction_updates=interaction_updates,
                interaction_mode=interaction_mode_effective,
            )
        memory_event_id = self._build_memory_event_id(conversation.id)

        # 2. Load history (context_config window) / 2. 加载历史
        ctx_cfg = agent.context_config or {}
        history_messages = await self.conversation_svc.load_chat_history(
            conversation_id=conversation.id,
            max_messages=ctx_cfg.get("max_history_messages", 0),
            max_tokens=ctx_cfg.get("max_history_tokens", 0),
        )

        # 3. Append user messages (batch ok; attachments on first only) / 3. 追加用户消息（首条可带附件）
        attach_list = (
            [a if isinstance(a, dict) else a.model_dump() for a in attachments]
            if attachments
            else None
        )
        if batch:
            user_msgs = [
                ChatMessage(
                    role="user", content=m, attachments=attach_list if i == 0 else None
                )
                for i, m in enumerate(batch)
            ]
        elif message.strip() or attach_list:
            user_msgs = [
                ChatMessage(role="user", content=message, attachments=attach_list),
            ]
        else:
            user_msgs = []
        all_messages = [*history_messages, *user_msgs]

        # 3.5 BEFORE_AGENT_CHAT hook (messages / system prompt / block) / 3.5 BEFORE_AGENT_CHAT 钩子
        hook_registry = get_hook_registry()
        if hook_registry.has_hooks(HookPoint.BEFORE_AGENT_CHAT):
            hook_ctx = await hook_registry.trigger(
                HookPoint.BEFORE_AGENT_CHAT,
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                messages=all_messages,
                config={
                    "variables": variables,
                    "knowledge_base_ids": knowledge_base_ids,
                },
            )
            if hook_ctx.get("blocked"):
                raise BusinessException(
                    message=hook_ctx.get(
                        "block_reason", _("agent_chat.error.blocked_by_hook")
                    )
                )
            all_messages = hook_ctx.get("messages", all_messages)

        # 4. Build execution request (stream) / 4. 构建执行请求（流式）
        normalized_scene, normalized_channel, normalized_source, memory_enabled = (
            self._resolve_memory_context(
                memory_scene=memory_scene,
                memory_channel=memory_channel,
                memory_source=memory_source,
            )
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
            long_term_memory_enabled=bool(
                ctx_cfg.get("long_term_memory_enabled", False)
            ),
            trust_policy_ref=resolved_trust_policy_ref,
            interaction_mode=interaction_mode_effective,
            page_session_id=page_session_id,
            interaction_updates=interaction_updates,
            knowledge_base_feedback=(
                {
                    "dropped_knowledge_base_ids": dropped_knowledge_base_ids,
                    "effective_knowledge_base_ids": knowledge_base_ids or [],
                }
                if dropped_knowledge_base_ids
                else None
            ),
        )

        # 4.1 Session memory injection (ai_chat_page only) / 4.1 会话记忆注入
        mem_text = await self._load_session_memory_context(request=request)
        if mem_text:
            # Prefer system slot, else prepend / system 位优先，否则插首位
            if request.messages and request.messages[0].role == "system":
                request.messages[
                    0
                ].content = f"{request.messages[0].content}\n\n{mem_text}"
            else:
                request.messages.insert(0, ChatMessage(role="system", content=mem_text))

        # 4.2 Conversation quota (max_turns / max_tokens per conversation) / 4.2 会话级配额
        quota_config = AgentQuotaConfig.from_dict(agent.quota_config)
        if (
            quota_config.max_turns_per_conversation > 0
            or quota_config.max_tokens_per_conversation > 0
        ):
            current_turns = sum(1 for m in request.messages if m.role == "assistant")
            current_tokens = sum(
                estimate_tokens(m.content or "") for m in request.messages
            )
            await AgentQuotaManager.check_conversation_limits(
                config=quota_config,
                current_turns=current_turns,
                current_tokens=current_tokens,
            )

        # 5. Pre-check quota, concurrency, hooks (match dispatch) / 5. 配额并发钩子前置检查
        lock_token: str = ""

        # Estimate input tokens for atomic pre-deduction (match dispatcher) / 预估输入 Token 以原子预扣
        estimated_tokens = max(
            sum(estimate_tokens(m.content or "") for m in all_messages),
            100,  # Floor 100 (system prompt + generation overhead) / 下限 100（system 与生成开销）
        )
        seeded_user_message_count = 0

        try:
            # Concurrency control / 并发控制
            if (
                quota_config.max_concurrent > 0
                or quota_config.tenant_max_concurrent > 0
            ):
                lock_token = await AgentConcurrencyLimiter.acquire(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    max_concurrent=quota_config.max_concurrent,
                    tenant_max_concurrent=quota_config.tenant_max_concurrent,
                )

            # Quota check (atomic pre-deduction) / 配额检查（原子预扣）
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

            # Plan monthly API call quota / 套餐月 API 调用配额
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

            # BEFORE_EXECUTE hook (registry from step 3.5) / BEFORE_EXECUTE 钩子
            hook_context = await hook_registry.trigger(
                HookPoint.BEFORE_EXECUTE,
                tenant_id=self.tenant_id,
                agent_id=agent_id,
                execution_mode=request.execution_mode,
                request=request,
            )
            if hook_context.get("blocked"):
                reason = hook_context.get(
                    "block_reason", _("agent.error.blocked_by_hook")
                )
                raise BusinessException(message=reason)

            # Commit only after all preflight checks pass, so failed requests do not
            # leave empty conversations or consume daily conversation quota.
            if is_new_conversation:
                await AgentQuotaManager.record_conversation(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    user_id=user_id,
                )
            seeded_user_message_count = 0
            if user_msgs:
                seeded_user_message_count = (
                    await self.conversation_svc.persist_user_messages(
                        conversation=conversation,
                        messages=user_msgs,
                    )
                )
            await self.db.commit()

            # ExecutionStarted event / 执行开始事件
            await BaseEngine._publish_execution_started(request, agent)

        except (AgentQuotaExceeded, AgentConcurrencyExceeded, BusinessException):
            # Release concurrency lock then re-raise / 释放并发锁后重抛
            if lock_token:
                await AgentConcurrencyLimiter.release(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    lock_token=lock_token,
                )
            raise

        # 6. Create Gateway / 6. 创建 Gateway
        gateway = AIGateway(self.db)

        # 6.1 Image model → ImageGenerationEngine / 6.1 生图模型走 ImageGenerationEngine
        model_obj = getattr(agent, "model", None)
        is_image_model = (
            model_obj is not None and getattr(model_obj, "type", "") == "image"
        )

        if is_image_model:
            from app.ai.engine.image_generation import ImageGenerationEngine

            engine = ImageGenerationEngine(gateway=gateway)
            skill_result = None
        else:
            # Resolve skills in Service layer (not inside Engine) / Service 层解析 Skill（Engine 内不查库）
            from app.ai.skills.resolver import resolve_for_agent

            try:
                skill_result = await resolve_for_agent(
                    self.db,
                    agent,
                    tenant_id=self.tenant_id,
                    user_role=user_role,
                )
            except Exception as skill_exc:
                logger.error(
                    "Skill resolution failed for agent {}: {}",
                    agent_id,
                    str(skill_exc),
                )
                skill_result = None

            # Platform Toolkit security config / 读取平台 Toolkit 安全配置
            from app.configs.service import ConfigService

            _cfg = ConfigService(self.db)
            _toolkit_security_level = await _cfg.get_platform_config(
                "toolkit_security_level",
                default="normal",
            )
            _toolkit_memory_limit_mb = await _cfg.get_platform_config(
                "toolkit_memory_limit_mb",
                default=256,
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
                trust_policy_ref=resolved_trust_policy_ref,
                interaction_mode=interaction_mode_effective,
            )
            engine = ConversationEngine(
                db=self.db,
                gateway=gateway,
                sandbox=sandbox,
            )

        # 7. Persist callback after stream (quota, lock release, hooks) / 7. 流式结束持久化回调
        history_count = len(history_messages) + int(seeded_user_message_count or 0)

        async def _persist_stream_last_error_marker(
            *,
            conversation_id: int,
            error_type: str,
            error_message: str,
            friendly_message: str,
            partial: bool,
            extra_payload: dict[str, Any] | None = None,
        ) -> None:
            """Persist conversation-level stream error marker / 持久化会话级流式错误标记。"""
            async with async_session_factory() as marker_db:
                marker_conv_svc = ConversationService(marker_db, self.tenant_id)
                marker_conv = await marker_conv_svc.repo.get_by_id(conversation_id)
                if marker_conv is None:
                    logger.warning(
                        "Skip stream error marker because conversation is missing: conversation_id={}",
                        conversation_id,
                    )
                    return

                conversation_metadata = dict(marker_conv.metadata_ or {})
                marker_payload: dict[str, Any] = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": error_type,
                    "error_message": str(error_message or "")[:500],
                    "friendly_message": friendly_message,
                    "partial": bool(partial),
                }
                if isinstance(extra_payload, dict) and extra_payload:
                    marker_payload["details"] = _JSON_SAFE(extra_payload)
                conversation_metadata["last_error"] = marker_payload
                marker_conv.metadata_ = (
                    _JSON_SAFE_DICT(conversation_metadata)
                    or {}
                )
                await marker_db.commit()

        async def _save_error_message_to_conversation(
            *,
            conversation_id: int,
            error_text: str,
            user_message: str,
            result: ExecutionResult,
            history_count: int,
            persist_user_message: bool,
            context_diagnostics_payload: dict[str, Any],
            last_run_summary_payload: dict[str, Any],
        ) -> None:
            """Persist a user-facing stream error message / 持久化面向用户的流式错误消息。"""
            from app.enums.agent import MessageRoleEnum

            async with async_session_factory() as err_db:
                err_conv_svc = ConversationService(err_db, self.tenant_id)
                err_conv = await err_conv_svc.repo.get_by_id(conversation_id)
                if err_conv is None:
                    logger.warning(
                        "Skip stream error persistence because conversation is missing: conversation_id={}",
                        conversation_id,
                    )
                    return

                current_count = await err_conv_svc.message_repo.count_by_conversation(
                    conversation_id
                )
                next_seq = await err_conv_svc.message_repo.get_next_sequence(
                    conversation_id
                )
                persisted_rows = 0
                normalized_user_message = str(user_message or "").strip()
                if persist_user_message and normalized_user_message:
                    await err_conv_svc.message_repo.create(
                        {
                            "tenant_id": self.tenant_id,
                            "conversation_id": conversation_id,
                            "role": MessageRoleEnum.USER.value,
                            "content": normalized_user_message,
                            "sequence": next_seq,
                            "token_count": estimate_tokens(normalized_user_message),
                            "agent_id": None,
                            "model_id": None,
                            "metadata_": _JSON_SAFE_DICT(
                                {
                                    "recovered_from_failed_stream": True,
                                    "stream_error_recovered": True,
                                }
                            )
                            or {},
                        }
                    )
                    next_seq += 1
                    persisted_rows += 1
                error_metadata: dict[str, Any] = {
                    "error": True,
                    "error_type": "stream_execution_error",
                    "raw_error_message": str(result.error or "")[:500],
                    "partial_output": result.output or "",
                    "total_tokens": result.total_tokens or 0,
                    "duration_ms": result.duration_ms or 0,
                    "user_message_preview": (user_message or "")[:200],
                }
                if context_diagnostics_payload:
                    error_metadata["context_diagnostics"] = _JSON_SAFE(
                        context_diagnostics_payload
                    )
                if last_run_summary_payload:
                    error_metadata["last_run_summary"] = _JSON_SAFE(
                        last_run_summary_payload
                    )
                error_metadata = _JSON_SAFE_DICT(error_metadata) or {}

                await err_conv_svc.message_repo.create(
                    {
                        "tenant_id": self.tenant_id,
                        "conversation_id": conversation_id,
                        "role": MessageRoleEnum.ASSISTANT.value,
                        "content": error_text,
                        "sequence": next_seq,
                        "token_count": estimate_tokens(error_text),
                        "agent_id": agent_id,
                        "model_id": result.runtime_model_id,
                        "metadata_": error_metadata,
                    }
                )
                persisted_rows += 1

                conversation_metadata = dict(err_conv.metadata_ or {})
                conversation_metadata["last_error"] = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "error_type": "stream_execution_error",
                    "error_message": str(result.error or "")[:500],
                    "friendly_message": error_text,
                    "partial": bool(result.partial),
                }
                if persisted_rows:
                    err_conv.message_count = max(
                        int(getattr(err_conv, "message_count", 0) or 0),
                        int(current_count or 0),
                    ) + persisted_rows
                err_conv.metadata_ = (
                    _JSON_SAFE_DICT(conversation_metadata)
                    or {}
                )
                await err_db.commit()
                logger.info(
                    "Stream error message saved: conversation_id={} error_type=stream_execution_error",
                    conversation_id,
                )

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
            persisted_message_count = 0
            context_diagnostics_payload: dict[str, Any] = {}
            last_run_summary_payload: dict[str, Any] = {}
            system_count = 0
            error_message_persisted = False
            try:
                context_diagnostics_payload = self._build_context_diagnostics(
                    result,
                    interaction_mode_effective=interaction_mode_effective,
                )
                last_run_summary_payload = self._build_last_run_summary(
                    result,
                    interaction_mode_effective=interaction_mode_effective,
                    downgrade_reason=interaction_mode_downgrade_reason,
                )

                # Persist when success OR when we have new messages (partial/interrupted) / 成功时持久化；或中断时如有新消息也持久化
                system_count = sum(
                    1 for m in (result.messages or []) if m.get("role") == "system"
                )
                has_new_messages = (result.messages or []) and len(
                    result.messages
                ) > system_count + history_count
                if result.success or has_new_messages:
                    # Commit messages and stats first, then memory extract (avoid full rollback on late cancel) / 先提交消息与统计再记忆抽取，避免取消导致整笔回滚
                    try:
                        async with async_session_factory() as cb_db:
                            try:
                                cb_conv_svc = ConversationService(
                                    cb_db,
                                    self.tenant_id,
                                )
                                cb_conv = await cb_conv_svc.repo.get_by_id(
                                    conversation.id,
                                )
                                (
                                    _persisted_tool_calls,
                                    persisted_message_count,
                                ) = await cb_conv_svc.persist_chat_messages(
                                    conversation=cb_conv,
                                    result=result,
                                    history_count=history_count,
                                    agent_id=agent_id,
                                    route_source=route_source,
                                    context_diagnostics=context_diagnostics_payload,
                                    last_run_summary=last_run_summary_payload,
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
                    except Exception as persist_exc:
                        logger.error(
                            "Stream completion persistence failed: tenant={} conversation={} err={}",
                            self.tenant_id,
                            conversation.id,
                            str(persist_exc),
                            exc_info=True,
                        )
                        extra["persistence_error"] = True
                        persist_failure_result = ExecutionResult(
                            **{
                                **result.__dict__,
                                "error": str(persist_exc),
                            }
                        )
                        try:
                            await _save_error_message_to_conversation(
                                conversation_id=conversation.id,
                                error_text=_("ai.stream.error.service_unavailable"),
                                user_message=first_message,
                                result=persist_failure_result,
                                history_count=history_count,
                                persist_user_message=seeded_user_message_count <= 0,
                                context_diagnostics_payload={
                                    **(context_diagnostics_payload or {}),
                                    "persistence_error": True,
                                    "persistence_error_message": str(persist_exc)[:500],
                                },
                                last_run_summary_payload={
                                    **(last_run_summary_payload or {}),
                                    "persistence_error": True,
                                    "persistence_error_message": str(persist_exc)[:500],
                                },
                            )
                            error_message_persisted = True
                        except Exception as fallback_exc:
                            logger.error(
                                "Fallback stream error persistence failed: tenant={} conversation={} err={}",
                                self.tenant_id,
                                conversation.id,
                                str(fallback_exc),
                                exc_info=True,
                            )
                            try:
                                await _persist_stream_last_error_marker(
                                    conversation_id=conversation.id,
                                    error_type="stream_on_complete_persistence_error",
                                    error_message=str(fallback_exc),
                                    friendly_message=_(
                                        "ai.stream.error.service_unavailable"
                                    ),
                                    partial=bool(result.partial),
                                    extra_payload={
                                        "stage": "persist_chat_messages",
                                        "original_error": str(persist_exc)[:500],
                                        "fallback_error": str(fallback_exc)[:500],
                                    },
                                )
                            except Exception as marker_exc:
                                logger.error(
                                    "Persist stream error marker failed after fallback error: tenant={} conversation={} err={}",
                                    self.tenant_id,
                                    conversation.id,
                                    str(marker_exc),
                                    exc_info=True,
                                )
                        persisted_message_count = max(persisted_message_count, 1)

                    try:
                        await AgentStatsManager.record_chat(
                            tenant_id=self.tenant_id,
                            agent_id=agent_id,
                            tokens=result.total_tokens,
                        )
                    except Exception as stats_exc:
                        logger.warning(
                            "Record agent stats failed: tenant={} agent={} conversation={} err={}",
                            self.tenant_id,
                            agent_id,
                            conversation.id,
                            str(stats_exc),
                        )

                    # Write session memory after stream / 流式完成后写入会话记忆
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
                                        mem_db,
                                        self.tenant_id,
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

                # Save error if failed and no assistant persisted / 失败且无 assistant 落库时写入错误
                # Count user messages in new slice / 统计新片段中 user 条数
                new_start = system_count + history_count
                new_messages_raw = (result.messages or [])[new_start:]
                user_message_count = sum(
                    1 for m in new_messages_raw if m.get("role") == "user"
                )
                # True if persisted rows include assistant (count > user-only) / 持久化条数大于纯 user 条数则含 assistant
                has_assistant_persisted = persisted_message_count > user_message_count
                if not result.success and not has_assistant_persisted:
                    lowered_error = str(result.error or "").lower()
                    friendly_error_text = (
                        _("ai.stream.error.fallback_failed")
                        if "fallback" in lowered_error
                        else _("ai.stream.error.service_unavailable")
                    )
                    await _save_error_message_to_conversation(
                        conversation_id=conversation.id,
                        error_text=friendly_error_text,
                        user_message=first_message,
                        result=result,
                        history_count=history_count,
                        persist_user_message=seeded_user_message_count <= 0,
                        context_diagnostics_payload=context_diagnostics_payload,
                        last_run_summary_payload=last_run_summary_payload,
                    )
                    error_message_persisted = True
                    logger.warning(
                        "Stream execution failed for conversation_id={}: {}",
                        conversation.id,
                        result.error or "Unknown error",
                    )

                # Adjust quota from estimate to actual (match dispatcher) / 配额从预估调整为实际
                actual_tokens = result.total_tokens or 0
                await AgentQuotaManager.adjust_usage(
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    estimated_tokens=estimated_tokens,
                    actual_tokens=actual_tokens,
                    config=quota_config,
                )

                # User-level usage record / 用户级用量记录
                if user_id and actual_tokens > 0:
                    await AgentQuotaManager.record_user_usage(
                        tenant_id=self.tenant_id,
                        agent_id=agent_id,
                        user_id=user_id,
                        tokens=actual_tokens,
                    )

                # AFTER_AGENT_CHAT hook (plugins may alter response) / AFTER_AGENT_CHAT 钩子
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

                # AFTER_EXECUTE hook / AFTER_EXECUTE 钩子
                await hook_registry.trigger(
                    HookPoint.AFTER_EXECUTE,
                    tenant_id=self.tenant_id,
                    agent_id=agent_id,
                    result=result,
                )

                # Emit execution complete/fail (stream bypasses dispatcher) / 发布执行完成或失败事件
                if result.success:
                    await BaseEngine._publish_execution_completed(
                        request,
                        agent,
                        result,
                    )
                else:
                    await BaseEngine._publish_execution_failed(
                        request,
                        agent,
                        result.error or "",
                    )
            except Exception as on_complete_exc:
                logger.error(
                    "Stream on_complete callback failed: tenant={} conversation={} err={}",
                    self.tenant_id,
                    conversation.id,
                    str(on_complete_exc),
                    exc_info=True,
                )
                extra["on_complete_error"] = True
                fallback_result = ExecutionResult(
                    **{
                        **result.__dict__,
                        "error": str(on_complete_exc),
                    }
                )
                fallback_error_text = _("ai.stream.error.service_unavailable")
                if not error_message_persisted:
                    try:
                        await _save_error_message_to_conversation(
                            conversation_id=conversation.id,
                            error_text=fallback_error_text,
                            user_message=first_message,
                            result=fallback_result,
                            history_count=history_count,
                            persist_user_message=seeded_user_message_count <= 0,
                            context_diagnostics_payload={
                                **(context_diagnostics_payload or {}),
                                "on_complete_error": True,
                                "on_complete_error_message": str(on_complete_exc)[
                                    :500
                                ],
                            },
                            last_run_summary_payload={
                                **(last_run_summary_payload or {}),
                                "on_complete_error": True,
                                "on_complete_error_message": str(on_complete_exc)[
                                    :500
                                ],
                            },
                        )
                    except Exception as fallback_exc:
                        logger.error(
                            "Final stream error message persistence failed: tenant={} conversation={} err={}",
                            self.tenant_id,
                            conversation.id,
                            str(fallback_exc),
                            exc_info=True,
                        )

                try:
                    await _persist_stream_last_error_marker(
                        conversation_id=conversation.id,
                        error_type="stream_on_complete_callback_error",
                        error_message=str(on_complete_exc),
                        friendly_message=fallback_error_text,
                        partial=bool(result.partial),
                        extra_payload={
                            "context_diagnostics_present": bool(
                                context_diagnostics_payload
                            ),
                            "last_run_summary_present": bool(last_run_summary_payload),
                        },
                    )
                except Exception as marker_exc:
                    logger.error(
                        "Final stream error marker persistence failed: tenant={} conversation={} err={}",
                        self.tenant_id,
                        conversation.id,
                        str(marker_exc),
                        exc_info=True,
                    )
            finally:
                # Release concurrency lock / 释放并发锁
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
    # Lightweight streaming (no conversation record) / 轻量级流式（无对话记录）
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
        (
            knowledge_base_ids,
            dropped_knowledge_base_ids,
        ) = await self._sanitize_client_knowledge_base_ids(
            agent_id,
            knowledge_base_ids,
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
            conversation_id=None,
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
            long_term_memory_enabled=False,
            knowledge_base_feedback=(
                {
                    "dropped_knowledge_base_ids": dropped_knowledge_base_ids,
                    "effective_knowledge_base_ids": knowledge_base_ids or [],
                }
                if dropped_knowledge_base_ids
                else None
            ),
        )

        quota_config = AgentQuotaConfig.from_dict(agent.quota_config)
        estimated_tokens = max(estimate_tokens(message), 100)
        lock_token: str = ""

        try:
            if (
                quota_config.max_concurrent > 0
                or quota_config.tenant_max_concurrent > 0
            ):
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
