"""Capability and tool hint builders extracted from BaseEngine."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.tools.types import ToolDefinition


def build_web_research_hint(
    tools: list[ToolDefinition],
    *,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    tool_names = {tool.name for tool in tools}
    has_search = "web_search" in tool_names
    has_fetch = "fetch_url" in tool_names
    if not (has_search or has_fetch):
        return ""

    workflow: list[str] = []
    if has_search:
        workflow.append("1) use web_search to find candidate sources")
    if has_fetch:
        next_step = "2" if has_search else "1"
        workflow.append(
            f"{next_step}) use fetch_url to read the most relevant page content"
        )

    compare_step = "3" if has_search and has_fetch else "2"
    workflow.append(
        f"{compare_step}) prefer official or primary sources, and compare more than one source when the user asks for current, recent, or high-stakes information"
    )
    return "\n\n" + render_contract("web_research", workflow="; ".join(workflow))


def build_weather_tools_hint(
    tools: list[ToolDefinition],
    *,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    tool_names = {tool.name for tool in tools}
    has_current = "get_current_weather" in tool_names
    has_forecast = "get_weather_forecast" in tool_names
    if not (has_current or has_forecast):
        return ""

    workflow: list[str] = []
    if has_current:
        workflow.append("use get_current_weather for current conditions")
    if has_forecast:
        workflow.append(
            "use get_weather_forecast for tomorrow, future days, or 7-day forecasts"
        )
    return "\n\n" + render_contract("weather_tools", workflow="; ".join(workflow))


def build_time_tools_hint(
    tools: list[ToolDefinition],
    *,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    if "get_current_time" not in {tool.name for tool in tools}:
        return ""
    return "\n\n" + render_contract("time_tools")


def build_capability_reporting_hint(
    *,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    tool_names = [tool.name for tool in tools]
    ui_tools: list[str] = []
    if input_variables:
        from app.ai.tools.semantic_defaults import (
            page_context_available_ui_tools,
            page_context_payload,
        )

        page_ctx = page_context_payload(input_variables)
        if isinstance(page_ctx, dict):
            ui_tools = page_context_available_ui_tools(
                page_ctx,
                available_tool_names=set(tool_names),
            )

    return "\n\n" + render_contract(
        "capability_reporting",
        tool_line=", ".join(tool_names) if tool_names else "none",
        ui_tool_line=", ".join(ui_tools) if ui_tools else "none",
    )


def build_runtime_capability_hint(
    *,
    runtime_capability_summary: dict[str, Any] | None,
    include_knowledge_base_hint: bool = True,
    include_page_context_hint: bool = True,
    include_memory_hint: bool = True,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    del include_knowledge_base_hint, include_page_context_hint, include_memory_hint

    summary = (
        dict(runtime_capability_summary)
        if isinstance(runtime_capability_summary, dict)
        else {}
    )
    selected_skill_names: list[str] = []
    for name in summary.get("selected_skill_names") or []:
        text = str(name or "").strip()
        if text and text not in selected_skill_names:
            selected_skill_names.append(text)
    if not selected_skill_names:
        return ""

    return "\n\n" + render_contract(
        "turn_capabilities",
        selected_skill_names=", ".join(selected_skill_names),
    )


def build_ordered_capability_hint(
    *,
    ordered_requested_families: list[str] | None,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
    allowed_tool_names_for_family: Callable[
        [str, list[ToolDefinition], dict[str, Any] | None],
        list[str],
    ],
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    del (
        ordered_requested_families,
        tools,
        input_variables,
        allowed_tool_names_for_family,
        render_contract,
    )
    return ""


def build_ordered_capability_hint_default(
    *,
    ordered_requested_families: list[str] | None,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
) -> str:
    del ordered_requested_families, tools, input_variables
    return ""
