"""Structured intent planning for multi-intent chat turns."""

from __future__ import annotations

from typing import Any

from app.ai.engine.intent_clause_helpers import _split_clauses
from app.ai.engine.intent_domain_rules import IntentDomainRules
from app.ai.engine.intent_page_rules import (
    detect_page_continuation_signal,
    detect_page_signal,
)
from app.ai.engine.intent_signal_helpers import (
    _has_page_context,
    _IntentSignal,
    _last_user_text,
    _tool_families,
)
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage

from .types import IntentPlan

_SUPPRESSED_DOMAIN_KINDS_ON_PAGE_CONTINUATION = {"web_research", "knowledge_query"}
_SUPPRESSED_DOMAIN_KINDS_ON_PAGE_SEARCH = {
    "knowledge_query",
    "weather_query",
    "web_research",
}
# TODO(2026-04-23): replace this transitional guard with planner-time LLM
# structured routing once the runtime owns a dedicated classifier seam.
_NAVIGATION_ACTION_CUES = (
    "点击",
    "单击",
    "打开",
    "switch",
    "open",
)
_NAVIGATION_TARGET_CUES = (
    "页面",
    "按钮",
    "菜单",
    "链接",
)
_NAVIGATION_RESULT_CUES = (
    "当前进入",
    "进入了什么页面",
    "当前页面",
    "现在在哪",
)
_SEQUENCE_CUES = (
    "然后",
    "再",
    "接着",
    "之后",
)
_PAGE_WORKFLOW_GOALS = {
    "page_summary": "page_summary",
    "page_screenshot": "page_screenshot",
    "page_navigation": "navigation",
    "page_search": "search",
    "page_pagination": "pagination",
    "page_row_detail": "row_detail",
    "page_form_read": "form_read",
    "page_form_write": "form_write",
    "page_editor_read": "editor_read",
    "page_editor_write": "editor_write",
}


def _normalize_turn_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _looks_like_navigation_preface_summary(source_text: str) -> bool:
    normalized = _normalize_turn_text(source_text)
    if not normalized:
        return False
    if not any(term in normalized for term in _NAVIGATION_ACTION_CUES):
        return False
    if not any(term in normalized for term in _NAVIGATION_TARGET_CUES):
        return False
    if not any(term in normalized for term in _NAVIGATION_RESULT_CUES):
        return False
    return any(term in normalized for term in _SEQUENCE_CUES)


def _prune_navigation_preface_summaries(plans: list[IntentPlan]) -> list[IntentPlan]:
    if not plans or not any(
        _page_workflow_goal(plan.kind, plan.metadata) == "navigation"
        for plan in plans
        if plan.family == "page_ops"
    ):
        return plans

    pruned: list[IntentPlan] = []
    for index, plan in enumerate(plans):
        if (
            plan.family != "page_ops"
            or _page_workflow_goal(plan.kind, plan.metadata) != "page_summary"
        ):
            pruned.append(plan)
            continue

        has_later_navigation = any(
            later_plan.family == "page_ops"
            and _page_workflow_goal(later_plan.kind, later_plan.metadata)
            == "navigation"
            for later_plan in plans[index + 1 :]
        )
        if has_later_navigation and _looks_like_navigation_preface_summary(
            plan.source_text
        ):
            continue
        pruned.append(plan)
    return pruned


def _page_workflow_goal(
    kind: str,
    metadata: dict[str, Any] | None,
) -> str:
    payload = dict(metadata or {})
    metadata_goal = str(payload.get("page_workflow_goal") or "").strip()
    if metadata_goal:
        return metadata_goal
    normalized_kind = str(kind or "").strip()
    if normalized_kind == "page_workflow":
        return ""
    return _PAGE_WORKFLOW_GOALS.get(normalized_kind, "")


