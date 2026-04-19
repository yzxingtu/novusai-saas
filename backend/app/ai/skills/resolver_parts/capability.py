from __future__ import annotations

from typing import Any

from app.ai.runtime.types import CapabilityDescriptor
from app.ai.tools.types import ToolDefinition


def build_skill_capability_descriptors(skills: list[Any]) -> list[CapabilityDescriptor]:
    descriptors: list[CapabilityDescriptor] = []
    seen_keys: set[tuple[int | None, str]] = set()

    for skill in skills:
        skill_name = str(getattr(skill, "name", "") or "").strip()
        if not skill_name:
            continue
        skill_id = getattr(skill, "id", None)
        key = (skill_id, skill_name)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        package = getattr(skill, "package", None)
        package_name = str(getattr(package, "name", "") or "").strip()
        source_plugin = str(getattr(package, "source_plugin", "") or "").strip()
        source = f"skill_package:{package_name}" if package_name else "skill_resolver"
        metadata: dict[str, Any] = {
            "skill_id": skill_id,
            "skill_type": getattr(skill, "type", None),
            "package_id": getattr(skill, "package_id", None),
        }
        if package_name:
            metadata["package_name"] = package_name
        if source_plugin:
            metadata["source_plugin"] = source_plugin

        descriptors.append(
            CapabilityDescriptor(
                name=skill_name,
                kind="capability_pack",
                source=source,
                description=str(getattr(skill, "description", "") or ""),
                metadata=metadata,
            )
        )

    return descriptors


def enrich_skill_capability_descriptors_with_tools(
    *,
    descriptors: list[CapabilityDescriptor],
    tools: list[ToolDefinition],
) -> None:
    tool_names_by_skill: dict[str, list[str]] = {}
    for tool in tools:
        skill_name = str(getattr(tool, "source_skill_name", "") or "").strip()
        tool_name = str(getattr(tool, "name", "") or "").strip()
        if not skill_name or not tool_name:
            continue
        bucket = tool_names_by_skill.setdefault(skill_name, [])
        if tool_name not in bucket:
            bucket.append(tool_name)

    for descriptor in descriptors:
        if str(descriptor.kind or "").strip() not in {"capability_pack", "prompt_skill"}:
            continue
        skill_name = str(descriptor.name or "").strip()
        if not skill_name:
            continue
        resolved_tool_names = list(tool_names_by_skill.get(skill_name, []))
        descriptor.metadata = {
            **dict(descriptor.metadata or {}),
            "resolved_tool_names": resolved_tool_names,
            "resolved_tool_count": len(resolved_tool_names),
            "has_execution_tools": bool(resolved_tool_names),
        }
