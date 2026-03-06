"""
页面上下文执行器

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

# page_data 输出给 LLM 的最大字符数（截断保护）
MAX_OUTPUT_CHARS = 6000

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.page_context")

# 页面上下文变量键名
PAGE_CONTEXT_KEY = SHARED_PAGE_CONTEXT_KEY


class PageContextExecutor(BaseToolExecutor):
    """
    页面上下文执行器

    从 ExecutionContext.variables['page_context'] 读取前端传入的页面信息，
    格式化后返回给 LLM，使其了解用户当前所在页面。

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
        """从上下文变量读取页面信息并返回"""
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

        # 构建结构化输出
        parts: list[str] = []

        page_key = page_ctx.get("page_key", "")
        page_title = page_ctx.get("page_title", "")
        page_data = page_ctx.get("page_data")

        if page_key:
            parts.append(f"Page: {page_key}")
        if page_title:
            parts.append(f"Title: {page_title}")
        if page_data and isinstance(page_data, dict):
            data_str = json.dumps(page_data, ensure_ascii=False, default=str)
            if len(data_str) > MAX_OUTPUT_CHARS:
                data_str = data_str[:MAX_OUTPUT_CHARS] + "... [truncated]"
                logger.warning(
                    "page_data truncated: original %d chars, limit %d",
                    len(json.dumps(page_data, ensure_ascii=False, default=str)),
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
        """页面上下文工具不需要参数校验"""
        return True


__all__ = ["PageContextExecutor"]
