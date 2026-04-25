"""
UI Snapshot Executor / UI 快照执行器

Reads lightweight UI snapshots for the current page session.
为当前页面会话读取轻量 UI 快照。
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, Literal

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.executors.page_runtime_support import (
    normalize_public_message as _normalize_public_message,
)
from app.ai.tools.executors.page_runtime_support import (
    read_executor_cache_value as _read_executor_cache_value,
)
from app.ai.tools.executors.page_runtime_support import (
    resolve_explicit_page_session_id as _resolve_explicit_page_session_id,
)
from app.ai.tools.executors.page_runtime_support import (
    store_executor_cache_value as _store_executor_cache_value,
)
from app.ai.tools.executors.page_runtime_support import text as _text
from app.ai.tools.types import ToolDefinition, ToolResult
from app.core.i18n import _
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.tool.ui_snapshot")

SNAPSHOT_MODE = Literal["compact", "full"]
_COMPACT_MAX_BYTES = 10 * 1024
_FULL_MAX_BYTES = 50 * 1024
_MAX_NODES_COMPACT = 160
_MAX_NODES_FULL = 320
def _byte_size(payload: Any) -> int:
    return len(json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"))


def _normalize_surface_stack(raw_stack: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_stack, list):
        return []
    stack: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in raw_stack:
        if not isinstance(item, dict):
            continue
        surface_id = _text(item.get("surface_id"), max_length=128)
        kind = _text(item.get("kind"), max_length=32)
        if not surface_id or not kind or surface_id in seen_ids:
            continue
        seen_ids.add(surface_id)
        stack.append(
            {
                "surface_id": surface_id,
                "kind": kind,
                "title": _text(item.get("title"), max_length=200),
            }
        )
        if len(stack) >= 12:
            break
    return stack


def _normalize_form_summary(raw_form: Any) -> dict[str, Any] | None:
    if not isinstance(raw_form, dict):
        return None
    form_session_id = _text(raw_form.get("form_session_id"), max_length=128)
    if not form_session_id:
        return None

    remaining_fields: list[str] = []
    raw_remaining = raw_form.get("remaining_required_fields")
    if isinstance(raw_remaining, list):
        seen: set[str] = set()
        for field_name in raw_remaining:
            normalized = _text(field_name, max_length=128)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            remaining_fields.append(normalized)
            if len(remaining_fields) >= 32:
                break

    return {
        "form_session_id": form_session_id,
        "entity_name": _text(raw_form.get("entity_name"), max_length=128),
        "mode": _text(raw_form.get("mode"), max_length=16) or "unknown",
        "stage": _text(raw_form.get("stage"), max_length=32) or "ready",
        "record_id": raw_form.get("record_id"),
        "remaining_required_fields": remaining_fields,
        "can_submit": bool(raw_form.get("can_submit", False)),
        "submit_policy": _text(raw_form.get("submit_policy"), max_length=16)
        or "confirm",
    }


def _normalize_nodes(raw_nodes: Any, mode: SNAPSHOT_MODE) -> list[dict[str, Any]]:
    if not isinstance(raw_nodes, list):
        return []

    node_limit = _MAX_NODES_COMPACT if mode == "compact" else _MAX_NODES_FULL
    nodes: list[dict[str, Any]] = []

    for index, raw_node in enumerate(raw_nodes):
        if not isinstance(raw_node, dict):
            continue
        node_id = (
            _text(raw_node.get("node_id"), max_length=128)
            or _text(raw_node.get("id"), max_length=128)
            or _text(raw_node.get("locator"), max_length=240)
            or f"node-{index}"
        )
        node = {
            "node_id": node_id,
            "kind": _text(raw_node.get("kind"), max_length=64)
            or _text(raw_node.get("type"), max_length=64)
            or "unknown",
            "locator": _text(raw_node.get("locator"), max_length=240),
            "surface_id": _text(raw_node.get("surface_id"), max_length=128),
            "role": _text(raw_node.get("role"), max_length=64),
            "interactable": bool(raw_node.get("interactable", False)),
            "children_count": (
                max(int(raw_node.get("children_count")), 0)
                if isinstance(raw_node.get("children_count"), int | float)
                else None
            ),
            "summary": _text(
                raw_node.get("summary")
                or raw_node.get("label")
                or raw_node.get("title")
                or raw_node.get("text")
                or raw_node.get("content"),
                max_length=180,
            ),
        }
        if mode == "full":
            node["content"] = _text(
                raw_node.get("content") or raw_node.get("text"),
                max_length=2000,
            )
        nodes.append(node)
        if len(nodes) >= node_limit:
            break

    return nodes


def _normalize_form_sessions(raw_form_sessions: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_form_sessions, list):
        return []
    normalized_sessions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_form_sessions:
        normalized = _normalize_form_summary(item)
        if not normalized:
            continue
        form_session_id = normalized["form_session_id"]
        if form_session_id in seen:
            continue
        seen.add(form_session_id)
        normalized_sessions.append(normalized)
        if len(normalized_sessions) >= 8:
            break
    return normalized_sessions


def _estimate_interactables(nodes: list[dict[str, Any]]) -> int:
    total = 0
    for node in nodes:
        if node.get("interactable") is True:
            total += 1
            continue
        if node.get("kind") in {"button", "input", "link", "select", "switch"}:
            total += 1
    return total


def _trim_snapshot_by_budget(
    snapshot: dict[str, Any], mode: SNAPSHOT_MODE
) -> dict[str, Any]:
    budget = _COMPACT_MAX_BYTES if mode == "compact" else _FULL_MAX_BYTES
    candidate = dict(snapshot)
    size = _byte_size(candidate)
    truncated = False

    while size > budget and len(candidate.get("nodes", [])) > 1:
        truncated = True
        next_length = max(1, int(len(candidate["nodes"]) * 0.8))
        candidate["nodes"] = candidate["nodes"][:next_length]
        size = _byte_size(candidate)

    if size > budget:
        truncated = True
        for node in candidate.get("nodes", []):
            node["summary"] = _text(node.get("summary"), max_length=80)
            if mode == "full":
                node["content"] = _text(node.get("content"), max_length=512)
        size = _byte_size(candidate)

    candidate["truncated"] = bool(candidate.get("truncated")) or truncated
    candidate["interactables_count"] = _estimate_interactables(
        candidate.get("nodes", [])
    )
    candidate["size_bytes"] = size
    return candidate


async def _request_ui_snapshot(
    *,
    page_session_id: str,
    mode: SNAPSHOT_MODE,
    surface_id: str | None,
    timeout: float,
) -> dict[str, Any] | None:
    from app.sio import page_session as page_session_module

    request_fn = getattr(page_session_module, "request_ui_snapshot", None)
    if not callable(request_fn):
        return None
    result = await request_fn(
        page_session_id=page_session_id,
        mode=mode,
        surface_id=surface_id,
        timeout=timeout,
    )
    return result if isinstance(result, dict) else None


def _resolve_mode(arguments: dict[str, Any]) -> SNAPSHOT_MODE:
    mode = str(arguments.get("mode") or "compact").strip().lower()
    return "full" if mode == "full" else "compact"


def _normalize_snapshot_payload(
    *,
    mode: SNAPSHOT_MODE,
    source: dict[str, Any],
) -> dict[str, Any]:
    raw_snapshot = (
        source.get("snapshot") if isinstance(source.get("snapshot"), dict) else source
    )
    surface_stack = _normalize_surface_stack(raw_snapshot.get("surface_stack"))
    active_surface_id = _text(raw_snapshot.get("active_surface_id"), max_length=128)
    if not active_surface_id and surface_stack:
        active_surface_id = surface_stack[-1]["surface_id"]

    active_form_summary = _normalize_form_summary(
        raw_snapshot.get("active_form_summary")
    )
    active_form_session_id = _text(
        raw_snapshot.get("active_form_session_id"), max_length=128
    )
    if not active_form_session_id and active_form_summary:
        active_form_session_id = active_form_summary["form_session_id"]

    snapshot = {
        "mode": mode,
        "ui_epoch": max(int(raw_snapshot.get("ui_epoch", 0) or 0), 0),
        "surface_stack": surface_stack,
        "active_surface_id": active_surface_id,
        "active_form_session_id": active_form_session_id,
        "active_form_summary": active_form_summary,
        "nodes": _normalize_nodes(raw_snapshot.get("nodes"), mode),
        "form_sessions": _normalize_form_sessions(raw_snapshot.get("form_sessions")),
        "interactables_count": 0,
        "truncated": bool(raw_snapshot.get("truncated", False)),
        "size_bytes": 0,
    }
    return _trim_snapshot_by_budget(snapshot, mode)


class UISnapshotExecutor(BaseToolExecutor):
    """Executor for ``ui_get_snapshot``."""

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        start = time.perf_counter()
        mode = _resolve_mode(arguments)
        surface_id = _text(arguments.get("surface_id"), max_length=128)
        page_session_id = _resolve_explicit_page_session_id(context)

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

        source_payload: dict[str, Any] | None = None
        try:
            source_payload = await _request_ui_snapshot(
                page_session_id=page_session_id,
                mode=mode,
                surface_id=surface_id,
                timeout=timeout_seconds,
            )
        except Exception as exc:
            logger.warning("ui snapshot bridge failed: {}", str(exc))

        if source_payload is None:
            cached_snapshot = _read_executor_cache_value(context, "ui_snapshot")
            if isinstance(cached_snapshot, dict):
                source_payload = {"success": True, "snapshot": cached_snapshot}

        if not source_payload:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_("tool.ui.snapshot.unavailable"),
                error_type="snapshot_unavailable",
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        if source_payload.get("success") is False:
            return ToolResult(
                tool_call_id=tool_call_id,
                name=definition.name,
                success=False,
                error=_normalize_public_message(source_payload.get("error"))
                or _("tool.ui.snapshot.failed"),
                error_type=str(source_payload.get("error_type") or "snapshot_failed"),
                duration_ms=int((time.perf_counter() - start) * 1000),
            )

        normalized_snapshot = _normalize_snapshot_payload(
            mode=mode, source=source_payload
        )
        _store_executor_cache_value(context, "ui_snapshot", normalized_snapshot)
        return ToolResult(
            tool_call_id=tool_call_id,
            name=definition.name,
            success=True,
            output=json.dumps(normalized_snapshot, ensure_ascii=False),
            duration_ms=int((time.perf_counter() - start) * 1000),
        )

    async def validate(
        self,
        _definition: ToolDefinition,
        arguments: dict[str, Any],
    ) -> bool:
        mode = str(arguments.get("mode") or "compact").strip().lower()
        if mode not in {"compact", "full"}:
            return False
        if "surface_id" in arguments and arguments.get("surface_id") is not None:
            return isinstance(arguments.get("surface_id"), str)
        return True


__all__ = ["UISnapshotExecutor"]
