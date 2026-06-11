from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.runtime.types import CapabilityDescriptor
from app.ai.tools.types import ToolDefinition, ToolParameter
from app.enums.agent import ToolTypeEnum

BASELINE_RUNTIME_BUILTINS = ("get_current_time",)
RUNTIME_BUILTINS = frozenset(BASELINE_RUNTIME_BUILTINS)


def augment_builtin_tool_description(
    tool_name: str,
    description: str,
) -> str:
    normalized = (tool_name or "").strip().lower()
    base = (description or "").strip()

    if normalized == "get_current_time":
        extra = render_prompt_contract("builtin_current_time_description")
    else:
        return base

    if not base:
        return extra
    if extra in base:
        return base
    return f"{base} {extra}"


def build_baseline_builtin_tool(
    *,
    tool_name: str,
    apply_tool_semantics: Callable[[ToolDefinition], None],
) -> ToolDefinition | None:
    normalized = (tool_name or "").strip().lower()
    tool: ToolDefinition | None = None
    if normalized == "get_current_time":
        tool = ToolDefinition(
            name="get_current_time",
            description=augment_builtin_tool_description(
                "get_current_time",
                "Get the current time, date, and weekday in the requested timezone.",
            ),
            tool_type=ToolTypeEnum.BUILTIN.value,
            parameters=[
                ToolParameter(
                    name="timezone_name",
                    type="string",
                    description=(
                        "Optional IANA timezone name like Asia/Shanghai or "
                        "America/Los_Angeles."
                    ),
                    required=False,
                ),
                ToolParameter(
                    name="format",
                    type="string",
                    description=(
                        "Optional strftime format string. Defaults to "
                        "%Y-%m-%d %H:%M:%S."
                    ),
                    required=False,
                ),
            ],
            config={"builtin_type": "get_current_time", "auto_injected": True},
            enabled=True,
            timeout=15,
            source_skill_name="get_current_time",
            source_skill_type=ToolTypeEnum.BUILTIN.value,
        )

    if tool is None:
        return None
    apply_tool_semantics(tool)
    return tool


def inject_baseline_runtime_builtins(
    *,
    result: Any,
    apply_tool_semantics: Callable[[ToolDefinition], None],
) -> None:
    existing_tool_names = {tool.name for tool in result.tools}
    existing_descriptor_names = {
        descriptor.name
        for descriptor in result.capability_descriptors
        if str(descriptor.kind or "").strip() == "capability_pack"
    }

    for tool_name in BASELINE_RUNTIME_BUILTINS:
        if tool_name in existing_tool_names:
            continue

        tool = build_baseline_builtin_tool(
            tool_name=tool_name,
            apply_tool_semantics=apply_tool_semantics,
        )
        if tool is None:
            continue

        result.tools.append(tool)
        result.tool_consent_modes.setdefault(tool.name, "auto")
        if tool_name not in existing_descriptor_names:
            result.capability_descriptors.append(
                CapabilityDescriptor(
                    name=tool_name,
                    kind="capability_pack",
                    source="system_baseline_builtin",
                    description=(
                        "System baseline builtin injected at runtime for "
                        "fast-lane time/date queries."
                    ),
                    metadata={
                        "auto_injected": True,
                        "resolved_tool_names": [tool.name],
                        "resolved_tool_count": 1,
                        "has_execution_tools": True,
                    },
                )
            )
            existing_descriptor_names.add(tool_name)
        existing_tool_names.add(tool.name)


def build_time_only_runtime_result(
    *,
    result_factory: Callable[[], Any],
    apply_tool_semantics: Callable[[ToolDefinition], None],
) -> Any:
    result = result_factory()
    inject_baseline_runtime_builtins(
        result=result,
        apply_tool_semantics=apply_tool_semantics,
    )
    return result


def resolve_builtin(
    *,
    skill: Any,
    config: dict[str, Any],
    result: Any,
    build_params_from_schema: Callable[[dict[str, Any] | None], list[ToolParameter]],
) -> None:
    # Internal-ops meta-tools are code-defined; the skill row is only a marker
    # 内部操作元工具由代码定义；技能记录仅作标记
    if str(config.get("builtin_type") or "").strip() == "internal_ops":
        from app.ai.internal_ops.tools import build_internal_ops_tool_definitions

        for tool in build_internal_ops_tool_definitions(skill=skill, config=config):
            result.tools.append(tool)
        return

    tools_config = config.get("tools")
    tool_type_override = config.get("tool_type", ToolTypeEnum.BUILTIN.value)

    if tools_config and isinstance(tools_config, list):
        for tool_cfg in tools_config:
            tool_name = tool_cfg.get("name", "")
            if not tool_name or str(tool_name).strip() in RUNTIME_BUILTINS:
                continue
            tool_params = build_params_from_schema(tool_cfg.get("parameters"))
            description = augment_builtin_tool_description(
                tool_name,
                tool_cfg.get("description", ""),
            )
            result.tools.append(
                ToolDefinition(
                    name=tool_name,
                    description=description,
                    tool_type=tool_type_override,
                    parameters=tool_params,
                    config=config,
                    enabled=True,
                    timeout=tool_cfg.get("timeout", skill.timeout),
                    source_skill_id=skill.id,
                    source_skill_name=skill.name,
                    source_skill_type=skill.type,
                )
            )
        return

    params = build_params_from_schema(skill.input_schema)
    if str(skill.name or "").strip() in RUNTIME_BUILTINS:
        return
    description = augment_builtin_tool_description(
        skill.name,
        skill.description or "",
    )
    result.tools.append(
        ToolDefinition(
            name=skill.name,
            description=description,
            tool_type=tool_type_override,
            parameters=params,
            config=config,
            enabled=True,
            timeout=skill.timeout,
            source_skill_id=skill.id,
            source_skill_name=skill.name,
            source_skill_type=skill.type,
        )
    )
