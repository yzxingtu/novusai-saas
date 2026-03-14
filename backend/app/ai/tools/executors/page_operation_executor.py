"""
Page Operation Executor
页面操作执行器

Sends page operation commands to the frontend via WebSocket, waits for result callback, and returns ToolResult.
通过 WebSocket 向前端下发页面操作指令，等待结果回传，返回 ToolResult。
Depends on ExecutionContext.page_session_id to locate the frontend page instance.
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
    Page operation executor.
    页面操作执行器。

    Sends page_operation_invoke event to the page_session:{id} room via Socket.IO,
    waits for the frontend to execute the operation and return results via page_operation_result.
    通过 Socket.IO 向 page_session:{id} 房间下发 page_operation_invoke 事件，
    等待前端执行操作并通过 page_operation_result 回传结果。

    LLM call arguments / LLM 调用参数:
        - page_key: str — Page identifier (pageContextKey) / 页面标识
        - operation_name: str — Operation name / 操作名称
        - params: dict — Operation parameters (optional) / 操作参数（可选）
        - requires_confirmation: bool — Whether user confirmation is needed (optional, default false)
          是否需要用户确认（可选，默认 false）
    """

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        """Send operation via WebSocket and wait for result / 通过 WebSocket 下发操作并等待结果"""
        start = time.perf_counter()

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

        # Resolve page_session_id: prefer fresh from active tracking (recover after reconnect)
        from app.sio.page_session import get_active_session_id, invoke_page_operation

        session_id = None
        if context:
            fresh_id = get_active_session_id(
                context.user_id,
                page_key,
                context.user_role,
            )
            session_id = fresh_id or context.page_session_id

        if not session_id:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error="No page_session_id available. Cannot invoke page operation without an active page session.",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        logger.info(
            "Invoking page operation: page_key=%s op=%s page_session=%s",
            page_key, operation_name, session_id,
        )

        result = await invoke_page_operation(
            page_session_id=session_id,
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
            result_data = result.get("data")
            if result_data and isinstance(result_data, dict):
                import json
                data_str = json.dumps(result_data, ensure_ascii=False, default=str)
                if len(data_str) <= 4000:
                    output += f"\nData: {data_str}"
                # Agent Loop guidance: suggest next step based on context_diff
                context_diff = result_data.get("context_diff", {})
                if context_diff.get("form_opened"):
                    output += (
                        "\n\n[Agent Loop] Form opened. "
                        "Next: call get_form_state to inspect current values, "
                        "then call fill_form with intelligent values."
                    )
                elif context_diff.get("form_closed"):
                    output += (
                        "\n\n[Agent Loop] Form closed. "
                        "Call refresh_list to see updated data."
                    )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=output,
                duration_ms=duration_ms,
            )

        # Failure case / 失败情况
        logger.warning(
            "Page operation failed: page_key=%s op=%s error_type=%s message=%s duration=%dms",
            page_key, operation_name, error_type, message, duration_ms,
        )
        error_msg = f"Operation '{operation_name}' failed on page '{page_key}'."
        if error_type == "timeout":
            error_msg = (
                f"Operation '{operation_name}' timed out (30s). "
                f"The WebSocket connection to page '{page_key}' may be broken. "
                "Do NOT retry this operation — tell the user the operation failed "
                "and suggest they refresh the page, then try again."
            )
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
        """Validate parameters: page_key and operation_name are required
        校验参数：page_key 和 operation_name 必填"""
        return bool(arguments.get("page_key")) and bool(arguments.get("operation_name"))


__all__ = ["PageOperationExecutor"]
