"""Tool-result helpers extracted from RecoveryManager."""

from __future__ import annotations

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage
from app.core.i18n import _

from .recovery_result_normalizer import RecoveryResultNormalizer
from .types import IntentPlan

DEFAULT_RECOVERY_RESULT_MAX_LENGTH = 500


def intent_recovery_result_max_length(intent: IntentPlan) -> int:
    _ = intent
    return DEFAULT_RECOVERY_RESULT_MAX_LENGTH


def successful_tool_names(
    messages: list[ChatMessage],
    tool_results: list[ToolResult] | None = None,
) -> list[str]:
    names: list[str] = []
    for result in tool_results or []:
        name = str(result.name or "").strip()
        if result.success and name and name not in names:
            names.append(name)
    for message in messages:
        if message.role != "assistant" or not message.tool_calls:
            continue
        for tool_call in message.tool_calls:
            if tool_call.get("success") is not True:
                continue
            func = tool_call.get("function") or {}
            name = str(func.get("name") or tool_call.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
    return names


def tool_attempted(
    messages: list[ChatMessage],
    tool_name: str,
    tool_results: list[ToolResult] | None = None,
) -> bool:
    normalized_name = str(tool_name or "").strip()
    if not normalized_name:
        return False
    for result in tool_results or []:
        if str(result.name or "").strip() == normalized_name:
            return True
    for message in messages:
        if message.role != "assistant" or not message.tool_calls:
            continue
        for tool_call in message.tool_calls:
            func = tool_call.get("function") or {}
            name = str(func.get("name") or tool_call.get("name") or "").strip()
            if name == normalized_name:
                return True
    return False


def latest_successful_tool_result(
    tool_name: str,
    tool_results: list[ToolResult] | None = None,
) -> ToolResult | None:
    normalized_name = str(tool_name or "").strip()
    if not normalized_name:
        return None
    for result in reversed(tool_results or []):
        if result.success and str(result.name or "").strip() == normalized_name:
            return result
    return None


def intent_result_from_tool_results(
    intent: IntentPlan,
    tool_results: list[ToolResult] | None = None,
) -> str | None:
    if not tool_results:
        return None
    candidate_tool_names: list[str] = []
    prioritized_tool_names = list(intent.completed_by_tool_names or [])
    if not prioritized_tool_names:
        prioritized_tool_names = list(intent.completion_signals or []) + list(
            intent.allowed_tool_names or []
        )
    for tool_name in prioritized_tool_names:
        normalized_name = str(tool_name or "").strip()
        if normalized_name and normalized_name not in candidate_tool_names:
            candidate_tool_names.append(normalized_name)
    if not candidate_tool_names:
        return None

    normalized_results: list[str] = []
    for name in candidate_tool_names:
        for result in tool_results:
            if not result.success or str(result.name or "").strip() != name:
                continue
            for candidate in (
                result.summary_payload,
                result.summary,
                result.output or result.error,
            ):
                normalized = RecoveryResultNormalizer._normalize_cached_result(
                    candidate
                )
                if normalized:
                    if (
                        str(intent.kind or "").strip() == "time_query"
                        and name == "get_current_time"
                        and not normalized.startswith("现在是")
                    ):
                        normalized = _("现在是 {time}。").format(time=normalized)
                    if normalized not in normalized_results:
                        normalized_results.append(normalized)
                    break
    if not normalized_results:
        return None
    return "；".join(normalized_results[:2])


__all__ = [
    "intent_recovery_result_max_length",
    "intent_result_from_tool_results",
    "latest_successful_tool_result",
    "successful_tool_names",
    "tool_attempted",
]