class _IntentPlannerOrchestrator:
    @classmethod
    def _detect_clause_signals(
        cls,
        clause: str,
        *,
        offset: int,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
        capability_bundle: Any | None,
        continuation_context: Any | None,
    ) -> list[_IntentSignal]:
        lowered = clause.lower()
        if IntentDomainRules.explicitly_forbids_tool_usage(
            lowered
        ) or IntentDomainRules.looks_like_capability_self_report(lowered):
            return []

        domain_signals = IntentDomainRules.detect_domain_signals(
            clause=clause,
            offset=offset,
            tools=tools,
            input_variables=input_variables,
            capability_bundle=capability_bundle,
            continuation_context=continuation_context,
        )
        if not (
            _has_page_context(input_variables)
            and "page_ops" in _tool_families(tools, input_variables)
        ):
            return domain_signals

        page_continuation_signal = detect_page_continuation_signal(
            clause=clause,
            offset=offset,
            input_variables=input_variables,
            continuation_context=continuation_context,
        )
        if page_continuation_signal is not None:
            filtered_domain_signals = [
                signal
                for signal in domain_signals
                if signal.kind not in _SUPPRESSED_DOMAIN_KINDS_ON_PAGE_CONTINUATION
            ]
            return sorted(
                [*filtered_domain_signals, page_continuation_signal],
                key=lambda item: item.position,
            )

        page_signal = detect_page_signal(
            clause=clause,
            offset=offset,
            input_variables=input_variables,
        )
        if page_signal is None:
            return domain_signals
        if _page_workflow_goal(page_signal.kind, page_signal.metadata) == "search":
            domain_signals = [
                signal
                for signal in domain_signals
                if signal.kind not in _SUPPRESSED_DOMAIN_KINDS_ON_PAGE_SEARCH
            ]
        return sorted([*domain_signals, page_signal], key=lambda item: item.position)

    @staticmethod
    def _build_direct_reply(user_text: str) -> list[IntentPlan]:
        return [
            IntentPlan(
                intent_id="intent-1",
                kind="direct_reply",
                family="none",
                order=1,
                user_visible_label="direct_reply",
                source_text=user_text,
                requires_tools=False,
                shortcircuit=True,
            )
        ]

    @classmethod
    def plan_turn(
        cls,
        *,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
        continuation_context: Any | None,
        capability_bundle: Any | None = None,
    ) -> list[IntentPlan]:
        user_text = _last_user_text(messages)
        if not user_text:
            return []

        detected: list[_IntentSignal] = []
        for offset, clause in _split_clauses(user_text):
            detected.extend(
                cls._detect_clause_signals(
                    clause,
                    offset=offset,
                    tools=tools,
                    input_variables=input_variables,
                    capability_bundle=capability_bundle,
                    continuation_context=continuation_context,
                )
            )

        if not detected:
            return cls._build_direct_reply(user_text)

        plans: list[IntentPlan] = []
        seen: set[tuple[str, str, int]] = set()
        for signal in sorted(detected, key=lambda item: item.position):
            key = (signal.kind, signal.family, signal.position)
            if key in seen:
                continue
            seen.add(key)

            metadata: dict[str, Any] = dict(signal.metadata or {})
            allow_text_response = False
            if signal.kind == "weather_query" and not IntentDomainRules.weather_query_has_city(
                user_text.lower()
            ):
                allow_text_response = True
                metadata = {**metadata, "missing_args": ["city"]}

            order = len(plans) + 1
            plans.append(
                IntentPlan(
                    intent_id=f"intent-{order}",
                    kind=signal.kind,
                    family=signal.family,
                    order=order,
                    user_visible_label=signal.label,
                    source_text=user_text,
                    requires_tools=signal.requires_tools,
                    allow_text_response=allow_text_response,
                    continuation=signal.continuation,
                    shortcircuit=signal.shortcircuit,
                    metadata=metadata,
                )
            )
        plans = _prune_navigation_preface_summaries(plans)
        return plans or cls._build_direct_reply(user_text)


class IntentPlanner:
    """Thin facade for intent planning."""

    @classmethod
    def plan_turn(
        cls,
        *,
        messages: list[ChatMessage],
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
        continuation_context: Any | None,
        capability_bundle: Any | None = None,
    ) -> list[IntentPlan]:
        return _IntentPlannerOrchestrator.plan_turn(
            messages=messages,
            tools=tools,
            input_variables=input_variables,
            continuation_context=continuation_context,
            capability_bundle=capability_bundle,
        )


__all__ = ["IntentPlanner"]
