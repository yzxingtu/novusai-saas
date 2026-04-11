"""Runtime turn-record support for stream execution."""

from __future__ import annotations

from typing import Any


def apply_runtime_turn_record_overlays(handler: Any) -> None:
    if not isinstance(handler._runtime_turn_record, dict):
        handler._runtime_turn_record = {}
    if not isinstance(handler._runtime_turn_record_overlays, dict):
        handler._runtime_turn_record_overlays = {}
    if not handler._runtime_turn_record_overlays:
        return

    record = dict(handler._runtime_turn_record)
    for key, value in handler._runtime_turn_record_overlays.items():
        if key == "tool_loop_progress" and isinstance(value, dict):
            current_progress = (
                dict(record.get("tool_loop_progress") or {})
                if isinstance(record.get("tool_loop_progress"), dict)
                else {}
            )
            current_progress.update(value)
            record[key] = current_progress
            continue
        record[key] = value
    handler._runtime_turn_record = record


def replace_runtime_turn_record(handler: Any, raw_turn_record: Any) -> None:
    if isinstance(raw_turn_record, dict):
        handler._runtime_turn_record_source = None
        handler._runtime_turn_record = dict(raw_turn_record)
    elif raw_turn_record is not None and hasattr(raw_turn_record, "__dict__"):
        handler._runtime_turn_record_source = raw_turn_record
        handler._runtime_turn_record = dict(
            getattr(raw_turn_record, "__dict__", {}) or {}
        )
    else:
        return
    apply_runtime_turn_record_overlays(handler)


def refresh_runtime_turn_record(handler: Any) -> None:
    if handler._runtime_turn_record_source is not None and hasattr(
        handler._runtime_turn_record_source,
        "__dict__",
    ):
        handler._runtime_turn_record = dict(
            getattr(handler._runtime_turn_record_source, "__dict__", {}) or {}
        )
    elif not isinstance(handler._runtime_turn_record, dict):
        handler._runtime_turn_record = {}
    apply_runtime_turn_record_overlays(handler)


def ensure_runtime_turn_record(handler: Any) -> dict[str, Any]:
    refresh_runtime_turn_record(handler)
    if not isinstance(handler._runtime_turn_record, dict):
        handler._runtime_turn_record = {}
    return handler._runtime_turn_record


def update_turn_progress(handler: Any, **fields: Any) -> None:
    record = ensure_runtime_turn_record(handler)
    if not isinstance(handler._runtime_turn_record_overlays, dict):
        handler._runtime_turn_record_overlays = {}
    overlay_progress = (
        dict(handler._runtime_turn_record_overlays.get("tool_loop_progress") or {})
        if isinstance(
            handler._runtime_turn_record_overlays.get("tool_loop_progress"),
            dict,
        )
        else {}
    )
    progress = (
        dict(record.get("tool_loop_progress") or {})
        if isinstance(record.get("tool_loop_progress"), dict)
        else {}
    )
    for key, value in fields.items():
        if key == "tool_loop_progress" and isinstance(value, dict):
            progress.update(value)
            overlay_progress.update(value)
            continue
        if value is None:
            continue
        record[key] = value
        handler._runtime_turn_record_overlays[key] = value
    if progress:
        record["tool_loop_progress"] = progress
    if overlay_progress:
        handler._runtime_turn_record_overlays["tool_loop_progress"] = overlay_progress


def register_budget_exit(handler: Any, reason: str | None) -> None:
    if not reason:
        return
    handler._state.register_provider_failure(
        kind="budget_exit",
        event={"kind": "budget_exit", "reason": reason},
    )
    update_turn_progress(
        handler,
        budget_exit_reason=reason,
        tool_loop_progress={"budget_exit_reason": reason},
    )


def resolved_protocol_path(
    handler: Any,
    *,
    diagnostics_payload: dict[str, Any] | None = None,
    turn_record: dict[str, Any] | None = None,
    response_metadata: dict[str, Any] | None = None,
) -> str:
    candidates = [
        (diagnostics_payload or {}).get("protocol_path"),
        (turn_record or {}).get("protocol_path"),
        (response_metadata or {}).get("protocol_path"),
        (handler._runtime_turn_record or {}).get("protocol_path")
        if isinstance(handler._runtime_turn_record, dict)
        else None,
        (handler._runtime_model_info or {}).get("wire_api")
        if isinstance(handler._runtime_model_info, dict)
        else None,
    ]
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return value
    return "chat_completions"

