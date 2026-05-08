"""
Test type: behavioral / structural
Scope: tenant admin auth API tenant-selection boundary.
Mock strategy: AuthService is replaced by a capturing fake; assertions target
route-to-service kwargs and source-level fallback removal.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _load_tenant_auth_module():
    module_path = Path(__file__).resolve().parents[2] / "app/api/tenant/auth.py"
    spec = importlib.util.spec_from_file_location(
        "test_tenant_auth_module",
        module_path,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _token_pair() -> dict[str, str]:
    return {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "token_type": "bearer",
    }


def _auth_service_factory(calls: list[dict]):
    class _TenantAdminAuth:
        async def authenticate(self, **kwargs):
            calls.append(dict(kwargs))
            return _token_pair()

    class _CapturingAuthService:
        def __init__(self, db):
            self.db = db
            self.tenant_admin_auth = _TenantAdminAuth()

    return _CapturingAuthService


class _Request:
    client = SimpleNamespace(host="198.51.100.8")


def test_tenant_auth_module_has_no_domain_tenant_context_fallback() -> None:
    """中文: 测试类型 structural；登录路由不再读取域名租户上下文。

    EN: Test type structural; the login route no longer reads domain tenant
    context.
    """
    backend_root = Path(__file__).resolve().parents[2]
    source = (backend_root / "app/api/tenant/auth.py").read_text(encoding="utf-8")

    assert "get_tenant_context" not in source
    assert "tenant_id_from_ctx" not in source


@pytest.mark.asyncio
async def test_tenant_auth_route_only_forwards_explicit_tenant_code(monkeypatch):
    """中文: 测试类型 behavioral；登录路由只把显式企业编码传给认证服务。

    EN: Test type behavioral; the login route only forwards the explicit tenant
    code to auth service.
    """
    tenant_auth = _load_tenant_auth_module()
    calls: list[dict] = []
    monkeypatch.setattr(tenant_auth, "AuthService", _auth_service_factory(calls))
    monkeypatch.setattr(tenant_auth, "check_login_rate_limit", lambda _request: None)

    db = SimpleNamespace(commit=AsyncMock())

    await tenant_auth.tenant_admin_login(
        db,
        _Request(),
        SimpleNamespace(
            username="owner",
            password="secret",
            tenant_code="tenant-a",
            captcha_challenge_id=None,
            captcha_solution=None,
            captcha_provider_code=None,
        ),
    )

    assert len(calls) == 1
    assert calls[0]["tenant_code"] == "tenant-a"
    assert calls[0]["client_ip"] == "198.51.100.8"
    assert "tenant_id_from_ctx" not in calls[0]
