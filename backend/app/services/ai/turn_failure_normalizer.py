"""Shared turn-failure normalization helpers for diagnostics/read-model parity."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

_ERROR_TERMINATION_REASONS = frozenset(
    {
        "error",
        "failed",
        "provider_timeout",
        "provider_unavailable",
        "provider_error",
        "provider_failure_after_partial_progress",
        "tool_error",
        "tool_round_failed",
        "stream_execution_error",
        "terminal_failure",
    }
)
_BUDGET_TERMINATION_REASONS = frozenset(
    {
        "budget_exit",
        "elapsed_budget_exceeded",
        "completion_budget_exceeded",
        "tool_round_budget_exceeded",
        "retry_budget_exhausted",
        "prompt_budget_exceeded",
        "tool_result_budget_exceeded",
        "candidate_tool_budget_exceeded",
    }
)
_NO_FAILURE_KINDS = frozenset({"none"})
_TRUSTED_FINAL_OUTPUT_SOURCES = frozenset({"assistant", "recovery_evidence"})
_INTERRUPTION_TERMINATION_REASONS = frozenset({"interrupted", "partial"})
_GENERIC_FAILURE_TERMINATION_REASONS = frozenset(
    {"error", "failed", "terminal_failure"}
)
_FAILURE_KIND_SIGNAL_ALIASES = {
    "provider_connection_error": "provider_unavailable",
    "provider_connection": "provider_unavailable",
    "provider_connection_error_error": "provider_unavailable",
    "provider_timeout_error": "provider_timeout",
    "provider_rate_limit_error": "provider_rate_limit",
    "provider_bad_response_error": "provider_bad_response",
}
_FAILURE_TERMINATION_BY_KIND = {
    "provider_timeout": "provider_timeout",
    "provider_unavailable": "provider_unavailable",
    "provider_http_5xx": "provider_error",
    "provider_gateway_error": "provider_error",
    "provider_bad_response": "provider_error",
    "provider_rate_limit": "provider_error",
    "tool_timeout": "tool_error",
    "tool_execution_error": "tool_error",
    "server_interrupt": "interrupted",
}
def _as_text(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered in {"none", "null", "undefined"}:
        return None
    return text


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_failure_kind(value: Any) -> str | None:
    kind = _as_text(value)
    if not kind:
        return None
    if kind.lower() in _NO_FAILURE_KINDS:
        return None
    return kind


def _normalize_signal_token(value: Any) -> str | None:
    text = _as_text(value)
    if not text:
        return None
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", text)
    snake = snake.replace("-", "_").replace(" ", "_").replace(".", "_")
    snake = re.sub(r"_+", "_", snake).strip("_").lower()
    return snake or None


def _infer_provider_error_kind_from_message(error_message: Any) -> str | None:
    lowered = (_as_text(error_message) or "").lower()
    if not lowered:
        return None

    if any(
        token in lowered
        for token in (
            "bad gateway",
            "gateway timeout",
            "service unavailable",
            "server error",
            "server_error",
            "服务端错误",
            "服务暂不可用",
            "服务器内部错误",
            "502",
            "503",
            "504",
        )
    ):
        return "provider_http_5xx"
    if "connection error" in lowered or "连接错误" in lowered or "连接失败" in lowered:
        return "provider_unavailable"
    if "timed out" in lowered or "timeout" in lowered or "超时" in lowered:
        return "provider_timeout"
    return "provider_gateway_error"


def infer_failure_kind_from_diagnostics(
    diagnostics: Mapping[str, Any] | None,
) -> str | None:
    payload = _as_dict(diagnostics)
    if not payload:
        return None

    turn_record = _as_dict(payload.get("turn_record"))
    turn_record_metadata = _as_dict(turn_record.get("metadata"))
    failures = _as_dict(payload.get("failures"))
    turn_record_failures = _as_dict(turn_record.get("failures"))

    candidates: list[Any] = [
        payload.get("failure_kind"),
        payload.get("provider_failure_kind"),
        payload.get("error_type"),
        failures.get("failure_kind"),
        turn_record.get("failure_kind"),
        turn_record.get("provider_failure_kind"),
        turn_record_failures.get("failure_kind"),
        turn_record_metadata.get("failure_kind"),
        turn_record_metadata.get("provider_failure_kind"),
        turn_record_metadata.get("protocol_fallback_blocked_reason"),
        turn_record_metadata.get("stream_failure_error_type"),
        turn_record_metadata.get("stream_failure_reason"),
    ]

    for provider_events in (
        payload.get("provider_events"),
        failures.get("provider_events"),
        turn_record.get("provider_events"),
        turn_record_failures.get("provider_events"),
    ):
        if not isinstance(provider_events, list):
            continue
        for item in provider_events:
            event = _as_dict(item)
            candidates.extend(
                [
                    event.get("kind"),
                    event.get("error_type"),
                ]
            )

    saw_generic_provider_error = False
    for candidate in candidates:
        signal_token = _normalize_signal_token(candidate)
        if signal_token == "provider_error":
            saw_generic_provider_error = True
            continue
        if signal_token and signal_token in _FAILURE_KIND_SIGNAL_ALIASES:
            return _FAILURE_KIND_SIGNAL_ALIASES[signal_token]
        normalized_kind = normalize_failure_kind(candidate)
        if normalized_kind:
            return normalized_kind

    error_message_parts = [
        payload.get("error_message"),
        payload.get("error"),
        _as_dict(payload.get("response")).get("error"),
        failures.get("error_message"),
        turn_record_failures.get("error_message"),
        turn_record_metadata.get("error_message"),
        turn_record_metadata.get("stream_failure_reason"),
    ]
    inferred_provider_error_kind = _infer_provider_error_kind_from_message(
        " ".join(
            part for part in (_as_text(item) for item in error_message_parts) if part
        )
    )
    if saw_generic_provider_error and inferred_provider_error_kind:
        return inferred_provider_error_kind

    lowered_error_message = (_as_text(payload.get("error_message")) or "").lower()
    if "connection error" in lowered_error_message:
        return "provider_unavailable"
    if "timed out" in lowered_error_message or "timeout" in lowered_error_message:
        return "provider_timeout"
    if saw_generic_provider_error:
        return "provider_gateway_error"
    return None


def normalize_failure_termination_reason(
    *,
    termination_reason: Any,
    failure_kind: Any,
    budget_exit_reason: Any = None,
) -> str | None:
    reason = _as_text(termination_reason)
    normalized_reason = (reason or "").strip().lower()
    normalized_budget_exit_reason = _as_text(budget_exit_reason)
    if normalized_budget_exit_reason:
        return normalized_budget_exit_reason

    normalized_failure_kind = infer_failure_kind_from_diagnostics(
        {"failure_kind": failure_kind}
    ) or normalize_failure_kind(failure_kind)
    mapped_failure_reason = (
        _FAILURE_TERMINATION_BY_KIND.get(normalized_failure_kind, reason)
        if normalized_failure_kind
        else None
    )
    if normalized_failure_kind and normalized_reason in _INTERRUPTION_TERMINATION_REASONS:
        return mapped_failure_reason
    if reason and normalized_reason not in _GENERIC_FAILURE_TERMINATION_REASONS:
        return reason
    if mapped_failure_reason:
        return mapped_failure_reason
    return reason


def normalize_turn_outcome(value: Any) -> str | None:
    token = (_as_text(value) or "").lower()
    if not token:
        return None
    if token in {"failed", "failure", "error"}:
        return "failed"
    if token in {"partial", "interrupted"}:
        return "partial"
    if token in {"success", "completed", "ok"}:
        return "success"
    return token


def is_trusted_final_output_source(value: Any) -> bool:
    source = (_as_text(value) or "").lower()
    if not source:
        return True
    return source in _TRUSTED_FINAL_OUTPUT_SOURCES


def derive_completed_tool_names(intent_plan: Any) -> list[str]:
    if not isinstance(intent_plan, list):
        return []
    names: list[str] = []
    for item in intent_plan:
        payload = _as_dict(item)
        for raw_name in payload.get("completed_by_tool_names") or []:
            tool_name = _as_text(raw_name)
            if tool_name and tool_name not in names:
                names.append(tool_name)
    return names


def _derive_budget_exit_reason_from_budget_snapshot(
    budget: Mapping[str, Any] | None,
) -> str | None:
    payload = _as_dict(budget)
    if not payload:
        return None
    usage = _as_dict(payload.get("usage"))
    limits = _as_dict(payload.get("limits"))

    prompt_tokens_used = _as_int(usage.get("prompt_tokens_used"))
    max_prompt_tokens = _as_int(limits.get("max_prompt_tokens"))
    if (
        max_prompt_tokens
        and prompt_tokens_used is not None
        and prompt_tokens_used > max_prompt_tokens
    ):
        return "prompt_budget_exceeded"

    completion_tokens_used = _as_int(usage.get("completion_tokens_used"))
    max_completion_tokens = _as_int(limits.get("max_completion_tokens"))
    if (
        max_completion_tokens
        and completion_tokens_used is not None
        and completion_tokens_used > max_completion_tokens
    ):
        return "completion_budget_exceeded"

    tool_rounds_used = _as_int(usage.get("tool_rounds_used"))
    max_tool_rounds = _as_int(limits.get("max_tool_rounds"))
    if (
        max_tool_rounds
        and tool_rounds_used is not None
        and tool_rounds_used > max_tool_rounds
    ):
        return "tool_round_budget_exceeded"

    elapsed_ms_used = _as_int(usage.get("elapsed_ms_used"))
    elapsed_limit_ms = (
        _as_int(usage.get("elapsed_limit_ms"))
        or _as_int(payload.get("elapsed_limit_ms"))
        or _as_int(limits.get("max_elapsed_ms"))
    )
    if (
        elapsed_limit_ms
        and elapsed_ms_used is not None
        and elapsed_ms_used > elapsed_limit_ms
    ):
        return "elapsed_budget_exceeded"
    if bool(usage.get("elapsed_over_limit")):
        return "elapsed_budget_exceeded"
    elapsed_over_limit_ms = _as_int(usage.get("elapsed_over_limit_ms")) or _as_int(
        payload.get("elapsed_over_limit_ms")
    )
    if elapsed_over_limit_ms and elapsed_over_limit_ms > 0:
        return "elapsed_budget_exceeded"

    tool_result_bytes_used = _as_int(usage.get("tool_result_bytes_used"))
    max_tool_result_bytes = _as_int(limits.get("max_tool_result_bytes"))
    if (
        max_tool_result_bytes
        and tool_result_bytes_used is not None
        and tool_result_bytes_used > max_tool_result_bytes
    ):
        return "tool_result_budget_exceeded"

    candidate_tools_count = _as_int(usage.get("candidate_tools_count"))
    max_candidate_tools = _as_int(limits.get("max_candidate_tools"))
    if (
        max_candidate_tools
        and candidate_tools_count is not None
        and candidate_tools_count > max_candidate_tools
    ):
        return "candidate_tool_budget_exceeded"

    return None


def derive_budget_projection(
    *,
    budget: Any,
    budget_status: Any = None,
    budget_exit_reason: Any = None,
    termination_reason: Any = None,
) -> dict[str, Any]:
    budget_payload = _as_dict(budget)
    normalized_budget = dict(budget_payload) if budget_payload else {}
    normalized_status = _as_text(budget_status) or _as_text(
        normalized_budget.get("status")
    )
    normalized_exit_reason = _as_text(budget_exit_reason) or _as_text(
        normalized_budget.get("exit_reason")
    )
    termination_budget_reason = _as_text(termination_reason)
    if termination_budget_reason not in _BUDGET_TERMINATION_REASONS:
        termination_budget_reason = None

    derived_exit_reason = (
        normalized_exit_reason
        or _derive_budget_exit_reason_from_budget_snapshot(normalized_budget)
        or termination_budget_reason
    )
    if derived_exit_reason:
        normalized_status = "exited"
    elif not normalized_status and normalized_budget:
        normalized_status = "ok"

    usage = _as_dict(normalized_budget.get("usage"))
    elapsed_limit_ms = (
        _as_int(usage.get("elapsed_limit_ms"))
        or _as_int(normalized_budget.get("elapsed_limit_ms"))
        or _as_int(_as_dict(normalized_budget.get("limits")).get("max_elapsed_ms"))
    )
    elapsed_ms_used = _as_int(usage.get("elapsed_ms_used"))
    if usage and elapsed_limit_ms is not None:
        usage.setdefault("elapsed_limit_ms", elapsed_limit_ms)
        if elapsed_ms_used is not None:
            elapsed_over_limit_ms = max(0, elapsed_ms_used - elapsed_limit_ms)
            usage.setdefault("elapsed_over_limit_ms", elapsed_over_limit_ms)
            usage.setdefault("elapsed_over_limit", elapsed_over_limit_ms > 0)
        normalized_budget["usage"] = usage
        normalized_budget.setdefault("elapsed_limit_ms", elapsed_limit_ms)
        normalized_budget.setdefault(
            "elapsed_over_limit_ms",
            usage.get("elapsed_over_limit_ms"),
        )
        normalized_budget.setdefault(
            "elapsed_over_limit",
            usage.get("elapsed_over_limit"),
        )

    if normalized_budget:
        if normalized_status:
            normalized_budget["status"] = normalized_status
        if derived_exit_reason:
            normalized_budget["exit_reason"] = derived_exit_reason

    return {
        "budget": normalized_budget,
        "budget_status": normalized_status,
        "budget_exit_reason": derived_exit_reason,
    }


def find_turn_flow_terminal_stage(
    turn_flow: Mapping[str, Any] | None,
) -> dict[str, Any]:
    payload = _as_dict(turn_flow)
    timeline = payload.get("timeline")
    if not isinstance(timeline, list) or not timeline:
        return {}
    for item in reversed(timeline):
        stage = _as_dict(item)
        stage_type = (_as_text(stage.get("type")) or "").lower()
        stage_id = (_as_text(stage.get("id")) or "").lower()
        if stage_type in {"completed", "failed"} or stage_id == "terminal":
            return stage
    return _as_dict(timeline[-1])


def derive_terminal_status(
    *,
    turn_outcome: str | None,
    completion_reason: str | None,
    interrupted: bool,
    failure_kind: str | None,
    final_output_source: Any = None,
) -> str:
    normalized_turn_outcome = normalize_turn_outcome(turn_outcome) or ""
    normalized_completion_reason = (completion_reason or "").strip().lower()
    normalized_failure_kind = normalize_failure_kind(failure_kind)
    non_trusted_final_output_source = bool(
        _as_text(final_output_source)
        and not is_trusted_final_output_source(final_output_source)
    )
    if interrupted:
        return "interrupted"
    if normalized_turn_outcome == "failed":
        return "error"
    if normalized_turn_outcome == "partial" and normalized_failure_kind:
        return "error"
    if normalized_failure_kind:
        return "error"
    if non_trusted_final_output_source:
        return "error"
    if normalized_completion_reason in _ERROR_TERMINATION_REASONS:
        return "error"
    if normalized_completion_reason in _BUDGET_TERMINATION_REASONS:
        return "error"
    return "completed"


def resolve_failure_projection(
    *,
    diagnostics: Mapping[str, Any] | None,
    turn_flow: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _as_dict(diagnostics)
    terminal_stage = find_turn_flow_terminal_stage(turn_flow)
    turn_flow_payload = _as_dict(turn_flow)
    turn_flow_error_surface = _as_dict(turn_flow_payload.get("error_surface"))

    explicit_turn_outcome = normalize_turn_outcome(payload.get("turn_outcome"))
    conversation_outcome = normalize_turn_outcome(payload.get("conversation_outcome"))
    preserve_partial_after_failed_conversation = (
        explicit_turn_outcome == "partial" and conversation_outcome == "failed"
    )
    turn_outcome = conversation_outcome or explicit_turn_outcome
    if preserve_partial_after_failed_conversation:
        # Keep turn-level truth distinct from conversation-level closure: a
        # failed conversation may still end with a partial assistant turn.
        turn_outcome = "partial"
    termination_reason = _as_text(
        payload.get("termination_reason") or payload.get("completion_reason")
    )
    failure_kind = infer_failure_kind_from_diagnostics(payload)
    budget_exit_reason = _as_text(
        payload.get("budget_exit_reason")
        or _as_dict(payload.get("budget")).get("exit_reason")
    )
    final_output_source = _as_text(payload.get("final_output_source"))
    contract_breach_type = _as_text(payload.get("contract_breach_type"))

    turn_flow_completion_reason = _as_text(turn_flow_payload.get("completion_reason"))
    if turn_flow_completion_reason:
        termination_reason = turn_flow_completion_reason

    turn_flow_terminal_stage_type = _as_text(terminal_stage.get("type"))
    turn_flow_terminal_stage_status = _as_text(terminal_stage.get("status"))
    if turn_flow_terminal_stage_status == "error":
        if not preserve_partial_after_failed_conversation:
            turn_outcome = "failed"
        failure_kind = failure_kind or infer_failure_kind_from_diagnostics(
            turn_flow_error_surface
        )
    elif turn_flow_terminal_stage_status == "interrupted":
        turn_outcome = "partial"
    elif turn_flow_terminal_stage_status == "completed" and not turn_outcome:
        turn_outcome = "success"

    termination_reason = (
        normalize_failure_termination_reason(
            termination_reason=termination_reason,
            failure_kind=failure_kind,
            budget_exit_reason=budget_exit_reason,
        )
        or termination_reason
    )
    normalized_termination_reason = (termination_reason or "").strip().lower()
    budget_signal = bool(
        budget_exit_reason
        or normalized_termination_reason in _BUDGET_TERMINATION_REASONS
    )
    has_failure_signal = bool(
        turn_flow_terminal_stage_status in {"error", "interrupted"}
        or turn_outcome in {"failed", "partial"}
        or failure_kind
        or normalized_termination_reason in _ERROR_TERMINATION_REASONS
        or budget_signal
        or contract_breach_type
        or bool(payload.get("assistant_claimed_tool_call_without_tool_event"))
        or bool(payload.get("unfinished_intents"))
    )
    non_trusted_final_output_source = bool(
        final_output_source and not is_trusted_final_output_source(final_output_source)
    )
    if budget_signal and turn_outcome not in {"failed", "partial"}:
        turn_outcome = "failed"
    if non_trusted_final_output_source and not failure_kind:
        failure_kind = "untrusted_final_output_source"
    if non_trusted_final_output_source and turn_outcome not in {"failed", "partial"}:
        turn_outcome = "failed"
    if budget_signal and not failure_kind:
        failure_kind = (
            budget_exit_reason or normalized_termination_reason or "budget_exit"
        )

    return {
        "turn_outcome": turn_outcome,
        "termination_reason": termination_reason,
        "failure_kind": failure_kind,
        "budget_exit_reason": budget_exit_reason,
        "final_output_source": final_output_source,
        "turn_flow_terminal_stage_type": turn_flow_terminal_stage_type,
        "turn_flow_terminal_stage_status": turn_flow_terminal_stage_status,
        "has_failure_signal": has_failure_signal,
        "non_trusted_final_output_source": non_trusted_final_output_source,
        "blocks_success_shortcut": bool(
            has_failure_signal or budget_signal or non_trusted_final_output_source
        ),
    }


__all__ = [
    "derive_completed_tool_names",
    "derive_budget_projection",
    "derive_terminal_status",
    "find_turn_flow_terminal_stage",
    "infer_failure_kind_from_diagnostics",
    "is_trusted_final_output_source",
    "normalize_failure_termination_reason",
    "normalize_failure_kind",
    "normalize_turn_outcome",
    "resolve_failure_projection",
]
