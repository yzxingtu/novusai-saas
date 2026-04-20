"""Structured tool routing for intent-aware orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.tools.types import ToolDefinition

from .page_workflow_state_machine import (
    PageIntentToolPlan,
    PageWorkflowState,
    PageWorkflowStateMachine,
)
from .types import ExecutionBudget, IntentPlan


@dataclass
class ToolRoutingDecision:
    candidate_tools: list[ToolDefinition] = field(default_factory=list)
    intent_allowed_tools: dict[str, list[str]] = field(default_factory=dict)
    intent_preferred_tools: dict[str, list[str]] = field(default_factory=dict)

    def candidate_tool_names(self) -> list[str]:
        return [tool.name for tool in self.candidate_tools]


class ToolRouter:
    _PAGE_INTENT_TOOL_MAP: dict[str, tuple[list[str], list[str]]] = {
        "page_summary": (
            ["ui_get_snapshot"],
            ["ui_get_snapshot"],
        ),
        "page_navigation": (
            [
                "ui_list_interactables",
                "ui_click",
                "ui_open_surface",
                "ui_get_snapshot",
            ],
            [
                "ui_list_interactables",
                "ui_click",
                "ui_open_surface",
                "ui_get_snapshot",
            ],
        ),
        "page_search": (
            [
                "ui_read_region",
                "ui_list_interactables",
                "ui_click",
            ],
            [
                "ui_read_region",
                "ui_click",
                "ui_list_interactables",
            ],
        ),
        "page_pagination": (
            [
                "ui_read_table",
                "ui_click",
                "ui_list_interactables",
            ],
            [
                "ui_read_table",
                "ui_click",
                "ui_list_interactables",
            ],
        ),
        "page_row_detail": (
            [
                "ui_read_region",
                "ui_read_table",
                "ui_get_snapshot",
            ],
            [
                "ui_read_region",
                "ui_read_table",
                "ui_get_snapshot",
            ],
        ),
        "page_form_read": (
            [
                "ui_get_form_state",
                "ui_read_region",
                "ui_get_snapshot",
            ],
            [
                "ui_get_form_state",
                "ui_read_region",
                "ui_get_snapshot",
            ],
        ),
        "page_screenshot": (
            [
                "ui_get_snapshot",
            ],
            [
                "ui_get_snapshot",
            ],
        ),
        "page_editor_read": (
            [
                "ui_read_region",
                "ui_get_snapshot",
            ],
            [
                "ui_read_region",
                "ui_get_snapshot",
            ],
        ),
        "page_editor_write": (
            [
                "ui_open_surface",
                "ui_fill_form",
                "ui_submit_form",
            ],
            [
                "ui_fill_form",
                "ui_submit_form",
                "ui_open_surface",
            ],
        ),
    }

    @classmethod
    def page_intent_tool_plan(
        cls,
        intent_kind: str,
        *,
        input_variables: dict[str, Any] | None = None,
    ) -> PageIntentToolPlan:
        plan = PageWorkflowStateMachine.plan_for_intent(
            intent_kind,
            input_variables=input_variables,
        )
        if (
            plan.allowed_names
            or plan.preferred_names
            or plan.workflow_goal != intent_kind
        ):
            return plan
        allowed_names, preferred_names = cls._PAGE_INTENT_TOOL_MAP.get(
            intent_kind, ([], [])
        )
        return PageIntentToolPlan(
            allowed_names=list(allowed_names),
            preferred_names=list(preferred_names),
            workflow_stage=plan.workflow_stage,
            workflow_phase=plan.workflow_phase,
            workflow_goal=plan.workflow_goal,
            workflow_state=plan.workflow_state,
            completion_contract=plan.completion_contract,
        )

    @classmethod
    def resolve_page_workflow_state(
        cls,
        *,
        input_variables: dict[str, Any] | None = None,
    ) -> PageWorkflowState:
        return PageWorkflowStateMachine.resolve_state(input_variables=input_variables)

    @classmethod
    def page_intent_tool_preferences(
        cls,
        intent_kind: str,
        *,
        input_variables: dict[str, Any] | None = None,
    ) -> tuple[list[str], list[str]]:
        plan = cls.page_intent_tool_plan(
            intent_kind,
            input_variables=input_variables,
        )
        return list(plan.allowed_names), list(plan.preferred_names)

    @classmethod
    def route(
        cls,
        *,
        intents: list[IntentPlan],
        tools: list[ToolDefinition],
        budget: ExecutionBudget,
        input_variables: dict[str, Any] | None,
        user_text: str = "",
    ) -> ToolRoutingDecision:
        tools_by_name = {tool.name: tool for tool in tools}
        candidate_names: list[str] = []
        intent_allowed: dict[str, list[str]] = {}
        intent_preferred: dict[str, list[str]] = {}
        lowered = user_text.lower()

        def register(
            intent: IntentPlan,
            names: list[str],
            preferred: list[str] | None = None,
        ) -> None:
            allowed = [name for name in names if name in tools_by_name]
            effective_preferred = [
                name for name in (preferred or allowed) if name in allowed
            ]
            intent_allowed[intent.intent_id] = allowed
            intent_preferred[intent.intent_id] = effective_preferred
            for name in allowed:
                if name not in candidate_names:
                    candidate_names.append(name)

        for intent in intents:
            if intent.family == "none" or not intent.requires_tools:
                intent_allowed[intent.intent_id] = []
                intent_preferred[intent.intent_id] = []
                continue

            if intent.kind == "weather_query":
                future_terms = (
                    "明天",
                    "未来",
                    "forecast",
                    "接下来",
                    "后天",
                    "7天",
                    "一周",
                )
                wants_forecast = any(term in lowered for term in future_terms)
                names = ["get_current_weather"]
                if wants_forecast and "get_weather_forecast" in tools_by_name:
                    names.append("get_weather_forecast")
                register(intent, names, names)
                continue

            if intent.kind == "time_query":
                register(intent, ["get_current_time"])
                continue

            if intent.kind == "web_research":
                metadata = dict(intent.metadata or {})
                explicit_url = str(metadata.get("explicit_url") or "").strip()
                fetch_only = bool(metadata.get("fetch_only")) or bool(explicit_url)
                prefer_fetch_url = fetch_only or bool(metadata.get("prefer_fetch_url"))
                if fetch_only:
                    if "fetch_url" in tools_by_name:
                        register(intent, ["fetch_url"], ["fetch_url"])
                    else:
                        register(intent, ["web_search"], ["web_search"])
                    continue
                if prefer_fetch_url:
                    register(
                        intent,
                        ["fetch_url", "web_search"],
                        ["fetch_url", "web_search"],
                    )
                    continue
                register(
                    intent,
                    ["web_search", "fetch_url"],
                    ["web_search", "fetch_url"],
                )
                continue

            if (
                intent.kind in cls._PAGE_INTENT_TOOL_MAP
                or intent.kind == "page_form_write"
            ):
                names, preferred = cls.page_intent_tool_preferences(
                    intent.kind,
                    input_variables=input_variables,
                )
                register(intent, names, preferred)
                continue

            if intent.kind == "knowledge_query":
                register(intent, [])

        if (
            budget.max_candidate_tools > 0
            and len(candidate_names) > budget.max_candidate_tools
        ):
            candidate_names = candidate_names[: budget.max_candidate_tools]

        candidate_tools = [
            tools_by_name[name] for name in candidate_names if name in tools_by_name
        ]
        for intent_id, allowed in list(intent_allowed.items()):
            intent_allowed[intent_id] = [
                name for name in allowed if name in candidate_names
            ]
            intent_preferred[intent_id] = [
                name
                for name in intent_preferred.get(intent_id, [])
                if name in candidate_names
            ]

        return ToolRoutingDecision(
            candidate_tools=candidate_tools,
            intent_allowed_tools=intent_allowed,
            intent_preferred_tools=intent_preferred,
        )


__all__ = [
    "PageIntentToolPlan",
    "PageWorkflowState",
    "ToolRouter",
    "ToolRoutingDecision",
]
