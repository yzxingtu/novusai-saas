"""Trace propagation regression tests / Trace 传播回归测试。"""

from __future__ import annotations

import asyncio
import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import app.celery_app as celery_module
from app.core.sse import SSEFormatter
from app.middleware.trace import TraceIdMiddleware, trace_id_var
from app.tasks.base import BaseTask


class _DummyTask(BaseTask):
    name = "tests.dummy"

    def _apply_db_config(self) -> None:
        return None

    def _record_task_log_start(self, task_id: str, args: tuple, kwargs: dict) -> None:
        _ = (task_id, args, kwargs)


def test_send_task_injects_trace_id_from_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    send_task_mock = MagicMock(return_value="queued")
    monkeypatch.setattr(celery_module, "_original_send_task", send_task_mock)

    token = trace_id_var.set("trace-send-task")
    try:
        result = celery_module.celery_app.send_task(
            "app.tasks.example",
            args=[1],
            queue="default",
        )
    finally:
        trace_id_var.reset(token)

    assert result == "queued"
    send_task_mock.assert_called_once_with(
        "app.tasks.example",
        args=[1],
        queue="default",
        headers={"trace_id": "trace-send-task"},
    )


def test_send_task_preserves_existing_trace_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    send_task_mock = MagicMock(return_value="queued")
    monkeypatch.setattr(celery_module, "_original_send_task", send_task_mock)

    token = trace_id_var.set("trace-ignored")
    try:
        celery_module.celery_app.send_task(
            "app.tasks.example",
            headers={"trace_id": "trace-explicit", "source": "test"},
        )
    finally:
        trace_id_var.reset(token)

    send_task_mock.assert_called_once_with(
        "app.tasks.example",
        headers={"trace_id": "trace-explicit", "source": "test"},
    )


def test_base_task_restores_and_clears_trace_id() -> None:
    task = _DummyTask()
    task.request_stack = SimpleNamespace(
        top=SimpleNamespace(headers={"trace_id": "trace-task"})
    )

    trace_id_var.set("stale-value")
    task.before_start("task-1", (), {})
    assert trace_id_var.get() == "trace-task"

    task.after_return("SUCCESS", None, "task-1", (), {}, None)
    assert trace_id_var.get() == ""


def test_base_task_generates_trace_id_when_header_missing() -> None:
    task = _DummyTask()
    task.request_stack = SimpleNamespace(top=SimpleNamespace(headers={}))

    trace_id_var.set("")
    task.before_start("task-1", (), {})
    generated = trace_id_var.get()

    assert generated
    assert uuid.UUID(generated)

    task.after_return("SUCCESS", None, "task-1", (), {}, None)
    assert trace_id_var.get() == ""


@pytest.mark.asyncio
async def test_notify_sync_preserves_trace_context_in_worker_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.services.common.notification_service as notification_module

    observed_trace_ids: list[str] = []

    class _DummyDB:
        async def commit(self) -> None:
            return None

    class _DummySessionContext:
        async def __aenter__(self) -> _DummyDB:
            return _DummyDB()

        async def __aexit__(self, exc_type, exc, tb) -> bool:
            _ = (exc_type, exc, tb)
            return False

    class _FakeNotificationService:
        def __init__(self, db) -> None:
            self.db = db

        async def send(self, **kwargs) -> int:
            _ = kwargs
            observed_trace_ids.append(trace_id_var.get())
            return 1

    monkeypatch.setattr(notification_module, "NotificationService", _FakeNotificationService)
    monkeypatch.setattr(
        "app.core.database.async_session_factory",
        lambda: _DummySessionContext(),
    )

    token = trace_id_var.set("trace-notify-sync")
    try:
        result = notification_module.notify_sync(
            "system.task_failure",
            [("admin", 1)],
        )
    finally:
        trace_id_var.reset(token)

    assert result == 1
    assert observed_trace_ids == ["trace-notify-sync"]


@pytest.mark.asyncio
async def test_trace_middleware_replaces_invalid_utf8_header() -> None:
    captured: dict[str, str] = {}
    messages: list[dict] = []

    async def app(scope, receive, send):
        _ = receive
        captured["trace_id"] = scope["state"].trace_id
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    middleware = TraceIdMiddleware(app)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await middleware(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [(b"x-trace-id", b"\xff")],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive,
        send,
    )

    response_start = next(
        message for message in messages if message["type"] == "http.response.start"
    )
    response_headers = dict(response_start["headers"])
    trace_id = response_headers[b"x-trace-id"].decode("utf-8")

    assert trace_id
    assert captured["trace_id"] == trace_id
    assert uuid.UUID(trace_id)


@pytest.mark.asyncio
async def test_trace_middleware_swallows_http_cancellation() -> None:
    async def app(scope, receive, send):
        _ = (scope, receive, send)
        raise asyncio.CancelledError()

    middleware = TraceIdMiddleware(app)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        raise AssertionError(f"unexpected send: {message}")

    await middleware(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/cancelled",
            "raw_path": b"/cancelled",
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        },
        receive,
        send,
    )


@pytest.mark.asyncio
async def test_trace_middleware_preserves_websocket_cancellation() -> None:
    async def app(scope, receive, send):
        _ = (scope, receive, send)
        raise asyncio.CancelledError()

    middleware = TraceIdMiddleware(app)

    async def receive():
        return {"type": "websocket.disconnect", "code": 1000}

    async def send(message):
        raise AssertionError(f"unexpected send: {message}")

    with pytest.raises(asyncio.CancelledError):
        await middleware(
            {
                "type": "websocket",
                "scheme": "ws",
                "path": "/ws",
                "raw_path": b"/ws",
                "query_string": b"",
                "headers": [],
                "client": ("testclient", 50000),
                "server": ("testserver", 80),
                "subprotocols": [],
            },
            receive,
            send,
        )


def test_sse_formatter_error_includes_trace_id_from_context() -> None:
    token = trace_id_var.set("trace-sse-error")
    try:
        raw = SSEFormatter.format_error("STREAM_ERROR", "boom")
    finally:
        trace_id_var.reset(token)

    payload_line = next(line for line in raw.splitlines() if line.startswith("data: "))
    payload = json.loads(payload_line[6:])

    assert payload["trace_id"] == "trace-sse-error"
