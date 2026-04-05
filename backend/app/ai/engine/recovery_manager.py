"""Intent-scoped recovery and partial-exit helpers."""

from __future__ import annotations

from typing import Any

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage
from app.core.i18n import _

from .types import ExecutionBudget, IntentPlan, ProviderFailureKind, RecoveryDecision


class RecoveryManager:
    @staticmethod
    def _partial_exit_labels(intents: list[IntentPlan]) -> tuple[list[str], list[str]]:
        completed = [
            intent.user_visible_label
            for intent in intents
            if intent.status == "completed"
        ]
        unfinished = [
            intent.user_visible_label
            for intent in intents
            if intent.status != "completed"
        ]
        return completed, unfinished

    @staticmethod
    def _successful_tool_names(
        messages: list[ChatMessage],
        tool_results: list[ToolResult] | None = None,
    ) -> list[str]:
        names: list[str] = []
        for result in tool_results or []:
            if result.success and result.name not in names:
                names.append(result.name)
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

    @staticmethod
    def _pending_consent_payload_from_tool_calls(
        tool_calls: list[dict[str, Any]] | None,
    ) -> dict[str, Any] | None:
        for tool_call in tool_calls or []:
            payload = tool_call.get("pending_consent")
            if isinstance(payload, dict) and not payload.get("resolved"):
                return dict(payload)
        return None

    @staticmethod
    def _extract_pending_consent_payload(
        messages: list[ChatMessage],
    ) -> dict[str, Any] | None:
        for message in reversed(messages):
            meta = message.metadata or {}
            payload = meta.get("pending_consent")
            if isinstance(payload, dict) and not payload.get("resolved"):
                return dict(payload)
            payload = RecoveryManager._pending_consent_payload_from_tool_calls(
                message.tool_calls
            )
            if payload:
                return payload
        return None

    @staticmethod
    def pending_consent_payload_from_decision(
        decision: RecoveryDecision | None,
    ) -> dict[str, Any] | None:
        if decision is None:
            return None
        meta = dict(decision.metadata or {})
        payload = meta.get("pending_consent")
        return dict(payload) if isinstance(payload, dict) else None

    @staticmethod
    def ensure_latest_assistant_pending_consent(
        messages: list[ChatMessage],
        payload: dict[str, Any] | None,
    ) -> None:
        if not isinstance(payload, dict) or not payload:
            return
        normalized_payload = dict(payload)
        for message in reversed(messages):
            if message.role != "assistant":
                continue
            metadata = dict(message.metadata or {})
            metadata["pending_consent"] = normalized_payload
            message.metadata = metadata
            return
        messages.append(
            ChatMessage(
                role="assistant",
                content="",
                metadata={"pending_consent": normalized_payload},
            )
        )

    @staticmethod
    def update_intent_statuses(
        intents: list[IntentPlan],
        *,
        messages: list[ChatMessage],
        tool_results: list[ToolResult] | None = None,
    ) -> list[IntentPlan]:
        successful_tool_names = set(
            RecoveryManager._successful_tool_names(messages, tool_results)
        )
        pending_payload = RecoveryManager._extract_pending_consent_payload(messages)
        pending_consent_assigned = False
        updated: list[IntentPlan] = []
        for intent in intents:
            clone = IntentPlan(**intent.to_dict())
            clone.metadata = dict(clone.metadata or {})
            clone.metadata.pop("pending_consent", None)
            completion_signals = set(
                clone.completion_signals or clone.allowed_tool_names
            )
            if clone.family == "none" or not clone.requires_tools:
                clone.status = "completed"
            elif completion_signals & successful_tool_names:
                clone.status = "completed"
                clone.completed_by_tool_names = sorted(
                    completion_signals & successful_tool_names
                )
            elif clone.status not in {"failed", "skipped"}:
                clone.status = "pending"
            if (
                pending_payload
                and not pending_consent_assigned
                and clone.status not in {"completed", "failed", "skipped"}
                and clone.requires_tools
            ):
                clone.status = "awaiting_consent"
                clone.metadata["pending_consent"] = dict(pending_payload)
                pending_consent_assigned = True
            updated.append(clone)
        return updated

    @staticmethod
    def next_unfinished_intents(intents: list[IntentPlan]) -> list[IntentPlan]:
        return [
            intent
            for intent in intents
            if intent.status not in {"completed", "skipped"}
        ]

    @staticmethod
    def _pending_consent_intent(intents: list[IntentPlan]) -> IntentPlan | None:
        for intent in intents:
            if intent.status == "awaiting_consent":
                return intent
        return None

    @staticmethod
    def decide(
        intents: list[IntentPlan],
        *,
        budget: ExecutionBudget | None,
        provider_failure_kind: ProviderFailureKind = "none",
    ) -> RecoveryDecision | None:
        unfinished = RecoveryManager.next_unfinished_intents(intents)
        completed = [
            intent.intent_id for intent in intents if intent.status == "completed"
        ]
        pending_intent = RecoveryManager._pending_consent_intent(intents)
        if pending_intent:
            pending_meta = (pending_intent.metadata or {}).get("pending_consent")
            payload = dict(pending_meta) if isinstance(pending_meta, dict) else None
            metadata: dict[str, Any] = {}
            if payload:
                metadata["pending_consent"] = payload
            return RecoveryDecision(
                action="pause_for_consent",
                target_intent_id=pending_intent.intent_id,
                completed_intent_ids=completed,
                unfinished_intent_ids=[intent.intent_id for intent in unfinished],
                reason="awaiting_user_consent",
                provider_failure_kind=provider_failure_kind,
                metadata=metadata,
            )
        budget_exit_reason = (
            budget.first_exceeded_reason() if budget is not None else None
        )
        if budget_exit_reason:
            return RecoveryDecision(
                action="return_partial",
                completed_intent_ids=completed,
                unfinished_intent_ids=[intent.intent_id for intent in unfinished],
                reason=budget_exit_reason,
                provider_failure_kind=provider_failure_kind,
            )
        if not unfinished and provider_failure_kind == "none":
            return None
        if unfinished:
            target = unfinished[0]
            retry_count = int(
                (
                    budget.retries_by_intent.get(target.intent_id, 0)
                    if budget is not None
                    else 0
                )
                or 0
            )
            if budget is not None and retry_count >= budget.max_retry_per_intent:
                return RecoveryDecision(
                    action="return_partial",
                    completed_intent_ids=completed,
                    unfinished_intent_ids=[intent.intent_id for intent in unfinished],
                    reason="retry_budget_exhausted",
                    provider_failure_kind=provider_failure_kind,
                )
            return RecoveryDecision(
                action="retry_intent",
                target_intent_id=target.intent_id,
                retry_family=target.family,
                allowed_tool_names=list(target.allowed_tool_names),
                completed_intent_ids=completed,
                unfinished_intent_ids=[intent.intent_id for intent in unfinished],
                reason="unfinished_intent_retry",
                provider_failure_kind=provider_failure_kind,
            )
        return RecoveryDecision(
            action="return_partial",
            completed_intent_ids=completed,
            unfinished_intent_ids=[],
            reason="provider_failure_after_partial_progress",
            provider_failure_kind=provider_failure_kind,
        )

    @staticmethod
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
        return ChatMessage(
            role="system",
            content=render_prompt_contract(
                "contract_recovery",
                breach_guidance="Only finish the remaining intent(s) listed below.\n",
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
                    else ""
                ),
            ),
        )

    @staticmethod
    def build_partial_output(
        intents: list[IntentPlan],
        *,
        reason: str,
        provider_failure_kind: ProviderFailureKind = "none",
    ) -> str:
        completed, unfinished = RecoveryManager._partial_exit_labels(intents)
        completed_summary = "、".join(completed)
        unfinished_summary = "、".join(unfinished)

        if completed and unfinished:
            return _(
                "我先把已经完成的部分整理给你：{completed}。其余部分还没有完成：{unfinished}。如果你愿意，我可以继续处理剩余内容。"
            ).format(
                completed=completed_summary,
                unfinished=unfinished_summary,
            )
        if completed:
            return _("我先整理到这里了：{completed}。").format(
                completed=completed_summary,
            )
        if reason == "elapsed_budget_exceeded":
            return _("这次处理在整理最终答复前超时了。如果你愿意，我可以继续处理。")
        if provider_failure_kind != "none":
            return _("这次处理被暂时中断了，请稍后再试一次。")
        if unfinished:
            return _("这次处理还没有完成：{unfinished}。如果你愿意，我可以继续。").format(
                unfinished=unfinished_summary,
            )
        return _("这次处理在完成前中断了。如果你愿意，我可以继续。")

    @staticmethod
    def build_partial_response_prompt(
        intents: list[IntentPlan],
        *,
        reason: str,
        provider_failure_kind: ProviderFailureKind = "none",
    ) -> ChatMessage:
        completed, unfinished = RecoveryManager._partial_exit_labels(intents)
        return ChatMessage(
            role="system",
            content=render_prompt_contract(
                "partial_exit",
                completed_summary="；".join(completed) if completed else "无",
                unfinished_summary="；".join(unfinished) if unfinished else "无",
                exit_reason=reason,
                failure_kind=provider_failure_kind
                if provider_failure_kind != "none"
                else "orchestration_partial_exit",
            ),
        )


__all__ = ["RecoveryManager"]
