"""Selection and policy assembly helpers for tool routing."""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition

from .tool_policy_semantics import tool_family_for_name, tool_semantic_family
from .types import IntentPlan, ToolUsePolicy


def first_incomplete_requested_family(
    ordered_requested_families: list[str],
    completed_families: set[str],
) -> str | None:
    for family in ordered_requested_families:
        if family not in completed_families:
            return family
    return None


def mark_multi_family_progress(
    *,
    func_name: str,
    success: bool,
    ordered_requested_families: list[str],
    completed_families: set[str],
    has_fetch_url_in_toolset: bool,
    input_variables: dict[str, Any] | None,
) -> None:
    if not success:
        return
    family = tool_family_for_name(func_name, input_variables)
    if family == "web_research":
        if func_name == "fetch_url" or (
            func_name == "web_search" and not has_fetch_url_in_toolset
        ):
            completed_families.add("web_research")
        return
    if family in ordered_requested_families:
        completed_families.add(family)


def allowed_tool_names_for_family(
    family: str,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
) -> list[str]:
    if family == "none":
        return [tool.name for tool in tools]

    allowed: list[str] = []
    for tool in tools:
        if tool_semantic_family(tool, input_variables) == family:
            allowed.append(tool.name)
    return allowed or [tool.name for tool in tools]


def allowed_tool_names_for_families(
    families: list[str],
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None = None,
) -> list[str]:
    ordered: list[str] = []
    for family in families:
        normalized = str(family or "").strip()
        if not normalized or normalized == "none":
            continue
        for name in allowed_tool_names_for_family(normalized, tools, input_variables):
            if name not in ordered:
                ordered.append(name)
    return ordered


def filter_tools_for_policy(
    tools: list[ToolDefinition],
    policy: ToolUsePolicy,
) -> list[ToolDefinition]:
    if not tools or not policy.allowed_tool_names:
        return tools
    allowed = set(policy.allowed_tool_names)
    filtered = [tool for tool in tools if tool.name in allowed]
    return filtered or tools


def restrict_tools_to_names(
    tools: list[ToolDefinition],
    allowed_names: list[str] | None,
) -> list[ToolDefinition]:
    if not allowed_names:
        return tools
    allowed = {str(name).strip() for name in allowed_names if str(name).strip()}
    restricted = [tool for tool in tools if tool.name in allowed]
    return restricted or tools


def restore_explicit_family_tools(
    *,
    selected_tools: list[ToolDefinition],
    all_tools: list[ToolDefinition],
    policy: ToolUsePolicy,
) -> tuple[list[ToolDefinition], bool]:
    if policy.family == "none" or not policy.allowed_tool_names or not all_tools:
        return selected_tools, False

    allowed = set(policy.allowed_tool_names)
    if any(tool.name in allowed for tool in selected_tools):
        return selected_tools, False

    restored = [tool for tool in all_tools if tool.name in allowed]
    if restored:
        return restored, True
    return selected_tools, False


def ensure_explicit_family_coverage(
    *,
    selected_tools: list[ToolDefinition],
    all_tools: list[ToolDefinition],
    explicit_requested_families: list[str],
    input_variables: dict[str, Any] | None = None,
) -> tuple[list[ToolDefinition], list[str]]:
    ordered_families: list[str] = []
    for family in explicit_requested_families:
        normalized = str(family or "").strip()
        if not normalized or normalized == "none" or normalized in ordered_families:
            continue
        ordered_families.append(normalized)
    if len(ordered_families) <= 1:
        return selected_tools, []

    selected_names = {tool.name for tool in selected_tools}
    selected_by_family: set[str] = set()
    for tool in selected_tools:
        family = tool_semantic_family(tool, input_variables)
        if family:
            selected_by_family.add(family)

    missing_families = [
        family for family in ordered_families if family not in selected_by_family
    ]
    if not missing_families:
        return selected_tools, []

    restored = list(selected_tools)
    restored_families: list[str] = []
    for family in missing_families:
        candidates = allowed_tool_names_for_family(family, all_tools, input_variables)
        restored_any = False
        for name in candidates:
            if name in selected_names:
                continue
            candidate = next((tool for tool in all_tools if tool.name == name), None)
            if candidate is None:
                continue
            restored.append(candidate)
            selected_names.add(name)
            restored_any = True
            break
        if restored_any:
            restored_families.append(family)

    return restored, restored_families


def ensure_web_research_tool_pair(
    *,
    selected_tools: list[ToolDefinition],
    all_tools: list[ToolDefinition],
    explicit_requested_families: list[str],
    policy: ToolUsePolicy,
) -> tuple[list[ToolDefinition], bool]:
    if not selected_tools or not all_tools:
        return selected_tools, False

    explicit_families = {
        str(family or "").strip() for family in explicit_requested_families
    }
    selected_names = {tool.name for tool in selected_tools}
    all_by_name = {tool.name: tool for tool in all_tools}
    if not ({"web_search", "fetch_url"} <= set(all_by_name)):
        return selected_tools, False

    web_research_active = (
        policy.family == "web_research"
        or "web_research" in explicit_families
        or bool({"web_search", "fetch_url"} & selected_names)
    )
    if not web_research_active:
        return selected_tools, False

    restored = list(selected_tools)
    restored_any = False
    for tool_name in ("web_search", "fetch_url"):
        if tool_name in selected_names:
            continue
        candidate = all_by_name.get(tool_name)
        if candidate is None:
            continue
        restored.append(candidate)
        selected_names.add(tool_name)
        restored_any = True
    return restored, restored_any


def ordered_requested_families_from_intents(*, intents: list[IntentPlan]) -> list[str]:
    ordered: list[str] = []
    for intent in intents:
        family = str(intent.family or "").strip()
        if not family or family == "none" or family in ordered:
            continue
        ordered.append(family)
    return ordered


def build_required_policy_for_family(
    family: str,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
    reason: str,
) -> ToolUsePolicy:
    return ToolUsePolicy(
        family=family,
        mode="required",
        allowed_tool_names=allowed_tool_names_for_family(
            family,
            tools,
            input_variables,
        ),
        retry_on_contract_breach=False,
        reason=reason,
    )


__all__ = [
    "allowed_tool_names_for_families",
    "allowed_tool_names_for_family",
    "build_required_policy_for_family",
    "ensure_explicit_family_coverage",
    "ensure_web_research_tool_pair",
    "filter_tools_for_policy",
    "first_incomplete_requested_family",
    "mark_multi_family_progress",
    "ordered_requested_families_from_intents",
    "restore_explicit_family_tools",
    "restrict_tools_to_names",
]
