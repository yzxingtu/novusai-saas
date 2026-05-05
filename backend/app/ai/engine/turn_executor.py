"""Unified turn execution loop for streaming and non-streaming flows."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.ai.tools.types import ExecutionContext, ToolResult
from app.ai.types import ChatMessage, ChatResponse
from app.ai.web_research import WebResearchEvidence, WebResearchRunOptions
from app.ai.web_research.providers import (
    BuiltinFetchUrlProvider,
    BuiltinWebSearchProvider,
)
from app.ai.web_research.runtime import WebResearchRuntime

from .execution_state_machine import ExecutionStateMachine
from .final_output_policy import (
    build_untrusted_final_output_fallback,
    is_trusted_assistant_final_output_source,
)
from .recovery_manager import RecoveryManager
from .recovery_tool_result_helpers import intent_result_from_tool_results
from .recovery_web_research_gate import (
    WEB_RESEARCH_TERMINAL_CONTRACT_KEY,
    RecoveryWebResearchGate,
)
from .turn_executor_tool_batch import (
    build_required_fetch_url_fallback_response,
    build_shortcircuit_fallback_response,
    execute_tool_batch,
    maybe_retry_web_research_contract,
    record_synthetic_required_fetch_url,
    run_contract_retry_round,
    run_tool_batch_or_update_intents,
)
from .types import RecoveryDecision, ToolUsePolicy


@dataclass
class ModelRoundResult:
    """Result produced by one model call round."""

    response: Any | None
    total_tokens: int = 0
    completion_tokens_used: int = 0
    # Retained as adapter diagnostics only. Platform WebResearch completion is
    # driven by normalized web_search/fetch_url evidence, not provider text.
    native_search_observed: bool = False


@dataclass
class ToolBatchResult:
    """Result produced by handling one batch of tool calls."""

    response: Any | None
    tool_results: list[Any] = field(default_factory=list)
    total_tokens: int = 0
    completion_tokens_used: int = 0


@dataclass
class TurnExecutionResult:
    """Unified execution output for sync/stream adapters."""

    output: str
    total_tokens: int
    completion_tokens_used: int
    tool_results: list[Any]
    response: Any | None
    partial: bool
    paused_for_consent: bool
    completion_reason: str
    final_output_source: Literal[
        "assistant",
        "tool_evidence_completed",
        "recovery_evidence",
        "partial_output",
        "budget_fallback",
    ]
    action_buttons: list[dict[str, Any]] | None = None


class TurnIOAdapter(Protocol):
    """Transport/helper adapter; execution loop remains in TurnExecutor."""

    async def call_llm(
        self,
        *,
        messages: list[Any],
        tools: list[Any] | None,
        tool_use_policy: Any,
        **kwargs: Any,
    ) -> ModelRoundResult: ...

    async def handle_tool_calls(
        self,
        *,
        response: Any,
        tools: list[Any],
        messages: list[Any],
        **kwargs: Any,
    ) -> ToolBatchResult: ...

    async def finalize_partial_output(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
    ) -> tuple[str, int, int]: ...

    async def finalize_completed_output(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
    ) -> tuple[str, int, int]: ...

    def should_retry_tool_contract_breach(
        self,
        *,
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[Any],
        input_variables: dict[str, Any] | None,
    ) -> tuple[bool, ToolUsePolicy | None, str]: ...

    def should_retry_web_research_contract_breach(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[Any],
        input_variables: dict[str, Any] | None,
        continuation: Any,
    ) -> tuple[bool, ToolUsePolicy | None, str]: ...

    def analyze_post_tool_contract_breach(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[Any],
        input_variables: dict[str, Any] | None,
    ) -> tuple[str | None, ToolUsePolicy | None, dict[str, Any]]: ...

    def restrict_tools_to_names(
        self,
        tools: list[Any],
        allowed_tool_names: list[str] | None,
    ) -> list[Any]: ...

    def log_tool_contract_diagnostics(
        self,
        *,
        agent: Any,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        tools: list[Any],
        policy: ToolUsePolicy,
        conversation_id: int | None,
        breach_type: str,
        retry_result: str,
        continuation: Any,
    ) -> None: ...

    async def emit_chunk(self, text: str) -> None: ...


def active_intent(state: Any) -> Any | None:
    for intent in state.intent_plan:
        if intent.status in {"completed", "failed", "skipped"}:
            continue
        if intent.family == "none" or not intent.requires_tools:
            continue
        return intent
    return None


def assistant_tool_round_count(messages: list[ChatMessage]) -> int:
    return sum(
        1
        for message in messages
        if message.role == "assistant" and bool(message.tool_calls)
    )


def register_tool_round_delta(
    state: Any,
    *,
    before_count: int,
    messages: list[ChatMessage],
) -> None:
    delta = max(0, assistant_tool_round_count(messages) - before_count)
    for _round_idx in range(delta):
        state.register_tool_round()


def current_turn_start_index(messages: list[ChatMessage]) -> int:
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].role == "user":
            return index
    return 0


def current_turn_messages(
    messages: list[ChatMessage],
    *,
    start_index: int,
) -> list[ChatMessage]:
    if start_index <= 0:
        return list(messages)
    return list(messages[start_index:])


def emit_round_started(
    state: ExecutionStateMachine,
    *,
    round_kind: str,
    policy: ToolUsePolicy | None,
    tools: list[Any] | None = None,
    intent: Any | None = None,
    reason: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "round_kind": round_kind,
        "tool_names": [tool.name for tool in (tools or [])],
        "allowed_tool_names": list(getattr(policy, "allowed_tool_names", []) or []),
        "tool_use_policy_family": getattr(policy, "family", None),
        "tool_use_policy_mode": getattr(policy, "mode", None),
        "tool_use_policy_reason": (
            reason or str(getattr(policy, "reason", "") or "").strip() or None
        ),
    }
    if intent is not None:
        payload["intent_id"] = getattr(intent, "intent_id", None)
        payload["intent_kind"] = getattr(intent, "kind", None)
        payload["intent_family"] = getattr(intent, "family", None)
    state.emit_event("turn.round_started", payload)


def response_has_visible_content(response: ChatResponse | None) -> bool:
    if response is None:
        return False
    return bool(str(response.message.content or "").strip())


def _tool_names(tools: list[Any]) -> set[str]:
    return {
        str(getattr(tool, "name", "") or "").strip()
        for tool in tools
        if str(getattr(tool, "name", "") or "").strip()
    }


def should_run_platform_web_research_runtime(
    *,
    intent: Any | None,
    tools: list[Any],
) -> bool:
    if intent is None:
        return False
    if str(getattr(intent, "family", "") or "").strip() != "web_research":
        return False
    if str(getattr(intent, "kind", "") or "").strip() != "web_research":
        return False
    if getattr(intent, "status", None) in {"completed", "failed", "skipped"}:
        return False
    metadata = dict(getattr(intent, "metadata", {}) or {})
    if str(metadata.get("web_research_runtime") or "").strip() != "platform":
        return False
    if (
        bool(metadata.get("fetch_only"))
        or str(metadata.get("explicit_url") or "").strip()
    ):
        return False
    available_tool_names = _tool_names(tools)
    return {"web_search", "fetch_url"}.issubset(available_tool_names)


def _web_research_query(intent: Any | None, messages: list[ChatMessage]) -> str:
    source_text = str(getattr(intent, "source_text", "") or "").strip()
    if source_text:
        return source_text
    for message in reversed(messages):
        if message.role == "user" and str(message.content or "").strip():
            return str(message.content or "").strip()
    return ""


def _web_research_execution_context(*, request: Any, agent: Any) -> ExecutionContext:
    return ExecutionContext(
        tenant_id=int(getattr(request, "tenant_id", 0) or 0),
        agent_id=int(getattr(agent, "id", getattr(request, "agent_id", 0)) or 0),
        user_id=getattr(request, "user_id", None),
        user_role=str(getattr(request, "user_role", "") or ""),
        permissions=set(getattr(request, "permissions", None) or set()),
        db=getattr(request, "db", None),
        consented_actions=set(getattr(request, "consented_actions", None) or []),
        trust_policy_ref=getattr(request, "trust_policy_ref", None),
        variables=dict(getattr(request, "input_variables", None) or {}),
        conversation_id=getattr(request, "conversation_id", None),
        interaction_mode=str(
            getattr(request, "interaction_mode", "") or "trusted_auto"
        ),
    )


def _search_tool_result_from_evidence(evidence: WebResearchEvidence) -> ToolResult:
    payload_items = [
        {
            "title": item.title,
            "url": item.url,
            "snippet": item.snippet,
            "rank": item.rank,
            "provider": item.provider,
            "answer_quality": item.answer_quality,
        }
        for item in evidence.search_results
    ]
    summary_payload: dict[str, Any] = {
        "status": evidence.status if evidence.search_results else evidence.status,
        "query": evidence.query,
        "provider": evidence.search_provider,
        "selected_backend": evidence.search_provider,
        "result_count": len(payload_items),
        "items": payload_items,
        "web_research_evidence": evidence.to_dict(),
    }
    if evidence.failure_kind:
        summary_payload["failure_reason"] = evidence.failure_kind
    return ToolResult(
        tool_call_id=(
            f"{evidence.diagnostics.pipeline_id}:web_search"
            if evidence.diagnostics.pipeline_id
            else "web_research_runtime:web_search"
        ),
        name="web_search",
        success=evidence.status != "failed" or bool(payload_items),
        output=json.dumps(
            {
                "query": evidence.query,
                "items": payload_items,
                "status": evidence.status,
            },
            ensure_ascii=False,
        ),
        error=evidence.failure_kind or "",
        error_type=evidence.failure_kind or "",
        summary=f"{len(payload_items)} search result(s) for {evidence.query}",
        summary_payload=summary_payload,
    )


def _fetch_output_from_page(page: Any) -> str:
    parts: list[str] = [f"Content from {page.url}:"]
    if page.title:
        parts.append(f"Title: {page.title}")
    if page.description:
        parts.append(f"Description: {page.description}")
    body = str(page.body_text or page.summary or "").strip()
    if body:
        parts.extend(["", body])
    return "\n".join(parts).strip()


def _fetch_tool_results_from_evidence(
    evidence: WebResearchEvidence,
) -> list[ToolResult]:
    results: list[ToolResult] = []
    evidence_accepted_for_answer = bool(
        evidence.status == "completed"
        and evidence.answer_quality != "none"
        and evidence.diagnostics.answer_source != "none"
        and not evidence.failure_kind
    )
    for index, page in enumerate(evidence.fetched_pages, start=1):
        success = bool(
            evidence_accepted_for_answer
            and page.status == "completed"
            and page.answer_quality != "none"
        )
        error_type = ""
        if not success:
            error_type = page.failure_kind or evidence.failure_kind or ""
        summary_payload: dict[str, Any] = {
            "fetch_url": True,
            "ok": success,
            "url": page.url,
            "final_url": page.url,
            "title": page.title,
            "description": page.description,
            "summary": page.summary,
            "answer_quality": page.answer_quality,
            "evidence_quality": evidence.answer_quality,
            "answer_source": evidence.diagnostics.answer_source,
            "status": page.status,
            "provider": page.provider,
            "relevance_status": page.relevance_status,
            "relevance_score": page.relevance_score,
            "relevance_profile": page.relevance_profile,
            "relevance_reason": page.relevance_reason,
            "relevance_matched_terms": list(page.relevance_matched_terms),
            "relevance_required_terms": list(page.relevance_required_terms),
            "web_research_evidence": evidence.to_dict(),
        }
        if error_type:
            summary_payload["error_type"] = error_type
        results.append(
            ToolResult(
                tool_call_id=(
                    f"{evidence.diagnostics.pipeline_id}:fetch_url:{index}"
                    if evidence.diagnostics.pipeline_id
                    else f"web_research_runtime:fetch_url:{index}"
                ),
                name="fetch_url",
                success=success,
                output=_fetch_output_from_page(page) if success else "",
                error=error_type,
                error_type=error_type,
                summary=page.summary or page.title or page.url,
                result_link=page.url,
                summary_payload=summary_payload,
            )
        )
    return results


def tool_results_from_web_research_evidence(
    evidence: WebResearchEvidence,
) -> list[ToolResult]:
    return [
        _search_tool_result_from_evidence(evidence),
        *_fetch_tool_results_from_evidence(evidence),
    ]


def intent_retry_policy_reason(
    decision: RecoveryDecision,
    retry_intent: Any | None,
) -> str:
    decision_reason = str(decision.reason or "").strip()
    if retry_intent is None:
        return decision_reason

    return decision_reason


def latest_auto_fetch_gate_reason(state: ExecutionStateMachine) -> str | None:
    for intent in reversed(state.intent_plan):
        metadata = dict(getattr(intent, "metadata", {}) or {})
        reason = str(metadata.get("auto_fetch_gate_reason") or "").strip()
        if reason:
            return reason
    return None


def latest_web_research_terminal_contract(
    state: ExecutionStateMachine,
) -> str | None:
    for intent in reversed(state.intent_plan):
        contract = RecoveryWebResearchGate.terminal_contract(intent)
        if contract:
            return contract
    return None


def completed_tool_intent_families(state: ExecutionStateMachine) -> set[str]:
    families: set[str] = set()
    for intent in state.intent_plan:
        if intent.status != "completed" or not intent.requires_tools:
            continue
        family = str(intent.family or "").strip()
        if family:
            families.add(family)
    return families


def should_complete_from_budgeted_web_research_evidence(
    *,
    state: ExecutionStateMachine,
    response: ChatResponse | None,
    tool_results: list[ToolResult],
    reason: str,
) -> Literal["none", "keep_visible_output", "replace_with_tool_evidence"]:
    if not RecoveryManager.is_budget_exit_reason(reason):
        return "none"
    if "web_research" not in completed_tool_intent_families(state):
        return "none"
    if RecoveryManager.next_unfinished_intents(state.intent_plan):
        return "none"

    response_text = str(
        getattr(getattr(response, "message", None), "content", "") or ""
    ).strip()
    if not response_text:
        return "replace_with_tool_evidence"
    if RecoveryManager.should_replace_budgeted_web_research_response(
        response_text=response_text,
        tool_results=tool_results,
    ):
        return "replace_with_tool_evidence"
    return "keep_visible_output"


def should_recover_web_search_evidence_from_partial(reason: str) -> bool:
    normalized = str(reason or "").strip()
    return bool(
        normalized == "retry_budget_exhausted"
        or normalized == "budget_exit"
        or RecoveryManager.is_budget_exit_reason(normalized)
    )


def post_tool_completion_state(
    *,
    state: ExecutionStateMachine,
    final_output_source: str,
    ran_post_tool_follow_up: bool,
) -> str:
    if final_output_source == "recovery_evidence":
        return "recovery_evidence"
    if final_output_source == "tool_evidence_completed":
        auto_fetch_gate_reason = latest_auto_fetch_gate_reason(state)
        if auto_fetch_gate_reason == "search_not_successful":
            return "search_not_successful"
        if auto_fetch_gate_reason == "search_no_results_completed":
            return "completed_no_result"
        return "tool_evidence_completed"
    if final_output_source == "partial_output":
        return "partial_output"
    if final_output_source == "budget_fallback":
        return "budget_fallback"
    if ran_post_tool_follow_up:
        return "llm_follow_up"
    return "assistant"


def has_completed_fetch_url_body_evidence(
    *,
    state: ExecutionStateMachine,
    tool_results: list[ToolResult],
) -> bool:
    completed_by_fetch_url = any(
        intent.status == "completed"
        and str(intent.family or "").strip() == "web_research"
        and "fetch_url"
        in {
            str(name or "").strip()
            for name in (intent.completed_by_tool_names or [])
            if str(name or "").strip()
        }
        for intent in state.intent_plan
    )
    if not completed_by_fetch_url:
        return False
    return any(
        bool(intent_result_from_tool_results(intent, tool_results))
        for intent in state.intent_plan
        if intent.status == "completed"
        and str(intent.family or "").strip() == "web_research"
        and "fetch_url" in set(intent.completed_by_tool_names or [])
    )


_UNACCEPTED_WEB_RESEARCH_GATE_REASONS = frozenset(
    {
        "search_not_successful",
        "search_no_results_completed",
        "candidate_urls_exhausted",
        "fetch_already_attempted",
        "blocked_url",
        "fetch_failed",
        "fetch_not_attempted",
        "low_query_relevance",
        "no_answer_quality_evidence",
        "insufficient_cross_checked_sources",
        "search_failed",
    }
)


def _tool_result_web_research_failure_reason(tool_results: list[ToolResult]) -> str:
    for result in reversed(tool_results or []):
        tool_name = str(getattr(result, "name", "") or "").strip()
        if tool_name not in {"web_search", "fetch_url"}:
            continue
        summary_payload = getattr(result, "summary_payload", None)
        if not isinstance(summary_payload, dict):
            summary_payload = {}
        reason = str(
            getattr(result, "error_type", "")
            or summary_payload.get("error_type")
            or summary_payload.get("failure_reason")
            or summary_payload.get("status")
            or ""
        ).strip()
        if reason == "search_candidates_exhausted":
            return "candidate_urls_exhausted"
        if tool_name == "web_search" and reason == "no_results":
            return "search_no_results_completed"
        if reason and reason not in {"success", "ok"}:
            return reason
    return ""


def _web_research_failure_reason(
    state: ExecutionStateMachine,
    *,
    tool_results: list[ToolResult],
) -> str:
    diagnostics = dict(state.preparation_diagnostics or {})
    web_diagnostics = diagnostics.get("web_research_diagnostics")
    if isinstance(web_diagnostics, dict):
        for key in ("failure_kind", "web_research_failure_kind"):
            reason = str(web_diagnostics.get(key) or "").strip()
            if reason:
                return reason
    for key in ("web_research_failure_kind", "failure_kind"):
        reason = str(diagnostics.get(key) or "").strip()
        if reason and reason != "none":
            return reason
    tool_failure_reason = _tool_result_web_research_failure_reason(tool_results)
    if tool_failure_reason:
        return tool_failure_reason
    auto_fetch_gate_reason = latest_auto_fetch_gate_reason(state)
    if auto_fetch_gate_reason:
        return auto_fetch_gate_reason
    return "web_research_evidence_incomplete"


def _has_web_research_runtime_signal(state: ExecutionStateMachine) -> bool:
    diagnostics = dict(state.preparation_diagnostics or {})
    if (
        "web_research_diagnostics" in diagnostics
        or "web_research_evidence" in diagnostics
        or "evidence_status" in diagnostics
        or "answer_source" in diagnostics
    ):
        return True
    return any(
        str(event.get("kind") or "").strip() == "web_research_runtime"
        for event in state.provider_events
        if isinstance(event, dict)
    )


def should_return_partial_for_unaccepted_web_research_evidence(
    *,
    state: ExecutionStateMachine,
    tool_results: list[ToolResult],
) -> str | None:
    if has_completed_fetch_url_body_evidence(state=state, tool_results=tool_results):
        return None
    diagnostics = dict(state.preparation_diagnostics or {})
    web_diagnostics = diagnostics.get("web_research_diagnostics")
    if isinstance(web_diagnostics, dict):
        merged_diagnostics = {**diagnostics, **web_diagnostics}
    else:
        merged_diagnostics = diagnostics

    evidence_status = str(merged_diagnostics.get("evidence_status") or "").strip()
    answer_source = str(merged_diagnostics.get("answer_source") or "").strip()
    failure_kind = str(
        merged_diagnostics.get("web_research_failure_kind")
        or merged_diagnostics.get("failure_kind")
        or ""
    ).strip()
    auto_fetch_gate_reason = latest_auto_fetch_gate_reason(state)
    tool_failure_reason = _tool_result_web_research_failure_reason(tool_results)
    has_web_signal = _has_web_research_runtime_signal(state) or bool(
        auto_fetch_gate_reason or tool_failure_reason
    )
    if not has_web_signal:
        return None
    if evidence_status == "completed" and answer_source not in {"", "none"}:
        return None
    if (
        evidence_status in {"partial", "failed"}
        or answer_source in {"none", ""}
        or failure_kind
        or auto_fetch_gate_reason in _UNACCEPTED_WEB_RESEARCH_GATE_REASONS
        or tool_failure_reason
    ):
        return _web_research_failure_reason(state, tool_results=tool_results)
    return None


def mark_web_research_intents_failed_for_unaccepted_evidence(
    state: ExecutionStateMachine,
    *,
    reason: str,
) -> None:
    for intent in state.intent_plan:
        if str(intent.family or "").strip() != "web_research":
            continue
        intent.metadata = dict(intent.metadata or {})
        intent.status = "failed"
        intent.completed_by_tool_names = []
        intent.metadata["failure_reason"] = reason
        intent.metadata["web_research_evidence_unaccepted"] = True


def record_web_research_partial_exit(
    state: ExecutionStateMachine,
    *,
    reason: str,
) -> None:
    target_intent_id = next(
        (
            intent.intent_id
            for intent in state.intent_plan
            if str(intent.family or "").strip() == "web_research"
            and intent.status != "completed"
        ),
        None,
    )
    unfinished_intent_ids = [
        intent.intent_id for intent in state.intent_plan if intent.status != "completed"
    ]
    decision = RecoveryDecision(
        action="return_partial",
        target_intent_id=target_intent_id,
        retry_family="web_research",
        unfinished_intent_ids=unfinished_intent_ids,
        reason=reason,
        provider_failure_kind="none",
        metadata={"web_research_evidence_unaccepted": True},
    )
    state.recovery_events.append(
        {
            "kind": "partial_output",
            "action": "return_partial",
            "target_intent_id": target_intent_id,
            "reason": reason,
            "web_research_evidence_unaccepted": True,
        }
    )
    decision.metadata["source_recovery_event_seq"] = len(state.recovery_events)
    state.recovery_history.append(decision)


def intent_missing_args(intent: Any | None) -> list[str]:
    metadata = dict(getattr(intent, "metadata", {}) or {}) if intent is not None else {}
    raw_missing_args = metadata.get("missing_args")
    if not isinstance(raw_missing_args, list):
        return []
    return [str(item).strip() for item in raw_missing_args if str(item).strip()]


def intent_requires_clarification(intent: Any | None) -> bool:
    return bool(
        intent is not None
        and getattr(intent, "allow_text_response", False)
        and intent_missing_args(intent)
    )


def cached_shortcircuit_intent(state: ExecutionStateMachine) -> Any | None:
    if active_intent(state) is not None:
        return None
    for intent in state.intent_plan:
        cached_result = str(getattr(intent, "cached_result", "") or "").strip()
        if bool(getattr(intent, "shortcircuit", False)) and cached_result:
            return intent
    return None


async def finalize_turn_execution(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    messages: list[ChatMessage],
    response: ChatResponse | None,
    decision: Any | None,
    tool_results: list[ToolResult],
    total_tokens: int,
    completion_tokens_used: int,
    ran_post_tool_follow_up: bool,
    emit_round_started_cb: Callable[..., None],
) -> tuple[
    str,
    bool,
    bool,
    str,
    Literal[
        "assistant",
        "tool_evidence_completed",
        "recovery_evidence",
        "partial_output",
        "budget_fallback",
    ],
    int,
    int,
    ChatResponse,
]:
    if response is None:
        response = ChatResponse(
            message=ChatMessage(role="assistant", content=""),
            total_tokens=0,
            output_tokens=0,
        )
    output = response.message.content
    paused_for_consent = bool(
        decision is not None and decision.action == "pause_for_consent"
    )
    partial = bool(decision is not None and decision.action == "return_partial")
    partial_reason = decision.reason or "return_partial" if decision is not None else ""
    recovered_web_search_intents: list[Any] = []
    recovered_web_search_output = ""
    if partial and should_recover_web_search_evidence_from_partial(partial_reason):
        recovered_web_search_intents, recovered_web_search_output = (
            RecoveryManager.recover_web_search_output_from_evidence(
                list(state.intent_plan or []),
                tool_results=tool_results,
                reason="partial_exit_recovery",
            )
        )
    promote_web_search_partial_to_completed = bool(recovered_web_search_output)
    budgeted_web_research_completion_mode: Literal[
        "none",
        "keep_visible_output",
        "replace_with_tool_evidence",
    ] = (
        should_complete_from_budgeted_web_research_evidence(
            state=state,
            response=response,
            tool_results=tool_results,
            reason=decision.reason or "return_partial",
        )
        if partial and decision is not None
        else "none"
    )
    promote_budget_partial_to_completed = bool(
        partial
        and decision is not None
        and budgeted_web_research_completion_mode != "none"
    )
    replace_budgeted_web_research_output = (
        budgeted_web_research_completion_mode == "replace_with_tool_evidence"
    )
    skip_budget_synthesis_for_synthetic_fetch = bool(
        replace_budgeted_web_research_output
        and state.preparation_diagnostics.get(
            "synthetic_required_fetch_url_after_search_success"
        )
        and has_completed_fetch_url_body_evidence(
            state=state,
            tool_results=tool_results,
        )
    )
    if decision is not None and (
        decision.action == "pause_for_consent"
        or (
            decision.action == "return_partial"
            and not promote_budget_partial_to_completed
            and not promote_web_search_partial_to_completed
        )
    ):
        recovery_event = {
            "kind": (
                "partial_output"
                if decision.action == "return_partial"
                else "pause_for_consent"
            ),
            "action": decision.action,
            "target_intent_id": decision.target_intent_id,
            "reason": decision.reason,
        }
        state.recovery_events.append(recovery_event)
        decision.metadata = dict(decision.metadata or {})
        decision.metadata["source_recovery_event_seq"] = len(state.recovery_events)
        state.recovery_history.append(decision)
    completion_reason = "completed"
    final_output_source: Literal[
        "assistant",
        "tool_evidence_completed",
        "recovery_evidence",
        "partial_output",
        "budget_fallback",
    ] = "assistant"
    if (
        not partial
        and not paused_for_consent
        and has_completed_fetch_url_body_evidence(
            state=state,
            tool_results=tool_results,
        )
        and RecoveryManager.should_replace_budgeted_web_research_response(
            response_text=str(output or ""),
            tool_results=tool_results,
        )
    ):
        output = ""
        if response is not None and getattr(response, "message", None) is not None:
            response.message.content = ""
        state.preparation_diagnostics[
            "assistant_preview_replaced_with_fetch_evidence"
        ] = True
    if paused_for_consent:
        state.transition("awaiting_consent")
        completion_reason = decision.reason or "pause_for_consent"
        RecoveryManager.ensure_latest_assistant_pending_consent(
            messages,
            RecoveryManager.pending_consent_payload_from_decision(decision),
        )
    elif promote_web_search_partial_to_completed:
        partial = False
        output = recovered_web_search_output
        state.intent_plan = recovered_web_search_intents
        recovered_provider_failure_kind = str(state.provider_failure_kind or "").strip()
        recovered_provider_events = list(state.provider_events or [])
        state.provider_failure_kind = "none"
        state.provider_events = []
        state.transition("completed")
        state.preparation_diagnostics.update(
            {
                "partial_exit_recovered_from_tool_evidence": True,
                "recovered_partial_exit_reason": partial_reason,
                "recovery_evidence_tool": "web_search",
            }
        )
        if (
            recovered_provider_failure_kind
            and recovered_provider_failure_kind != "none"
        ):
            state.preparation_diagnostics.update(
                {
                    "provider_failure_recovered_from_tool_evidence": True,
                    "recovered_provider_failure_kind": recovered_provider_failure_kind,
                    "recovered_provider_events": recovered_provider_events,
                }
            )
        if response is not None and getattr(response, "message", None) is not None:
            response.message.content = output
        completion_reason = "completed"
        final_output_source = "recovery_evidence"
    elif promote_budget_partial_to_completed:
        partial = False
        state.transition("completed")
        state.preparation_diagnostics["budgeted_web_research_completion_mode"] = (
            budgeted_web_research_completion_mode
        )
        if replace_budgeted_web_research_output and response is not None:
            response.message.content = ""
        if skip_budget_synthesis_for_synthetic_fetch:
            state.preparation_diagnostics[
                "budget_synthesis_skipped_for_synthetic_fetch_url"
            ] = True
        if (
            replace_budgeted_web_research_output
            and tool_results
            and not skip_budget_synthesis_for_synthetic_fetch
        ):
            synthesis_policy = ToolUsePolicy(
                family="none",
                mode="none",
                allowed_tool_names=[],
                retry_on_contract_breach=False,
                reason="budget_exceeded_synthesis",
            )
            emit_round_started_cb(
                state,
                round_kind="budget_exceeded_synthesis",
                policy=synthesis_policy,
                tools=[],
                reason="budget_exceeded_synthesis",
            )
            synthesis_round = await io.call_llm(
                messages=messages,
                tools=None,
                tool_use_policy=synthesis_policy,
                breach_retry_result="budget_exceeded_synthesis",
            )
            synthesis_text = str(
                getattr(
                    getattr(synthesis_round.response, "message", None),
                    "content",
                    "",
                )
                or ""
            ).strip()
            if synthesis_text:
                total_tokens += int(synthesis_round.total_tokens or 0)
                completion_tokens_used += int(
                    synthesis_round.completion_tokens_used or 0
                )
                state.register_completion_tokens(completion_tokens_used)
                if RecoveryManager.should_replace_budgeted_web_research_response(
                    response_text=synthesis_text,
                    tool_results=tool_results,
                ):
                    state.preparation_diagnostics[
                        "budget_synthesis_replaced_with_fetch_evidence"
                    ] = True
                else:
                    output = synthesis_text
                    final_output_source = "assistant"
        if not str(output or "").strip():
            (
                output,
                total_tokens,
                completion_tokens_used,
            ) = await io.finalize_completed_output(
                messages=messages,
                response=response,
                state=state,
                tool_results=tool_results,
                reason=decision.reason or "completed",
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
            )
            if str(output or "").strip():
                if has_completed_fetch_url_body_evidence(
                    state=state,
                    tool_results=tool_results,
                ):
                    final_output_source = "recovery_evidence"
                    state.preparation_diagnostics.update(
                        {
                            "recovered_completed_output_rebuilt_from_tool_evidence": True,
                            "recovery_evidence_tool": "fetch_url",
                        }
                    )
                else:
                    final_output_source = "tool_evidence_completed"
    elif partial:
        state.transition("partial_exit")
        completion_reason = decision.reason or "return_partial"
        had_visible_output = bool(str(output or "").strip())
        output, total_tokens, completion_tokens_used = await io.finalize_partial_output(
            messages=messages,
            response=response,
            state=state,
            tool_results=tool_results,
            reason=completion_reason,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
        )
        if (
            not had_visible_output
            and state.provider_failure_kind == "budget_exit"
            and str(output or "").strip()
        ):
            final_output_source = "budget_fallback"
        else:
            final_output_source = "partial_output"
    elif (
        unaccepted_web_research_reason
        := should_return_partial_for_unaccepted_web_research_evidence(
            state=state,
            tool_results=tool_results,
        )
    ):
        partial = True
        completion_reason = unaccepted_web_research_reason
        final_output_source = "partial_output"
        mark_web_research_intents_failed_for_unaccepted_evidence(
            state,
            reason=completion_reason,
        )
        record_web_research_partial_exit(state, reason=completion_reason)
        state.preparation_diagnostics.update(
            {
                "partial_exit_reason": completion_reason,
                "web_research_evidence_unaccepted": True,
                "untrusted_final_output_fallback_applied": True,
                "stripped_untrusted_final_output": True,
            }
        )
        if latest_auto_fetch_gate_reason(state) == "search_not_successful":
            state.preparation_diagnostics["search_not_successful_untrusted_output"] = (
                True
            )
        output = build_untrusted_final_output_fallback(
            auto_fetch_gate_reason=latest_auto_fetch_gate_reason(state),
            failure_kind=completion_reason,
        )
        if response is not None and getattr(response, "message", None) is not None:
            response.message.content = output
        state.transition("partial_exit")
    else:
        state.transition("completed")
        if not str(output or "").strip() and state.intent_plan:
            (
                output,
                total_tokens,
                completion_tokens_used,
            ) = await io.finalize_completed_output(
                messages=messages,
                response=response,
                state=state,
                tool_results=tool_results,
                reason=completion_reason,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
            )
            if str(output or "").strip():
                if str(
                    state.preparation_diagnostics.get("contract_breach_type") or ""
                ).strip() and not RecoveryManager.has_completed_output_evidence(
                    state.intent_plan,
                    tool_results=tool_results,
                ):
                    final_output_source = "partial_output"
                elif has_completed_fetch_url_body_evidence(
                    state=state,
                    tool_results=tool_results,
                ):
                    final_output_source = "recovery_evidence"
                    state.preparation_diagnostics.update(
                        {
                            "recovered_completed_output_rebuilt_from_tool_evidence": True,
                            "recovery_evidence_tool": "fetch_url",
                        }
                    )
                else:
                    final_output_source = "tool_evidence_completed"

    state.preparation_diagnostics["final_output_source"] = final_output_source
    state.preparation_diagnostics["post_tool_completion_state"] = (
        post_tool_completion_state(
            state=state,
            final_output_source=final_output_source,
            ran_post_tool_follow_up=ran_post_tool_follow_up,
        )
    )
    auto_fetch_gate_reason = latest_auto_fetch_gate_reason(state)
    trusted_final_output = bool(str(output or "").strip()) and (
        is_trusted_assistant_final_output_source(final_output_source)
    )
    if (
        not partial
        and not paused_for_consent
        and not trusted_final_output
        and final_output_source in {"tool_evidence_completed", "budget_fallback"}
    ):
        fallback_output = build_untrusted_final_output_fallback(
            auto_fetch_gate_reason=auto_fetch_gate_reason,
        )
        if auto_fetch_gate_reason == "search_not_successful":
            state.preparation_diagnostics["search_not_successful_untrusted_output"] = (
                True
            )
        state.preparation_diagnostics["stripped_untrusted_final_output"] = True
        state.preparation_diagnostics["untrusted_final_output_fallback_applied"] = True
        output = fallback_output
        final_output_source = "platform_fallback"
        state.preparation_diagnostics["final_output_source"] = final_output_source
        if response is not None and getattr(response, "message", None) is not None:
            response.message.content = fallback_output

    if auto_fetch_gate_reason:
        state.preparation_diagnostics["auto_fetch_gate_reason"] = auto_fetch_gate_reason
    web_research_terminal_contract = latest_web_research_terminal_contract(state)
    if web_research_terminal_contract:
        state.preparation_diagnostics[WEB_RESEARCH_TERMINAL_CONTRACT_KEY] = (
            web_research_terminal_contract
        )

    return (
        str(output or ""),
        partial,
        paused_for_consent,
        completion_reason,
        final_output_source,
        total_tokens,
        completion_tokens_used,
        response,
    )


@dataclass
class _TurnRunLoop:
    """Keep turn-local mutable state inside one private owner during execution."""

    state: ExecutionStateMachine
    io: TurnIOAdapter
    prep: Any
    request: Any
    agent: Any
    messages: list[ChatMessage] = field(init=False)
    turn_start_index: int = field(init=False)
    tools: list[Any] = field(init=False)
    active_policy: ToolUsePolicy | None = field(init=False)
    active_tools: list[Any] = field(init=False)
    intent: Any | None = field(init=False)
    response: ChatResponse | None = field(init=False, default=None)
    tool_results: list[ToolResult] = field(init=False, default_factory=list)
    total_tokens: int = field(init=False, default=0)
    completion_tokens_used: int = field(init=False, default=0)
    decision: RecoveryDecision | None = field(init=False, default=None)
    ran_post_tool_follow_up: bool = field(init=False, default=False)
    platform_web_research_ran: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        self.messages = self.prep.messages
        self.turn_start_index = current_turn_start_index(self.messages)
        self.tools = list(self.prep.tools or [])
        self.active_policy = self.prep.tool_use_policy
        self.active_tools, self.active_policy, self.intent = (
            TurnExecutor._scope_tools_to_active_intent(
                state=self.state,
                tools=self.tools,
                policy=self.active_policy,
                io=self.io,
            )
        )

    @property
    def turn_messages(self) -> list[ChatMessage]:
        return current_turn_messages(
            self.messages,
            start_index=self.turn_start_index,
        )

    def emit_round(self, **kwargs: Any) -> None:
        emit_round_started(self.state, **kwargs)

    def emit_round_started(
        self,
        state: ExecutionStateMachine,
        **kwargs: Any,
    ) -> None:
        emit_round_started(state, **kwargs)

    def _apply_model_round(
        self,
        model_round: ModelRoundResult,
        *,
        replace_totals: bool,
    ) -> None:
        self.response = model_round.response
        total_tokens = int(model_round.total_tokens or 0)
        completion_tokens_used = int(model_round.completion_tokens_used or 0)
        if replace_totals:
            self.total_tokens = total_tokens
            self.completion_tokens_used = completion_tokens_used
        else:
            self.total_tokens += total_tokens
            self.completion_tokens_used += completion_tokens_used
        self.state.register_completion_tokens(self.completion_tokens_used)

    def _register_budget_exit_if_needed(self) -> None:
        budget_exit_reason = self.state.budget_exit_reason()
        if not budget_exit_reason:
            return
        self.state.register_provider_failure(
            kind="budget_exit",
            event={"kind": "budget_exit", "reason": budget_exit_reason},
        )

    def _decide_recovery(self) -> RecoveryDecision | None:
        return RecoveryManager.decide(
            self.state.intent_plan,
            budget=self.state.budget,
            provider_failure_kind=self.state.provider_failure_kind,
        )

    def _apply_cached_shortcircuit(self, intent: Any) -> None:
        cached_result = str(getattr(intent, "cached_result", "") or "").strip()
        intent.status = "completed"
        intent.metadata = dict(getattr(intent, "metadata", {}) or {})
        intent.metadata["cached_shortcircuit_completed"] = True
        self.state.preparation_diagnostics["cached_shortcircuit"] = True
        self.state.preparation_diagnostics["cached_shortcircuit_intent_kind"] = getattr(
            intent, "kind", None
        )
        self.response = ChatResponse(
            message=ChatMessage(role="assistant", content=cached_result),
            total_tokens=0,
            output_tokens=0,
            finish_reason="stop",
            metadata={
                "cached_shortcircuit": True,
                "cached_shortcircuit_intent_kind": getattr(intent, "kind", None),
            },
        )

    async def _run_platform_web_research_runtime(
        self,
        *,
        intent: Any | None = None,
        tools: list[Any] | None = None,
    ) -> bool:
        active_intent = intent if intent is not None else self.intent
        active_tools = list(
            tools if tools is not None else self.prep.all_tools or self.tools
        )
        if not should_run_platform_web_research_runtime(
            intent=active_intent,
            tools=active_tools,
        ):
            return False

        query = _web_research_query(active_intent, self.messages)
        context = _web_research_execution_context(
            request=self.request,
            agent=self.agent,
        )
        runtime = WebResearchRuntime(
            search_provider=BuiltinWebSearchProvider(context=context),
            fetch_provider=BuiltinFetchUrlProvider(),
        )
        self.emit_round(
            round_kind="web_research_runtime",
            policy=ToolUsePolicy(
                family="web_research",
                mode="required",
                allowed_tool_names=["web_search", "fetch_url"],
                retry_on_contract_breach=False,
                reason="platform_web_research_runtime",
            ),
            tools=self.io.restrict_tools_to_names(
                active_tools,
                ["web_search", "fetch_url"],
            ),
            intent=active_intent,
            reason="platform_web_research_runtime",
        )
        evidence = await runtime.run(
            query,
            WebResearchRunOptions(
                max_search_results=5,
                max_fetches=3,
                require_fetch=True,
                provider_disable_reason="optional_provider_skipped:builtin_default",
                diagnostics={
                    "intent_id": getattr(active_intent, "intent_id", None),
                    "conversation_id": getattr(self.request, "conversation_id", None),
                },
            ),
        )
        self.tool_results = tool_results_from_web_research_evidence(evidence)
        if self.state.budget is not None:
            self.state.register_tool_round()
        self.state.provider_events.append(
            {
                "kind": "web_research_runtime",
                "pipeline_id": evidence.diagnostics.pipeline_id,
                "search_provider": evidence.search_provider,
                "fetch_provider": evidence.fetch_provider,
                "evidence_status": evidence.status,
                "answer_source": evidence.diagnostics.answer_source,
            }
        )
        self.state.preparation_diagnostics.update(
            {
                "web_research_evidence": evidence.to_dict(),
                "web_research_diagnostics": evidence.diagnostics.to_dict(),
                "web_research_pipeline_id": evidence.diagnostics.pipeline_id,
                "search_provider": evidence.search_provider,
                "fetch_provider": evidence.fetch_provider,
                "evidence_status": evidence.status,
                "candidate_urls": list(evidence.diagnostics.candidate_urls),
                "fetched_urls": list(evidence.diagnostics.fetched_urls),
                "rejected_urls": list(evidence.diagnostics.rejected_urls),
                "evidence_quality": evidence.answer_quality,
                "answer_source": evidence.diagnostics.answer_source,
                "web_research_failure_kind": evidence.failure_kind,
                "web_research_relevance_profile": (
                    evidence.diagnostics.relevance_profile
                ),
                "web_research_relevance_rejection_count": (
                    evidence.diagnostics.relevance_rejection_count
                ),
                "web_research_provider_disable_reason": (
                    evidence.diagnostics.provider_disable_reason
                ),
            }
        )
        self.state.register_tool_results(
            messages=self.messages,
            turn_messages=self.turn_messages,
            tool_results=self.tool_results,
        )
        unaccepted_reason = should_return_partial_for_unaccepted_web_research_evidence(
            state=self.state,
            tool_results=self.tool_results,
        )
        if unaccepted_reason:
            mark_web_research_intents_failed_for_unaccepted_evidence(
                self.state,
                reason=unaccepted_reason,
            )
        self.response = ChatResponse(
            message=ChatMessage(role="assistant", content=""),
            total_tokens=0,
            output_tokens=0,
            finish_reason="stop",
            metadata={"web_research_evidence": evidence.to_dict()},
        )
        self.platform_web_research_ran = True
        return True

    async def _run_missing_args_clarification(self, intent: Any) -> None:
        missing_args = intent_missing_args(intent)
        decision = RecoveryDecision(
            action="retry_intent",
            target_intent_id=getattr(intent, "intent_id", None),
            retry_family=getattr(intent, "family", None),
            completed_intent_ids=[
                item.intent_id
                for item in self.state.intent_plan
                if item.status == "completed"
            ],
            unfinished_intent_ids=[
                item.intent_id
                for item in self.state.intent_plan
                if item.status not in {"completed", "skipped"}
            ],
            reason="missing_args_clarification",
            metadata={"missing_args": missing_args},
        )
        self.state.register_retry(decision)
        self.messages.append(
            RecoveryManager.build_missing_args_clarification_message(
                decision=decision,
                intents=self.state.intent_plan,
                missing_args=missing_args,
            )
        )
        clarification_policy = ToolUsePolicy(
            family="none",
            mode="none",
            allowed_tool_names=[],
            retry_on_contract_breach=False,
            reason="missing_args_clarification",
        )
        self.emit_round(
            round_kind="intent_retry",
            policy=clarification_policy,
            tools=[],
            intent=intent,
            reason="missing_args_clarification",
        )
        clarification_round = await self.io.call_llm(
            messages=self.messages,
            tools=None,
            tool_use_policy=clarification_policy,
            breach_retry_result="intent_retry",
        )
        self._apply_model_round(clarification_round, replace_totals=False)
        intent.status = "completed"
        intent.metadata = dict(getattr(intent, "metadata", {}) or {})
        intent.metadata["clarification_requested"] = True

    async def run(self) -> TurnExecutionResult:
        await self._run_initial_round()
        if not self.platform_web_research_ran:
            await self._run_tool_batch_or_update_intents()
            await self._run_contract_retry_round()
            await self._run_intent_retry_loop()
            await self._maybe_retry_web_research_contract()
            await self._maybe_run_post_tool_follow_up_round()
        return await self._finalize_result()

    async def _run_initial_round(self) -> None:
        initial_budget_exit = self.state.budget_exit_reason()
        if initial_budget_exit:
            self.state.register_provider_failure(
                kind="budget_exit",
                event={"kind": "budget_exit", "reason": initial_budget_exit},
            )
            self.response = ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                total_tokens=0,
                output_tokens=0,
            )
            return

        if intent_requires_clarification(self.intent):
            await self._run_missing_args_clarification(self.intent)
            return

        shortcircuit_intent = cached_shortcircuit_intent(self.state)
        if shortcircuit_intent is not None:
            self._apply_cached_shortcircuit(shortcircuit_intent)
            return

        if await self._run_platform_web_research_runtime():
            return

        model_round = await self.io.call_llm(
            messages=self.messages,
            tools=self.active_tools or None,
            tool_use_policy=self.active_policy,
        )
        self._apply_model_round(model_round, replace_totals=True)

    async def _run_tool_batch_or_update_intents(self) -> None:
        (
            self.response,
            self.tool_results,
            self.total_tokens,
            self.completion_tokens_used,
        ) = await run_tool_batch_or_update_intents(
            state=self.state,
            io=self.io,
            intent=self.intent,
            response=self.response,
            tools=self.active_tools,
            all_tools=self.prep.all_tools or self.tools,
            messages=self.messages,
            turn_messages=self.turn_messages,
            tool_use_policy=self.active_policy,
            input_variables=self.request.input_variables,
            total_tokens=self.total_tokens,
            completion_tokens_used=self.completion_tokens_used,
        )

    async def _run_contract_retry_round(self) -> None:
        (
            self.response,
            self.tool_results,
            self.total_tokens,
            self.completion_tokens_used,
            self.active_policy,
            self.active_tools,
        ) = await run_contract_retry_round(
            state=self.state,
            io=self.io,
            agent=self.agent,
            request=self.request,
            prep=self.prep,
            messages=self.messages,
            turn_messages=self.turn_messages,
            response=self.response,
            active_policy=self.active_policy,
            active_intent=self.intent,
            active_tools=self.active_tools,
            tools=self.tools,
            tool_results=self.tool_results,
            total_tokens=self.total_tokens,
            completion_tokens_used=self.completion_tokens_used,
            emit_round_started=self.emit_round_started,
        )

    async def _run_intent_retry_loop(self) -> None:
        self._register_budget_exit_if_needed()
        self.decision = self._decide_recovery()
        while self.decision is not None and self.decision.action == "retry_intent":
            decision = self.decision
            retry_intent = next(
                (
                    intent
                    for intent in self.state.intent_plan
                    if intent.intent_id == decision.target_intent_id
                ),
                None,
            )
            if intent_requires_clarification(retry_intent):
                await self._run_missing_args_clarification(retry_intent)
                self.decision = self._decide_recovery()
                continue

            self.state.register_retry(decision)
            self.messages.append(
                RecoveryManager.build_recovery_message(
                    decision=decision,
                    intents=self.state.intent_plan,
                )
            )
            retry_tools = self.io.restrict_tools_to_names(
                self.prep.all_tools or self.tools,
                decision.allowed_tool_names,
            )
            retry_policy = ToolUsePolicy(
                family=decision.retry_family or self.prep.tool_use_policy.family,
                mode="required",
                allowed_tool_names=decision.allowed_tool_names
                or [tool.name for tool in retry_tools],
                retry_on_contract_breach=False,
                reason=intent_retry_policy_reason(decision, retry_intent),
            )
            self.emit_round(
                round_kind="intent_retry",
                policy=retry_policy,
                tools=retry_tools,
                intent=retry_intent,
                reason=retry_policy.reason or "intent_retry",
            )
            if retry_policy.mode == "required" and retry_tools:
                self.io.log_tool_contract_diagnostics(
                    agent=self.agent,
                    messages=self.messages,
                    response=self.response,
                    tools=retry_tools,
                    policy=retry_policy,
                    conversation_id=self.request.conversation_id,
                    breach_type=retry_policy.reason or "intent_retry",
                    retry_result="retrying",
                    continuation=self.prep.continuation_context,
                )
            if await self._run_platform_web_research_runtime(
                intent=retry_intent,
                tools=retry_tools,
            ):
                self.decision = self._decide_recovery()
                continue
            retry_round = await self.io.call_llm(
                messages=self.messages,
                tools=retry_tools or None,
                tool_use_policy=retry_policy,
                breach_retry_result="intent_retry",
            )
            self._apply_model_round(retry_round, replace_totals=False)
            if getattr(self.response, "tool_calls", None) and retry_tools:
                (
                    self.response,
                    extra_tool_results,
                    self.total_tokens,
                    self.completion_tokens_used,
                ) = await execute_tool_batch(
                    state=self.state,
                    io=self.io,
                    response=self.response,
                    tools=retry_tools,
                    all_tools=self.prep.all_tools or self.tools,
                    messages=self.messages,
                    turn_messages=self.turn_messages,
                    tool_use_policy=retry_policy,
                    input_variables=self.request.input_variables,
                    total_tokens=self.total_tokens,
                    completion_tokens_used=self.completion_tokens_used,
                )
                self.tool_results.extend(extra_tool_results)
            elif retry_tools:
                fallback_response = build_required_fetch_url_fallback_response(
                    intent=retry_intent,
                    response=self.response,
                    tools=retry_tools,
                    total_tokens=self.total_tokens,
                    completion_tokens_used=self.completion_tokens_used,
                )
                if fallback_response is None:
                    fallback_response = build_shortcircuit_fallback_response(
                        intent=retry_intent,
                        response=self.response,
                        tools=retry_tools,
                        total_tokens=self.total_tokens,
                        completion_tokens_used=self.completion_tokens_used,
                    )
                if fallback_response is not None:
                    record_synthetic_required_fetch_url(
                        self.state,
                        fallback_response,
                    )
                    (
                        self.response,
                        extra_tool_results,
                        self.total_tokens,
                        self.completion_tokens_used,
                    ) = await execute_tool_batch(
                        state=self.state,
                        io=self.io,
                        response=fallback_response,
                        tools=retry_tools,
                        all_tools=self.prep.all_tools or self.tools,
                        messages=self.messages,
                        turn_messages=self.turn_messages,
                        tool_use_policy=retry_policy,
                        input_variables=self.request.input_variables,
                        total_tokens=self.total_tokens,
                        completion_tokens_used=self.completion_tokens_used,
                    )
                    self.tool_results.extend(extra_tool_results)
                    self.decision = self._decide_recovery()
                    continue
            if self.state.intent_plan and not getattr(
                self.response, "tool_calls", None
            ):
                self.state.intent_plan = RecoveryManager.update_intent_statuses(
                    self.state.intent_plan,
                    messages=self.messages,
                    turn_messages=self.turn_messages,
                    tool_results=[],
                )
                if (
                    retry_policy.mode == "required"
                    and retry_tools
                    and self.response is not None
                ):
                    self.io.log_tool_contract_diagnostics(
                        agent=self.agent,
                        messages=self.messages,
                        response=self.response,
                        tools=retry_tools,
                        policy=retry_policy,
                        conversation_id=self.request.conversation_id,
                        breach_type=decision.reason or "intent_retry",
                        retry_result="failed",
                        continuation=self.prep.continuation_context,
                    )
            self._register_budget_exit_if_needed()
            self.decision = self._decide_recovery()

    async def _maybe_retry_web_research_contract(self) -> None:
        if (
            self.decision is not None
            or self.response is None
            or not self.tool_results
            or bool(getattr(self.response, "tool_calls", None))
        ):
            return

        (
            self.response,
            self.total_tokens,
            self.completion_tokens_used,
            retried_web_research,
            self.active_policy,
        ) = await maybe_retry_web_research_contract(
            state=self.state,
            io=self.io,
            agent=self.agent,
            request=self.request,
            prep=self.prep,
            messages=self.messages,
            response=self.response,
            active_policy=self.active_policy,
            active_tools=self.active_tools,
            tools=self.tools,
            total_tokens=self.total_tokens,
            completion_tokens_used=self.completion_tokens_used,
            emit_round_started=self.emit_round_started,
        )
        if retried_web_research:
            self.ran_post_tool_follow_up = True

    def _should_run_post_tool_follow_up_round(self) -> bool:
        return bool(
            self.decision is None
            and self.tool_results
            and active_intent(self.state) is None
            and not response_has_visible_content(self.response)
            and not bool(getattr(self.response, "tool_calls", None))
            and "web_research" not in completed_tool_intent_families(self.state)
        )

    async def _maybe_run_post_tool_follow_up_round(self) -> None:
        if not self._should_run_post_tool_follow_up_round():
            return

        self.ran_post_tool_follow_up = True
        follow_up_policy = ToolUsePolicy(
            family="none",
            mode="none",
            allowed_tool_names=[],
            retry_on_contract_breach=False,
            reason="post_tool_follow_up",
        )
        self.emit_round(
            round_kind="normal_follow_up_round",
            policy=follow_up_policy,
            tools=[],
            reason="post_tool_follow_up",
        )
        follow_up_round = await self.io.call_llm(
            messages=self.messages,
            tools=None,
            tool_use_policy=follow_up_policy,
            breach_retry_result="normal_follow_up_round",
        )
        self._apply_model_round(follow_up_round, replace_totals=False)

    async def _finalize_result(self) -> TurnExecutionResult:
        (
            output,
            partial,
            paused_for_consent,
            completion_reason,
            final_output_source,
            self.total_tokens,
            self.completion_tokens_used,
            self.response,
        ) = await finalize_turn_execution(
            state=self.state,
            io=self.io,
            messages=self.messages,
            response=self.response,
            decision=self.decision,
            tool_results=self.tool_results,
            total_tokens=self.total_tokens,
            completion_tokens_used=self.completion_tokens_used,
            ran_post_tool_follow_up=self.ran_post_tool_follow_up,
            emit_round_started_cb=self.emit_round_started,
        )

        return TurnExecutionResult(
            output=str(output or ""),
            total_tokens=int(self.total_tokens or 0),
            completion_tokens_used=int(self.completion_tokens_used or 0),
            tool_results=self.tool_results,
            response=self.response,
            partial=partial,
            paused_for_consent=paused_for_consent,
            completion_reason=completion_reason,
            final_output_source=final_output_source,
            action_buttons=None,
        )


class TurnExecutor:
    """State-machine-driven execution entrypoint shared by sync/stream paths."""

    @staticmethod
    def _scope_tools_to_active_intent(
        *,
        state: ExecutionStateMachine,
        tools: list[Any],
        policy: ToolUsePolicy | None,
        io: TurnIOAdapter,
    ) -> tuple[list[Any], ToolUsePolicy | None, Any | None]:
        intent = active_intent(state)
        if intent is None or policy is None:
            return list(tools), policy, intent

        allowed_tool_names = list(
            intent.allowed_tool_names or policy.allowed_tool_names or []
        )
        if not allowed_tool_names:
            return list(tools), policy, intent

        scoped_tools = list(io.restrict_tools_to_names(list(tools), allowed_tool_names))
        if not scoped_tools:
            return list(tools), policy, intent

        scoped_tool_names = [tool.name for tool in scoped_tools]
        if scoped_tool_names == list(policy.allowed_tool_names or []):
            return scoped_tools, policy, intent

        return (
            scoped_tools,
            ToolUsePolicy(
                family=intent.family or policy.family,
                mode=policy.mode,
                allowed_tool_names=scoped_tool_names,
                retry_on_contract_breach=policy.retry_on_contract_breach,
                reason=policy.reason or f"intent:{intent.kind}",
            ),
            intent,
        )

    @staticmethod
    async def run(
        *,
        state: ExecutionStateMachine,
        io: TurnIOAdapter,
        prep: Any,
        request: Any,
        agent: Any,
    ) -> TurnExecutionResult:
        """Run one turn using a shared orchestration loop (sync path ready)."""
        return await _TurnRunLoop(
            state=state,
            io=io,
            prep=prep,
            request=request,
            agent=agent,
        ).run()


__all__ = [
    "ModelRoundResult",
    "RecoveryManager",
    "ToolBatchResult",
    "TurnExecutionResult",
    "TurnIOAdapter",
    "TurnExecutor",
    "assistant_tool_round_count",
    "finalize_turn_execution",
    "register_tool_round_delta",
]
