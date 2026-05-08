"""Capability and tool hint builders extracted from BaseEngine."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.tools.types import ToolDefinition

_LIVE_TURN_SELECTION_SEMANTICS = "turn_selected_subset"
_SELECTION_CONTRACT_KEYS = (
    "selection_semantics",
    "selection_live",
    "live_turn_bound",
)


def build_time_tools_hint(
    tools: list[ToolDefinition],
    *,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    del tools, render_contract
    return ""


def build_capability_reporting_hint(
    *,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    del tools, input_variables, render_contract
    return ""


def build_runtime_capability_hint(
    *,
    runtime_capability_summary: dict[str, Any] | None,
    render_contract: Callable[..., str] = render_prompt_contract,
) -> str:
    selected_skill_names = resolve_live_turn_selected_skill_names(
        runtime_capability_summary=runtime_capability_summary,
    )
    if not selected_skill_names:
        return ""

    return "\n\n" + render_contract(
        "turn_capabilities",
        selected_skill_names=selected_skill_names,
    )


def resolve_live_turn_selected_skill_names(
    *,
    runtime_capability_summary: dict[str, Any] | None,
) -> list[str]:
    summary = (
        dict(runtime_capability_summary)
        if isinstance(runtime_capability_summary, dict)
        else {}
    )
    if _has_selection_contract(summary) and not _is_live_turn_selection(summary):
        return []

    selected_skill_names: list[str] = []
    for name in summary.get("selected_skill_names") or []:
        text = str(name or "").strip()
        if text and text not in selected_skill_names:
            selected_skill_names.append(text)
    return selected_skill_names


def _has_selection_contract(summary: dict[str, Any]) -> bool:
    return any(key in summary for key in _SELECTION_CONTRACT_KEYS)


def _is_live_turn_selection(summary: dict[str, Any]) -> bool:
    semantics = str(summary.get("selection_semantics") or "").strip()
    return (
        semantics == _LIVE_TURN_SELECTION_SEMANTICS
        and summary.get("selection_live") is True
        and summary.get("live_turn_bound") is True
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
