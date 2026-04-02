"""Dynamic CORS middleware tests / 动态 CORS 中间件测试."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.core import cors as cors_module
from app.core.config import settings
from app.core.cors import (
    forget_verified_custom_domain,
    get_cors_headers_for_origin,
    is_origin_allowed_sync,
    remember_verified_custom_domain,
)
from app.middleware.dynamic_cors import DynamicCORSMiddleware
from tests.services.conftest import make_scalar_result


class _SessionManager:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, tb):
        return False


async def _ok_handler(request: Request):
    return JSONResponse({"ok": True})


async def _error_handler(request: Request):
    raise ValueError("boom")


def _build_app():
    app = Starlette(
        routes=[
            Route("/ok", _ok_handler),
            Route("/error", _error_handler),
        ]
    )
    app.add_middleware(DynamicCORSMiddleware)
    return app


class TestDynamicCORSMiddleware:
    def test_allows_tenant_subdomain_origin(self):
        client = TestClient(_build_app())
        origin = f"https://demo{settings.TENANT_DOMAIN_SUFFIX}"

        resp = client.get("/ok", headers={"Origin": origin})

        assert resp.status_code == 200
        assert resp.headers["Access-Control-Allow-Origin"] == origin
        assert resp.headers["Access-Control-Allow-Credentials"] == "true"
        assert resp.headers["Vary"] == "Origin"

    def test_rejects_unknown_origin(self):
        client = TestClient(_build_app())

        resp = client.get("/ok", headers={"Origin": "https://evil.example.com"})

        assert resp.status_code == 200
        assert "Access-Control-Allow-Origin" not in resp.headers

    @pytest.mark.asyncio
    async def test_error_header_helper_allows_tenant_subdomain_origin(self):
        origin = f"https://demo{settings.TENANT_DOMAIN_SUFFIX}"
        headers = await get_cors_headers_for_origin(origin)
        assert headers["Access-Control-Allow-Origin"] == origin

    def test_preflight_allows_verified_custom_domain(self, monkeypatch):
        mock_db = type("DB", (), {"execute": None})()
        mock_db.execute = AsyncMock(
            return_value=make_scalar_result("tenant.custom.example.com"),
        )

        monkeypatch.setattr(
            cors_module,
            "async_session_factory",
            lambda: _SessionManager(mock_db),
        )

        client = TestClient(_build_app())
        origin = "https://tenant.custom.example.com"
        resp = client.options(
            "/ok",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-trace-id",
            },
        )

        assert resp.status_code == 204
        assert resp.headers["Access-Control-Allow-Origin"] == origin
        assert resp.headers["Access-Control-Allow-Headers"] == "content-type,x-trace-id"

    def test_socketio_origin_checker_uses_shared_cache(self):
        remember_verified_custom_domain("tenant.custom.example.com")
        try:
            assert is_origin_allowed_sync("https://tenant.custom.example.com")
        finally:
            forget_verified_custom_domain("tenant.custom.example.com")
