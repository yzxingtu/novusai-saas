"""Plugin API dispatcher / sandbox security regression tests. 插件 API 分发与沙箱安全回归测试."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.requests import Request

from app.core.security import TOKEN_SCOPE_ADMIN
from app.plugins.api_dispatcher import (
    _context_has_db_capability,
    _check_plugin_permission,
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


def _gate_result(
    manifest: dict,
    *,
    allowed: bool = True,
    reason_code: str = "allowed",
    granted_capabilities: list[str] | None = None,
):
    return SimpleNamespace(
        allowed=allowed,
        reason_code=reason_code,
        plugin_id=1,
        plugin_name="demo",
        plugin_scope="admin_only",
        plugin_status="enabled",
        manifest=manifest,
        config={},
        granted_capabilities=granted_capabilities or [],
        pricing_type="free",
        license_status={"runtime_allowed": allowed},
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
    db = AsyncMock()

    def _handler(request=None, ctx=None):  # noqa: ANN001
        _ = (request, ctx)
        return {"error": "permission denied", "code": 4030}

    monkeypatch.setattr(
        "app.plugins.api_dispatcher.evaluate_plugin_runtime_gate",
        AsyncMock(return_value=_gate_result(manifest)),
    )
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
    db = AsyncMock()

    def _handler(request=None, ctx=None):  # noqa: ANN001
        _ = (request, ctx)
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "app.plugins.api_dispatcher.evaluate_plugin_runtime_gate",
        AsyncMock(return_value=_gate_result(manifest)),
    )
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
    assert str(exc_info.value) == "服务器内部错误"
    assert "boom" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_dispatch_raises_app_exception_on_error_json_response(
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
    db = AsyncMock()

    def _handler(request=None, ctx=None):  # noqa: ANN001
        _ = (request, ctx)
        return JSONResponse(
            status_code=500,
            content={"code": 5000, "message": "raw plugin traceback"},
        )

    monkeypatch.setattr(
        "app.plugins.api_dispatcher.evaluate_plugin_runtime_gate",
        AsyncMock(return_value=_gate_result(manifest)),
    )
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
    assert str(exc_info.value) == "服务器内部错误"


@pytest.mark.asyncio
async def test_dispatch_allows_success_streaming_response_passthrough(
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
    db = AsyncMock()

    def _handler(request=None, ctx=None):  # noqa: ANN001
        _ = (request, ctx)
        return StreamingResponse(iter([b"ok"]), media_type="text/plain")

    monkeypatch.setattr(
        "app.plugins.api_dispatcher.evaluate_plugin_runtime_gate",
        AsyncMock(return_value=_gate_result(manifest)),
    )
    monkeypatch.setattr("app.plugins.api_dispatcher.load_plugin_handler", lambda *_: _handler)
    monkeypatch.setattr("app.plugins.api_dispatcher._build_plugin_context", lambda **_: _CtxWithoutCap())

    response = await _dispatch_plugin_api(
        plugin_name="demo",
        path="ping",
        request=_build_request(path="/admin/plugins/demo/api/ping"),
        db=db,
    )

    assert isinstance(response, StreamingResponse)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dispatch_uses_scope_trace_id_for_plugin_context_request_id(
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
    db = AsyncMock()
    captured: dict[str, object] = {}

    def _handler(request=None, ctx=None):  # noqa: ANN001
        _ = (request, ctx)
        return {"ok": True}

    def _fake_build_plugin_context(**kwargs):
        captured.update(kwargs)
        return _CtxWithoutCap()

    monkeypatch.setattr(
        "app.plugins.api_dispatcher.evaluate_plugin_runtime_gate",
        AsyncMock(return_value=_gate_result(manifest)),
    )
    monkeypatch.setattr("app.plugins.api_dispatcher.load_plugin_handler", lambda *_: _handler)
    monkeypatch.setattr("app.plugins.api_dispatcher._build_plugin_context", _fake_build_plugin_context)

    request = _build_request(path="/admin/plugins/demo/api/ping")
    request.scope["state"] = {"trace_id": "trace-generated-by-middleware"}

    await _dispatch_plugin_api(
        plugin_name="demo",
        path="ping",
        request=request,
        db=db,
    )

    assert captured["request_id"] == "trace-generated-by-middleware"


@pytest.mark.asyncio
async def test_dispatch_returns_404_when_runtime_gate_denies_license(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    monkeypatch.setattr(
        "app.plugins.api_dispatcher.evaluate_plugin_runtime_gate",
        AsyncMock(
            return_value=_gate_result(
                manifest={},
                allowed=False,
                reason_code="license_inactive",
            )
        ),
    )

    response = await _dispatch_plugin_api(
        plugin_name="demo",
        path="ping",
        request=_build_request(path="/admin/plugins/demo/api/ping"),
        db=db,
    )

    assert response.status_code == 404
    assert b"Plugin not found or disabled" in response.body


@pytest.mark.asyncio
async def test_admin_dispatcher_no_longer_falls_back_to_tenant_routes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = {
        "extensions": {
            "api": {
                "admin_routes": [],
                "tenant_routes": [
                    {"path": "ping", "method": "GET", "handler": "handlers.demo.ping"},
                ],
                "public_routes": [],
            }
        }
    }
    db = AsyncMock()
    monkeypatch.setattr(
        "app.plugins.api_dispatcher.evaluate_plugin_runtime_gate",
        AsyncMock(return_value=_gate_result(manifest)),
    )

    response = await _dispatch_plugin_api(
        plugin_name="demo",
        path="ping",
        request=_build_request(path="/admin/plugins/demo/api/ping"),
        db=db,
    )

    assert response.status_code == 404
    assert b"Route not found" in response.body


@pytest.mark.asyncio
async def test_check_plugin_permission_requires_admin_rbac_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    admin = SimpleNamespace(id=9, is_super=False, role_id=3, is_deleted=False)

    class _Result:
        def scalar_one_or_none(self):
            return admin

    db.execute.return_value = _Result()

    registry = MagicMock()
    registry.get_plugin_permissions.return_value = [
        {"code": "plugin.demo.runtime_ops", "actions": ["view", "terminate"]},
    ]

    class _PermService:
        def __init__(self, _db):
            self._db = _db

        async def get_admin_permissions(self, _admin):
            return {"plugin.demo.runtime_ops:view"}

        def check_permission(self, user_permissions: set[str], required: str) -> bool:
            return required in user_permissions

    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry,
    )
    monkeypatch.setattr(
        "app.rbac.services.permission_service.PermissionService",
        _PermService,
    )

    allowed = await _check_plugin_permission(
        db=db,
        plugin_name="demo",
        route_permission="runtime_ops:view",
        user_id=admin.id,
        user_role=TOKEN_SCOPE_ADMIN,
        tenant_id=None,
    )

    assert allowed is True


@pytest.mark.asyncio
async def test_check_plugin_permission_denies_admin_without_required_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    admin = SimpleNamespace(id=9, is_super=False, role_id=3, is_deleted=False)

    class _Result:
        def scalar_one_or_none(self):
            return admin

    db.execute.return_value = _Result()

    registry = MagicMock()
    registry.get_plugin_permissions.return_value = [
        {"code": "plugin.demo.runtime_ops", "actions": ["view", "terminate"]},
    ]

    class _PermService:
        def __init__(self, _db):
            self._db = _db

        async def get_admin_permissions(self, _admin):
            return {"plugin.demo.runtime_ops:view"}

        def check_permission(self, user_permissions: set[str], required: str) -> bool:
            return required in user_permissions

    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry,
    )
    monkeypatch.setattr(
        "app.rbac.services.permission_service.PermissionService",
        _PermService,
    )

    allowed = await _check_plugin_permission(
        db=db,
        plugin_name="demo",
        route_permission="runtime_ops:terminate",
        user_id=admin.id,
        user_role=TOKEN_SCOPE_ADMIN,
        tenant_id=None,
    )

    assert allowed is False


@pytest.mark.asyncio
async def test_dispatch_returns_403_when_admin_lacks_plugin_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = {
        "extensions": {
            "api": {
                "admin_routes": [
                    {
                        "path": "runs/1",
                        "method": "GET",
                        "handler": "handlers.demo.runs",
                        "permission": "runtime_ops:view",
                    },
                ],
                "tenant_routes": [],
                "public_routes": [],
            }
        }
    }
    db = AsyncMock()
    monkeypatch.setattr(
        "app.plugins.api_dispatcher.evaluate_plugin_runtime_gate",
        AsyncMock(return_value=_gate_result(manifest)),
    )
    monkeypatch.setattr(
        "app.plugins.api_dispatcher._check_plugin_permission",
        AsyncMock(return_value=False),
    )

    response = await _dispatch_plugin_api(
        plugin_name="demo",
        path="runs/1",
        request=_build_request(path="/admin/plugins/demo/api/runs/1"),
        db=db,
        user_id=9,
        user_role=TOKEN_SCOPE_ADMIN,
    )

    assert response.status_code == 403
    assert b"Permission denied" in response.body


@pytest.mark.asyncio
async def test_admin_plugin_permission_requires_platform_rbac_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()

    class _Result:
        def scalar_one_or_none(self):
            return SimpleNamespace(id=7, is_super=False, role_id=11)

    db.execute = AsyncMock(return_value=_Result())

    class _PermService:
        def __init__(self, _db):
            self.db = _db

        async def get_admin_permissions(self, _admin):
            return {"plugin.demo.other:view"}

        def check_permission(self, user_permissions: set[str], required: str) -> bool:
            return required in user_permissions

    registry = MagicMock()
    registry.get_plugin_permissions.return_value = [
        {"code": "plugin.demo.orchestration_admin", "actions": ["view", "configure"]}
    ]

    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry,
    )
    monkeypatch.setattr(
        "app.rbac.services.permission_service.PermissionService",
        _PermService,
    )

    allowed = await _check_plugin_permission(
        db,
        "demo",
        "orchestration_admin:view",
        user_id=7,
        user_role="admin",
        tenant_id=None,
    )

    assert allowed is False


@pytest.mark.asyncio
async def test_admin_plugin_permission_allows_platform_rbac_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()

    class _Result:
        def scalar_one_or_none(self):
            return SimpleNamespace(id=7, is_super=False, role_id=11)

    db.execute = AsyncMock(return_value=_Result())

    class _PermService:
        def __init__(self, _db):
            self.db = _db

        async def get_admin_permissions(self, _admin):
            return {"plugin.demo.orchestration_admin:view"}

        def check_permission(self, user_permissions: set[str], required: str) -> bool:
            return required in user_permissions

    registry = MagicMock()
    registry.get_plugin_permissions.return_value = [
        {"code": "plugin.demo.orchestration_admin", "actions": ["view", "configure"]}
    ]

    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda: registry,
    )
    monkeypatch.setattr(
        "app.rbac.services.permission_service.PermissionService",
        _PermService,
    )

    allowed = await _check_plugin_permission(
        db,
        "demo",
        "orchestration_admin:view",
        user_id=7,
        user_role="admin",
        tenant_id=None,
    )

    assert allowed is True
