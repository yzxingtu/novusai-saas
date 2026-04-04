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

from app.ai.prompt_contracts import render_prompt_contract
from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.agent import ActionLevelEnum, ActionStatusEnum, ActionTypeEnum
from app.enums.execution import (
    ExecutionDecisionScopeEnum,
    ExecutionDecisionStatusEnum,
    ExecutionDecisionSubjectEnum,
    ExecutionDecisionTypeEnum,
)
from app.schemas.ai.agent_chat import PAGE_CONTEXT_KEY as SHARED_PAGE_CONTEXT_KEY
from app.schemas.ai.agent_chat import PageContext
from app.services.ai.action_log_service import resolve_action_level, write_ai_action_log
from app.services.ai.execution_decision_service import ExecutionDecisionService
from app.services.ai.execution_trust_policy_service import (
    ExecutionTrustPolicyService,
)

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.page_operation")
PAGE_CONTEXT_TURN_SEEN_KEY = "_page_context_already_returned_this_turn"


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

        # Resolve page_session_id: prefer active tracking (reconnect recovery) / 解析 page_session_id：优先活跃追踪（断线恢复）
        from app.sio.page_session import get_active_session_id, invoke_page_operation

        session_id = None
        if context:
            current_page_context = (
                PageContext.normalize(context.variables.get(SHARED_PAGE_CONTEXT_KEY))
                if isinstance(context.variables, dict)
                else None
            )
            current_page_key = (
                str(current_page_context.get("page_key") or "").strip()
                if current_page_context
                else ""
            )
            recovered_session_id = get_active_session_id(
                context.user_id,
                page_key,
                context.user_role,
            )
            if context.page_session_id:
                session_id = context.page_session_id
                if (
                    page_key
                    and current_page_key
                    and page_key != current_page_key
                    and recovered_session_id
                ):
                    session_id = recovered_session_id
            else:
                session_id = recovered_session_id

        if not session_id:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("page_operation.error.no_session"),
                duration_ms=int((time.perf_counter() - start) * 1000),
                error_type="session_not_found",
            )

        auto_approved = bool(
            context
            and not requires_confirmation
            and isinstance(context.trust_policy_ref, dict)
            and ExecutionTrustPolicyService.allows_tool(
                tool_name=definition.name,
                tool_family=ExecutionTrustPolicyService.tool_family_for_name(
                    definition.name,
                ),
                policy_ref=context.trust_policy_ref,
            )
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
            auto_approved=auto_approved,
            tool_call_id=tool_call_id,
        )

        duration_ms = int((time.perf_counter() - start) * 1000)
        success = bool(result.get("success", False))
        invoke_id = result.get("invoke_id")
        message = result.get("message", "")
        error_type = result.get("error_type", "")
        result_data = result.get("data")
        decision_meta = (
            dict(result_data.get("_execution_decision"))
            if isinstance(result_data, dict)
            and isinstance(result_data.get("_execution_decision"), dict)
            else None
        )
        llm_result_data = (
            {
                key: value
                for key, value in result_data.items()
                if key != "_execution_decision"
            }
            if isinstance(result_data, dict)
            else result_data
        )
        if operation_name == "navigate_menu" and success and isinstance(
            llm_result_data, dict
        ):
            destination_ready = bool(llm_result_data.get("destination_ready"))
            can_auto_continue = bool(llm_result_data.get("can_auto_continue"))
            destination_ready_reason = str(
                llm_result_data.get("destination_ready_reason") or ""
            ).strip()
            if message:
                if not message.endswith(("。", ".", "！", "!")):
                    message = f"{message}。"
                if destination_ready and can_auto_continue:
                    message = f"{message}目标页面已就绪，可以继续执行操作。"
                elif destination_ready:
                    message = f"{message}目标页面已到达，但暂不自动继续执行下一步。"
                else:
                    message = f"{message}目标页面已到达，但尚未就绪。"

            llm_result_data["_navigation_completed"] = True
            llm_result_data["_page_ready"] = destination_ready
            llm_result_data["_can_auto_continue"] = can_auto_continue
            if destination_ready_reason:
                llm_result_data["_destination_ready_reason"] = (
                    destination_ready_reason
                )
            page_ctx = llm_result_data.get("page_context")
            if isinstance(page_ctx, dict):
                page_data = page_ctx.get("page_data")
                if isinstance(page_data, dict):
                    ops = page_data.get("available_operations", [])
                    if isinstance(ops, list) and ops:
                        llm_result_data["_available_operations_count"] = len(ops)
                        op_names = [
                            str(op.get("name") or "").strip()
                            for op in ops
                            if isinstance(op, dict) and op.get("name")
                        ]
                        if op_names:
                            llm_result_data["_available_operation_names"] = op_names[:10]
        screenshot_attachment = (
            _extract_screenshot_attachment(llm_result_data)
            if operation_name == "capture_screenshot"
            else None
        )
        if context and isinstance(context.variables, dict):
            next_page_context = (
                PageContext.normalize(llm_result_data.get("page_context"))
                if isinstance(llm_result_data, dict)
                else None
            )
            next_page_session_id = (
                str(llm_result_data.get("page_session_id") or "").strip()
                if isinstance(llm_result_data, dict)
                and isinstance(llm_result_data.get("page_session_id"), str)
                else ""
            )
            if next_page_context:
                previous_page_context = PageContext.normalize(
                    context.variables.get(SHARED_PAGE_CONTEXT_KEY)
                )
                previous_page_key = (
                    str(previous_page_context.get("page_key") or "").strip()
                    if previous_page_context
                    else ""
                )
                next_page_key = str(next_page_context.get("page_key") or "").strip()
                context.variables[SHARED_PAGE_CONTEXT_KEY] = next_page_context
                if next_page_key and next_page_key != previous_page_key:
                    context.variables.pop(PAGE_CONTEXT_TURN_SEEN_KEY, None)
                if next_page_session_id:
                    context.page_session_id = next_page_session_id
                elif next_page_key and context.user_id:
                    recovered_next_session_id = get_active_session_id(
                        context.user_id,
                        next_page_key,
                        context.user_role,
                    )
                    if recovered_next_session_id:
                        context.page_session_id = recovered_next_session_id
            elif next_page_session_id:
                context.page_session_id = next_page_session_id
        execution_decision_id: int | None = None

        if context and context.db and decision_meta:
            try:
                decision = await ExecutionDecisionService(
                    context.db,
                    context.tenant_id,
                ).record_decision(
                    {
                        "tenant_id": context.tenant_id,
                        "conversation_id": context.conversation_id,
                        "agent_id": context.agent_id,
                        "operator_id": context.user_id,
                        "operator_type": context.user_role,
                        "decision_type": ExecutionDecisionTypeEnum.CONFIRMATION.value,
                        "subject_type": ExecutionDecisionSubjectEnum.PAGE_OPERATION.value,
                        "status": str(
                            decision_meta.get("status")
                            or ExecutionDecisionStatusEnum.APPROVED.value
                        ),
                        "decision_scope": str(
                            decision_meta.get("decision_scope")
                            or ExecutionDecisionScopeEnum.ONCE.value
                        ),
                        "risk_level": resolve_action_level(
                            operation_name,
                            default=ActionLevelEnum.SAFE_WRITE.value,
                        ),
                        "auto_approved": bool(decision_meta.get("auto_approved")),
                        "tool_call_id": tool_call_id or None,
                        "tool_name": definition.name,
                        "action_name": operation_name,
                        "table_name": None,
                        "correlation_key": (
                            f"pageop:{context.conversation_id or 0}:{invoke_id or tool_call_id or operation_name}:"
                            f"{decision_meta.get('status') or 'approved'}"
                        ),
                        "reason": str(
                            decision_meta.get("reason") or "page_operation_confirmation"
                        ),
                        "evidence": {
                            "page_key": page_key,
                            "page_session_id": session_id,
                            "invoke_id": invoke_id,
                            "params": params,
                            "frontend_decision": decision_meta,
                        },
                    }
                )
                execution_decision_id = getattr(decision, "id", None)
            except Exception as exc:
                logger.warning(
                    "Failed to record page operation execution decision: {}",
                    str(exc),
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
                    operator_type=context.user_role,
                    skill_id=context.skill_id,
                    conversation_id=context.conversation_id,
                    execution_decision_id=execution_decision_id,
                    tool_call_id=tool_call_id,
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
                        "auto_approved": auto_approved,
                        "execution_decision": decision_meta,
                    },
                    response_data={
                        "invoke_id": invoke_id or None,
                        "message": message,
                        "error_type": error_type or None,
                        "data": llm_result_data,
                        "auto_approved": auto_approved,
                        "execution_decision_id": execution_decision_id,
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
            elif llm_result_data and isinstance(llm_result_data, dict):
                import json

                data_str = json.dumps(llm_result_data, ensure_ascii=False, default=str)
                if len(data_str) <= 4000:
                    output += f"\nData: {data_str}"
                elif operation_name == "get_editor_html" and "html" in llm_result_data:
                    # Large doc: still pass html for replace_section old_html / 长文档仍传 html 供 replace_section 匹配
                    html_content = llm_result_data.get("html", "") or ""
                    max_html_chars = 12000
                    if len(html_content) > max_html_chars:
                        html_content = (
                            html_content[:max_html_chars] + "\n... (truncated)"
                        )
                    hint = llm_result_data.get("_hint") or _(
                        "page_operation.hint.replace_section"
                    )
                    output += f"\n{hint}\nHTML:\n{html_content}"
                    output += "\n" + render_prompt_contract(
                        "page_operation_html_relay"
                    )
                # Agent Loop: suggest next step from context_diff / Agent 循环：据 context_diff 提示下一步
                context_diff = llm_result_data.get("context_diff", {})
                remaining_empty_fields = llm_result_data.get("remaining_empty_fields")
                remaining_empty_preview = ""
                if isinstance(remaining_empty_fields, list) and remaining_empty_fields:
                    preview = ", ".join(
                        str(item) for item in remaining_empty_fields[:8]
                    )
                    if len(remaining_empty_fields) > 8:
                        preview += f", +{len(remaining_empty_fields) - 8} more"
                    remaining_empty_preview = preview

                if operation_name in {"create_record", "edit_record"}:
                    form_is_open = bool(
                        result_data.get("form_is_open")
                        or result_data.get("already_open")
                        or context_diff.get("form_opened")
                    )
                    if form_is_open:
                        output += "\n\n" + render_prompt_contract(
                            "page_operation_form_already_open",
                            remaining_empty_preview=remaining_empty_preview,
                        )
                elif operation_name == "fill_form":
                    if remaining_empty_preview:
                        output += "\n\n" + render_prompt_contract(
                            "page_operation_fill_remaining",
                            remaining_empty_preview=remaining_empty_preview,
                        )
                    else:
                        output += "\n\n" + render_prompt_contract(
                            "page_operation_fill_ready"
                        )
                elif operation_name == "validate_form":
                    valid = bool(result_data.get("valid"))
                    if valid:
                        output += "\n\n" + render_prompt_contract(
                            "page_operation_validate_passed"
                        )
                    else:
                        output += "\n\n" + render_prompt_contract(
                            "page_operation_validate_failed"
                        )
                elif context_diff.get("form_opened"):
                    output += "\n\n" + render_prompt_contract(
                        "page_operation_form_opened"
                    )
                elif context_diff.get("form_closed"):
                    output += "\n\n" + render_prompt_contract(
                        "page_operation_form_closed"
                    )
                elif operation_name == "navigate_menu":
                    available_operation_names = llm_result_data.get(
                        "_available_operation_names", []
                    )
                    can_auto_continue = bool(
                        llm_result_data.get("_can_auto_continue")
                    )
                    destination_ready = bool(llm_result_data.get("_page_ready"))
                    destination_ready_reason = str(
                        llm_result_data.get("_destination_ready_reason") or ""
                    ).strip()
                    if isinstance(available_operation_names, list):
                        available_preview = ", ".join(
                            str(item)
                            for item in available_operation_names[:8]
                            if str(item).strip()
                        )
                    else:
                        available_preview = ""
                    if destination_ready and can_auto_continue:
                        output += "\n\n" + render_prompt_contract(
                            "page_operation_nav_ready"
                        )
                    elif destination_ready:
                        output += "\n\n" + render_prompt_contract(
                            "page_operation_nav_disabled"
                        )
                    else:
                        output += "\n\n" + render_prompt_contract(
                            "page_operation_nav_pending"
                        )
                    if available_preview and destination_ready:
                        output += (
                            render_prompt_contract(
                                "page_operation_nav_available_ops",
                                available_preview=available_preview,
                            )
                            + " "
                        )
                    if destination_ready and can_auto_continue:
                        output += render_prompt_contract(
                            "page_operation_nav_continue_now"
                        )
                    elif destination_ready_reason:
                        output += (
                            render_prompt_contract(
                                "page_operation_nav_reason",
                                destination_ready_reason=destination_ready_reason,
                            )
                            + " "
                        )
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=output,
                duration_ms=duration_ms,
                attachments=[screenshot_attachment] if screenshot_attachment else None,
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
