"""
页面操作执行器

通过 WebSocket 向前端下发页面操作指令，等待结果回传，返回 ToolResult。
依赖 ExecutionContext.page_session_id 定位前端页面实例。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.page_operation")


class PageOperationExecutor(BaseToolExecutor):
    """
    页面操作执行器

    通过 Socket.IO 向 page_session:{id} 房间下发 page_operation_invoke 事件，
    等待前端执行操作并通过 page_operation_result 回传结果。

    LLM 调用参数:
        - page_key: str — 页面标识（pageContextKey）
        - operation_name: str — 操作名称
        - params: dict — 操作参数（可选）
        - requires_confirmation: bool — 是否需要用户确认（可选，默认 false）
    """

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        """通过 WebSocket 下发操作并等待结果"""
        start = time.perf_counter()

        # 检查 page_session_id
        if not context or not context.page_session_id:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error="No page_session_id available. Cannot invoke page operation without an active page session.",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        page_key = arguments.get("page_key", "")
        operation_name = arguments.get("operation_name", "")
        params = arguments.get("params") or {}
        requires_confirmation = bool(arguments.get("requires_confirmation", False))

        if not page_key or not operation_name:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error="Both 'page_key' and 'operation_name' are required.",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        # 通过 WebSocket 下发操作
        from app.sio.page_session import invoke_page_operation

        logger.info(
            "Invoking page operation: page_key=%s op=%s page_session=%s",
            page_key, operation_name, context.page_session_id,
        )

        result = await invoke_page_operation(
            page_session_id=context.page_session_id,
            page_key=page_key,
            operation_name=operation_name,
            params=params,
            requires_confirmation=requires_confirmation,
        )

        duration_ms = int((time.perf_counter() - start) * 1000)
        success = bool(result.get("success", False))
        message = result.get("message", "")
        error_type = result.get("error_type", "")

        if success:
            logger.info(
                "Page operation succeeded: page_key=%s op=%s duration=%dms",
                page_key, operation_name, duration_ms,
            )
            output = f"Operation '{operation_name}' executed successfully on page '{page_key}'."
            if message:
                output += f" Result: {message}"
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=output,
                duration_ms=duration_ms,
            )

        # 失败情况
        logger.warning(
            "Page operation failed: page_key=%s op=%s error_type=%s message=%s duration=%dms",
            page_key, operation_name, error_type, message, duration_ms,
        )
        error_msg = f"Operation '{operation_name}' failed on page '{page_key}'."
        if error_type == "timeout":
            error_msg = f"Operation '{operation_name}' timed out. The user may not be on page '{page_key}'."
        elif error_type == "pending_confirmation":
            error_msg = f"Operation '{operation_name}' requires user confirmation. Awaiting user approval."
        elif message:
            error_msg += f" Reason: {message}"

        return ToolResult(
            tool_call_id=tool_call_id,
            name=definition.name,
            success=False,
            error=error_msg,
            duration_ms=duration_ms,
        )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """校验参数：page_key 和 operation_name 必填"""
        return bool(arguments.get("page_key")) and bool(arguments.get("operation_name"))


__all__ = ["PageOperationExecutor"]
