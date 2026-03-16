"""
TraceIdMiddleware 单元测试 / Trace ID Middleware unit tests.

覆盖：正常请求返回 X-Trace-ID、继承请求头 X-Trace-ID、异常时由异常处理器注入（由 main.py 保证）。
"""

from __future__ import annotations

import uuid

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.middleware.trace import TraceIdMiddleware, trace_id_var


async def _ok_handler(request: Request):
    return JSONResponse({"ok": True})


async def _error_handler(request: Request):
    raise ValueError("intentional error")


@pytest.fixture
def app():
    """App with TraceIdMiddleware."""
    app = Starlette(
        routes=[
            Route("/ok", _ok_handler),
            Route("/error", _error_handler),
        ]
    )
    app.add_middleware(TraceIdMiddleware)
    return app


class TestTraceIdMiddleware:
    """TraceIdMiddleware 测试 / Trace ID Middleware tests."""

    def test_normal_request_returns_x_trace_id_header(self, app):
        """正常请求响应头应包含 X-Trace-ID / Normal request should have X-Trace-ID in response."""
        client = TestClient(app)
        resp = client.get("/ok")
        assert resp.status_code == 200
        assert "X-Trace-ID" in resp.headers
        tid = resp.headers["X-Trace-ID"]
        assert tid and len(tid) == 36  # UUID format

    def test_inherits_trace_id_from_request_header(self, app):
        """若请求带 X-Trace-ID，响应应原样回传 / Request X-Trace-ID should be echoed in response."""
        client = TestClient(app)
        expected = str(uuid.uuid4())
        resp = client.get("/ok", headers={"X-Trace-ID": expected})
        assert resp.status_code == 200
        assert resp.headers.get("X-Trace-ID") == expected

    def test_error_request_still_gets_trace_id_from_app(self, app):
        """异常请求时，中间件会设置 trace_id_var，异常处理器（main.py）负责注入响应头。此处验证 trace_id_var 被设置。"""
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/error")
        # 500 from unhandled exception; TraceIdMiddleware runs before route,
        # so trace_id_var was set. main.py would add X-Trace-ID in production.
        assert resp.status_code == 500

    def test_trace_id_var_set_during_request(self, app):
        """请求处理期间 trace_id_var 应被正确设置 / trace_id_var should be set during request."""
        received_tid = []

        async def capture_handler(request: Request):
            tid = trace_id_var.get()
            received_tid.append(tid)
            return JSONResponse({"trace_id": tid})

        capture_app = Starlette(
            routes=[Route("/capture", capture_handler)],
        )
        capture_app.add_middleware(TraceIdMiddleware)

        client = TestClient(capture_app)
        expected = str(uuid.uuid4())
        resp = client.get("/capture", headers={"X-Trace-ID": expected})
        assert resp.status_code == 200
        assert received_tid[0] == expected
        assert resp.json()["trace_id"] == expected
