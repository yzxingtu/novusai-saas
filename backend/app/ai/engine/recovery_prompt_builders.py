"""Recovery prompt and partial-output builders."""

from __future__ import annotations

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage
from app.core.i18n import _

from .recovery_result_normalizer import RecoveryResultNormalizer
from .recovery_tool_result_helpers import intent_result_from_tool_results
from .types import IntentPlan, ProviderFailureKind, RecoveryDecision

_BUDGET_EXIT_REASONS: frozenset[str] = frozenset(
    {
        "prompt_budget_exceeded",
        "completion_budget_exceeded",
        "tool_round_budget_exceeded",
        "elapsed_budget_exceeded",
        "tool_result_budget_exceeded",
        "candidate_tool_budget_exceeded",
    }
)
_TERMINAL_FAILURE_KINDS: frozenset[ProviderFailureKind] = frozenset(
    {
        "provider_unavailable",
        "provider_http_5xx",
        "provider_bad_response",
        "server_interrupt",
    }
)


def is_budget_exit_reason(reason: str) -> bool:
    return reason in _BUDGET_EXIT_REASONS


def is_terminal_failure_kind(kind: ProviderFailureKind) -> bool:
    return kind == "budget_exit" or kind in _TERMINAL_FAILURE_KINDS


def _collect_completed_output_parts(
    intents: list[IntentPlan],
    *,
    tool_results: list[ToolResult] | None = None,
    intent_results: dict[str, str] | None = None,
) -> tuple[list[str], list[str]]:
    completed_results: list[str] = []
    completed_labels: list[str] = []
    for intent in intents:
        if intent.status != "completed":
            continue
        intent_result = RecoveryResultNormalizer._intent_cached_result(
            intent,
            intent_results=intent_results,
        )
        if not intent_result:
            intent_result = intent_result_from_tool_results(intent, tool_results)
        if intent_result:
            if intent_result not in completed_results:
                completed_results.append(intent_result)
            continue
        display_label = str(intent.user_visible_label or "").strip()
        if display_label and display_label not in completed_labels:
            completed_labels.append(display_label)
    return completed_results, completed_labels


def _should_surface_unfinished_partial_result(
    intent: IntentPlan,
    *,
    provider_failure_kind: ProviderFailureKind,
) -> bool:
    normalized_family = str(intent.family or "").strip().lower()
    if provider_failure_kind == "none":
        return True
    if normalized_family == "web_research":
        return False
    return not is_terminal_failure_kind(provider_failure_kind)


def build_recovery_message(
    *,
    decision: RecoveryDecision,
    intents: list[IntentPlan],
) -> ChatMessage:
    completed = [
        intent.user_visible_label
        for intent in intents
        if intent.intent_id in decision.completed_intent_ids
    ]
    unfinished = [
        intent.user_visible_label
        for intent in intents
        if intent.intent_id in decision.unfinished_intent_ids
    ]
    breach_guidance = "Only finish the remaining intent(s) listed below.\n"
    return ChatMessage(
        role="system",
        content=render_prompt_contract(
            "contract_recovery",
            breach_guidance=breach_guidance,
            unfinished_line=(
                f"Unfinished requested intents: {', '.join(unfinished)}.\n"
                if unfinished
                else ""
            ),
            completed_line=(
                "Already completed intents with real tool evidence: "
                f"{', '.join(completed)}.\n"
                if completed
                else ""
            ),
            leaked_line=(
                f"Allowed tools for this recovery: {', '.join(decision.allowed_tool_names)}.\n"
                if decision.allowed_tool_names
                and "Allowed tools for this recovery:" not in breach_guidance
                else ""
            ),
        ),
        internal_only=True,
    )


def build_missing_args_clarification_message(
    *,
    decision: RecoveryDecision,
    intents: list[IntentPlan],
    missing_args: list[str],
) -> ChatMessage:
    completed = [
        intent.user_visible_label
        for intent in intents
        if intent.intent_id in decision.completed_intent_ids
    ]
    unfinished = [
        intent.user_visible_label
        for intent in intents
        if intent.intent_id in decision.unfinished_intent_ids
    ]
    return ChatMessage(
        role="system",
        content=render_prompt_contract(
            "contract_recovery",
            breach_guidance=(
                "Do not call any tools yet. Ask one short clarification question "
                "to collect the missing arguments needed for the remaining intent(s).\n"
            ),
            unfinished_line=(
                f"Unfinished requested intents: {', '.join(unfinished)}.\n"
                if unfinished
                else ""
            ),
            completed_line=(
                "Already completed intents with real tool evidence: "
                f"{', '.join(completed)}.\n"
                if completed
                else ""
            ),
            leaked_line=(
                f"Missing arguments that must be clarified first: {', '.join(missing_args)}.\n"
                if missing_args
                else ""
            ),
        ),
        internal_only=True,
    )


