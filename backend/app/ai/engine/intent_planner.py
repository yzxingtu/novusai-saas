"""Structured intent planning for multi-intent chat turns."""

from __future__ import annotations

import re
from typing import Any

from app.ai.engine.intent_clause_helpers import _split_clauses
from app.ai.engine.intent_domain_rules import IntentDomainRules
from app.ai.engine.intent_page_rules import (
    detect_page_continuation_signal,
    detect_page_signal,
    page_continuation_workflow_goal,
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
_MIXED_PAGE_REFERENCE_RE = re.compile(
    r"(?:(?<=[\u4e00-\u9fff])page\b|\bpage(?=[\u4e00-\u9fff]))",
    re.IGNORECASE,
)


def _page_workflow_goal(
    kind: str,
    metadata: dict[str, Any] | None,
) -> str:
    payload = dict(metadata or {})
    metadata_goal = str(payload.get("page_workflow_goal") or "").strip()
    if metadata_goal:
        return metadata_goal
    return ""


def _normalize_page_reference_clause(clause: str) -> str:
    if "page" not in clause.lower():
        return clause
    return _MIXED_PAGE_REFERENCE_RE.sub("页面", clause)


def _page_signal_can_upgrade(
    clause: str,
    signal: _IntentSignal,
) -> bool:
    if signal.kind != "page_workflow" or signal.family != "page_ops":
        return False
    if _page_workflow_goal(signal.kind, signal.metadata) != "page_summary":
        return False
    return (
        str((signal.metadata or {}).get("routing_provenance") or "").strip()
        == "page_reference_fallback"
    )


def _page_signal_upgrade_goal(
    clause: str,
    *,
    input_variables: dict[str, Any] | None,
) -> tuple[str, str]:
    normalized_clause = _normalize_page_reference_clause(clause)
    # SHORTCIRCUIT: explicit page-aware action clauses should not collapse into
    # read-only page_summary when the user is asking us to act on the current page.
    if (
        page_continuation_workflow_goal(
            clause=normalized_clause,
            input_variables=input_variables,
            continuation_context=None,
        )
        == "navigation"
    ):
        return "navigation", "page_action_guard"
    return "", ""


def _upgrade_page_signal(
    signal: _IntentSignal,
    *,
    workflow_goal: str,
    routing_provenance: str,
) -> _IntentSignal:
    metadata = dict(signal.metadata or {})
    metadata.update(
        {
            "routing_mode": "deterministic_shortcircuit",
            "routing_provenance": routing_provenance,
            "page_workflow_kind": "page_workflow",
            "page_workflow_goal": workflow_goal,
        }
    )
    return _IntentSignal(
        kind=signal.kind,
        family=signal.family,
        label=signal.label,
        position=signal.position,
        requires_tools=signal.requires_tools,
        shortcircuit=False,
        continuation=signal.continuation,
        metadata=metadata,
    )


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

        page_clause = _normalize_page_reference_clause(clause)
        page_signal = detect_page_signal(
            clause=page_clause,
            offset=offset,
            input_variables=input_variables,
        )
        if page_signal is None:
            return domain_signals
        if _page_signal_can_upgrade(page_clause, page_signal):
            workflow_goal, routing_provenance = _page_signal_upgrade_goal(
                page_clause,
                input_variables=input_variables,
            )
            if workflow_goal:
                page_signal = _upgrade_page_signal(
                    page_signal,
                    workflow_goal=workflow_goal,
                    routing_provenance=routing_provenance,
                )
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
