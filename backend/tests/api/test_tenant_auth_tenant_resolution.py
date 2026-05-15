"""
Test type: behavioral / structural
Scope: tenant admin auth API tenant-selection boundary.
Mock strategy: AuthService is replaced by a capturing fake; assertions target
route-to-service kwargs and the domain tenant context contract.
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
    def __init__(
        self,
        tenant_code: str | None = None,
        *,
        resolved: bool = True,
    ) -> None:
        self.client = SimpleNamespace(host="198.51.100.8")
        self.state = SimpleNamespace(
            tenant_ctx=SimpleNamespace(
                is_resolved=resolved,
                tenant_code=tenant_code,
            )
        )


def test_tenant_auth_module_uses_domain_tenant_context_fallback() -> None:
    """中文: 测试类型 structural；登录路由支持读取域名租户上下文。

    EN: Test type structural; the login route supports reading domain tenant
    context.
    """
    backend_root = Path(__file__).resolve().parents[2]
    source = (backend_root / "app/api/tenant/auth.py").read_text(encoding="utf-8")

    assert "get_tenant_context" in source
    assert "_tenant_code_from_request_domain" in source
    assert "login_data.tenant_code" not in source
    assert "explicit_tenant_code" not in source
    assert "tenant_id_from_ctx" not in source


@pytest.mark.asyncio
async def test_tenant_auth_route_uses_domain_tenant_code(monkeypatch):
    """中文: 测试类型 behavioral；登录路由使用域名企业编码。

    EN: Test type behavioral; the login route uses the domain tenant code.
    """
    tenant_auth = _load_tenant_auth_module()
    calls: list[dict] = []
    monkeypatch.setattr(tenant_auth, "AuthService", _auth_service_factory(calls))
    monkeypatch.setattr(tenant_auth, "check_login_rate_limit", lambda _request: None)

    db = SimpleNamespace(commit=AsyncMock())

    await tenant_auth.tenant_admin_login(
        db,
        _Request(tenant_code="domain-tenant"),
        SimpleNamespace(
            username="owner",
            password="secret",
            captcha_challenge_id=None,
            captcha_solution=None,
            captcha_provider_code=None,
        ),
    )

    assert len(calls) == 1
    assert calls[0]["tenant_code"] == "domain-tenant"
    assert calls[0]["client_ip"] == "198.51.100.8"
    assert "tenant_id_from_ctx" not in calls[0]


@pytest.mark.asyncio
async def test_tenant_auth_route_ignores_body_tenant_code(monkeypatch):
    """中文: 测试类型 behavioral；请求体企业编码不会覆盖域名企业。

    EN: Test type behavioral; a body tenant code does not override the domain
    tenant.
    """
    tenant_auth = _load_tenant_auth_module()
    calls: list[dict] = []
    monkeypatch.setattr(tenant_auth, "AuthService", _auth_service_factory(calls))
    monkeypatch.setattr(tenant_auth, "check_login_rate_limit", lambda _request: None)

    db = SimpleNamespace(commit=AsyncMock())

    await tenant_auth.tenant_admin_login(
        db,
        _Request(tenant_code="domain-tenant"),
        SimpleNamespace(
            username="owner",
            password="secret",
            tenant_code="spoofed-tenant",
            captcha_challenge_id=None,
            captcha_solution=None,
            captcha_provider_code=None,
        ),
    )

    assert len(calls) == 1
    assert calls[0]["tenant_code"] == "domain-tenant"
    assert calls[0]["client_ip"] == "198.51.100.8"
    assert "tenant_id_from_ctx" not in calls[0]
