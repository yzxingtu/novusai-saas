"""Structured intent planning for multi-intent chat turns."""

from __future__ import annotations

from typing import Any

from app.ai.engine.intent_clause_helpers import _split_clauses
from app.ai.engine.intent_domain_rules import IntentDomainRules
from app.ai.engine.intent_signal_helpers import (
    _IntentSignal,
    _last_user_text,
)
from app.ai.tools.types import ToolDefinition
from app.ai.types import ChatMessage

from .types import IntentPlan


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

        return IntentDomainRules.detect_domain_signals(
            clause=clause,
            offset=offset,
            tools=tools,
            input_variables=input_variables,
            capability_bundle=capability_bundle,
            continuation_context=continuation_context,
        )

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
