"""Intent-scoped recovery and partial-exit helpers."""

from __future__ import annotations

import json
from typing import Any

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage
from app.core.i18n import _

from .types import ExecutionBudget, IntentPlan, ProviderFailureKind, RecoveryDecision


class RecoveryManager:
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
    _RETRYABLE_FAILURE_KINDS: frozenset[ProviderFailureKind] = frozenset(
        {"tool_timeout", "tool_execution_error", "provider_timeout", "provider_rate_limit"}
    )
    _TERMINAL_FAILURE_KINDS: frozenset[ProviderFailureKind] = frozenset(
        {
            "provider_unavailable",
            "provider_http_5xx",
            "provider_bad_response",
            "server_interrupt",
        }
    )

    @staticmethod
    def is_budget_exit_reason(reason: str) -> bool:
        return reason in RecoveryManager._BUDGET_EXIT_REASONS

    @staticmethod
    def is_retryable_failure_kind(kind: ProviderFailureKind) -> bool:
        return kind in RecoveryManager._RETRYABLE_FAILURE_KINDS

    @staticmethod
    def is_terminal_failure_kind(kind: ProviderFailureKind) -> bool:
        return kind == "budget_exit" or kind in RecoveryManager._TERMINAL_FAILURE_KINDS

    @staticmethod
    def _normalize_structured_cached_result(
        value: Any,
        *,
        max_length: int = 500,
    ) -> str | None:
        if isinstance(value, dict):
            items = value.get("items")
            if isinstance(items, list):
                normalized_items: list[str] = []
                seen_items: set[str] = set()
                for item in items[:3]:
                    if not isinstance(item, dict):
                        continue
                    title = str(item.get("title") or "").strip()
                    url = str(item.get("url") or "").strip()
                    if not title and not url:
                        continue
                    label = title or url
                    if title and url:
                        label = f"{title} - {url}"
                    if label in seen_items:
                        continue
                    seen_items.add(label)
                    normalized_items.append(label)
                if normalized_items:
                    return "；".join(normalized_items)

            city = str(value.get("city") or value.get("location") or "").strip()
            condition = str(
                value.get("condition") or value.get("weather") or ""
            ).strip()
            temperature = str(
                value.get("temperature") or value.get("temp") or ""
            ).strip()
            if city and (condition or temperature):
                parts = [f"{city}现在{condition}" if condition else city]
                if temperature:
                    parts.append(f"气温约 {temperature}")
                return "，".join(part for part in parts if part) + "。"

            for key in (
                "summary",
                "result",
                "message",
                "answer",
                "content",
                "text",
                "output",
                "description",
                "title",
            ):
                candidate = value.get(key)
                if candidate is None:
                    continue
                normalized = RecoveryManager._normalize_cached_result(
                    candidate,
                    max_length=max_length,
                )
                if normalized:
                    return normalized
            return None

        if isinstance(value, list):
            items: list[str] = []
            for item in value[:3]:
                normalized = RecoveryManager._normalize_cached_result(
                    item,
                    max_length=max_length,
                )
                if normalized and normalized not in items:
                    items.append(normalized)
            if not items:
                return None
            return "；".join(items)

        return None

    @staticmethod
    def _normalize_cached_result(value: Any, *, max_length: int = 500) -> str | None:
        if value is None:
            return None
        structured = RecoveryManager._normalize_structured_cached_result(
            value,
            max_length=max_length,
        )
        if structured:
            return structured
        text = str(value).strip()
        if not text:
            return None
        lowered = text.lower()
        if "result(s)" in lowered and "http" not in lowered:
            return None
        if text.startswith("{") or text.startswith("["):
            try:
                parsed = json.loads(text)
            except (TypeError, ValueError, json.JSONDecodeError):
                parsed = None
            structured = RecoveryManager._normalize_structured_cached_result(
                parsed,
                max_length=max_length,
            )
            if structured:
                return structured
            return None
        if len(text) > max_length:
            return f"{text[:max_length].rstrip()}..."
        return text

    @staticmethod
    def _should_prefix_result_with_label(label: str | None) -> bool:
        normalized = str(label or "").strip()
        if not normalized:
            return False
        lowered = normalized.lower()
        if lowered in {
            "direct_reply",
            "time",
            "time_query",
            "weather",
            "weather_query",
            "web_research",
            "page_read",
            "page_summary",
        }:
            return False
        if normalized.isascii() and ("_" in normalized or lowered == normalized):
            return False
        return True

    @staticmethod
    def _partial_output_label(intent: IntentPlan) -> str:
        label = str(intent.user_visible_label or "").strip()
        if RecoveryManager._should_prefix_result_with_label(label):
            return label
        normalized_kind = str(intent.kind or "").strip().lower()
        normalized_family = str(intent.family or "").strip().lower()
        if normalized_kind == "web_research" or normalized_family == "web_research":
            return _("这些来源")
        if normalized_kind == "weather_query" or normalized_family == "weather":
            return _("天气")
        if normalized_kind == "time_query" or normalized_family == "time_ops":
            return _("时间")
        return _("这部分")

    @staticmethod
    def _cache_intent_result(intent: IntentPlan, value: Any) -> None:
        normalized = RecoveryManager._normalize_cached_result(value)
        if not normalized:
            return
        intent.cached_result = normalized
        intent.metadata = dict(intent.metadata or {})
        intent.metadata["cached_result"] = normalized

    @staticmethod
    def _cache_partial_intent_result(intent: IntentPlan, value: Any) -> None:
        normalized = RecoveryManager._normalize_cached_result(value)
        if not normalized:
            return
        intent.metadata = dict(intent.metadata or {})
        intent.metadata["partial_result"] = normalized

    @staticmethod
    def _intent_result_from_tool_results(
        intent: IntentPlan,
        tool_results: list[ToolResult] | None = None,
    ) -> str | None:
        if not tool_results:
            return None
        candidate_tool_names: list[str] = []
        for tool_name in (
            list(intent.completed_by_tool_names or [])
            + list(intent.completion_signals or [])
            + list(intent.allowed_tool_names or [])
        ):
            normalized_name = str(tool_name or "").strip()
            if normalized_name and normalized_name not in candidate_tool_names:
                candidate_tool_names.append(normalized_name)
        if not candidate_tool_names:
            return None
        normalized_results: list[str] = []
        for name in candidate_tool_names:
            for result in tool_results:
                if not result.success or result.name != name:
                    continue
                for candidate in (
                    result.summary_payload,
                    result.summary,
                    result.output or result.error,
                ):
                    normalized = RecoveryManager._normalize_cached_result(candidate)
                    if normalized:
                        if normalized not in normalized_results:
                            normalized_results.append(normalized)
                        break
        if not normalized_results:
            return None
        return "；".join(normalized_results[:2])

    @staticmethod
    def _intent_cached_result(
        intent: IntentPlan,
        *,
        intent_results: dict[str, str] | None = None,
    ) -> str | None:
        if intent_results and intent.intent_id in intent_results:
            normalized = RecoveryManager._normalize_cached_result(
                intent_results.get(intent.intent_id)
            )
            if normalized:
                return normalized
        normalized = RecoveryManager._normalize_cached_result(intent.cached_result)
        if normalized:
            return normalized
        metadata = dict(intent.metadata or {})
        for key in (
            "cached_result",
            "intent_result",
            "result_summary",
            "partial_result",
        ):
            normalized = RecoveryManager._normalize_cached_result(metadata.get(key))
            if normalized:
                return normalized
        return None

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
            if clone.status == "completed":
                cached_result = RecoveryManager._intent_cached_result(clone)
                if not cached_result:
                    cached_result = RecoveryManager._intent_result_from_tool_results(
                        clone, tool_results
                    )
                if cached_result:
                    RecoveryManager._cache_intent_result(clone, cached_result)
            elif clone.status not in {"failed", "skipped"}:
                clone.status = "pending"
                partial_result = RecoveryManager._intent_result_from_tool_results(
                    clone,
                    tool_results,
                )
                if partial_result:
                    RecoveryManager._cache_partial_intent_result(
                        clone,
                        partial_result,
                    )
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
                provider_failure_kind=(
                    "budget_exit"
                    if provider_failure_kind == "none"
                    else provider_failure_kind
                ),
            )
        if provider_failure_kind == "budget_exit":
            return RecoveryDecision(
                action="return_partial",
                completed_intent_ids=completed,
                unfinished_intent_ids=[intent.intent_id for intent in unfinished],
                reason="budget_exit",
                provider_failure_kind=provider_failure_kind,
            )
        if not unfinished and provider_failure_kind == "none":
            return None
        if unfinished:
            target = unfinished[0]
            if (
                provider_failure_kind != "none"
                and not RecoveryManager.is_retryable_failure_kind(provider_failure_kind)
            ):
                return RecoveryDecision(
                    action="return_partial",
                    completed_intent_ids=completed,
                    unfinished_intent_ids=[intent.intent_id for intent in unfinished],
                    reason="terminal_failure",
                    provider_failure_kind=provider_failure_kind,
                )
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
        if provider_failure_kind != "none":
            return RecoveryDecision(
                action="return_partial",
                completed_intent_ids=completed,
                unfinished_intent_ids=[],
                reason=(
                    "terminal_failure"
                    if RecoveryManager.is_terminal_failure_kind(provider_failure_kind)
                    else "provider_failure_after_partial_progress"
                ),
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
        )

    @staticmethod
    def build_partial_output(
        intents: list[IntentPlan],
        *,
        reason: str,
        provider_failure_kind: ProviderFailureKind = "none",
        intent_results: dict[str, str] | None = None,
    ) -> str:
        completed_results: list[str] = []
        completed_labels: list[str] = []
        unfinished_results: list[str] = []
        unfinished_labels: list[str] = []
        retry_budget_exhausted = reason == "retry_budget_exhausted"
        for intent in intents:
            display_label = RecoveryManager._partial_output_label(intent)
            intent_result = RecoveryManager._intent_cached_result(
                intent,
                intent_results=intent_results,
            )
            if intent.status == "completed":
                if intent_result:
                    if intent_result not in completed_results:
                        completed_results.append(intent_result)
                elif display_label and display_label not in completed_labels:
                    completed_labels.append(display_label)
                continue
            if intent_result:
                result_line = intent_result
                if (
                    RecoveryManager._should_prefix_result_with_label(
                        intent.user_visible_label
                    )
                    and intent.user_visible_label not in result_line
                ):
                    result_line = f"{intent.user_visible_label}：{intent_result}"
                if result_line not in unfinished_results:
                    unfinished_results.append(result_line)
            if display_label and display_label not in unfinished_labels:
                unfinished_labels.append(display_label)

        parts: list[str] = []
        parts.extend(completed_results)
        if completed_labels:
            parts.append(_("我先把已完成部分整理给你：{completed}。").format(completed="、".join(completed_labels)))
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
                or RecoveryManager.is_budget_exit_reason(reason)
                or retry_budget_exhausted
            ):
                parts.append(
                    _("{unfinished}还需要继续核验，我先把目前能确认的内容给你。").format(
                        unfinished=unfinished_summary
                    )
                )
            elif RecoveryManager.is_terminal_failure_kind(provider_failure_kind):
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
            or RecoveryManager.is_budget_exit_reason(reason)
            or retry_budget_exhausted
        ):
            return _("这次处理在本轮收口前达到了限制，我先把目前能确认的内容给你。")
        if RecoveryManager.is_terminal_failure_kind(provider_failure_kind):
            return _("这次处理被系统中断了，请稍后再试。")
        if provider_failure_kind != "none":
            return _("这次处理被暂时中断了，请稍后再试一次。")
        return _("这次处理在完成前中断了。如果你愿意，我可以继续。")

    @staticmethod
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
                cached_result = RecoveryManager._intent_cached_result(
                    intent, intent_results=intent_results
                )
                completed.append(cached_result or intent.user_visible_label)
            else:
                unfinished.append(intent.user_visible_label)
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
