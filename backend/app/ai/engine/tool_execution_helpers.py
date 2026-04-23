"""Shared helpers for tool batch normalization and failure registration."""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolResult
from app.ai.types import ChatResponse

from .failure_classifier import FailureClassifier


def normalize_tool_call_outcome(
    outcome: tuple[Any, ...],
) -> tuple[ChatResponse | None, list[Any], int, int]:
    if len(outcome) == 4:
        response, tool_results, total_tokens, completion_tokens_used = outcome
        return response, tool_results, total_tokens, completion_tokens_used
    if len(outcome) == 3:
        response, tool_results, total_tokens = outcome
        completion_tokens_used = int(
            getattr(response, "output_tokens", None)
            if getattr(response, "output_tokens", None) is not None
            else (total_tokens or 0)
        )
        return response, tool_results, total_tokens, completion_tokens_used
    raise ValueError(
        f"Unexpected tool call outcome shape: expected 3 or 4 items, got {len(outcome)}"
    )


def register_tool_failures(state: Any, tool_results: list[ToolResult]) -> None:
    tool_failure_kind, tool_failure_events = FailureClassifier.classify_tool_results(
        tool_results
    )
    if tool_failure_kind != "none":
        for event in tool_failure_events:
            state.register_provider_failure(kind=tool_failure_kind, event=event)


def synthesize_tool_results_from_calls(
    tool_calls: list[dict[str, Any]] | None,
    *,
    skip_unresolved_interactions: bool = False,
) -> list[ToolResult]:
    synthesized: list[ToolResult] = []
    for index, tool_call in enumerate(tool_calls or []):
        if skip_unresolved_interactions:
            pending_consent = tool_call.get("pending_consent")
            if isinstance(pending_consent, dict) and not pending_consent.get("resolved"):
                continue
            pending_confirmation = tool_call.get("pending_confirmation")
            if isinstance(pending_confirmation, dict) and not pending_confirmation.get(
                "resolved"
            ):
                continue
        function_block = tool_call.get("function") or {}
        tool_name = str(function_block.get("name") or tool_call.get("name") or "").strip()
        if not tool_name:
            continue
        tool_call_id = str(tool_call.get("id") or f"synthetic_tool_call_{index}")
        synthesized.append(
            ToolResult(
                tool_call_id=tool_call_id,
                name=tool_name,
                success=True,
            )
        )
    return synthesized


def recover_tool_results_from_messages(
    messages: list[Any] | None,
    *,
    start_index: int = 0,
    skip_unresolved_interactions: bool = False,
) -> list[ToolResult]:
    tool_output_by_id: dict[str, str] = {}
    relevant_messages = list(messages or [])[max(0, int(start_index or 0)) :]

    for message in relevant_messages:
        role = (
            str(message.get("role") or "").strip()
            if isinstance(message, dict)
            else str(getattr(message, "role", "") or "").strip()
        )
        if role != "tool":
            continue
        tool_call_id = (
            str(message.get("tool_call_id") or "").strip()
            if isinstance(message, dict)
            else str(getattr(message, "tool_call_id", "") or "").strip()
        )
        if not tool_call_id:
            continue
        content = (
            str(message.get("content") or "")
            if isinstance(message, dict)
            else str(getattr(message, "content", "") or "")
        )
        tool_output_by_id[tool_call_id] = content

    recovered: dict[str, ToolResult] = {}
    synthetic_index = 0
    for message in relevant_messages:
        role = (
            str(message.get("role") or "").strip()
            if isinstance(message, dict)
            else str(getattr(message, "role", "") or "").strip()
        )
        if role != "assistant":
            continue
        raw_tool_calls = (
            message.get("tool_calls")
            if isinstance(message, dict)
            else getattr(message, "tool_calls", None)
        )
        for tool_call in raw_tool_calls or []:
            if not isinstance(tool_call, dict):
                continue
            if skip_unresolved_interactions:
                pending_consent = tool_call.get("pending_consent")
                if isinstance(pending_consent, dict) and not pending_consent.get(
                    "resolved"
                ):
                    continue
                pending_confirmation = tool_call.get("pending_confirmation")
                if isinstance(pending_confirmation, dict) and not pending_confirmation.get(
                    "resolved"
                ):
                    continue
            function_block = tool_call.get("function") or {}
            tool_name = str(
                function_block.get("name") or tool_call.get("name") or ""
            ).strip()
            if not tool_name:
                continue
            tool_call_id = str(
                tool_call.get("id") or f"recovered_tool_call_{synthetic_index}"
            ).strip()
            synthetic_index += 1
            content = tool_output_by_id.get(tool_call_id, "")
            raw_success = tool_call.get("success")
            success = (
                bool(raw_success)
                if raw_success is not None
                else bool(content) and not str(tool_call.get("error_type") or "").strip()
            )
            recovered[tool_call_id] = ToolResult(
                tool_call_id=tool_call_id,
                name=tool_name,
                success=success,
                output=content if success else "",
                error="" if success else (content or str(tool_call.get("summary") or "").strip()),
                duration_ms=int(tool_call.get("duration_ms") or 0),
                display_name=(
                    str(tool_call.get("display_name") or "").strip() or None
                ),
                summary=str(tool_call.get("summary") or "").strip() or None,
                result_link=str(tool_call.get("result_link") or "").strip() or None,
                error_type=str(tool_call.get("error_type") or "").strip(),
                summary_payload=(
                    dict(tool_call.get("summary_payload") or {})
                    if isinstance(tool_call.get("summary_payload"), dict)
                    else None
                ),
            )
    return list(recovered.values())
