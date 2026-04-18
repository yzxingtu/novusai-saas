"""
UI action executor.

Dispatches UI actions to frontend via page session channel and waits for ui_action_result.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.executors.page_runtime_support import (
    normalize_public_message as _normalize_public_message,
)
from app.ai.tools.executors.page_runtime_support import (
    user_role_to_namespace as _user_role_to_namespace,
)
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.i18n import _
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.ui_action")

UI_ACTION_CLICK = "ui_click"
UI_ACTION_OPEN_SURFACE = "ui_open_surface"
UI_GET_FORM_STATE = "ui_get_form_state"
UI_SET_FIELD = "ui_set_field"
UI_FILL_FORM = "ui_fill_form"
UI_SUBMIT_FORM = "ui_submit_form"
UI_ACTION_NAMES = {
    UI_ACTION_CLICK,
    UI_ACTION_OPEN_SURFACE,
    UI_GET_FORM_STATE,
    UI_SET_FIELD,
    UI_FILL_FORM,
    UI_SUBMIT_FORM,
}


def _normalize_action_name(
    definition_name: str,
    arguments: dict[str, Any],
) -> str:
    if definition_name in UI_ACTION_NAMES:
        return definition_name
    from_argument = str(arguments.get("action_type") or "").strip()
    if from_argument in UI_ACTION_NAMES:
        return from_argument
    return ""


class UIActionExecutor(BaseToolExecutor):
    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        start = time.perf_counter()
        action_name = _normalize_action_name(definition.name, arguments)
        if not action_name:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.ui.action.unsupported_tool"),
                error_type="invalid_input",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        target_locator = str(arguments.get("target_locator") or "").strip()
        surface = arguments.get("surface")
        if action_name == UI_ACTION_CLICK and not target_locator:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.missing_required_param", field="target_locator"),
                error_type="invalid_input",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )
        if action_name == UI_ACTION_OPEN_SURFACE and not (
            target_locator
            or (
                isinstance(surface, dict)
                and (
                    str(surface.get("locator") or "").strip()
                    or str(surface.get("title") or "").strip()
                )
            )
        ):
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.ui.action.open_surface_target_required"),
                error_type="invalid_input",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )
        if action_name == UI_SET_FIELD and not str(arguments.get("field_name") or "").strip():
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.missing_required_param", field="field_name"),
                error_type="invalid_input",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )
        if action_name == UI_FILL_FORM and not isinstance(arguments.get("fields"), dict):
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.error.missing_required_param", field="fields"),
                error_type="invalid_input",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        page_key = str(arguments.get("page_key") or "").strip()
        session_id = None
        if context:
            if not page_key and isinstance(context.variables, dict):
                page_context = context.variables.get("page_context")
                if isinstance(page_context, dict):
                    page_key = str(page_context.get("page_key") or "").strip()
            session_id = context.page_session_id

        if not session_id and context and context.user_id and page_key:
            from app.sio.page_session import get_active_session_id

            session_id = get_active_session_id(
                context.user_id,
                page_key,
                context.user_role,
            )

        if not session_id:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.ui.session_required"),
                error_type="session_not_found",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        from app.sio import page_session as page_session_module

        invoke_ui_action = getattr(page_session_module, "invoke_ui_action", None)
        if not callable(invoke_ui_action):
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.ui.action.unavailable"),
                error_type="ui_action_unavailable",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        timeout = float(arguments.get("timeout_seconds") or 60)
        invoke_payload: dict[str, Any] = {
            "action_type": action_name,
            "confirm": bool(arguments.get("confirm", False)),
            "page_key": page_key,
            "wait_timeout_ms": arguments.get("wait_timeout_ms"),
        }
        if action_name in {UI_ACTION_CLICK, UI_ACTION_OPEN_SURFACE}:
            invoke_payload.update(
                {
                    "target_locator": target_locator,
                    "surface": surface if isinstance(surface, dict) else {},
                }
            )
        if action_name in {
            UI_GET_FORM_STATE,
            UI_SET_FIELD,
            UI_FILL_FORM,
            UI_SUBMIT_FORM,
        }:
            form_session_id = str(arguments.get("form_session_id") or "").strip()
            if form_session_id:
                invoke_payload["form_session_id"] = form_session_id
        if action_name == UI_SET_FIELD:
            invoke_payload["field_name"] = str(arguments.get("field_name") or "").strip()
            invoke_payload["value"] = arguments.get("value")
        if action_name == UI_FILL_FORM:
            invoke_payload["fields"] = (
                dict(arguments.get("fields"))
                if isinstance(arguments.get("fields"), dict)
                else {}
            )
        invoke_payload = {
            key: value
            for key, value in invoke_payload.items()
            if value not in ("", None, {})
        }

        logger.info(
            "Invoking ui action: action={} page_key={} page_session={}",
            action_name,
            page_key,
            session_id,
        )

        result = await invoke_ui_action(
            page_session_id=session_id,
            page_key=page_key,
            action_type=action_name,
            payload=invoke_payload,
            timeout=timeout,
            namespace=_user_role_to_namespace(context.user_role if context else ""),
            tool_call_id=tool_call_id,
        )

        duration_ms = int((time.perf_counter() - start) * 1000)
        success = bool(result.get("success", False))
        message = _normalize_public_message(
            result.get("message") if success else result.get("error")
        ) or _normalize_public_message(result.get("message"))
        error_type = str(result.get("error_type") or "").strip()
        diff = result.get("diff") if isinstance(result.get("diff"), dict) else None
        data = result.get("data") if isinstance(result.get("data"), dict) else None

        if success:
            output = _("tool.ui.action.executed", action=action_name)
            if message:
                output += f" {_('tool.ui.action.result', message=message)}"
            if diff:
                diff_payload = json.dumps(diff, ensure_ascii=False, default=str)
                output += f"\n{_('tool.ui.action.diff', diff=diff_payload)}"
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=output,
                summary=message or _("tool.ui.action.success_summary", action=action_name),
                summary_payload={"data": data, "diff": diff} if (data or diff) else None,
                duration_ms=duration_ms,
            )

        error_detail = _normalize_public_message(
            result.get("error_detail") or result.get("detail")
        )
        error_text = message or _("tool.ui.action.failed", action=action_name)
        if error_detail and error_detail not in error_text:
            error_text = f"{error_text} ({error_detail})"
        return ToolResult(
            tool_call_id=tool_call_id,
            name=definition.name,
            success=False,
            error=error_text,
            error_type=error_type or "execution_failed",
            summary=error_text,
            summary_payload=(
                {
                    **({"data": data} if data else {}),
                    **({"diff": diff} if diff else {}),
                    **({"error_detail": error_detail} if error_detail else {}),
                }
                if (data or diff or error_detail)
                else None
            ),
            duration_ms=duration_ms,
        )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        action_name = _normalize_action_name(definition.name, arguments)
        if action_name == UI_ACTION_CLICK:
            return bool(str(arguments.get("target_locator") or "").strip())
        if action_name == UI_ACTION_OPEN_SURFACE:
            target_locator = str(arguments.get("target_locator") or "").strip()
            surface = arguments.get("surface")
            if target_locator:
                return True
            return bool(
                isinstance(surface, dict)
                and (
                    str(surface.get("locator") or "").strip()
                    or str(surface.get("title") or "").strip()
                )
            )
        if action_name == UI_GET_FORM_STATE:
            return True
        if action_name == UI_SET_FIELD:
            return bool(str(arguments.get("field_name") or "").strip())
        if action_name == UI_FILL_FORM:
            return isinstance(arguments.get("fields"), dict)
        return action_name == UI_SUBMIT_FORM


__all__ = ["UIActionExecutor"]
