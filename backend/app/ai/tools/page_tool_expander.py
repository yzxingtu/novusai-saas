"""
Page Tool Expander / 页面工具展开器

Expands dedicated editor tools for rich-text/document pages before tool optimization.
When page_context has available_operations with editor ops (get_editor_html, replace_section, etc.),
injects pageop_* tools so the LLM calls them directly instead of invoke_page_operation.
富文本/文档编辑页时，根据 available_operations 展开专用 pageop_* tools，模型可直接调用。
"""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition, ToolParameter
from app.core.logging import LogManager
from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY

logger = LogManager.get_logger("ai.tool.page_expander")

# Editor ops that get expanded as dedicated tools (when present in available_operations)
# 展开为专用工具的编辑操作（当 available_operations 中存在时）
EDITOR_OPS_TO_EXPAND: frozenset[str] = frozenset({
    "get_editor_html",
    "get_editor_text",
    "replace_section",
    "replace_content",
    "insert_content",
    "append_content",
    "update_title",
    "insert_table",
    "manage_link",
})

PREFIX = "pageop_"


def _params_to_parameters(op_params: dict[str, Any] | None) -> list[ToolParameter]:
    """
    Convert frontend op.params schema to ToolParameter list.
    将前端 op.params 转换为 ToolParameter 列表。
    """
    if not op_params:
        return []
    params: list[ToolParameter] = []
    for name, spec in op_params.items():
        if not isinstance(spec, dict):
            continue
        param_type = spec.get("type", "string")
        desc = spec.get("description", "")
        required = bool(spec.get("required", True))
        enum_val = spec.get("enum")
        default_val = spec.get("default")
        params.append(ToolParameter(
            name=name,
            type=str(param_type),
            description=str(desc) if desc else "",
            required=required,
            enum=list(enum_val) if isinstance(enum_val, list) else None,
            default=default_val,
        ))
    return params


def expand_editor_tools(
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> list[ToolDefinition]:
    """
    Expand dedicated editor tools for rich-text pages. Inserts pageop_* tools
    when page_context.available_operations contains editor ops.
    富文本页时展开专用工具。当 available_operations 含编辑操作时注入 pageop_* tools。

    Runs BEFORE tool optimization so expanded tools can be optimized/filtered.
    在工具优化之前执行，以便展开的工具参与优化筛选。
    """
    if not input_variables:
        return tools

    page_ctx = input_variables.get(PAGE_CONTEXT_KEY)
    if not isinstance(page_ctx, dict):
        return tools

    page_key = (page_ctx.get("page_key") or "").strip()
    page_data = page_ctx.get("page_data")
    if not isinstance(page_data, dict) or not page_key:
        return tools

    raw_ops = page_data.get("available_operations")
    if not isinstance(raw_ops, list) or not raw_ops:
        return tools

    # Build op map: name -> {label, description, params, readonly}
    op_map: dict[str, dict[str, Any]] = {}
    for o in raw_ops:
        if not isinstance(o, dict) or not o.get("name"):
            continue
        name = str(o["name"])
        if name not in EDITOR_OPS_TO_EXPAND:
            continue
        op_map[name] = {
            "label": o.get("label", name),
            "description": o.get("description", ""),
            "params": o.get("params"),
            "readonly": bool(o.get("readonly", False)),
        }

    if not op_map:
        return tools

    # Build expanded tool definitions
    expanded: list[ToolDefinition] = []
    for op_name in sorted(op_map.keys()):
        meta = op_map[op_name]
        tool_name = f"{PREFIX}{op_name}"
        # Avoid duplicate if already present
        if any(t.name == tool_name for t in tools):
            continue

        params_list = _params_to_parameters(meta.get("params"))
        desc = str(meta.get("description", "") or meta.get("label", op_name))

        expanded.append(ToolDefinition(
            name=tool_name,
            description=desc,
            tool_type="builtin",  # Executed via sandbox redirect to invoke_page_operation
            parameters=params_list,
            config={"underlying_operation": op_name, "page_tool": True},
        ))

    if expanded:
        logger.info(
            "PageToolExpander: page_key={} expanded {} editor tools: {}",
            page_key,
            len(expanded),
            [t.name for t in expanded],
        )
        return tools + expanded

    return tools


__all__ = ["expand_editor_tools", "EDITOR_OPS_TO_EXPAND", "PREFIX"]
