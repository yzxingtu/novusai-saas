"""
Tool Schema Enhancer / 工具 Schema 动态增强器

Dynamically enhances tool definitions with runtime context before sending to LLM.
在发送给 LLM 之前，根据运行时上下文动态增强工具定义。

Primary use-case: inject ``enum`` (valid operation names) and ``default`` (current page_key)
into the ``invoke_page_operation`` tool so the LLM is structurally constrained to produce
valid calls. / 主要用途：向 invoke_page_operation 注入 enum 与 default，约束 LLM 产出合法调用。
"""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition
from app.core.logging import LogManager
from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY

logger = LogManager.get_logger("ai.tool.enhancer")

_TARGET_TOOL = "invoke_page_operation"


def enhance_tools_with_page_context(
    tools: list[ToolDefinition],
    input_variables: dict[str, Any] | None,
) -> None:
    """Mutate *tools* in-place: add ``enum`` / ``default`` to invoke_page_operation. / 原地增强 *tools*：为 invoke_page_operation 添加 enum 与 default。无页面上下文时安全返回。"""
    if not input_variables:
        return

    page_ctx = input_variables.get(PAGE_CONTEXT_KEY)
    if not isinstance(page_ctx, dict):
        return

    page_key = (page_ctx.get("page_key") or "").strip()
    page_data = page_ctx.get("page_data")
    if not isinstance(page_data, dict):
        return

    raw_ops = page_data.get("available_operations")
    if not isinstance(raw_ops, list) or not raw_ops:
        return

    op_names: list[str] = [
        o["name"] for o in raw_ops if isinstance(o, dict) and o.get("name")
    ]
    if not op_names:
        return

    tool_def: ToolDefinition | None = None
    for t in tools:
        if t.name == _TARGET_TOOL:
            tool_def = t
            break
    if tool_def is None:
        return

    for param in tool_def.parameters:
        if param.name == "operation_name":
            param.enum = op_names
            param.description = "The operation to execute. Pick one from the enum list."
        elif param.name == "page_key" and page_key:
            param.default = page_key

    logger.debug(
        "Enhanced {}: page_key={} ops={}",
        _TARGET_TOOL,
        page_key,
        op_names,
    )


__all__ = ["enhance_tools_with_page_context"]
