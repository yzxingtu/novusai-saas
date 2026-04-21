"""Live Socket.IO-backed bridge for page-runtime tools."""

from __future__ import annotations

from typing import Any

from app.ai.tools.executors.page_runtime_support import (
    normalize_public_message as _normalize_public_message,
)
from app.ai.tools.executors.page_runtime_support import (
    text as _text,
)
from app.ai.tools.executors.page_runtime_support import (
    user_role_to_namespace as _user_role_to_namespace,
)
from app.ai.tools.executors.ui_read_executor import (
    _normalize_interactables_payload,
    _normalize_region_payload,
    _normalize_table_payload,
)
from app.ai.tools.executors.ui_snapshot_executor import _normalize_snapshot_payload

_ACTION_TOOL_NAMES = {
    "ui_click",
    "ui_open_surface",
    "ui_get_form_state",
    "ui_set_field",
    "ui_fill_form",
    "ui_submit_form",
}


class SocketIOPageRuntimeBridge:
    """Adapt live Socket.IO page-session helpers to the page-runtime contract."""

    async def invoke(
        self,
        *,
        arguments: dict[str, Any],
        page_session_id: str,
        tool_name: str,
        user_role: str,
    ) -> dict[str, Any]:
        from app.sio import page_session as page_session_module

        normalized_tool_name = str(tool_name or "").strip()
        payload = dict(arguments or {})
        payload.pop("page_key", None)
        payload.pop("_page_context", None)
        timeout = float(payload.get("timeout_seconds") or 60)
        namespace = _user_role_to_namespace(user_role)

        if normalized_tool_name == "ui_get_snapshot":
            mode = str(payload.get("mode") or "compact").strip().lower()
            normalized_mode = "full" if mode == "full" else "compact"
            surface_id = _text(payload.get("surface_id"), max_length=128)
            raw_result = await page_session_module.request_ui_snapshot(
                page_session_id=page_session_id,
                mode=normalized_mode,
                surface_id=surface_id,
                timeout=timeout,
                namespace=namespace,
            )
            return self._snapshot_result(
                raw_result,
                mode=normalized_mode,
            )

        if normalized_tool_name == "ui_read_region":
            locator = _text(payload.get("locator"), max_length=240) or ""
            raw_result = await page_session_module.request_ui_read_region(
                page_session_id=page_session_id,
                region_locator=locator,
                timeout=timeout,
                namespace=namespace,
            )
            return self._read_result(
                raw_result,
                default_error_type="read_region_failed",
                data=_normalize_region_payload(locator, raw_result or {}),
            )

        if normalized_tool_name == "ui_read_table":
            locator = _text(payload.get("locator"), max_length=240) or ""
            page = max(int(payload.get("page", 1) or 1), 1)
            page_size = max(1, min(int(payload.get("page_size", 20) or 20), 100))
            filters = payload.get("filters")
            if not isinstance(filters, dict):
                filters = None
            raw_result = await page_session_module.request_ui_read_table(
                page_session_id=page_session_id,
                table_locator=locator,
                page=page,
                page_size=page_size,
                filters=filters,
                timeout=timeout,
                namespace=namespace,
            )
            return self._read_result(
                raw_result,
                default_error_type="read_table_failed",
                data=_normalize_table_payload(
                    locator,
                    raw_result or {},
                    page=page,
                    page_size=page_size,
                ),
            )

        if normalized_tool_name == "ui_list_interactables":
            surface_id = _text(payload.get("surface_id"), max_length=128)
            raw_result = await page_session_module.request_ui_list_interactables(
                page_session_id=page_session_id,
                surface_id=surface_id,
                timeout=timeout,
                namespace=namespace,
            )
            return self._read_result(
                raw_result,
                default_error_type="read_interactables_failed",
                data=_normalize_interactables_payload(
                    raw_result or {},
                    surface_id=surface_id,
                ),
            )

        if normalized_tool_name in _ACTION_TOOL_NAMES:
            action_payload = self._build_action_payload(payload, normalized_tool_name)
            raw_result = await page_session_module.invoke_ui_action(
                page_session_id=page_session_id,
                action_type=normalized_tool_name,
                payload=action_payload,
                timeout=timeout,
                namespace=namespace,
            )
            return self._action_result(
                raw_result, default_error_type="execution_failed"
            )

        return {
            "success": False,
            "message": f"Unsupported page-runtime tool '{normalized_tool_name}'.",
            "error_type": "invalid_tool",
        }

    @staticmethod
    def _build_action_payload(
        arguments: dict[str, Any],
        tool_name: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "action_type": tool_name,
            "confirm": bool(arguments.get("confirm", False)),
            "wait_timeout_ms": arguments.get("wait_timeout_ms"),
        }
        if tool_name in {"ui_click", "ui_open_surface"}:
            payload["target_locator"] = _text(
                arguments.get("target_locator"), max_length=240
            )
            surface = arguments.get("surface")
            if isinstance(surface, dict):
                payload["surface"] = dict(surface)
        if tool_name in {
            "ui_get_form_state",
            "ui_set_field",
            "ui_fill_form",
            "ui_submit_form",
        }:
            form_session_id = _text(arguments.get("form_session_id"), max_length=128)
            if form_session_id:
                payload["form_session_id"] = form_session_id
        if tool_name == "ui_set_field":
            payload["field_name"] = _text(arguments.get("field_name"), max_length=200)
            payload["value"] = arguments.get("value")
        if tool_name == "ui_fill_form" and isinstance(arguments.get("fields"), dict):
            payload["fields"] = dict(arguments.get("fields") or {})
        return {
            key: value for key, value in payload.items() if value not in ("", None, {})
        }

    @staticmethod
    def _error_fields(result: dict[str, Any] | None) -> tuple[str | None, str | None]:
        payload = result if isinstance(result, dict) else {}
        message = _normalize_public_message(payload.get("message"))
        error = _normalize_public_message(payload.get("error"))
        detail = _normalize_public_message(
            payload.get("error_detail") or payload.get("detail")
        )
        if detail:
            return message or error, detail
        return message, error

    @classmethod
    def _read_result(
        cls,
        result: dict[str, Any] | None,
        *,
        default_error_type: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(result, dict):
            return {
                "success": False,
                "message": "Page runtime read is unavailable.",
                "error_type": default_error_type,
            }
        if result.get("success") is False:
            message, detail = cls._error_fields(result)
            return {
                "success": False,
                "message": message or "Page runtime read failed.",
                "error": detail or message or "Page runtime read failed.",
                "error_detail": detail,
                "error_type": str(result.get("error_type") or default_error_type),
                "data": (
                    result.get("data") if isinstance(result.get("data"), dict) else None
                ),
            }
        return {
            "success": True,
            "message": "Page runtime read completed.",
            "data": data,
        }

    @classmethod
    def _snapshot_result(
        cls,
        result: dict[str, Any] | None,
        *,
        mode: str,
    ) -> dict[str, Any]:
        if not isinstance(result, dict):
            return {
                "success": False,
                "message": "Page runtime snapshot is unavailable.",
                "error_type": "snapshot_unavailable",
            }
        if result.get("success") is False:
            message, detail = cls._error_fields(result)
            return {
                "success": False,
                "message": message or "Page runtime snapshot failed.",
                "error": detail or message or "Page runtime snapshot failed.",
                "error_detail": detail,
                "error_type": str(result.get("error_type") or "snapshot_failed"),
            }
        return {
            "success": True,
            "message": "Page runtime snapshot loaded.",
            "data": _normalize_snapshot_payload(mode=mode, source=result),
        }

    @classmethod
    def _action_result(
        cls,
        result: dict[str, Any] | None,
        *,
        default_error_type: str,
    ) -> dict[str, Any]:
        if not isinstance(result, dict):
            return {
                "success": False,
                "message": "Page runtime action is unavailable.",
                "error_type": default_error_type,
            }
        if result.get("success") is False:
            message, detail = cls._error_fields(result)
            return {
                "success": False,
                "message": message or "Page runtime action failed.",
                "error": detail or message or "Page runtime action failed.",
                "error_detail": detail,
                "error_type": str(result.get("error_type") or default_error_type),
                "data": (
                    result.get("data") if isinstance(result.get("data"), dict) else None
                ),
                "detail": detail,
            }
        data = result.get("data") if isinstance(result.get("data"), dict) else {}
        diff = result.get("diff") if isinstance(result.get("diff"), dict) else {}
        payload = {**data, **({"diff": diff} if diff else {})}
        return {
            "success": True,
            "message": _normalize_public_message(result.get("message"))
            or "Page runtime action completed.",
            "data": payload,
        }
