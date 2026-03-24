from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.middleware.audit_log import AuditLogMiddleware


@pytest.mark.asyncio
async def test_audit_log_collects_chunked_json_response_metadata() -> None:
    captured: dict[str, object] = {}

    async def chunked_app(scope, receive, send):  # noqa: ANN001
        _ = scope
        await receive()
        await send({"type": "http.response.start", "status": 500, "headers": []})
        await send(
            {
                "type": "http.response.body",
                "body": b'{"code":5000,',
                "more_body": True,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b'"message":"failed"}',
                "more_body": False,
            }
        )

    middleware = AuditLogMiddleware(chunked_app)
    middleware._write_log = AsyncMock(
        side_effect=lambda **kwargs: captured.update(kwargs["response_info"])
    )

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/admin/test",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
    }

    received = False

    async def receive():  # noqa: ANN202
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": b"", "more_body": False}
        return {"type": "http.disconnect"}

    sent_messages: list[dict] = []

    async def send(message):  # noqa: ANN202, ANN001
        sent_messages.append(message)

    await middleware(scope, receive, send)

    assert sent_messages[0]["type"] == "http.response.start"
    assert captured["status_code"] == 500
    assert captured["response_code"] == 5000
    assert captured["response_message"] == "failed"
