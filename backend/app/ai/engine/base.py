"""
Execution Engine Abstract Base Class / 执行引擎抽象基类

Provides shared infrastructure for all execution modes:
message building, tool parsing, tool call loop, event publishing.
提供所有执行模式共享的基础设施：消息构建、工具解析、工具调用循环、事件发布。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.events.bus import get_event_bus
from app.ai.events.types import (
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionStarted,
)

if TYPE_CHECKING:
    from app.ai.gateway import AIGateway
from app.ai.prompt_contracts import render_prompt_contract
from app.ai.skills.resolver import SkillResolveResult
from app.ai.tools.sandbox import ToolSandbox
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage, ChatResponse
from app.core.logging import LogManager
from app.core.runtime_identity import get_runtime_identity_tag
from app.enums.common import UserRoleEnum
from app.enums.log import UserTypeEnum as LogUserTypeEnum
from app.models.ai.agent import Agent

from .base_helpers import (
    build_user_message,
    messages_to_dicts,
    parse_tool_arguments,
    stable_unique_text_list,
    tool_call_name,
    tool_call_operation_name,
    truncate_preview,
    truncate_tool_calls_after_page_navigation,
)
from .budget_helpers import budget_exit_response as _budget_exit_response_impl
from .contract_diagnostics_helpers import (
    build_contract_recovery_system_message as _build_contract_recovery_system_message_impl,
)
from .contract_diagnostics_helpers import (
    merge_contract_diagnostics_into_turn_record as _merge_contract_diagnostics_into_turn_record_impl,
)
from .llm_call_helpers import (
    apply_llm_response_metadata as _apply_llm_response_metadata_impl,
)
from .llm_call_helpers import (
    prepare_llm_gateway_call as _prepare_llm_gateway_call_impl,
)
from .page_flow_recovery_helpers import (
    build_page_no_progress_recovery_default as _build_page_no_progress_recovery_default_impl,
)
from .prepare_execution_pipeline import (
    prepare_execution_with_defaults as _prepare_execution_with_defaults_impl,
)
from .system_prompt_helpers import (
    build_capability_reporting_hint as _build_capability_reporting_hint_impl,
)
from .system_prompt_helpers import (
    build_ordered_capability_hint_default as _build_ordered_capability_hint_default_impl,
)
from .system_prompt_helpers import (
    build_page_operations_hint as _build_page_operations_hint_impl,
)
from .system_prompt_helpers import (
    build_research_continuation_hint as _build_research_continuation_hint_impl,
)
from .system_prompt_helpers import (
    build_runtime_capability_hint as _build_runtime_capability_hint_impl,
)
from .system_prompt_helpers import (
    build_system_message_default as _build_system_message_default_impl,
)
from .system_prompt_helpers import (
    build_time_tools_hint as _build_time_tools_hint_impl,
)
from .system_prompt_helpers import (
    build_weather_tools_hint as _build_weather_tools_hint_impl,
)
from .system_prompt_helpers import (
    build_web_research_hint as _build_web_research_hint_impl,
)
from .system_prompt_helpers import (
    deserialize_intent_plan as _deserialize_intent_plan_impl,
)
from .system_prompt_helpers import (
    inject_runtime_summary as _inject_runtime_summary_impl,
)
from .system_prompt_helpers import (
    intent_completion_signals as _intent_completion_signals_impl,
)
from .system_prompt_helpers import (
    intent_plan_gating_flags as _intent_plan_gating_flags_impl,
)
from .system_prompt_helpers import (
    is_capability_reporting_query as _is_capability_reporting_query_impl,
)
from .tool_call_loop_runtime import (
    ToolCallLoopCallbacks,
    ToolCallLoopRuntime,
    run_tool_call_loop,
)
from .tool_contract_retry_helpers import (
    analyze_post_tool_contract_breach as _analyze_post_tool_contract_breach_impl,
)
from .tool_contract_retry_helpers import (
    build_post_tool_retry_policy as _build_post_tool_retry_policy_impl,
)
from .tool_contract_retry_helpers import (
    collect_tool_family_evidence as _collect_tool_family_evidence_impl,
)
from .tool_contract_retry_helpers import (
    log_tool_contract_diagnostics_default as _log_tool_contract_diagnostics_default_impl,
)
from .tool_contract_retry_helpers import (
    log_web_research_contract_diagnostics_default as _log_web_research_contract_diagnostics_default_impl,
)
from .tool_contract_retry_helpers import (
    resolve_breach_retry_policy as _resolve_breach_retry_policy_impl,
)
from .tool_contract_retry_helpers import (
    should_retry_tool_contract_breach as _should_retry_tool_contract_breach_impl,
)
from .tool_contract_retry_helpers import (
    should_retry_web_research_contract_breach as _should_retry_web_research_contract_breach_impl,
)
from .tool_policy_helpers import (
    allowed_tool_names_for_families as _allowed_tool_names_for_families_impl,
)
from .tool_policy_helpers import (
    allowed_tool_names_for_family as _allowed_tool_names_for_family_impl,
)
from .tool_policy_helpers import (
    apply_execution_trust_policy as _apply_execution_trust_policy_impl,
)
from .tool_policy_helpers import (
    build_required_policy_for_family as _build_required_policy_for_family_impl,
)
from .tool_policy_helpers import (
    collect_completed_turn_intents as _collect_completed_turn_intents_impl,
)
from .tool_policy_helpers import (
    detect_requested_turn_intents as _detect_requested_turn_intents_impl,
)
from .tool_policy_helpers import (
    ensure_explicit_family_coverage as _ensure_explicit_family_coverage_impl,
)
from .tool_policy_helpers import (
    ensure_web_research_tool_pair as _ensure_web_research_tool_pair_impl,
)
from .tool_policy_helpers import (
    extract_textual_tool_call_names as _extract_textual_tool_call_names_impl,
)
from .tool_policy_helpers import (
    family_capability_terms as _family_capability_terms_impl,
)
from .tool_policy_helpers import (
    filter_tools_for_policy as _filter_tools_for_policy_impl,
)
from .tool_policy_helpers import (
    first_incomplete_requested_family as _first_incomplete_requested_family_impl,
)
from .tool_policy_helpers import (
    first_page_intent_kind as _first_page_intent_kind_impl,
)
from .tool_policy_helpers import (
    log_tool_selection_status as _log_tool_selection_status_impl,
)
from .tool_policy_helpers import (
    looks_like_explicit_time_request as _looks_like_explicit_time_request_impl,
)
from .tool_policy_helpers import (
    looks_like_explicit_web_research_request as _looks_like_explicit_web_research_request_impl,
)
from .tool_policy_helpers import (
    looks_like_generic_follow_up as _looks_like_generic_follow_up_impl,
)
from .tool_policy_helpers import (
    looks_like_generic_page_summary_request as _looks_like_generic_page_summary_request_impl,
)
from .tool_policy_helpers import (
    looks_like_tool_planning_leak as _looks_like_tool_planning_leak_impl,
)
from .tool_policy_helpers import (
    mark_multi_family_progress as _mark_multi_family_progress_impl,
)
from .tool_policy_helpers import (
    messages_have_blocking_pending_interaction as _messages_have_blocking_pending_interaction_impl,
)
from .tool_policy_helpers import (
    ordered_requested_families_from_intents as _ordered_requested_families_from_intents_impl,
)
from .tool_policy_helpers import (
    response_denies_family_capability as _response_denies_family_capability_impl,
)
from .tool_policy_helpers import (
    response_has_native_web_search_evidence as _response_has_native_web_search_evidence_impl,
)
from .tool_policy_helpers import (
    restore_explicit_family_tools as _restore_explicit_family_tools_impl,
)
from .tool_policy_helpers import (
    restrict_page_tools_for_generic_summary as _restrict_page_tools_for_generic_summary_impl,
)
from .tool_policy_helpers import (
    restrict_tools_to_names as _restrict_tools_to_names_impl,
)
from .tool_policy_helpers import (
    tool_family_for_name as _tool_family_for_name_impl,
)
from .tool_policy_helpers import (
    tool_semantic_family as _tool_semantic_family_impl,
)
from .tool_policy_helpers import (
    tool_semantic_tags as _tool_semantic_tags_impl,
)
from .turn_research_helpers import (
    apply_fetch_url_only_gate as _apply_fetch_url_only_gate_impl,
)
from .turn_research_helpers import (
    build_web_research_continuation_context as _build_web_research_continuation_context_impl,
)
from .turn_research_helpers import (
    collect_current_turn_fetch_titles as _collect_current_turn_fetch_titles_impl,
)
from .turn_research_helpers import (
    collect_web_research_evidence as _collect_web_research_evidence_impl,
)
from .turn_research_helpers import (
    extract_fetch_title_from_output as _extract_fetch_title_from_output_impl,
)
from .turn_research_helpers import (
    extract_last_user_text as _extract_last_user_text_impl,
)
from .turn_research_helpers import (
    extract_latest_turn_runtime_facts as _extract_latest_turn_runtime_facts_impl,
)
from .turn_research_helpers import (
    extract_recent_research_instruction_texts as _extract_recent_research_instruction_texts_impl,
)
from .turn_research_helpers import (
    extract_recent_successful_tool_names as _extract_recent_successful_tool_names_impl,
)
from .turn_research_helpers import (
    extract_recent_web_queries as _extract_recent_web_queries_impl,
)
from .turn_research_helpers import has_page_context as _has_page_context_impl
from .turn_research_helpers import (
    is_title_only_fetch_response as _is_title_only_fetch_response_impl,
)
from .turn_research_helpers import (
    looks_like_explicit_title_request as _looks_like_explicit_title_request_impl,
)
from .turn_research_helpers import (
    needs_fetch_url_before_summary as _needs_fetch_url_before_summary_impl,
)
from .turn_research_helpers import (
    normalize_web_research_contract_text as _normalize_web_research_contract_text_impl,
)
from .turn_research_helpers import (
    page_operation_names_from_input_variables as _page_operation_names_from_input_variables_impl,
)
from .types import (
    ExecutionBudget,
    ExecutionRequest,
    ExecutionResult,
    IntentPlan,
    PreparedExecution,
    ResearchContinuationContext,
    ToolUsePolicy,
)

logger = LogManager.get_logger("ai.engine")

def log_user_type_for_call_log(user_role: str) -> str:
    """Map ExecutionRequest.user_role → call_log.user_type / 执行请求角色 → 调用日志用户类型."""
    if user_role == UserRoleEnum.PLATFORM_ADMIN.value:
        return LogUserTypeEnum.ADMIN.value
    if user_role == UserRoleEnum.TENANT_USER.value:
        return LogUserTypeEnum.TENANT_USER.value
    return LogUserTypeEnum.TENANT_ADMIN.value

class BaseEngine(ABC):
    """
    Execution Engine Abstract Base Class / 执行引擎抽象基类

    Subclasses only need to implement execute(); base class provides:
    子类只需实现 execute() 方法，基类提供：
    - _build_messages: Build system + user messages / 构建 system + user 消息
    - _prepare_execution: Shared pre-logic (Skill resolve + RAG + tool optimization) / 共享前置逻辑
    - _handle_tool_calls: Tool calling loop / tool calling 循环
    - _call_llm: Call AIGateway / 调用 AIGateway
    """

    def __init__(
        self,
        db: AsyncSession,
        gateway: AIGateway,
        sandbox: ToolSandbox | None,
    ):
        """
        Args:
            db: Database session / 数据库会话
            gateway: AI Gateway / AI 网关
            sandbox: Tool sandbox / 工具沙箱
        """
        self.db = db
        self.gateway = gateway
        self.sandbox = sandbox

    @abstractmethod
    async def execute(self, agent: Agent, request: ExecutionRequest) -> ExecutionResult:
        """
        Execute request.
        执行请求。

        Args:
            agent: Agent model instance / 智能体模型实例
            request: Execution request / 执行请求

        Returns:
            ExecutionResult
        """

    # ========================================
    # Message Building / 消息构建
    # ========================================

    _build_system_message = staticmethod(_build_system_message_default_impl)

    @staticmethod
    def _inject_runtime_summary(
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        _input_variables: dict[str, Any] | None = None,
        continuation_context: ResearchContinuationContext | None = None,
        runtime_capability_summary: dict[str, Any] | None = None,
        ordered_requested_families: list[str] | None = None,
        skip_capability_summary: bool = False,
        intent_plan: list[IntentPlan] | None = None,
        execution_path: str | None = None,
        execution_budget: ExecutionBudget | None = None,
        include_knowledge_base_hint: bool = True,
        include_page_context_hint: bool = True,
        include_memory_hint: bool = True,
    ) -> bool:
        return _inject_runtime_summary_impl(
            messages=messages,
            tools=tools,
            continuation_context=continuation_context,
            runtime_capability_summary=runtime_capability_summary,
            ordered_requested_families=ordered_requested_families,
            skip_capability_summary=skip_capability_summary,
            intent_plan=intent_plan,
            execution_path=execution_path,
            execution_budget=execution_budget,
            include_knowledge_base_hint=include_knowledge_base_hint,
            include_page_context_hint=include_page_context_hint,
            include_memory_hint=include_memory_hint,
            render_contract=render_prompt_contract,
        )

    @staticmethod
    def _build_page_operations_hint(
        input_variables: dict[str, Any] | None,
        tools: list[ToolDefinition] | None = None,
    ) -> str:
        return _build_page_operations_hint_impl(
            input_variables=input_variables,
            tools=tools,
            render_contract=render_prompt_contract,
        )

    _deserialize_intent_plan = staticmethod(_deserialize_intent_plan_impl)
    _intent_plan_gating_flags = staticmethod(_intent_plan_gating_flags_impl)
    _is_capability_reporting_query = staticmethod(_is_capability_reporting_query_impl)
    _intent_completion_signals = staticmethod(_intent_completion_signals_impl)
    _build_web_research_hint = staticmethod(_build_web_research_hint_impl)
    _build_weather_tools_hint = staticmethod(_build_weather_tools_hint_impl)
    _build_time_tools_hint = staticmethod(_build_time_tools_hint_impl)
    _build_capability_reporting_hint = staticmethod(
        _build_capability_reporting_hint_impl
    )
    _build_runtime_capability_hint = staticmethod(
        _build_runtime_capability_hint_impl
    )
    _build_ordered_capability_hint = staticmethod(
        _build_ordered_capability_hint_default_impl
    )
    _build_research_continuation_hint = staticmethod(
        _build_research_continuation_hint_impl
    )
    _prepare_llm_gateway_call = staticmethod(_prepare_llm_gateway_call_impl)
    _apply_llm_response_metadata = staticmethod(_apply_llm_response_metadata_impl)
    _user_message = staticmethod(build_user_message)
    _parse_tool_arguments = staticmethod(parse_tool_arguments)
    _tool_call_operation_name = staticmethod(tool_call_operation_name)
    _tool_call_name = staticmethod(tool_call_name)
    _truncate_tool_calls_after_navigation = staticmethod(
        truncate_tool_calls_after_page_navigation
    )
    _restrict_tools_to_names = staticmethod(_restrict_tools_to_names_impl)
    _build_page_no_progress_recovery = staticmethod(
        _build_page_no_progress_recovery_default_impl
    )
    _extract_recent_successful_tool_names = staticmethod(
        _extract_recent_successful_tool_names_impl
    )
    _extract_recent_web_queries = staticmethod(_extract_recent_web_queries_impl)
    _collect_web_research_evidence = staticmethod(_collect_web_research_evidence_impl)
    _collect_current_turn_fetch_titles = staticmethod(
        _collect_current_turn_fetch_titles_impl
    )
    _extract_fetch_title_from_output = staticmethod(_extract_fetch_title_from_output_impl)
    _normalize_web_research_contract_text = staticmethod(
        _normalize_web_research_contract_text_impl
    )
    _looks_like_explicit_title_request = staticmethod(
        _looks_like_explicit_title_request_impl
    )
    _is_title_only_fetch_response = staticmethod(_is_title_only_fetch_response_impl)
    _needs_fetch_url_before_summary = staticmethod(_needs_fetch_url_before_summary_impl)
    _apply_fetch_url_only_gate = staticmethod(_apply_fetch_url_only_gate_impl)
    _extract_last_user_text = staticmethod(_extract_last_user_text_impl)
    _extract_recent_research_instruction_texts = staticmethod(
        _extract_recent_research_instruction_texts_impl
    )
    _truncate_preview = staticmethod(truncate_preview)
    _has_page_context = staticmethod(_has_page_context_impl)
    _page_operation_names_from_input_variables = staticmethod(
        _page_operation_names_from_input_variables_impl
    )
    _stable_unique_text_list = staticmethod(stable_unique_text_list)
    _extract_latest_turn_runtime_facts = staticmethod(
        _extract_latest_turn_runtime_facts_impl
    )
    _tool_family_for_name = staticmethod(_tool_family_for_name_impl)
    _messages_have_blocking_pending_interaction = staticmethod(
        _messages_have_blocking_pending_interaction_impl
    )
    _first_incomplete_requested_family = staticmethod(
        _first_incomplete_requested_family_impl
    )
    _mark_multi_family_progress = staticmethod(_mark_multi_family_progress_impl)
    _tool_semantic_family = staticmethod(_tool_semantic_family_impl)
    _tool_semantic_tags = staticmethod(_tool_semantic_tags_impl)
    _family_capability_terms = staticmethod(_family_capability_terms_impl)
    _response_denies_family_capability = staticmethod(
        _response_denies_family_capability_impl
    )
    _extract_textual_tool_call_names = staticmethod(
        _extract_textual_tool_call_names_impl
    )
    _looks_like_tool_planning_leak = staticmethod(_looks_like_tool_planning_leak_impl)
    _detect_requested_turn_intents = staticmethod(_detect_requested_turn_intents_impl)
    _collect_completed_turn_intents = staticmethod(
        _collect_completed_turn_intents_impl
    )
    _response_has_native_web_search_evidence = staticmethod(
        _response_has_native_web_search_evidence_impl
    )
    _build_post_tool_retry_policy = staticmethod(_build_post_tool_retry_policy_impl)
    _analyze_post_tool_contract_breach = staticmethod(
        _analyze_post_tool_contract_breach_impl
    )
    _build_contract_recovery_system_message = staticmethod(
        _build_contract_recovery_system_message_impl
    )
    _merge_contract_diagnostics_into_turn_record = staticmethod(
        _merge_contract_diagnostics_into_turn_record_impl
    )
    _looks_like_generic_follow_up = staticmethod(_looks_like_generic_follow_up_impl)
    _allowed_tool_names_for_family = staticmethod(_allowed_tool_names_for_family_impl)
    _allowed_tool_names_for_families = staticmethod(
        _allowed_tool_names_for_families_impl
    )
    _filter_tools_for_policy = staticmethod(_filter_tools_for_policy_impl)
    _restore_explicit_family_tools = staticmethod(
        _restore_explicit_family_tools_impl
    )
    _ensure_explicit_family_coverage = staticmethod(
        _ensure_explicit_family_coverage_impl
    )
    _ensure_web_research_tool_pair = staticmethod(
        _ensure_web_research_tool_pair_impl
    )
    _looks_like_explicit_web_research_request = staticmethod(
        _looks_like_explicit_web_research_request_impl
    )
    _first_page_intent_kind = staticmethod(_first_page_intent_kind_impl)
    _looks_like_generic_page_summary_request = staticmethod(
        _looks_like_generic_page_summary_request_impl
    )
    _restrict_page_tools_for_generic_summary = staticmethod(
        _restrict_page_tools_for_generic_summary_impl
    )
    _looks_like_explicit_time_request = staticmethod(
        _looks_like_explicit_time_request_impl
    )
    _log_tool_selection_status = staticmethod(_log_tool_selection_status_impl)
    _ordered_requested_families_from_intents = staticmethod(
        _ordered_requested_families_from_intents_impl
    )
    _build_required_policy_for_family = staticmethod(
        _build_required_policy_for_family_impl
    )
    _resolve_breach_retry_policy = staticmethod(_resolve_breach_retry_policy_impl)
    _should_retry_tool_contract_breach = staticmethod(
        _should_retry_tool_contract_breach_impl
    )
    _should_retry_web_research_contract_breach = staticmethod(
        _should_retry_web_research_contract_breach_impl
    )
    _collect_tool_family_evidence = staticmethod(_collect_tool_family_evidence_impl)
    _build_web_research_continuation_context = staticmethod(
        _build_web_research_continuation_context_impl
    )

    # ========================================
    # Shared Pre-logic / 共享前置逻辑
    # ========================================

    async def _prepare_execution(
        self,
        agent: Agent,
        request: ExecutionRequest,
        skill_result: SkillResolveResult | None = None,
    ) -> PreparedExecution:
        """
        Build execution context (shared pre-logic for execute / stream_execute).
        构建执行上下文（execute / stream_execute 共享前置逻辑）。

        Includes / 包含：
        1. Use pre-resolved Skill result (or fallback to internal resolve) / 使用预解析的 Skill 结果
        2. Build message list (system + history) / 构建消息列表
        3. RAG knowledge base injection / RAG 知识库注入
        4. Tool optimization / 工具优化
        5. Tool awareness hint injection / 工具感知提示注入

        Args:
            agent: Agent model instance / 智能体模型实例
            request: Execution request / 执行请求
            skill_result: Pre-resolved Skill result (from Dispatcher layer) / 预解析的 Skill 结果

        Returns:
            PreparedExecution context / PreparedExecution 上下文
        """
        return await _prepare_execution_with_defaults_impl(
            db=self.db,
            base_engine=self,
            sandbox=self.sandbox,
            agent=agent,
            request=request,
            skill_result=skill_result,
            render_contract=render_prompt_contract,
        )

    # ========================================
    # LLM Call / LLM 调用
    # ========================================

    async def _call_llm(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None = None,
        all_tool_names: list[str] | None = None,
        tool_use_policy: ToolUsePolicy | None = None,
        breach_retry_result: str | None = None,
        tenant_id: int | None = None,
        user_id: int | None = None,
        conversation_id: int | None = None,
        billing_context: dict[str, Any] | None = None,
        route_result: Any | None = None,
        log_user_type: str | None = None,
        selected_skill_names: list[str] | None = None,
        context_sources: list[Any] | None = None,
    ) -> ChatResponse:
        """
        Call LLM.
        调用 LLM。

        Args:
            agent: Agent (with model config) / 智能体（含模型配置）
            messages: Message list / 消息列表
            tools: Tool definition list / 工具定义列表
            tenant_id: Tenant ID / 企业 ID
            user_id: User ID / 用户 ID
            route_result: ModelRouter route result (None uses agent's original model) / ModelRouter 路由结果
        """
        del selected_skill_names, context_sources
        prepared_call = await self._prepare_llm_gateway_call(
            db=self.db,
            agent=agent,
            messages=messages,
            tools=tools,
            all_tool_names=all_tool_names,
            tool_use_policy=tool_use_policy,
            breach_retry_result=breach_retry_result,
            tenant_id=tenant_id,
            user_id=user_id,
            conversation_id=conversation_id,
            billing_context=billing_context,
            route_result=route_result,
            log_user_type=log_user_type,
        )

        logger.info(
            "LLM call entry: runtime={} agent_id={} conversation_id={} provider={} model={} family={} mode={} allowed_tool_names={} tool_count={}",
            get_runtime_identity_tag(),
            getattr(agent, "id", None),
            conversation_id,
            prepared_call.llm_call_context.provider_code,
            prepared_call.llm_call_context.model_code,
            prepared_call.effective_policy.family,
            prepared_call.effective_policy.mode,
            prepared_call.effective_policy.allowed_tool_names,
            len(tools or []),
        )
        response = await self.gateway.chat(
            **prepared_call.gateway_kwargs,
        )
        return self._apply_llm_response_metadata(
            response,
            llm_call_context=prepared_call.llm_call_context,
        )

    def _log_tool_contract_diagnostics(
        self,
        *,
        agent: Any,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        tools: list[ToolDefinition],
        policy: ToolUsePolicy,
        conversation_id: int | None,
        breach_type: str,
        retry_result: str,
        continuation: ResearchContinuationContext | None = None,
    ) -> None:
        _ = self
        _log_tool_contract_diagnostics_default_impl(
            agent=agent,
            messages=messages,
            response=response,
            tools=tools,
            policy=policy,
            conversation_id=conversation_id,
            breach_type=breach_type,
            retry_result=retry_result,
            continuation=continuation,
        )

    def _log_web_research_contract_diagnostics(
        self,
        *,
        agent: Any,
        messages: list[ChatMessage],
        response: ChatResponse,
        tools: list[ToolDefinition],
        continuation: ResearchContinuationContext | None,
        conversation_id: int | None,
    ) -> None:
        _ = self
        _log_web_research_contract_diagnostics_default_impl(
            agent=agent,
            messages=messages,
            response=response,
            tools=tools,
            continuation=continuation,
            conversation_id=conversation_id,
        )

    _budget_exit_response = staticmethod(_budget_exit_response_impl)

    # ========================================
    # Tool Call Loop / 工具调用循环
    # ========================================

    async def _handle_tool_calls(
        self,
        agent: Agent,
        messages: list[ChatMessage],
        response: ChatResponse,
        tools: list[ToolDefinition],
        all_tools: list[ToolDefinition] | None,
        request: ExecutionRequest,
        skip_final_call: bool = False,
        route_result: Any | None = None,
        tool_consent_modes: dict[str, str] | None = None,
        continuation_context: ResearchContinuationContext | None = None,
        selected_skill_names: list[str] | None = None,
        context_sources: list[Any] | None = None,
        tool_use_policy: ToolUsePolicy | None = None,
        execution_budget: ExecutionBudget | None = None,
        starting_total_tokens: int | None = None,
        starting_completion_tokens: int | None = None,
    ) -> tuple[ChatResponse | None, list[ToolResult], int, int]:
        """
        Handle tool call loop.
        处理工具调用循环。

        When LLM returns tool_calls, executes tools and appends results to messages,
        then calls LLM again until no more tool_calls or max rounds reached.
        当 LLM 返回 tool_calls 时，执行工具并将结果追加到消息中，
        然后再次调用 LLM，直到不再返回 tool_calls 或达到最大轮次。

        Args:
            agent: Agent / 智能体
            messages: Current message list (will be modified) / 当前消息列表（会被修改）
            response: LLM response / LLM 响应
            tools: Tool definition list / 工具定义列表
            request: Original request / 原始请求
            skip_final_call: Skip final LLM call (for streaming path, caller handles streaming) / 跳过最终 LLM 调用
            route_result: ModelRouter route result (maintains model consistency within tool call loop) / ModelRouter 路由结果

        Returns:
            (final_response, all_tool_results, total_tokens, completion_tokens)
            final_response is None when skip_final_call=True
            当 skip_final_call=True 时 final_response 为 None
        """
        async def _call_followup_llm(
            round_tools: list[ToolDefinition],
            round_policy: ToolUsePolicy,
        ) -> ChatResponse:
            return await self._call_llm(
                agent=agent,
                messages=messages,
                tools=round_tools,
                all_tool_names=[tool.name for tool in (all_tools or tools or [])],
                tool_use_policy=round_policy,
                tenant_id=request.tenant_id,
                user_id=request.user_id,
                conversation_id=request.conversation_id,
                billing_context=request.billing_context,
                route_result=route_result,
                log_user_type=log_user_type_for_call_log(request.user_role),
                selected_skill_names=selected_skill_names,
                context_sources=context_sources,
            )

        runtime = ToolCallLoopRuntime(
            sandbox=self.sandbox,
            agent=agent,
            messages=messages,
            response=response,
            tools=tools,
            all_tools=all_tools,
            request=request,
            skip_final_call=skip_final_call,
            tool_consent_modes=tool_consent_modes or {},
            continuation_context=continuation_context,
            tool_use_policy=tool_use_policy,
            execution_budget=execution_budget,
            starting_total_tokens=starting_total_tokens,
            starting_completion_tokens=starting_completion_tokens,
        )
        callbacks = ToolCallLoopCallbacks(
            ordered_requested_families_from_intents=self._ordered_requested_families_from_intents,
            truncate_tool_calls_after_navigation=self._truncate_tool_calls_after_navigation,
            mark_multi_family_progress=self._mark_multi_family_progress,
            budget_exit_response=self._budget_exit_response,
            build_page_no_progress_recovery=self._build_page_no_progress_recovery,
            messages_have_blocking_pending_interaction=self._messages_have_blocking_pending_interaction,
            first_incomplete_requested_family=self._first_incomplete_requested_family,
            allowed_tool_names_for_family=self._allowed_tool_names_for_family,
            build_ordered_capability_hint=self._build_ordered_capability_hint,
            needs_fetch_url_before_summary=self._needs_fetch_url_before_summary,
            apply_fetch_url_only_gate=self._apply_fetch_url_only_gate,
            restrict_tools_to_names=self._restrict_tools_to_names,
            call_followup_llm=_call_followup_llm,
        )
        return await run_tool_call_loop(runtime=runtime, callbacks=callbacks)

    # ========================================
    # Event Publishing / 事件发布
    # ========================================

    @staticmethod
    async def _publish_execution_started(
        request: ExecutionRequest, agent: Agent
    ) -> None:
        """Publish execution started event / 发布执行开始事件"""
        await get_event_bus().publish(
            ExecutionStarted(
                tenant_id=request.tenant_id,
                agent_id=agent.id,
                execution_mode=request.execution_mode,
            )
        )

    @staticmethod
    async def _publish_execution_completed(
        request: ExecutionRequest,
        agent: Agent,
        result: ExecutionResult,
    ) -> None:
        """Publish execution completed event / 发布执行完成事件"""
        await get_event_bus().publish(
            ExecutionCompleted(
                tenant_id=request.tenant_id,
                agent_id=agent.id,
                total_tokens=result.total_tokens,
                duration_ms=result.duration_ms,
            )
        )

    @staticmethod
    async def _publish_execution_failed(
        request: ExecutionRequest,
        agent: Agent,
        error: str,
        error_type: str = "",
    ) -> None:
        """Publish execution failed event / 发布执行失败事件"""
        await get_event_bus().publish(
            ExecutionFailed(
                tenant_id=request.tenant_id,
                agent_id=agent.id,
                error=error,
                error_type=error_type,
            )
        )

    _messages_to_dicts = staticmethod(messages_to_dicts)
    _apply_execution_trust_policy = staticmethod(_apply_execution_trust_policy_impl)


__all__ = ["BaseEngine", "log_user_type_for_call_log"]
