"""Minimal tool routing for structured intents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.tools.semantic_defaults import tool_semantic_family
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
    @staticmethod
    def _tool_map(
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
    ) -> dict[str, list[ToolDefinition]]:
        grouped: dict[str, list[ToolDefinition]] = {}
        for tool in tools:
            family = tool_semantic_family(tool, input_variables)
            grouped.setdefault(family, []).append(tool)
        return grouped

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
        grouped = cls._tool_map(tools, input_variables)
        candidate_names: list[str] = []
        intent_allowed: dict[str, list[str]] = {}
        intent_preferred: dict[str, list[str]] = {}
        lowered = user_text.lower()

        def register(
            intent: IntentPlan, names: list[str], preferred: list[str] | None = None
        ) -> None:
            allowed = [name for name in names if name in tools_by_name]
            intent_allowed[intent.intent_id] = allowed
            intent_preferred[intent.intent_id] = [
                name for name in (preferred or allowed) if name in allowed
            ]
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
                    intent, ["web_search", "fetch_url"], ["web_search", "fetch_url"]
                )
                continue
            if intent.kind == "page_read":
                register(intent, ["get_page_context"])
                continue
            if intent.kind == "page_navigation":
                register(
                    intent,
                    [
                        "get_page_context",
                        "pageop_list_available_menus",
                        "pageop_navigate_menu",
                        "invoke_page_operation",
                    ],
                    [
                        "pageop_navigate_menu",
                        "pageop_list_available_menus",
                        "invoke_page_operation",
                    ],
                )
                continue
            if intent.kind == "page_write":
                pageop_names = sorted(
                    tool.name
                    for tool in grouped.get("page_ops", [])
                    if tool.name.startswith("pageop_")
                )
                register(
                    intent,
                    ["get_page_context", "invoke_page_operation", *pageop_names[:3]],
                    ["invoke_page_operation", *pageop_names[:2]],
                )
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
