"""Structured tool routing for intent-aware orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
            ["get_page_context"],
            ["get_page_context"],
        ),
        "page_navigation": (
            [
                "pageop_list_available_menus",
                "pageop_navigate_menu",
                "invoke_page_operation",
            ],
            [
                "pageop_list_available_menus",
                "pageop_navigate_menu",
                "invoke_page_operation",
            ],
        ),
        "page_search": (
            [
                "pageop_search",
                "pageop_clear_search",
                "pageop_refresh_list",
            ],
            [
                "pageop_search",
                "pageop_clear_search",
                "pageop_refresh_list",
            ],
        ),
        "page_pagination": (
            [
                "pageop_go_to_page",
                "pageop_prev_page",
                "pageop_next_page",
                "pageop_set_page_size",
            ],
            [
                "pageop_go_to_page",
                "pageop_next_page",
                "pageop_prev_page",
                "pageop_set_page_size",
            ],
        ),
        "page_row_detail": (
            [
                "pageop_read_row_detail",
                "pageop_read_visible_rows",
            ],
            [
                "pageop_read_row_detail",
                "pageop_read_visible_rows",
            ],
        ),
        "page_form_read": (
            [
                "pageop_get_form_state",
                "pageop_get_form_options",
            ],
            [
                "pageop_get_form_state",
                "pageop_get_form_options",
            ],
        ),
        "page_form_write": (
            [
                "pageop_create_record",
                "pageop_edit_record",
                "pageop_fill_form",
                "pageop_validate_form",
                "pageop_submit_form",
            ],
            [
                "pageop_create_record",
                "pageop_edit_record",
                "pageop_fill_form",
                "pageop_validate_form",
                "pageop_submit_form",
            ],
        ),
        "page_screenshot": (
            [
                "pageop_capture_screenshot",
                "invoke_page_operation",
            ],
            [
                "pageop_capture_screenshot",
                "invoke_page_operation",
            ],
        ),
        "page_editor_read": (
            [
                "pageop_get_editor_html",
                "pageop_get_editor_text",
            ],
            [
                "pageop_get_editor_html",
                "pageop_get_editor_text",
            ],
        ),
        "page_editor_write": (
            [
                "pageop_replace_content",
                "pageop_replace_section",
                "pageop_append_content",
                "pageop_insert_content",
                "pageop_update_title",
            ],
            [
                "pageop_replace_content",
                "pageop_replace_section",
                "pageop_append_content",
                "pageop_insert_content",
                "pageop_update_title",
            ],
        ),
    }

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

            if intent.kind in cls._PAGE_INTENT_TOOL_MAP:
                names, preferred = cls._PAGE_INTENT_TOOL_MAP[intent.kind]
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