def build_partial_output(
    intents: list[IntentPlan],
    *,
    tool_results: list[ToolResult] | None = None,
    reason: str,
    provider_failure_kind: ProviderFailureKind = "none",
    intent_results: dict[str, str] | None = None,
) -> str:
    completed_results, completed_labels = _collect_completed_output_parts(
        intents,
        tool_results=tool_results,
        intent_results=intent_results,
    )
    unfinished_results: list[str] = []
    unfinished_labels: list[str] = []
    retry_budget_exhausted = reason == "retry_budget_exhausted"

    for intent in intents:
        if intent.status == "completed":
            continue
        display_label = RecoveryResultNormalizer._partial_output_label(intent)
        intent_result = RecoveryResultNormalizer._intent_cached_result(
            intent,
            intent_results=intent_results,
        )
        if not intent_result:
            intent_result = intent_result_from_tool_results(intent, tool_results)
        if intent_result:
            result_line = intent_result
            if (
                RecoveryResultNormalizer._should_prefix_result_with_label(
                    intent.user_visible_label
                )
                and intent.user_visible_label not in result_line
            ):
                result_line = f"{intent.user_visible_label}：{intent_result}"
            if (
                _should_surface_unfinished_partial_result(
                    intent,
                    provider_failure_kind=provider_failure_kind,
                )
                and result_line not in unfinished_results
            ):
                unfinished_results.append(result_line)
        if display_label and display_label not in unfinished_labels:
            unfinished_labels.append(display_label)

    parts: list[str] = []
    parts.extend(completed_results)
    if completed_labels:
        parts.append(
            _("我先把已完成部分整理给你：{completed}。").format(
                completed="、".join(completed_labels)
            )
        )
    if unfinished_results:
        parts.append(
            _("我先把目前拿到的结果给你：{results}。").format(
                results="；".join(unfinished_results)
            )
        )

    unfinished_summary = "、".join(unfinished_labels)
    if unfinished_summary:
        if provider_failure_kind == "tool_timeout":
            parts.append(
                _("{unfinished}暂时超时了，你可以稍后再问。").format(
                    unfinished=unfinished_summary
                )
            )
        elif (
            provider_failure_kind == "budget_exit"
            or is_budget_exit_reason(reason)
            or retry_budget_exhausted
        ):
            parts.append(
                _(
                    "{unfinished}还需要继续核验，我先把目前能确认的内容给你。"
                ).format(unfinished=unfinished_summary)
            )
        elif is_terminal_failure_kind(provider_failure_kind):
            parts.append(
                _("{unfinished}被系统中断了，请稍后再试。").format(
                    unfinished=unfinished_summary
                )
            )
        elif provider_failure_kind != "none":
            parts.append(
                _("{unfinished}被暂时中断了，请稍后再试。").format(
                    unfinished=unfinished_summary
                )
            )
        else:
            parts.append(
                _("{unfinished}还没有完成。如果你愿意，我可以继续。").format(
                    unfinished=unfinished_summary
                )
            )
    if parts:
        return " ".join(part.strip() for part in parts if part.strip())
    if (
        reason == "budget_exit"
        or provider_failure_kind == "budget_exit"
        or is_budget_exit_reason(reason)
        or retry_budget_exhausted
    ):
        return _("这次处理在本轮收口前达到了限制，我先把目前能确认的内容给你。")
    if is_terminal_failure_kind(provider_failure_kind):
        return _("这次处理被系统中断了，请稍后再试。")
    if provider_failure_kind != "none":
        return _("这次处理被暂时中断了，请稍后再试一次。")
    return _("这次处理在完成前中断了。如果你愿意，我可以继续。")


def has_completed_output_evidence(
    intents: list[IntentPlan],
    *,
    tool_results: list[ToolResult] | None = None,
    intent_results: dict[str, str] | None = None,
) -> bool:
    completed_results, _completed_labels = _collect_completed_output_parts(
        intents,
        tool_results=tool_results,
        intent_results=intent_results,
    )
    return bool(completed_results)


def build_completed_output(
    intents: list[IntentPlan],
    *,
    tool_results: list[ToolResult] | None = None,
    intent_results: dict[str, str] | None = None,
    reason: str = "completed",
    contract_breach_type: str | None = None,
) -> str:
    _reason = reason
    completed_results, completed_labels = _collect_completed_output_parts(
        intents,
        tool_results=tool_results,
        intent_results=intent_results,
    )
    if completed_results:
        return " ".join(
            result.strip() for result in completed_results if result.strip()
        )
    if str(contract_breach_type or "").strip():
        return _("这次处理没有成功生成最终答复，请再试一次。")
    if completed_labels:
        return _("已根据现有工具结果完成：{completed}。").format(
            completed="、".join(completed_labels)
        )
    return _("我已经根据现有工具结果完成了这次请求。")


def build_partial_response_prompt(
    intents: list[IntentPlan],
    *,
    reason: str,
    provider_failure_kind: ProviderFailureKind = "none",
    intent_results: dict[str, str] | None = None,
) -> ChatMessage:
    completed: list[str] = []
    unfinished: list[str] = []
    for intent in intents:
        if intent.status == "completed":
            cached_result = RecoveryResultNormalizer._intent_cached_result(
                intent,
                intent_results=intent_results,
            )
            completed.append(cached_result or intent.user_visible_label)
        else:
            unfinished.append(intent.user_visible_label)
    return ChatMessage(
        role="system",
        content=render_prompt_contract(
            "partial_exit",
            completed_summary="；".join(completed) if completed else _("无"),
            unfinished_summary="；".join(unfinished) if unfinished else _("无"),
            exit_reason=reason,
            failure_kind=(
                provider_failure_kind
                if provider_failure_kind != "none"
                else "orchestration_partial_exit"
            ),
        ),
        internal_only=True,
    )


__all__ = [
    "build_completed_output",
    "build_missing_args_clarification_message",
    "build_partial_output",
    "build_partial_response_prompt",
    "build_recovery_message",
    "has_completed_output_evidence",
    "is_budget_exit_reason",
    "is_terminal_failure_kind",
]
