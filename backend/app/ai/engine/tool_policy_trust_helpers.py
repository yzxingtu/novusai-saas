"""Trust-policy enforcement helpers for tool execution."""

from __future__ import annotations

from typing import Any

from app.ai.runtime.execution_trust_policy import (
    allows_tool as trust_policy_allows_tool,
)
from app.ai.tools.types import ToolDefinition

from .tool_policy_semantics import tool_semantic_family


def apply_execution_trust_policy(
    *,
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
    tool_consent_modes: dict[str, str],
    trust_policy_ref: dict[str, Any] | None,
    interaction_mode: str = "confirm",
) -> dict[str, str]:
    is_trusted_auto = str(interaction_mode or "confirm").strip() == "trusted_auto"
    has_policy = isinstance(trust_policy_ref, dict)

    if not is_trusted_auto:
        if not tools or not has_policy:
            return tool_consent_modes
        updated = dict(tool_consent_modes)
        for tool in tools:
            current_mode = updated.get(tool.name, "auto")
            if current_mode != "ask":
                continue
            tool_family = tool_semantic_family(tool, input_variables)
            if trust_policy_allows_tool(
                tool_name=tool.name,
                tool_family=tool_family,
                policy_ref=trust_policy_ref,
            ):
                updated[tool.name] = "auto"
        return updated

    if not tools:
        return tool_consent_modes

    from .tool_processor import is_trusted_auto_read_only_tool_call

    updated = dict(tool_consent_modes)
    for tool in tools:
        current_mode = updated.get(tool.name, "auto")
        if current_mode != "ask":
            continue
        if has_policy:
            tool_family = tool_semantic_family(tool, input_variables)
            if trust_policy_allows_tool(
                tool_name=tool.name,
                tool_family=tool_family,
                policy_ref=trust_policy_ref,
            ):
                updated[tool.name] = "auto"
                continue
        if is_trusted_auto_read_only_tool_call(tool.name):
            updated[tool.name] = "auto"
    return updated


__all__ = ["apply_execution_trust_policy"]
