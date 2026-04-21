"""Standalone page-runtime executor core."""

from __future__ import annotations

import json
from typing import Any

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ExecutionContext, ToolDefinition, ToolResult

from .contracts import PageRuntimeBridge
from .policy import (
    confirmation_guard,
    forbidden_field_guard,
    resolve_page_context,
    resolve_page_session_id,
    stale_context_guard,
)

_ALIAS_TOOL_NAMES = {"ui_get_snapshot": "ui_read_page"}


class PageRuntimeToolExecutor(BaseToolExecutor):
    """Boundary-safe page-runtime executor that depends on an injected bridge."""

    def __init__(self, bridge: PageRuntimeBridge) -> None:
        self._bridge = bridge

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        tool_name = _ALIAS_TOOL_NAMES.get(definition.name, definition.name)
        page_context = resolve_page_context(context)
        session_id = resolve_page_session_id(context)
        bridge_arguments = dict(arguments)
        bridge_arguments.pop("page_key", None)
        if page_context and "_page_context" not in bridge_arguments:
            bridge_arguments["_page_context"] = dict(page_context)

        for guard in (
            stale_context_guard(arguments=arguments, page_context=page_context),
            forbidden_field_guard(arguments=arguments, tool_name=tool_name),
            confirmation_guard(arguments=arguments, tool_name=tool_name),
        ):
            if not guard.allowed:
                return ToolResult(
                    tool_call_id=tool_call_id,
                    name=definition.name,
                    success=False,
                    error=guard.message,
                    error_type=guard.error_type,
                    summary=guard.message,
                    summary_payload=guard.payload,
                )

        if not session_id:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error="No active page session is available.",
                error_type="session_not_found",
            )

        result = await self._bridge.invoke(
            arguments=bridge_arguments,
            page_session_id=session_id,
            tool_name=tool_name,
            user_role=context.user_role if context else "tenant_admin",
        )
        success = bool(result.get("success", False))
        payload = (
            result.get("data")
            if isinstance(result.get("data"), dict)
            else {key: value for key, value in result.items() if key != "success"}
        )
        error_detail = str(
            result.get("error_detail")
            or result.get("detail")
            or result.get("error")
            or ""
        ).strip()
        raw_error = str(result.get("error") or "").strip()
        message = str(
            result.get("message")
            or result.get("error")
            or (
                "Page runtime action completed."
                if success
                else f"Page runtime action '{tool_name}' failed."
            )
        ).strip()
        if not success and error_detail and error_detail != message:
            message = f"{message} Detail: {error_detail}".strip()
        if success:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=True,
                output=json.dumps(payload, ensure_ascii=False, default=str),
                summary=message,
                summary_payload=payload or None,
            )
        return ToolResult(
            tool_call_id=tool_call_id,
            name=definition.name,
            success=False,
            error=message,
            error_type=str(result.get("error_type") or "execution_failed"),
            summary=message,
            summary_payload=(
                {
                    **payload,
                    **({"error_detail": error_detail} if error_detail else {}),
                    **({"error": raw_error} if raw_error else {}),
                }
                if payload or error_detail
                else None
            ),
        )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        tool_name = _ALIAS_TOOL_NAMES.get(definition.name, definition.name)
        if tool_name == "ui_read_surface":
            return isinstance(arguments.get("surface_id"), str)
        if tool_name in {"ui_read_region", "ui_read_table"}:
            return isinstance(arguments.get("locator"), str)
        if tool_name == "ui_click":
            return isinstance(arguments.get("target_locator"), str)
        if tool_name == "ui_fill_form":
            return isinstance(arguments.get("fields"), dict)
        if tool_name == "ui_set_field":
            return isinstance(arguments.get("field_name"), str)
        return True
