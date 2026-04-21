"""
Execution engine types.

This module keeps the runtime request/result contracts stable for the legacy
engines while also carrying the structured orchestration state introduced by
the 666 rebuild.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from app.ai.constants import DEFAULT_MEMORY_SCENE, MEMORY_CHANNEL_SYSTEM
from app.ai.runtime.contracts import (
    ProtocolExecutionPlan,
    TurnCommand,
    TurnExecutionResult,
)
from app.ai.runtime.types import CapabilityBundle, TurnRecord
from app.ai.tools.types import ToolDefinition, ToolResult
from app.ai.types import ChatMessage
from app.enums.agent import AgentExecutionModeEnum
from app.enums.common import UserRoleEnum

if TYPE_CHECKING:
    from app.ai.routing.router import RouteResult


ExecutionPath = Literal["fast", "normal", "deep"]
IntentStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "skipped",
    "awaiting_consent",
]
ProviderFailureKind = Literal[
    "none",
    "provider_timeout",
    "provider_rate_limit",
    "provider_unavailable",
    "provider_http_5xx",
    "provider_bad_response",
    "tool_timeout",
    "tool_execution_error",
    "server_interrupt",
    "budget_exit",
]


@dataclass
class IntentPlan:
    """Structured execution intent for a single user turn."""

    intent_id: str
    kind: str
    family: str
    order: int
    user_visible_label: str
    source_text: str
    status: IntentStatus = "pending"
    requires_tools: bool = True
    allow_text_response: bool = False
    continuation: bool = False
    shortcircuit: bool = False
    cached_result: str | None = None
    allowed_tool_names: list[str] = field(default_factory=list)
    preferred_tool_names: list[str] = field(default_factory=list)
    completion_signals: list[str] = field(default_factory=list)
    completed_by_tool_names: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "kind": self.kind,
            "family": self.family,
            "order": self.order,
            "user_visible_label": self.user_visible_label,
            "source_text": self.source_text,
            "status": self.status,
            "requires_tools": self.requires_tools,
            "allow_text_response": self.allow_text_response,
            "continuation": self.continuation,
            "shortcircuit": self.shortcircuit,
            "cached_result": self.cached_result,
            "allowed_tool_names": list(self.allowed_tool_names),
            "preferred_tool_names": list(self.preferred_tool_names),
            "completion_signals": list(self.completion_signals),
            "completed_by_tool_names": list(self.completed_by_tool_names),
            "metadata": dict(self.metadata),
        }


@dataclass
class ExecutionBudget:
    """Hard orchestration budget for one turn."""

    max_prompt_tokens: int
    max_completion_tokens: int
    max_tool_rounds: int
    max_elapsed_ms: int
    max_retry_per_intent: int
    max_candidate_tools: int
    max_tool_result_bytes: int
    finalization_grace_ms: int = 0
    prompt_tokens_used: int = 0
    completion_tokens_used: int = 0
    tool_rounds_used: int = 0
    elapsed_ms_used: int = 0
    tool_result_bytes_used: int = 0
    candidate_tools_count: int = 0
    retries_by_intent: dict[str, int] = field(default_factory=dict)
    finalization_grace_applied: bool = False

    def _effective_elapsed_limit_ms(self) -> int:
        base_limit = max(0, int(self.max_elapsed_ms or 0))
        if (
            not self.finalization_grace_applied
            or int(self.finalization_grace_ms or 0) <= 0
        ):
            return base_limit
        return base_limit + int(self.finalization_grace_ms or 0)

    def apply_finalization_grace(self) -> bool:
        if self.finalization_grace_ms <= 0 or self.finalization_grace_applied:
            return False
        self.finalization_grace_applied = True
        return True

    def first_exceeded_reason(self) -> str | None:
        if self.max_prompt_tokens and self.prompt_tokens_used > self.max_prompt_tokens:
            return "prompt_budget_exceeded"
        if (
            self.max_completion_tokens
            and self.completion_tokens_used > self.max_completion_tokens
        ):
            return "completion_budget_exceeded"
        if self.max_tool_rounds and self.tool_rounds_used > self.max_tool_rounds:
            return "tool_round_budget_exceeded"
        if (
            self.max_elapsed_ms
            and self.elapsed_ms_used > self._effective_elapsed_limit_ms()
        ):
            return "elapsed_budget_exceeded"
        if (
            self.max_tool_result_bytes
            and self.tool_result_bytes_used > self.max_tool_result_bytes
        ):
            return "tool_result_budget_exceeded"
        if (
            self.max_candidate_tools
            and self.candidate_tools_count > self.max_candidate_tools
        ):
            return "candidate_tool_budget_exceeded"
        return None

    def snapshot(self) -> dict[str, Any]:
        exit_reason = self.first_exceeded_reason()
        elapsed_limit_ms = self._effective_elapsed_limit_ms()
        elapsed_ms_used = max(0, int(self.elapsed_ms_used or 0))
        elapsed_over_limit_ms = (
            max(0, elapsed_ms_used - elapsed_limit_ms) if self.max_elapsed_ms else 0
        )
        elapsed_over_limit = bool(elapsed_over_limit_ms > 0)
        return {
            "status": "exited" if exit_reason else "ok",
            "exit_reason": exit_reason,
            "limits": {
                "max_prompt_tokens": self.max_prompt_tokens,
                "max_completion_tokens": self.max_completion_tokens,
                "max_tool_rounds": self.max_tool_rounds,
                "max_elapsed_ms": self.max_elapsed_ms,
                "max_retry_per_intent": self.max_retry_per_intent,
                "max_candidate_tools": self.max_candidate_tools,
                "max_tool_result_bytes": self.max_tool_result_bytes,
                "finalization_grace_ms": self.finalization_grace_ms,
            },
            "usage": {
                "prompt_tokens_used": self.prompt_tokens_used,
                "completion_tokens_used": self.completion_tokens_used,
                "tool_rounds_used": self.tool_rounds_used,
                "elapsed_ms_used": elapsed_ms_used,
                "elapsed_limit_ms": elapsed_limit_ms,
                "elapsed_over_limit": elapsed_over_limit,
                "elapsed_over_limit_ms": elapsed_over_limit_ms,
                "tool_result_bytes_used": self.tool_result_bytes_used,
                "candidate_tools_count": self.candidate_tools_count,
                "retries_by_intent": dict(self.retries_by_intent),
                "finalization_grace_applied": self.finalization_grace_applied,
            },
            "exceeded_reason": exit_reason,
            "elapsed_limit_ms": elapsed_limit_ms,
            "elapsed_over_limit": elapsed_over_limit,
            "elapsed_over_limit_ms": elapsed_over_limit_ms,
        }


@dataclass
class RecoveryDecision:
    """Recovery decision scoped to unfinished intents."""

    action: Literal[
        "none",
        "retry_intent",
        "return_partial",
        "abort",
        "pause_for_consent",
    ] = "none"
    target_intent_id: str | None = None
    retry_family: str | None = None
    allowed_tool_names: list[str] = field(default_factory=list)
    completed_intent_ids: list[str] = field(default_factory=list)
    unfinished_intent_ids: list[str] = field(default_factory=list)
    reason: str = ""
    provider_failure_kind: ProviderFailureKind = "none"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "target_intent_id": self.target_intent_id,
            "retry_family": self.retry_family,
            "allowed_tool_names": list(self.allowed_tool_names),
            "completed_intent_ids": list(self.completed_intent_ids),
            "unfinished_intent_ids": list(self.unfinished_intent_ids),
            "reason": self.reason,
            "provider_failure_kind": self.provider_failure_kind,
            "metadata": dict(self.metadata),
        }


@dataclass
class ToolUsePolicy:
    """
    Tool-use policy for the current turn.

    The legacy engine still consumes this shape heavily, so it remains the
    runtime projection of the currently active intent/tool subset.
    """

    family: str = "none"
    mode: str = "auto"
    allowed_tool_names: list[str] = field(default_factory=list)
    retry_on_contract_breach: bool = False
    reason: str = ""


@dataclass
class ExecutionRequest:
    """Execution request passed into the dispatcher/engines."""

    agent_id: int
    tenant_id: int
    user_id: int | None = None
    messages: list[ChatMessage] = field(default_factory=list)
    input_variables: dict[str, Any] = field(default_factory=dict)
    execution_mode: str = AgentExecutionModeEnum.CONVERSATION.value
    stream: bool = False
    conversation_id: int | None = None
    knowledge_base_ids: list[int] | None = None
    system_prompt_additions: list[str] = field(default_factory=list)
    trust_policy_ref: dict[str, Any] | None = None
    interaction_mode: str = "trusted_auto"
    attachments: list[dict[str, Any]] | None = None
    consented_actions: list[str] | None = None
    interaction_updates: list[dict[str, Any]] | None = None
    user_role: str = UserRoleEnum.TENANT_ADMIN.value
    user_role_id: int | None = None
    permissions: set[str] | None = None
    billing_context: dict[str, Any] | None = None
    skip_quota: bool = False
    skip_persistence: bool = False
    skip_logging: bool = False
    memory_scene: str = DEFAULT_MEMORY_SCENE
    memory_channel: str = MEMORY_CHANNEL_SYSTEM
    memory_source: str = ""
    memory_enabled: bool = False
    session_memory_injected: bool = False
    long_term_memory_enabled: bool = False
    memory_runtime_policy: dict[str, Any] = field(default_factory=dict)
    page_session_id: str | None = None
    knowledge_base_feedback: dict[str, Any] | None = None
    tool_use_policy: ToolUsePolicy = field(default_factory=ToolUsePolicy)


@dataclass
class ExecutionResult:
    """Execution result returned by an engine."""

    success: bool = True
    output: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    total_tokens: int = 0
    duration_ms: int = 0
    conversation_id: int | None = None
    runtime_model_id: int | None = None
    runtime_model_name: str | None = None
    runtime_provider_id: int | None = None
    runtime_provider_name: str | None = None
    error: str = ""
    partial: bool = False
    interrupted: bool = False
    completion_reason: str = ""
    rag_sources: list[dict[str, Any]] | None = None
    rag_source_kinds: list[str] = field(default_factory=list)
    context_compacted: bool = False
    memory_flush_triggered: bool = False
    memory_recalled: bool = False
    prune_stats: dict[str, Any] | None = None
    tool_planner: dict[str, Any] | None = None
    turn_record: TurnRecord | dict[str, Any] | None = None
    intent_plan: list[IntentPlan] = field(default_factory=list)
    execution_path: ExecutionPath | None = None
    execution_budget: dict[str, Any] | None = None
    recovery_history: list[dict[str, Any]] = field(default_factory=list)
    provider_failure_kind: ProviderFailureKind = "none"
    provider_events: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: dict[str, Any] | None = None
    memory_runtime_policy: dict[str, Any] = field(default_factory=dict)


@dataclass
class PreparedExecution:
    """Shared execution context built by BaseEngine._prepare_execution()."""

    messages: list[ChatMessage] = field(default_factory=list)
    tools: list[ToolDefinition] = field(default_factory=list)
    all_tools: list[ToolDefinition] = field(default_factory=list)
    continuation_context: ResearchContinuationContext | None = None
    tool_use_policy: ToolUsePolicy = field(default_factory=ToolUsePolicy)
    rag_sources: list[dict[str, Any]] | None = None
    rag_source_kinds: list[str] = field(default_factory=list)
    compact_summary: str | None = None
    prune_stats: dict[str, Any] | None = None
    memory_recall_slice: dict[str, Any] | None = None
    context_compacted: bool = False
    memory_flush_triggered: bool = False
    memory_recalled: bool = False
    system_prompt_additions: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    tool_planner: dict[str, Any] | None = None
    context_engine: Any | None = None
    capability_bundle: CapabilityBundle | None = None
    tool_consent_modes: dict[str, str] = field(default_factory=dict)
    optimize_event: dict[str, Any] | None = None
    route_result: RouteResult | None = None
    stream_runtime: Any | None = None
    intent_plan: list[IntentPlan] = field(default_factory=list)
    execution_path: ExecutionPath = "fast"
    execution_budget: ExecutionBudget | None = None
    active_intent_id: str | None = None
    provider_events: list[dict[str, Any]] = field(default_factory=list)
    recovery_history: list[RecoveryDecision] = field(default_factory=list)


@dataclass
class ResearchContinuationContext:
    """Runtime metadata for external web research."""

    active: bool = False
    family: str | None = None
    origin: str = "none"
    current_user_text: str = ""
    research_target_text: str = ""
    recent_successful_tool_names: list[str] = field(default_factory=list)
    recent_web_queries: list[str] = field(default_factory=list)
    search_query_count: int = 0
    fetched_url_count: int = 0
    research_instruction_texts: list[str] = field(default_factory=list)
    tool_families: list[str] = field(default_factory=list)
    page_operation_names: list[str] = field(default_factory=list)
    page_context_attached: bool = False
    web_research_pair_complete: bool = False
    continuation_capable_families: list[str] = field(default_factory=list)
    last_tool_name: str = ""
    last_page_key: str = ""
    last_page_op: str = ""
    active_intent_kind: str | None = None


@dataclass
class BatchItem:
    """Single item in a batch execution."""

    item_id: str
    input_variables: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    result: ExecutionResult | None = None


@dataclass
class BatchResult:
    """Aggregated batch execution result."""

    batch_run_id: int | None = None
    items: list[BatchItem] = field(default_factory=list)
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    duration_ms: int = 0


__all__ = [
    "BatchItem",
    "BatchResult",
    "ExecutionBudget",
    "ExecutionPath",
    "ExecutionRequest",
    "ExecutionResult",
    "IntentPlan",
    "ProtocolExecutionPlan",
    "PreparedExecution",
    "ProviderFailureKind",
    "RecoveryDecision",
    "ResearchContinuationContext",
    "TurnExecutionResult",
    "TurnCommand",
    "ToolUsePolicy",
]
