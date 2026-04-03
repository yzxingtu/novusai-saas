"""
Page Tool Expander / 页面工具展开器

Expands dedicated pageop_* tools before tool optimization.
Supports both rich-text/document editor operations and high-frequency generic page operations,
so the LLM can call pageop_* directly instead of wrapping everything in invoke_page_operation.
在工具优化前展开专用 pageop_* 工具。
同时支持富文本/文档编辑操作与高频通用页面操作，减少模型对 invoke_page_operation 包装的依赖。
"""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition, ToolParameter
from app.core.logging import LogManager
from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY

logger = LogManager.get_logger("ai.tool.page_expander")

# Editor ops that get expanded as dedicated tools (when present in available_operations)
# 展开为专用工具的编辑操作（当 available_operations 中存在时）
EDITOR_OPS_TO_EXPAND: frozenset[str] = frozenset(
    {
        "get_editor_html",
        "get_editor_text",
        "replace_section",
        "replace_content",
        "insert_content",
        "append_content",
        "update_title",
        "insert_table",
        "manage_link",
    }
)

# High-frequency generic page ops that also benefit from dedicated tool schemas
# 高频通用页面操作也展开为专用工具，减少 invoke_page_operation 的参数包装错误
GENERIC_PAGE_OPS_TO_EXPAND: frozenset[str] = frozenset(
    {
        "capture_screenshot",
        "clear_search",
        "create_record",
        "edit_record",
        "fill_form",
        "get_form_options",
        "get_form_state",
        "go_to_page",
        "next_page",
        "prev_page",
        "read_row_detail",
        "read_visible_rows",
        "refresh_list",
        "search",
        "set_page_size",
        "submit_form",
        "validate_form",
    }
)

EXPANDABLE_PAGE_OPS: frozenset[str] = EDITOR_OPS_TO_EXPAND | GENERIC_PAGE_OPS_TO_EXPAND

PREFIX = "pageop_"


def _infer_schema_scalar_type(values: list[Any]) -> str | None:
    """Infer a JSON Schema scalar type from sample values / 根据样本值推断 JSON Schema 标量类型。"""
    normalized = [value for value in values if value is not None]
    if not normalized:
        return None
    if all(isinstance(value, bool) for value in normalized):
        return "boolean"
    if all(
        isinstance(value, int) and not isinstance(value, bool) for value in normalized
    ):
        return "integer"
    if all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        for value in normalized
    ):
        return "number"
    if all(isinstance(value, str) for value in normalized):
        return "string"
    return None


def _infer_array_items_schema(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Infer missing array.items schema from frontend hints / 根据前端提示推断缺失的 array.items schema。"""
    explicit_items = spec.get("items")
    if isinstance(explicit_items, dict) and explicit_items.get("type"):
        return dict(explicit_items)

    options = spec.get("options")
    if isinstance(options, list) and options:
        option_values = [
            option.get("value")
            for option in options
            if isinstance(option, dict) and "value" in option
        ]
        inferred_type = _infer_schema_scalar_type(option_values)
        if inferred_type:
            return {"type": inferred_type}

    default_value = spec.get("default")
    if default_value is None:
        default_value = spec.get("defaultValue")
    if isinstance(default_value, list) and default_value:
        inferred_type = _infer_schema_scalar_type(default_value)
        if inferred_type:
            return {"type": inferred_type}

    normalized_name = str(name or "").strip().lower()
    if normalized_name.endswith("_ids"):
        return {"type": "integer"}
    if normalized_name.endswith("_numbers"):
        return {"type": "number"}
    if normalized_name.endswith("_flags"):
        return {"type": "boolean"}

    return {"type": "string"}


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
        if default_val is None and "defaultValue" in spec:
            default_val = spec.get("defaultValue")
        items_schema = (
            _infer_array_items_schema(name, spec)
            if str(param_type) == "array"
            else None
        )
        params.append(
            ToolParameter(
                name=name,
                type=str(param_type),
                description=str(desc) if desc else "",
                required=required,
                enum=list(enum_val) if isinstance(enum_val, list) else None,
                default=default_val,
                items=items_schema,
            )
        )
    return params


def expand_page_tools(
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> list[ToolDefinition]:
    """
    Expand dedicated page tools. Inserts pageop_* tools when
    page_context.available_operations contains editor ops or common page ops.
    展开专用页面工具。当 available_operations 含编辑操作或高频页面操作时注入 pageop_* tools。

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

    # Build op map: name -> {label, description, params, readonly} / 上文为英文说明 / English above
    op_map: dict[str, dict[str, Any]] = {}
    for o in raw_ops:
        if not isinstance(o, dict) or not o.get("name"):
            continue
        name = str(o["name"])
        if name not in EXPANDABLE_PAGE_OPS:
            continue
        op_map[name] = {
            "label": o.get("label", name),
            "description": o.get("description", ""),
            "params": o.get("params"),
            "readonly": bool(o.get("readonly", False)),
        }

    if not op_map:
        return tools

    # Build expanded tool definitions / 上文为英文说明 / English above
    expanded: list[ToolDefinition] = []
    for op_name in sorted(op_map.keys()):
        meta = op_map[op_name]
        tool_name = f"{PREFIX}{op_name}"
        # Avoid duplicate if already present / 上文为英文说明 / English above
        if any(t.name == tool_name for t in tools):
            continue

        params_list = _params_to_parameters(meta.get("params"))
        desc = str(meta.get("description", "") or meta.get("label", op_name))
        label = str(meta.get("label", op_name) or op_name)
        capability_tags = [
            "页面操作",
            "page operation",
            op_name,
            label,
        ]
        if desc:
            capability_tags.append(desc)
        capability_tags.append("只读" if meta.get("readonly") else "可写")

        expanded.append(
            ToolDefinition(
                name=tool_name,
                description=desc,
                tool_type="builtin",  # Executed via sandbox redirect to invoke_page_operation  # 补充说明 / note
                parameters=params_list,
                config={"underlying_operation": op_name, "page_tool": True},
                semantic_family="page_ops",
                semantic_tags=capability_tags,
            )
        )

    if expanded:
        logger.info(
            "PageToolExpander: page_key={} expanded {} page tools: {}",
            page_key,
            len(expanded),
            [t.name for t in expanded],
        )
        return tools + expanded

    return tools


__all__ = [
    "EDITOR_OPS_TO_EXPAND",
    "EXPANDABLE_PAGE_OPS",
    "GENERIC_PAGE_OPS_TO_EXPAND",
    "PREFIX",
    "expand_page_tools",
]
