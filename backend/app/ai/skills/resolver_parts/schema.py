from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition, ToolParameter
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.skill.resolver")


def build_unique_tool_name(
    base_name: str,
    suffix: str,
    used_names: set[str],
) -> str:
    max_len = 64
    available = max_len - len(suffix)
    short_base = base_name[:available] if available > 0 else ""
    candidate = f"{short_base}{suffix}" if short_base else suffix.strip("_")
    if not candidate:
        candidate = "tool"

    unique_name = candidate
    idx = 1
    while unique_name in used_names:
        extra = f"_{idx}"
        keep = max_len - len(extra)
        unique_name = f"{candidate[:keep]}{extra}" if keep > 0 else candidate
        idx += 1
    return unique_name


def ensure_unique_tool_names(tools: list[ToolDefinition]) -> None:
    used_names: set[str] = set()
    duplicate_counts: dict[str, int] = {}

    for td in tools:
        name = td.name
        if name not in used_names:
            used_names.add(name)
            duplicate_counts.setdefault(name, 1)
            continue

        duplicate_counts[name] = duplicate_counts.get(name, 1) + 1
        serial = duplicate_counts[name]
        suffix = (
            f"__s{td.source_skill_id}"
            if td.source_skill_id is not None
            else f"__dup{serial}"
        )
        unique_name = build_unique_tool_name(name, suffix, used_names)
        logger.warning(
            "Duplicate tool name '{}' detected, renamed to '{}' (skill_id={})",
            name,
            unique_name,
            td.source_skill_id,
        )
        td.name = unique_name
        used_names.add(unique_name)


def build_params_from_schema(
    input_schema: dict[str, Any] | None,
) -> list[ToolParameter]:
    if not input_schema:
        return []

    properties = input_schema.get("properties", {})
    required_set = set(input_schema.get("required", []))
    params: list[ToolParameter] = []

    for name, prop in properties.items():
        params.append(
            ToolParameter(
                name=name,
                type=prop.get("type", "string"),
                description=prop.get("description", ""),
                required=name in required_set,
                default=prop.get("default"),
                enum=prop.get("enum"),
                items=(
                    dict(prop.get("items"))
                    if isinstance(prop.get("items"), dict)
                    else None
                ),
            )
        )

    return params
