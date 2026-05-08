"""
Test type: behavioral
Scope: user auth API tenant-selection boundary.
Mock strategy: AuthService is replaced by a capturing fake; assertions target the
route-to-service kwargs rather than a mocked success value.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _token_pair() -> dict[str, str]:
    return {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "token_type": "bearer",
    }


def _auth_service_factory(calls: list[tuple[str, dict]]):
    class _CapturingAuthService:
        def __init__(self, db):
            self.db = db

        async def authenticate_tenant_user(self, **kwargs):
            calls.append(("authenticate_tenant_user", dict(kwargs)))
            return _token_pair()

        async def send_tenant_user_login_code(self, **kwargs):
            calls.append(("send_tenant_user_login_code", dict(kwargs)))
            return {"sent": True}

        async def authenticate_tenant_user_by_code(self, **kwargs):
            calls.append(("authenticate_tenant_user_by_code", dict(kwargs)))
            return _token_pair()

        async def register_tenant_user(self, **kwargs):
            calls.append(("register_tenant_user", dict(kwargs)))
            return {"id": 17}

        async def request_password_reset(self, **kwargs):
            calls.append(("request_password_reset", dict(kwargs)))
            return {"sent": True}

        async def reset_tenant_user_password(self, **kwargs):
            calls.append(("reset_tenant_user_password", dict(kwargs)))

    return _CapturingAuthService


class _Request:
    client = SimpleNamespace(host="198.51.100.7")

    async def form(self) -> dict[str, str]:
        return {
            "tenant_code": "form-tenant",
            "captcha_challenge_id": "challenge-1",
            "captcha_solution": "solution-1",
            "captcha_provider_code": "captcha-provider",
        }


def _load_user_auth_module():
    backend_root = Path(__file__).resolve().parents[2]
    module_path = backend_root / "app/api/user/auth.py"
    spec = importlib.util.spec_from_file_location(
        "test_user_auth_tenant_resolution_auth_module",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("Unable to load app/api/user/auth.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_user_auth_module_has_no_domain_tenant_context_fallback() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    source = (backend_root / "app/api/user/auth.py").read_text(encoding="utf-8")

    assert "get_tenant_context" not in source
    assert "tenant_id_from_ctx" not in source


@pytest.mark.asyncio
async def test_user_auth_routes_only_forward_explicit_tenant_code(monkeypatch):
    user_auth = _load_user_auth_module()

    calls: list[tuple[str, dict]] = []
    monkeypatch.setattr(user_auth, "AuthService", _auth_service_factory(calls))
    monkeypatch.setattr(user_auth, "check_login_rate_limit", lambda _request: None)

    db = SimpleNamespace(commit=AsyncMock())
    request = _Request()

    await user_auth.login_oauth2(
        db,
        request,
        SimpleNamespace(username="alice", password="secret"),
    )
    await user_auth.login_json(
        db,
        request,
        SimpleNamespace(
            username="bob",
            password="secret",
            tenant_code="json-tenant",
            captcha_challenge_id=None,
            captcha_solution=None,
            captcha_provider_code=None,
        ),
    )
    await user_auth.send_login_code(
        db,
        request,
        SimpleNamespace(
            channel="email",
            email="alice@example.com",
            phone=None,
            tenant_code="code-tenant",
            captcha_challenge_id=None,
            captcha_solution=None,
            captcha_provider_code=None,
        ),
    )
    await user_auth.login_by_code(
        db,
        request,
        SimpleNamespace(
            channel="email",
            code="123456",
            email="alice@example.com",
            phone=None,
            tenant_code="otp-tenant",
        ),
    )
    await user_auth.register(
        db,
        request,
        SimpleNamespace(
            username="carol",
            email="carol@example.com",
            password="secret123",
            tenant_code="register-tenant",
            phone=None,
            nickname=None,
            captcha_challenge_id=None,
            captcha_solution=None,
            captcha_provider_code=None,
        ),
    )
    await user_auth.forgot_password(
        db,
        request,
        SimpleNamespace(email="dave@example.com", tenant_code="forgot-tenant"),
    )
    await user_auth.reset_password(
        db,
        request,
        SimpleNamespace(
            email="erin@example.com",
            code="654321",
            new_password="secret123",
            tenant_code="reset-tenant",
        ),
    )

    assert [name for name, _kwargs in calls] == [
        "authenticate_tenant_user",
        "authenticate_tenant_user",
        "send_tenant_user_login_code",
        "authenticate_tenant_user_by_code",
        "register_tenant_user",
        "request_password_reset",
        "reset_tenant_user_password",
    ]
    assert [kwargs.get("tenant_code") for _name, kwargs in calls] == [
        "form-tenant",
        "json-tenant",
        "code-tenant",
        "otp-tenant",
        "register-tenant",
        "forgot-tenant",
        "reset-tenant",
    ]
    assert all("tenant_id_from_ctx" not in kwargs for _name, kwargs in calls)
