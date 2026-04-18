"""Structured tool routing for intent-aware orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.tools.semantic_defaults import (
    page_context_has_active_form,
    page_context_payload,
)
from app.ai.tools.types import ToolDefinition

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
    def page_intent_tool_preferences(
        cls,
        intent_kind: str,
        *,
        input_variables: dict[str, Any] | None = None,
    ) -> tuple[list[str], list[str]]:
        if intent_kind == "page_form_read":
            page_context = page_context_payload(input_variables)
            if page_context_has_active_form(page_context):
                return cls._PAGE_INTENT_TOOL_MAP.get(intent_kind, ([], []))

            return (
                [
                    "ui_list_interactables",
                    "ui_click",
                    "ui_open_surface",
                    "ui_get_form_state",
                    "ui_read_region",
                    "ui_get_snapshot",
                ],
                [
                    "ui_list_interactables",
                    "ui_click",
                    "ui_open_surface",
                    "ui_get_form_state",
                    "ui_read_region",
                    "ui_get_snapshot",
                ],
            )

        if intent_kind != "page_form_write":
            return cls._PAGE_INTENT_TOOL_MAP.get(intent_kind, ([], []))

        page_context = page_context_payload(input_variables)
        if page_context_has_active_form(page_context):
            return (
                [
                    "ui_get_form_state",
                    "ui_fill_form",
                    "ui_set_field",
                    "ui_submit_form",
                    "ui_open_surface",
                ],
                [
                    "ui_fill_form",
                    "ui_set_field",
                    "ui_submit_form",
                    "ui_get_form_state",
                    "ui_open_surface",
                ],
            )

        return (
            [
                "ui_list_interactables",
                "ui_open_surface",
                "ui_click",
                "ui_get_form_state",
                "ui_fill_form",
                "ui_submit_form",
            ],
            [
                "ui_list_interactables",
                "ui_open_surface",
                "ui_click",
                "ui_get_form_state",
                "ui_fill_form",
                "ui_submit_form",
            ],
        )

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
        _ = input_variables
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
                register(
                    intent,
                    ["web_search", "fetch_url"],
                    ["web_search", "fetch_url"],
                )
                continue

            if intent.kind in cls._PAGE_INTENT_TOOL_MAP or intent.kind == "page_form_write":
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


__all__ = ["ToolRouter", "ToolRoutingDecision"]
