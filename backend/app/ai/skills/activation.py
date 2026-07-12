"""Turn-level skill activation state for autonomous ReAct execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnSkillActivation:
    applied: bool = False
    activated_tool_names: list[str] = field(default_factory=list)
    activated_skill_names: list[str] = field(default_factory=list)
    reason: str | None = None


def _stable_unique(values: list[Any]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def activated_tools_for_turn(skill_result: Any | None) -> list[Any]:
    if skill_result is None:
        return []
    return list(getattr(skill_result, "tools", []) or [])


def execution_tools_for_turn(skill_result: Any | None) -> list[Any]:
    return activated_tools_for_turn(skill_result)


def execution_selected_tool_names_for_turn(skill_result: Any | None) -> list[str]:
    return _stable_unique(
        [getattr(tool, "name", None) for tool in execution_tools_for_turn(skill_result)]
    )


def execution_capability_descriptors_for_turn(skill_result: Any | None) -> list[Any]:
    if skill_result is None:
        return []
    return list(getattr(skill_result, "capability_descriptors", []) or [])


def apply_turn_skill_activation(
    *,
    skill_result: Any | None,
    request: Any,
    intent_flags: dict[str, Any] | None,
    allow_catalog_skill_activation: bool = False,
) -> Any | None:
    del request, intent_flags, allow_catalog_skill_activation
    if skill_result is None:
        return None

    skill_result.turn_activation = TurnSkillActivation(
        applied=False,
        reason="react_autonomous",
    )
    return skill_result


__all__ = [
    "activated_tools_for_turn",
    "execution_capability_descriptors_for_turn",
    "execution_selected_tool_names_for_turn",
    "execution_tools_for_turn",
    "TurnSkillActivation",
    "apply_turn_skill_activation",
]
