"""
Socket.IO trace/session helpers.

This mixin keeps ordinary realtime namespaces able to propagate trace ids.
"""

from __future__ import annotations

import contextlib
from typing import Any

import socketio

from app.middleware.trace import (
    extract_optional_trace_id,
    normalize_trace_id,
    trace_id_var,
)


def _extract_trace_id(payload: dict[str, Any] | None = None) -> str | None:
    if not isinstance(payload, dict):
        return None
    return extract_optional_trace_id(payload.get("trace_id"))


class SocketTraceMixin:
    """Bind trace context for generic Socket.IO namespace events."""

    async def trigger_event(
        self: socketio.AsyncNamespace,
        event: str,
        *args: Any,
    ) -> Any:
        if event in ("connect", "disconnect"):
            return await super().trigger_event(event, *args)

        sid = str(args[0]) if args else ""
        payload = args[1] if len(args) > 1 and isinstance(args[1], dict) else None
        try:
            if sid:
                await self.bind_socket_trace(sid, payload)
            return await super().trigger_event(event, *args)
        finally:
            trace_id_var.set("")

    async def get_socket_session_with_fallback(
        self: socketio.AsyncNamespace,
        sid: str,
    ) -> dict[str, Any] | None:
        with contextlib.suppress(Exception):
            session = await self.get_session(sid)
            if isinstance(session, dict):
                return session

        sid_sessions = getattr(self, "_sid_sessions", None)
        if isinstance(sid_sessions, dict):
            fallback = sid_sessions.get(sid)
            if isinstance(fallback, dict):
                return fallback
        return None

    async def bind_socket_trace(
        self: socketio.AsyncNamespace,
        sid: str,
        payload: dict[str, Any] | None = None,
        default_trace_id: str | None = None,
    ) -> dict[str, Any] | None:
        session = await self.get_socket_session_with_fallback(sid)
        trace_id = normalize_trace_id(
            _extract_trace_id(payload) or (session or {}).get("trace_id"),
            default=default_trace_id,
        )
        trace_id_var.set(trace_id)

        updated_session = session
        if session is not None and session.get("trace_id") != trace_id:
            updated_session = {**session, "trace_id": trace_id}
            with contextlib.suppress(Exception):
                await self.save_session(sid, updated_session)
            sid_sessions = getattr(self, "_sid_sessions", None)
            if isinstance(sid_sessions, dict):
                sid_sessions[sid] = updated_session

        return updated_session
