"""
Page Context Executor
页面上下文执行器

Reads page_context info from ExecutionContext.variables
and returns it to the LLM to enable page-aware capabilities.
从 ExecutionContext.variables 中读取 page_context 信息，
返回给 LLM 以实现页面感知能力。
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.logging import LogManager
from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY as SHARED_PAGE_CONTEXT_KEY, PageContext

# Maximum characters of page_data output to LLM (truncation protection)
# page_data 输出给 LLM 的最大字符数（截断保护）
MAX_OUTPUT_CHARS = 6000

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.page_context")

# Page context variable key name / 页面上下文变量键名
PAGE_CONTEXT_KEY = SHARED_PAGE_CONTEXT_KEY


class PageContextExecutor(BaseToolExecutor):
    """
    Page context executor.
    页面上下文执行器。

    Reads page info passed by the frontend from ExecutionContext.variables['page_context'],
    formats it and returns to LLM so it knows which page the user is currently on.
    从 ExecutionContext.variables['page_context'] 读取前端传入的页面信息，
    格式化后返回给 LLM，使其了解用户当前所在页面。

    Unified variable structure (across Router and standard chat pipeline):
    统一变量结构（贯穿 Router 与标准聊天链路）:
        {
            "page_key": "tenant.agent.detail",
            "page_title": "智能体详情",
            "page_data": {"agent_id": 42, "agent_name": "客服助手", ...}
        }
    """

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        """Read page info from context variables and return / 从上下文变量读取页面信息并返回"""
        start = time.perf_counter()

        if not context or not context.variables:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output="No page context available.",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        page_ctx = PageContext.normalize(context.variables.get(PAGE_CONTEXT_KEY))
        if not page_ctx:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output="No page context available.",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        # Build structured output with enhanced semantic information
        # 构建含增强语义信息的结构化输出
        parts: list[str] = []

        page_key = page_ctx.get("page_key", "")
        page_title = page_ctx.get("page_title", "")
        page_data = page_ctx.get("page_data")

        if page_key:
            parts.append(f"Page: {page_key}")
        if page_title:
            parts.append(f"Title: {page_title}")

        if page_data and isinstance(page_data, dict):
            # Extract and present semantic fields prominently
            # 将语义字段突出展示
            entity_name = page_data.get("entity_name")
            entity_desc = page_data.get("entity_description")
            form_purpose = page_data.get("form_purpose")
            form_is_open = page_data.get("form_is_open")

            if entity_name:
                parts.append(f"Entity: {entity_name}")
            if entity_desc:
                parts.append(f"Description: {entity_desc}")
            if form_purpose and isinstance(form_purpose, dict):
                purpose_parts = []
                if form_purpose.get("create"):
                    purpose_parts.append(f"Create: {form_purpose['create']}")
                if form_purpose.get("edit"):
                    purpose_parts.append(f"Edit: {form_purpose['edit']}")
                if purpose_parts:
                    parts.append(f"Form Purpose: {'; '.join(purpose_parts)}")
            if form_is_open:
                parts.append("Form Status: OPEN (use get_form_state to inspect current values)")

            # Present visual_state concisely
            visual = page_data.get("visual_state")
            if visual and isinstance(visual, dict):
                vs_parts = [f"URL: {visual.get('url', '')}"]
                if visual.get("has_modal") or visual.get("has_drawer"):
                    overlays = visual.get("open_overlays", [])
                    if overlays and isinstance(overlays, list):
                        overlay_desc = ", ".join(
                            f"{o.get('type', '?')}({o.get('title', '?')})"
                            for o in overlays[:5] if isinstance(o, dict)
                        )
                        vs_parts.append(f"Overlays: {overlay_desc}")
                    else:
                        if visual.get("has_modal"):
                            vs_parts.append("Modal: open")
                        if visual.get("has_drawer"):
                            vs_parts.append("Drawer: open")
                parts.append(f"Visual: {' | '.join(vs_parts)}")

            # Present list_summary if available
            list_summary = page_data.get("list_summary")
            if list_summary and isinstance(list_summary, dict):
                total_rows = list_summary.get("total_rows", 0)
                sample_rows = list_summary.get("sample_rows", [])
                parts.append(f"List: {total_rows} total rows, {len(sample_rows)} sample rows shown")
                if sample_rows and isinstance(sample_rows, list):
                    for i, row in enumerate(sample_rows[:3]):
                        if isinstance(row, dict):
                            row_str = ", ".join(f"{k}={v}" for k, v in list(row.items())[:4])
                            parts.append(f"  [{i + 1}] {row_str}")

            # Build guidance for form operations
            # 构建表单操作指引
            form_fields = page_data.get("form_fields")
            ops = page_data.get("available_operations")
            if form_fields and isinstance(form_fields, dict):
                parts.append(f"Form Fields ({len(form_fields)}):")
                for field_name, desc in form_fields.items():
                    if not isinstance(desc, dict):
                        continue
                    comp = desc.get("component", "input")
                    required = " [REQUIRED]" if desc.get("required") else ""
                    opts_info = ""
                    options = desc.get("options")
                    if options and isinstance(options, list):
                        opt_labels = [str(o.get("label", o.get("value", ""))) for o in options[:8]]
                        opts_info = f" options=[{', '.join(opt_labels)}]"
                        if len(options) > 8:
                            opts_info = opts_info[:-1] + f", ... +{len(options) - 8} more]"
                    elif desc.get("optionsSource") == "remote":
                        opts_info = " (remote options, use get_form_options to fetch)"
                    constraints_info = ""
                    constraints = desc.get("constraints")
                    if constraints and isinstance(constraints, dict):
                        c_parts = []
                        for ck, cv in constraints.items():
                            c_parts.append(f"{ck}={cv}")
                        if c_parts:
                            constraints_info = f" ({', '.join(c_parts)})"
                    parts.append(
                        f"  - {field_name}: {desc.get('description', '')} "
                        f"[{comp}:{desc.get('type', 'string')}]{required}{opts_info}{constraints_info}"
                    )

            # Add operation workflow guidance if operations are available
            # 如果有可用操作，添加操作流程指引
            if ops and isinstance(ops, list):
                op_names = [o.get("name", "") for o in ops if isinstance(o, dict)]
                has_form_ops = any(
                    n in op_names
                    for n in ("create_record", "edit_record", "fill_form")
                )
                if has_form_ops:
                    parts.append("")
                    parts.append("## Agent Loop — Form Operation Workflow:")
                    parts.append("Execute ALL steps in sequence WITHOUT waiting for user input between steps:")
                    parts.append("1. Call create_record/edit_record to open the form")
                    parts.append("2. Immediately call get_form_state to inspect current field values and schema")
                    parts.append("3. Immediately call fill_form to fill ALL fields with intelligent values")
                    parts.append("4. Check fill_form result field_feedback for mismatches, retry if needed")
                    parts.append("5. User reviews the pre-filled form and submits manually")
                    parts.append("IMPORTANT: Do NOT stop after step 1. Continue all steps in this single turn.")

            # Serialize remaining page_data (exclude already-presented fields)
            # 序列化剩余 page_data（排除已展示的字段）
            presented_keys = {
                "entity_name", "entity_description", "form_purpose",
                "form_is_open", "form_fields", "available_operations",
                "visual_state", "list_summary", "source",
            }
            remaining = {k: v for k, v in page_data.items() if k not in presented_keys}
            if remaining:
                data_str = json.dumps(remaining, ensure_ascii=False, default=str)
                if len(data_str) > MAX_OUTPUT_CHARS:
                    data_str = data_str[:MAX_OUTPUT_CHARS] + "... [truncated]"
                    logger.warning(
                        "page_data truncated: original %d chars, limit %d",
                        len(json.dumps(remaining, ensure_ascii=False, default=str)),
                        MAX_OUTPUT_CHARS,
                    )
                parts.append(f"Data: {data_str}")

        output = "\n".join(parts) if parts else "No page context available."
        duration_ms = int((time.perf_counter() - start) * 1000)

        logger.info(
            "Page context resolved: page_key=%s",
            page_ctx.get("page_key", "unknown") if isinstance(page_ctx, dict) else "raw",
        )

        return ToolResult(
            tool_call_id=tool_call_id,
            name=definition.name,
            success=True,
            output=output,
            duration_ms=duration_ms,
        )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """Page context tool requires no parameter validation
        页面上下文工具不需要参数校验"""
        return True


__all__ = ["PageContextExecutor"]
