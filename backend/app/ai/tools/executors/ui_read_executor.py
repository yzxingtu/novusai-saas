"""
UI Read Executor / UI 读取执行器

Implements:
- ui_read_region
- ui_read_table
- ui_list_interactables
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
    resolve_page_session_id as _resolve_page_session_id,
)
from app.ai.tools.executors.page_runtime_support import text as _text
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.i18n import _
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.ui_read")

_TABLE_MAX_PAGE_SIZE = 100
_INTERACTABLE_LIMIT = 200
_REGION_TEXT_MAX = 4000
def _byte_size(payload: Any) -> int:
    return len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"))


async def _request_ui_read(
    *,
    event_name: str,
    page_session_id: str,
    payload: dict[str, Any],
    timeout: float,
) -> dict[str, Any] | None:
    from app.sio import page_session as page_session_module

    fn_name = {
        "ui_read_region": "request_ui_read_region",
        "ui_read_table": "request_ui_read_table",
        "ui_list_interactables": "request_ui_list_interactables",
    }.get(event_name)
    if not fn_name:
        return None
    read_fn = getattr(page_session_module, fn_name, None)
    if not callable(read_fn):
        return None
    result = await read_fn(
        page_session_id=page_session_id,
        timeout=timeout,
        **payload,
    )
    return result if isinstance(result, dict) else None


def _normalize_scalar_cell(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return _text(value, max_length=240)
    return _text(str(value), max_length=240)


def _normalize_region_payload(locator: str, source: dict[str, Any]) -> dict[str, Any]:
    payload = source.get("data") if isinstance(source.get("data"), dict) else source
    raw_items = payload.get("items")
    items: list[dict[str, Any]] = []
    if isinstance(raw_items, list):
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            label = _text(item.get("label"), max_length=200)
            value = _text(item.get("value"), max_length=400)
            if not label and not value:
                continue
            items.append({"label": label, "value": value})
            if len(items) >= 50:
                break

    region = {
        "region_locator": locator,
        "surface_id": _text(payload.get("surface_id"), max_length=128),
        "title": _text(payload.get("title"), max_length=200),
        "text": _text(payload.get("text"), max_length=_REGION_TEXT_MAX),
        "items": items,
        "truncated": bool(payload.get("truncated", False)),
    }
    region["size_bytes"] = _byte_size(region)
    return region


def _normalize_table_payload(
    locator: str,
    source: dict[str, Any],
    *,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    payload = source.get("data") if isinstance(source.get("data"), dict) else source

    columns: list[str] = []
    raw_columns = payload.get("columns")
    if isinstance(raw_columns, list):
        seen_cols: set[str] = set()
        for item in raw_columns:
            col = _text(item, max_length=80)
            if not col or col in seen_cols:
                continue
            seen_cols.add(col)
            columns.append(col)
            if len(columns) >= 40:
                break

    rows: list[dict[str, Any]] = []
    raw_rows = payload.get("rows")
    if isinstance(raw_rows, list):
        for row in raw_rows[:page_size]:
            if not isinstance(row, dict):
                continue
            normalized_row: dict[str, Any] = {}
            for key, value in row.items():
                normalized_key = _text(key, max_length=80)
                if not normalized_key:
                    continue
                normalized_row[normalized_key] = _normalize_scalar_cell(value)
                if len(normalized_row) >= 40:
                    break
            rows.append(normalized_row)

    total_rows = payload.get("total_rows")
    if not isinstance(total_rows, int):
        total_rows = len(rows)
    total_rows = max(total_rows, 0)
    has_more = payload.get("has_more")
    if not isinstance(has_more, bool):
        has_more = page * page_size < total_rows

    table = {
        "table_locator": locator,
        "columns": columns,
        "rows": rows,
        "page": page,
        "page_size": page_size,
        "total_rows": total_rows,
        "has_more": has_more,
        "truncated": bool(payload.get("truncated", False)),
    }
    table["size_bytes"] = _byte_size(table)
    return table


def _normalize_interactables_payload(
    source: dict[str, Any],
    *,
    surface_id: str | None,
) -> dict[str, Any]:
    payload = source.get("data") if isinstance(source.get("data"), dict) else source
    raw_items = (
        payload.get("items") if isinstance(payload.get("items"), list) else payload
    )
    items: list[dict[str, Any]] = []
    seen_locators: set[str] = set()

    if isinstance(raw_items, list):
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            locator = _text(item.get("locator"), max_length=240)
            if not locator or locator in seen_locators:
                continue
            seen_locators.add(locator)
            normalized = {
                "locator": locator,
                "label": _text(item.get("label"), max_length=200),
                "kind": _text(item.get("kind"), max_length=64) or "unknown",
                "surface_id": _text(item.get("surface_id"), max_length=128),
                "enabled": bool(item.get("enabled", True)),
                "requires_confirmation": bool(item.get("requires_confirmation", False)),
            }
            if (
                surface_id
                and normalized["surface_id"]
                and normalized["surface_id"] != surface_id
            ):
                continue
            items.append(normalized)
            if len(items) >= _INTERACTABLE_LIMIT:
                break

    result = {
        "surface_id": surface_id,
        "items": items,
        "count": len(items),
        "truncated": bool(payload.get("truncated", False)),
    }
    result["size_bytes"] = _byte_size(result)
    return result


class UIReadExecutor(BaseToolExecutor):
    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        start = time.perf_counter()
        page_session_id = _resolve_page_session_id(context)
        if not page_session_id:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.ui.session_required"),
                error_type="session_not_found",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        timeout_seconds = (
            float(context.tool_timeout_seconds)
            if context and context.tool_timeout_seconds
            else 30.0
        )

        tool_name = definition.name
        locator = _text(
            arguments.get("region_locator")
            or arguments.get("table_locator")
            or arguments.get("locator"),
            max_length=240,
        )
        if tool_name in {"ui_read_region", "ui_read_table"} and not locator:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=tool_name,
                success=False,
                error=_("tool.error.missing_required_param", field="locator"),
                error_type="invalid_input",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        page = max(int(arguments.get("page", 1) or 1), 1)
        page_size = int(arguments.get("page_size", 20) or 20)
        page_size = max(1, min(page_size, _TABLE_MAX_PAGE_SIZE))
        surface_id = _text(arguments.get("surface_id"), max_length=128)
        filters = arguments.get("filters")
        if not isinstance(filters, dict):
            filters = None

        bridge_payload: dict[str, Any] = {}
        if tool_name == "ui_read_region":
            bridge_payload = {
                "region_locator": locator,
            }
        elif tool_name == "ui_read_table":
            bridge_payload = {
                "table_locator": locator,
                "page": page,
                "page_size": page_size,
                "filters": filters,
            }
        elif tool_name == "ui_list_interactables":
            bridge_payload = {"surface_id": surface_id}
        else:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=tool_name,
                success=False,
                error=_("tool.ui.read.unsupported_tool"),
                error_type="invalid_tool",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        response_payload: dict[str, Any] | None = None
        try:
            response_payload = await _request_ui_read(
                event_name=tool_name,
                page_session_id=page_session_id,
                payload=bridge_payload,
                timeout=timeout_seconds,
            )
        except Exception as exc:
            logger.warning("ui read bridge failed: {}", str(exc))

        if response_payload is None and context and isinstance(context.variables, dict):
            if tool_name == "ui_read_region":
                cached_regions = context.variables.get("ui_regions")
                if isinstance(cached_regions, dict) and locator in cached_regions:
                    response_payload = {
                        "success": True,
                        "data": cached_regions[locator],
                    }
            elif tool_name == "ui_read_table":
                cached_tables = context.variables.get("ui_tables")
                if isinstance(cached_tables, dict) and locator in cached_tables:
                    response_payload = {"success": True, "data": cached_tables[locator]}
            elif tool_name == "ui_list_interactables":
                cached_interactables = context.variables.get("ui_interactables")
                if isinstance(cached_interactables, list):
                    response_payload = {"success": True, "items": cached_interactables}

        if not response_payload:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=tool_name,
                success=False,
                error=_("tool.ui.read.unavailable"),
                error_type="read_unavailable",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        if response_payload.get("success") is False:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=tool_name,
                success=False,
                error=_normalize_public_message(response_payload.get("error"))
                or _("tool.ui.read.failed"),
                error_type=str(response_payload.get("error_type") or "read_failed"),
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        if tool_name == "ui_read_region":
            normalized = _normalize_region_payload(locator or "", response_payload)
        elif tool_name == "ui_read_table":
            normalized = _normalize_table_payload(
                locator or "",
                response_payload,
                page=page,
                page_size=page_size,
            )
        else:
            normalized = _normalize_interactables_payload(
                response_payload,
                surface_id=surface_id,
            )

        return ToolResult(
            tool_call_id=tool_call_id,
            name=tool_name,
            success=True,
            output=json.dumps(normalized, ensure_ascii=False),
            duration_ms=int((time.perf_counter() - start) * 1000),
        )

    async def validate(
        self,
        definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        tool_name = definition.name
        if tool_name not in {
            "ui_read_region",
            "ui_read_table",
            "ui_list_interactables",
        }:
            return False

        if tool_name in {"ui_read_region", "ui_read_table"}:
            locator = (
                arguments.get("region_locator")
                or arguments.get("table_locator")
                or arguments.get("locator")
            )
            if locator is None:
                return False
            if not isinstance(locator, str):
                return False

        if "surface_id" in arguments and arguments.get("surface_id") is not None and not isinstance(
            arguments.get("surface_id"), str
        ):
            return False

        if "page" in arguments and arguments.get("page") is not None and not isinstance(
            arguments.get("page"), int
        ):
            return False
        if "page_size" in arguments and arguments.get("page_size") is not None and not isinstance(
            arguments.get("page_size"), int
        ):
            return False
        return not (
            "filters" in arguments
            and arguments.get("filters") is not None
            and not isinstance(arguments.get("filters"), dict)
        )


__all__ = ["UIReadExecutor"]
