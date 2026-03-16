"""Plugin API dispatcher / sandbox security regression tests. 插件 API 分发与沙箱安全回归测试."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request

from app.enums.plugin import PluginStatusEnum
from app.plugins.api_dispatcher import (
    _context_has_db_capability,
    _dispatch_plugin_api,
    _handler_accepts_param,
)
from app.plugins.context import PluginContext, PluginDbProxy
from app.plugins.exceptions import PluginSecurityError


class _OwnTableModel:
    __tablename__ = "px_demo_items"


class _ForeignTableModel:
    __tablename__ = "users"


class _DependencyTableModel:
    __tablename__ = "px_dependency_items"


class _CtxWithCap:
    def has_capability(self, cap: str) -> bool:
        return cap == "db:own_tables"


class _CtxWithoutCap:
    def has_capability(self, cap: str) -> bool:
        _ = cap
        return False


def _build_request(
    method: str = "GET",
    path: str = "/admin/plugins/demo/api/ping",
) -> Request:
    async def _receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "headers": [],
    }
    return Request(scope, _receive)


def _enabled_plugin_row(manifest: dict) -> tuple:
    return (
        1,
        PluginStatusEnum.ENABLED.value,
        "admin_only",
        manifest,
        [],
    )


def test_handler_accepts_param_by_name() -> None:
    def handler(request, ctx):
        return request, ctx

    assert _handler_accepts_param(handler, "request") is True
    assert _handler_accepts_param(handler, "ctx") is True
    assert _handler_accepts_param(handler, "db") is False


def test_handler_accepts_param_by_kwargs() -> None:
    """**kwargs 不视为显式接受参数，不自动注入 / **kwargs does not receive auto-injection."""
    def handler(request, **kwargs):
        return request, kwargs

    assert _handler_accepts_param(handler, "db") is False


def test_context_has_db_capability() -> None:
    assert _context_has_db_capability(_CtxWithCap()) is True
    assert _context_has_db_capability(_CtxWithoutCap()) is False


@pytest.mark.asyncio
async def test_plugin_db_proxy_blocks_raw_session_access() -> None:
    proxy = PluginDbProxy(AsyncMock(), "demo")

    with pytest.raises(PluginSecurityError):
        _ = proxy.session


@pytest.mark.asyncio
async def test_plugin_db_proxy_blocks_foreign_model_get() -> None:
    proxy = PluginDbProxy(AsyncMock(), "demo")

    with pytest.raises(PluginSecurityError):
        await proxy.get(_ForeignTableModel, 1)


@pytest.mark.asyncio
async def test_plugin_db_proxy_allows_own_table_model_add_all() -> None:
    db = MagicMock()
    proxy = PluginDbProxy(db, "demo")

    proxy.add_all([_OwnTableModel()])

    db.add_all.assert_called_once()


@pytest.mark.asyncio
async def test_plugin_context_get_db_blocks_dependency_prefix_tables() -> None:
    manifest = MagicMock()
    # 即使声明依赖插件，也不应放宽 DB 前缀沙箱
    manifest.dependencies.plugins = ["dependency"]

    ctx = PluginContext(
        plugin_name="demo",
        manifest=manifest,
        db=MagicMock(),
        granted_capabilities=["db:own_tables"],
    )
    proxy = ctx.get_db()

    with pytest.raises(PluginSecurityError):
        await proxy.get(_DependencyTableModel, 1)


@pytest.mark.asyncio
async def test_dispatch_raises_app_exception_when_handler_returns_error_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = {
        "extensions": {
            "api": {
                "admin_routes": [
                    {"path": "ping", "method": "GET", "handler": "handlers.demo.ping"},
                ],
                "tenant_routes": [],
                "public_routes": [],
            }
        }
    }
    query_result = MagicMock()
    query_result.one_or_none.return_value = _enabled_plugin_row(manifest)

    db = AsyncMock()
    db.execute = AsyncMock(return_value=query_result)

    def _handler(request=None, ctx=None):  # noqa: ANN001
        _ = (request, ctx)
        return {"error": "permission denied", "code": 4030}

    monkeypatch.setattr("app.plugins.api_dispatcher.load_plugin_handler", lambda *_: _handler)
    monkeypatch.setattr("app.plugins.api_dispatcher._build_plugin_context", lambda **_: _CtxWithoutCap())

    request = _build_request(path="/admin/plugins/demo/api/ping")
    with pytest.raises(Exception) as exc_info:
        await _dispatch_plugin_api(
            plugin_name="demo",
            path="ping",
            request=request,
            db=db,
        )

    assert getattr(exc_info.value, "code", None) == 4030
    assert getattr(exc_info.value, "status_code", None) == 403
    assert "permission denied" in str(exc_info.value)


@pytest.mark.asyncio
async def test_dispatch_raises_app_exception_on_handler_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = {
        "extensions": {
            "api": {
                "admin_routes": [
                    {"path": "ping", "method": "GET", "handler": "handlers.demo.ping"},
                ],
                "tenant_routes": [],
                "public_routes": [],
            }
        }
    }
    query_result = MagicMock()
    query_result.one_or_none.return_value = _enabled_plugin_row(manifest)

    db = AsyncMock()
    db.execute = AsyncMock(return_value=query_result)

    def _handler(request=None, ctx=None):  # noqa: ANN001
        _ = (request, ctx)
        raise RuntimeError("boom")

    monkeypatch.setattr("app.plugins.api_dispatcher.load_plugin_handler", lambda *_: _handler)
    monkeypatch.setattr("app.plugins.api_dispatcher._build_plugin_context", lambda **_: _CtxWithoutCap())
    monkeypatch.setattr("app.plugins.api_dispatcher.settings.DEBUG", False, raising=False)

    request = _build_request(path="/admin/plugins/demo/api/ping")
    with pytest.raises(Exception) as exc_info:
        await _dispatch_plugin_api(
            plugin_name="demo",
            path="ping",
            request=request,
            db=db,
        )

    assert getattr(exc_info.value, "code", None) == 5000
    assert getattr(exc_info.value, "status_code", None) == 500
    assert str(exc_info.value) == "Internal server error"
