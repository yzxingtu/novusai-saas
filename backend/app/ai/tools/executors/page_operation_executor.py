"""
Page Operation Executor. / 页面操作执行器。

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
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import ActionLevelEnum, ActionStatusEnum, ActionTypeEnum
from app.services.ai.action_log_service import resolve_action_level, write_ai_action_log

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.page_operation")


def _extract_screenshot_attachment(
    result_data: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Extract screenshot attachment metadata from frontend page op result / 从前端页面操作结果中提取截图附件元数据"""
    if not isinstance(result_data, dict):
        return None
    attachment = result_data.get("attachment")
    if not isinstance(attachment, dict):
        return None

    att_type = str(attachment.get("type") or "").strip().lower()
    att_url = str(attachment.get("url") or "").strip()
    if att_type != "image" or not att_url:
        return None

    normalized: dict[str, Any] = {
        "type": "image",
        "url": att_url,
    }
    attachment_id = attachment.get("attachment_id")
    if isinstance(attachment_id, int) and attachment_id > 0:
        normalized["attachment_id"] = attachment_id
    if attachment.get("name"):
        normalized["name"] = attachment.get("name")
    if attachment.get("mime_type"):
        normalized["mime_type"] = attachment.get("mime_type")
    return normalized


class PageOperationExecutor(BaseToolExecutor):
    """
    Page operation executor. / 页面操作执行器。

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
                error=_("page_operation.error.both_required"),
                duration_ms=int((time.perf_counter() - start) * 1000),
                error_type="invalid_input",
            )

        runtime_model_capabilities = (
            context.variables.get("runtime_model_capabilities", {})
            if context and isinstance(context.variables, dict)
            else {}
        )
        if (
            operation_name == "capture_screenshot"
            and runtime_model_capabilities.get("supports_vision") is False
        ):
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("page_operation.error.screenshot_requires_vision"),
                duration_ms=int((time.perf_counter() - start) * 1000),
                error_type="vision_not_supported",
            )

        # Resolve page_session_id: prefer fresh from active tracking (recover after reconnect) / 上文为英文说明 / English above
        from app.sio.page_session import get_active_session_id, invoke_page_operation

        session_id = None
        if context:
            session_id = context.page_session_id
            if not session_id:
                session_id = get_active_session_id(
                    context.user_id,
                    page_key,
                    context.user_role,
                )
            else:
                fresh_id = get_active_session_id(
                    context.user_id,
                    page_key,
                    context.user_role,
                )
                if fresh_id and fresh_id != session_id:
                    logger.info(
                        "Page operation keeps explicit session_id over active mapping: "
                        "page_key={} explicit={} active={}",
                        page_key,
                        session_id,
                        fresh_id,
                    )

        if not session_id:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("page_operation.error.no_session"),
                duration_ms=int((time.perf_counter() - start) * 1000),
                error_type="session_not_found",
            )

        logger.info(
            "Invoking page operation: page_key={} op={} page_session={}",
            page_key,
            operation_name,
            session_id,
        )

        result = await invoke_page_operation(
            page_session_id=session_id,
            page_key=page_key,
            operation_name=operation_name,
            params=params,
            requires_confirmation=requires_confirmation,
            tool_call_id=tool_call_id,
        )

        duration_ms = int((time.perf_counter() - start) * 1000)
        success = bool(result.get("success", False))
        invoke_id = result.get("invoke_id")
        message = result.get("message", "")
        error_type = result.get("error_type", "")
        result_data = result.get("data")
        screenshot_attachment = (
            _extract_screenshot_attachment(result_data)
            if operation_name == "capture_screenshot"
            else None
        )

        async def audit_page_operation(
            status: str,
            *,
            error_message: str | None = None,
        ) -> None:
            if not context or not context.db:
                return
            try:
                await write_ai_action_log(
                    context.db,
                    tenant_id=context.tenant_id,
                    agent_id=context.agent_id,
                    operator_id=context.user_id,
                    skill_id=context.skill_id,
                    action_name=operation_name,
                    action_type=(
                        ActionTypeEnum.CONFIRM.value
                        if error_type in {"pending_confirmation", "user_cancelled"}
                        else ActionTypeEnum.ACTION.value
                    ),
                    action_level=resolve_action_level(
                        operation_name,
                        default=(
                            ActionLevelEnum.SAFE_WRITE.value
                            if requires_confirmation
                            else ActionLevelEnum.READ.value
                        ),
                    ),
                    request_data={
                        "page_session_id": session_id,
                        "page_key": page_key,
                        "operation_name": operation_name,
                        "params": params,
                        "requires_confirmation": requires_confirmation,
                    },
                    response_data={
                        "invoke_id": invoke_id or None,
                        "message": message,
                        "error_type": error_type or None,
                        "data": result_data,
                    },
                    status=status,
                    error_message=error_message,
                    duration_ms=duration_ms,
                )
            except Exception as exc:
                logger.warning(
                    "Failed to write page operation audit log: {}",
                    str(exc),
                )

        if success:
            logger.info(
                "Page operation succeeded: page_key={} op={} duration={}ms",
                page_key,
                operation_name,
                duration_ms,
            )
            await audit_page_operation(ActionStatusEnum.SUCCESS.value)
            output = f"Operation '{operation_name}' executed successfully on page '{page_key}'."
            if message:
                output += f" Result: {message}"
            if screenshot_attachment:
                output += "\n" + _("page_operation.hint.screenshot_attached")
            elif result_data and isinstance(result_data, dict):
                import json

                data_str = json.dumps(result_data, ensure_ascii=False, default=str)
                if len(data_str) <= 4000:
                    output += f"\nData: {data_str}"
                elif operation_name == "get_editor_html" and "html" in result_data:
                    # Large document: still expose html so LLM can use it for replace_section old_html / 上文为英文说明 / English above
                    html_content = result_data.get("html", "") or ""
                    max_html_chars = 12000
                    if len(html_content) > max_html_chars:
                        html_content = (
                            html_content[:max_html_chars] + "\n... (truncated)"
                        )
                    hint = result_data.get("_hint") or _(
                        "page_operation.hint.replace_section"
                    )
                    output += f"\n{hint}\nHTML:\n{html_content}"
                    output += "\n[Do NOT echo this HTML to the user. Use it internally for replace_section, then respond in natural language.]"
                # Agent Loop guidance: suggest next step based on context_diff / 上文为英文说明 / English above
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
                attachments=[screenshot_attachment] if screenshot_attachment else None,
                llm_follow_up_message=(
                    _("page_operation.hint.screenshot_follow_up")
                    if screenshot_attachment
                    else None
                ),
            )

        # Failure case with recovery guidance / 失败情况，含恢复指引
        logger.warning(
            "Page operation failed: page_key={} op={} error_type={} message={} duration={}ms",
            page_key,
            operation_name,
            error_type,
            message,
            duration_ms,
        )
        error_msg = _("page_operation.error.failed", op=operation_name, page=page_key)
        if error_type == "timeout":
            error_msg = _(
                "page_operation.error.timeout_hint", op=operation_name, page=page_key
            )
        elif error_type == "pending_confirmation":
            error_msg = _(
                "page_operation.error.pending_confirmation", op=operation_name
            )
        elif error_type == "target_not_found":
            error_msg = _(
                "page_operation.error.target_not_found_next", message=message or ""
            )
        elif error_type == "non_unique_match":
            error_msg = _("page_operation.error.non_unique_next", message=message or "")
        elif error_type == "invalid_html":
            error_msg = _(
                "page_operation.error.invalid_html_next", message=message or ""
            )
        elif message:
            error_msg += _("page_operation.error.reason_suffix", message=message)
        error_msg += "\n\n" + _("page_operation.error.no_echo")

        audit_status = ActionStatusEnum.FAILED.value
        if error_type == "pending_confirmation":
            audit_status = ActionStatusEnum.PENDING_CONFIRM.value
        elif error_type == "user_cancelled":
            audit_status = ActionStatusEnum.REJECTED.value
        await audit_page_operation(
            audit_status,
            error_message=message or error_msg,
        )

        return ToolResult(
            tool_call_id=tool_call_id,
            name=definition.name,
            success=False,
            error=error_msg,
            duration_ms=duration_ms,
            error_type=error_type or "execution_failed",
        )

    async def validate(
        self,
        _definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        """校验参数：page_key 和 operation_name 必填 / Validate parameters: page_key and operation_name are required."""
        return bool(arguments.get("page_key")) and bool(arguments.get("operation_name"))


__all__ = ["PageOperationExecutor"]
