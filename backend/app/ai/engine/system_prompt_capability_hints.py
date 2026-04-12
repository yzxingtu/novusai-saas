"""Capability and tool hint builders extracted from BaseEngine."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.tools.types import ToolDefinition


def build_page_operations_hint(
    *,
    input_variables: dict[str, Any] | None,
    tools: list[ToolDefinition] | None = None,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    """Build PAGE OPERATIONS hint from page context and available ui tools."""
    if not input_variables:
        return ""
    from app.ai.tools.semantic_defaults import (
        UI_DANGEROUS_PAGE_TOOL_NAMES,
        UI_READONLY_PAGE_TOOL_NAMES,
        UI_SAFE_WRITE_PAGE_TOOL_NAMES,
        page_context_available_ui_tools,
        page_context_payload,
    )

    page_ctx = page_context_payload(input_variables)
    if not isinstance(page_ctx, dict):
        return ""

    page_key = (page_ctx.get("page_key") or "").strip()
    if not page_key:
        return ""

    tool_names = [t.name for t in (tools or [])]
    available_ui_tools = page_context_available_ui_tools(
        page_ctx,
        available_tool_names=set(tool_names),
    )
    if not available_ui_tools:
        return ""

    readonly_tools = [
        name for name in available_ui_tools if name in UI_READONLY_PAGE_TOOL_NAMES
    ]
    action_tools = [
        name
        for name in available_ui_tools
        if name in {"ui_click", "ui_open_surface", "ui_list_interactables"}
    ]
    form_tools = [
        name
        for name in available_ui_tools
        if name in {"ui_get_form_state", "ui_set_field", "ui_fill_form"}
    ]
    submit_tools = [
        name for name in available_ui_tools if name in UI_DANGEROUS_PAGE_TOOL_NAMES
    ]
    safe_write_tools = [
        name
        for name in available_ui_tools
        if name in UI_SAFE_WRITE_PAGE_TOOL_NAMES and name not in action_tools
    ]

    return "\n\n" + render_contract(
        "page_operations_dedicated",
        page_key=page_key,
        readonly_tools=", ".join(readonly_tools),
        action_tools=", ".join(action_tools),
        safe_write_tools=", ".join(safe_write_tools),
        form_tools=", ".join(form_tools),
        submit_tools=", ".join(submit_tools),
    )


def build_web_research_hint(
    tools: list[ToolDefinition],
    *,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    tool_names = {t.name for t in tools}
    has_search = "web_search" in tool_names
    has_fetch = "fetch_url" in tool_names
    if not (has_search or has_fetch):
        return ""

    workflow = []
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

    return "\n\n" + render_contract(
        "web_research",
        workflow="; ".join(workflow),
    )


def build_weather_tools_hint(
    tools: list[ToolDefinition],
    *,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    tool_names = {t.name for t in tools}
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

    return "\n\n" + render_contract(
        "weather_tools",
        workflow="; ".join(workflow),
    )


def build_time_tools_hint(
    tools: list[ToolDefinition],
    *,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    tool_names = {t.name for t in tools}
    if "get_current_time" not in tool_names:
        return ""
    return "\n\n" + render_contract("time_tools")


def build_capability_reporting_hint(
    *,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    tool_names = [t.name for t in tools]
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

    tool_line = ", ".join(tool_names) if tool_names else "none"
    ui_tool_line = ", ".join(ui_tools) if ui_tools else "none"
    return "\n\n" + render_contract(
        "capability_reporting",
        tool_line=tool_line,
        ui_tool_line=ui_tool_line,
    )


def build_runtime_capability_hint(
    *,
    runtime_capability_summary: dict[str, Any] | None,
    include_knowledge_base_hint: bool = True,
    include_page_context_hint: bool = True,
    include_memory_hint: bool = True,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    summary = (
        dict(runtime_capability_summary)
        if isinstance(runtime_capability_summary, dict)
        else {}
    )
    normalized_skill_names: list[str] = []
    for name in summary.get("selected_skill_names") or []:
        text = str(name or "").strip()
        if text and text not in normalized_skill_names:
            normalized_skill_names.append(text)

    context_line = str(summary.get("context_line") or "").strip()
    if not normalized_skill_names and not context_line:
        return ""
    return "\n\n" + render_contract(
        "turn_capabilities",
        selected_skill_names=", ".join(normalized_skill_names),
        context_line=context_line,
        knowledge_base_hint=(
            include_knowledge_base_hint
            and bool(summary.get("knowledge_base_hint", False))
        ),
        page_context_hint=(
            include_page_context_hint and bool(summary.get("page_context_hint", False))
        ),
        memory_hint=(include_memory_hint and bool(summary.get("memory_hint", False))),
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
    ordered: list[str] = []
    for family in ordered_requested_families or []:
        normalized = str(family or "").strip()
        if not normalized or normalized == "none" or normalized in ordered:
            continue
        ordered.append(normalized)

    if len(ordered) <= 1:
        return ""

    label_map = {
        "page_ops": "page operations",
        "weather": "weather tools",
        "time_ops": "time tools",
        "web_research": "web research tools",
    }
    sequence_lines: list[str] = []
    for idx, family in enumerate(ordered, start=1):
        label = label_map.get(family, family.replace("_", " "))
        family_tools = allowed_tool_names_for_family(family, tools, input_variables)
        shown_tools = ", ".join(family_tools[:4]) if family_tools else "none"
        suffix = "..." if len(family_tools) > 4 else ""
        sequence_lines.append(f"{idx}. {label} (tools: {shown_tools}{suffix})")

    return "\n\n" + render_contract(
        "ordered_capability_intent",
        sequence_lines="\n".join(sequence_lines),
    )


def build_ordered_capability_hint_default(
    *,
    ordered_requested_families: list[str] | None,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
) -> str:
    from .tool_policy_helpers import (
        allowed_tool_names_for_family as _allowed_tool_names_for_family_impl,
    )

    return build_ordered_capability_hint(
        ordered_requested_families=ordered_requested_families,
        tools=tools,
        input_variables=input_variables,
        allowed_tool_names_for_family=_allowed_tool_names_for_family_impl,
    )
