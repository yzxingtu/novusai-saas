"""
Page Context Executor. / 页面上下文执行器。

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
from app.schemas.ai.agent_chat import (
    PAGE_CONTEXT_KEY as SHARED_PAGE_CONTEXT_KEY,
)
from app.schemas.ai.agent_chat import (
    PageContext,
)

# Maximum characters of page_data output to LLM (truncation protection)
# page_data 输出给 LLM 的最大字符数（截断保护）
MAX_OUTPUT_CHARS = 6000

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.page_context")

# Page context variable key name / 页面上下文变量键名
PAGE_CONTEXT_KEY = SHARED_PAGE_CONTEXT_KEY
FALLBACK_PAGE_CONTEXT_SOURCES = {
    "dom_snapshot": "DOM snapshot fallback (best-effort, may be incomplete)",
    "minimal_fallback": "Minimal fallback (best-effort, limited structure)",
}


def _summarize_operation_params(params: Any) -> str:
    """Build a concise parameter summary for available_operations / 为 available_operations 构建精简参数摘要。"""
    if not isinstance(params, dict) or not params:
        return ""

    entries: list[str] = []
    for param_name, schema in list(params.items())[:8]:
        if not isinstance(schema, dict):
            entries.append(str(param_name))
            continue

        param_type = schema.get("type")
        type_suffix = f":{param_type}" if param_type else ""
        required_suffix = " required" if schema.get("required") else ""
        enum_values = schema.get("enum")
        enum_suffix = ""
        if isinstance(enum_values, list) and enum_values:
            preview = ", ".join(str(item) for item in enum_values[:4])
            if len(enum_values) > 4:
                preview += f", +{len(enum_values) - 4} more"
            enum_suffix = f" enum[{preview}]"
        entries.append(f"{param_name}{type_suffix}{required_suffix}{enum_suffix}")

    if len(params) > 8:
        entries.append(f"... +{len(params) - 8} more")

    return ", ".join(entries)


class PageContextExecutor(BaseToolExecutor):
    """
    Page context executor. / 页面上下文执行器。

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
        _arguments: dict[str, Any],
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
            source = str(page_data.get("source") or "").strip()

            if entity_name:
                parts.append(f"Entity: {entity_name}")
            if entity_desc:
                parts.append(f"Description: {entity_desc}")
            if source in FALLBACK_PAGE_CONTEXT_SOURCES:
                parts.append(
                    "Context Source: "
                    f"{source} ({FALLBACK_PAGE_CONTEXT_SOURCES[source]})"
                )
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

            # Present visual_state concisely / 上文为英文说明 / English above
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

            # Present list_summary if available / 上文为英文说明 / English above
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

            stat_cards = page_data.get("stat_cards")
            if stat_cards and isinstance(stat_cards, list):
                metric_parts: list[str] = []
                for card in stat_cards[:4]:
                    if not isinstance(card, dict):
                        continue
                    label = str(card.get("label", "")).strip()
                    value = str(card.get("value", "")).strip()
                    if label and value:
                        metric_parts.append(f"{label}={value}")
                if metric_parts:
                    parts.append(f"Key Metrics: {' | '.join(metric_parts)}")

            detail_fields = page_data.get("detail_fields")
            if detail_fields and isinstance(detail_fields, list):
                detail_parts: list[str] = []
                for field in detail_fields[:6]:
                    if not isinstance(field, dict):
                        continue
                    label = str(field.get("label", "")).strip()
                    value = str(field.get("value", "")).strip()
                    if label and value:
                        detail_parts.append(f"{label}={value}")
                if detail_parts:
                    parts.append(f"Visible Details: {' | '.join(detail_parts)}")

            text_blocks = page_data.get("text_blocks")
            if text_blocks and isinstance(text_blocks, list):
                visible_texts = [
                    str(block).strip()
                    for block in text_blocks[:4]
                    if isinstance(block, str) and str(block).strip()
                ]
                if visible_texts:
                    parts.append("Visible Text Summary:")
                    for idx, block in enumerate(visible_texts, start=1):
                        parts.append(f"  [{idx}] {block}")

            overlays = page_data.get("overlays")
            if overlays and isinstance(overlays, list):
                overlay_parts: list[str] = []
                for overlay in overlays[:3]:
                    if not isinstance(overlay, dict):
                        continue
                    overlay_type = str(overlay.get("type", "")).strip() or "overlay"
                    title = str(overlay.get("title", "")).strip() or "Untitled"
                    summary = str(overlay.get("summary", "")).strip()
                    if summary:
                        overlay_parts.append(f"{overlay_type}({title}: {summary})")
                    else:
                        overlay_parts.append(f"{overlay_type}({title})")
                if overlay_parts:
                    parts.append(f"Active Overlays: {' | '.join(overlay_parts)}")

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

            has_editor = page_data.get("has_editor")
            if has_editor and ops and isinstance(ops, list):
                parts.append("")
                parts.append("## Available Editor Operations (use dedicated pageop_* tools):")
            elif ops and isinstance(ops, list):
                parts.append("")
                parts.append("## Available Page Operations:")

            if ops and isinstance(ops, list):
                mutation_ops = [
                    o for o in ops
                    if isinstance(o, dict) and not bool(o.get("readonly", False))
                ]
                readonly_ops = [
                    o for o in ops
                    if isinstance(o, dict) and bool(o.get("readonly", False))
                ]
                ordered_ops = mutation_ops + readonly_ops
                if mutation_ops:
                    mutation_names = [
                        str(o.get("name", ""))
                        for o in mutation_ops
                        if isinstance(o, dict) and o.get("name")
                    ]
                    parts.append(
                        "Writable Operations Available: "
                        + ", ".join(mutation_names)
                    )
                    parts.append(
                        "You ARE allowed to use writable page operations on this page. "
                        "Do not claim the page is read-only when these operations are present."
                    )

                for o in ordered_ops:
                    if not isinstance(o, dict) or not o.get("name"):
                        continue
                    op_name = str(o.get("name", ""))
                    op_label = str(o.get("label", "") or op_name)
                    op_desc = str(o.get("description", "") or op_label)
                    readonly = bool(o.get("readonly", False))
                    readonly_tag = "readonly" if readonly else "mutation"
                    param_summary = _summarize_operation_params(o.get("params"))
                    summary_suffix = f" params: {param_summary}" if param_summary else ""
                    parts.append(
                        f"  - {op_name} [{readonly_tag}] {op_label}: "
                        f"{op_desc}{summary_suffix}"
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
                    parts.append("Execute ALL applicable steps in sequence WITHOUT stopping at the first tool call:")
                    parts.append("1. Call create_record/edit_record to open the form")
                    parts.append("2. Immediately call get_form_state to inspect current values and schema")
                    parts.append("3. Immediately call fill_form to fill ALL relevant fields")
                    parts.append("4. If validate_form exists, call validate_form and fix any errors")
                    parts.append("5. If submit_form exists and the user asked you to create/update the record, call submit_form")
                    parts.append("6. Only wait for user review when the page explicitly requires confirmation or submit_form is unavailable")
                    parts.append("IMPORTANT: Do NOT answer 'only read operations are available' when create_record/edit_record/fill_form/submit_form exist.")

                parts.append("")
                parts.append("## Execution Discipline:")
                parts.append("If the latest user turn asks for multiple page operations, execute those operations in the requested order.")
                parts.append("Do NOT stop early and do NOT substitute screenshot analysis or free-form commentary for requested operations that are available as tools.")
                parts.append("If a newer user turn conflicts with an older temporary constraint such as 'read-only', 'do not write', or 'do not submit', follow the latest user turn unless the user explicitly keeps the older constraint in effect.")

            # Serialize remaining page_data (exclude already-presented fields)
            # 序列化剩余 page_data（排除已展示的字段）
            presented_keys = {
                "entity_name", "entity_description", "form_purpose",
                "form_is_open", "form_fields", "available_operations",
                "visual_state", "list_summary", "source", "stat_cards",
                "detail_fields", "text_blocks", "overlays",
            }
            remaining = {k: v for k, v in page_data.items() if k not in presented_keys}
            if remaining:
                data_str = json.dumps(remaining, ensure_ascii=False, default=str)
                if len(data_str) > MAX_OUTPUT_CHARS:
                    data_str = data_str[:MAX_OUTPUT_CHARS] + "... [truncated]"
                    logger.warning(
                        "page_data truncated: original {} chars, limit {}",
                        len(json.dumps(remaining, ensure_ascii=False, default=str)),
                        MAX_OUTPUT_CHARS,
                    )
                parts.append(f"Data: {data_str}")

        output = "\n".join(parts) if parts else "No page context available."
        duration_ms = int((time.perf_counter() - start) * 1000)

        logger.info(
            "Page context resolved: page_key={}",
            page_ctx.get("page_key", "unknown") if isinstance(page_ctx, dict) else "raw",
        )

        follow_up_message = (
            f"{output}\n\n"
            "You have already called get_page_context for this turn. "
            "Do not call get_page_context again unless the page visibly changed. "
            "Use the page information above to answer the user directly."
        )

        return ToolResult(
            tool_call_id=tool_call_id,
            name=definition.name,
            success=True,
            output=output,
            llm_follow_up_message=follow_up_message,
            duration_ms=duration_ms,
        )

    async def validate(
        self,
        _definition: ToolDefinition,
        _arguments: dict[str, Any],
    ) -> bool:
        """页面上下文工具不需要参数校验 / Page context tool requires no parameter validation."""
        return True


__all__ = ["PageContextExecutor"]
