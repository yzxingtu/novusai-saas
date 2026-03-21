"""Webhook 分发器安全加固的回归测试。 / Test."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request

from app.plugins.webhook_dispatcher import _verify_webhook_auth, webhook_dispatcher


def _gate_result(
    manifest: dict,
    *,
    allowed: bool = True,
    reason_code: str = "allowed",
    config: dict | None = None,
):
    return SimpleNamespace(
        allowed=allowed,
        reason_code=reason_code,
        plugin_id=1,
        plugin_name="demo",
        plugin_scope="admin_only",
        plugin_status="enabled",
        manifest=manifest,
        config=config or {},
        granted_capabilities=[],
        pricing_type="free",
        license_status={"runtime_allowed": allowed},
    )


def _build_request(
    method: str = "POST",
    path: str = "/webhooks/plugins/demo/test",
    headers: dict[str, str] | None = None,
    body: bytes = b"{}",
) -> Request:
    raw_headers: list[tuple[bytes, bytes]] = []
    for key, value in (headers or {}).items():
        raw_headers.append((key.lower().encode("utf-8"), value.encode("utf-8")))

    sent = {"done": False}

    async def _receive() -> dict:
        if sent["done"]:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent["done"] = True
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "headers": raw_headers,
    }
    return Request(scope, _receive)


@pytest.mark.asyncio
async def test_verify_webhook_token_auth_supports_encrypted_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.plugins.crypto import _FERNET_PREFIX

    encrypted_token = f"{_FERNET_PREFIX}ciphertext"
    monkeypatch.setattr("app.core.security.decrypt_data", lambda _: "secret-token")

    request = _build_request(headers={"Authorization": "Bearer secret-token"})
    ok = await _verify_webhook_auth(
        auth_type="token",
        auth_config={"secret_config_key": "webhook_token", "header_name": "Authorization"},
        plugin_config={"webhook_token": encrypted_token},
        request=request,
        body=b"{}",
    )

    assert ok is True


@pytest.mark.asyncio
async def test_webhook_dispatcher_redacts_internal_error_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _build_request()

    db = AsyncMock()

    class _SessionContext:
        async def __aenter__(self):
            return db

        async def __aexit__(self, exc_type, exc, tb):
            _ = (exc_type, exc, tb)
            return False

    monkeypatch.setattr("app.core.database.async_session_factory", lambda: _SessionContext())
    monkeypatch.setattr(
        "app.plugins.webhook_dispatcher.evaluate_plugin_runtime_gate",
        AsyncMock(
            return_value=_gate_result(
                {
                    "extensions": {
                        "webhooks": [
                            {
                                "path": "test",
                                "method": "POST",
                                "auth": {"type": "none"},
                                "handler": "webhooks.demo.handle",
                            }
                        ]
                    }
                }
            )
        ),
    )

    async def _raise_handler(**kwargs):
        _ = kwargs
        raise RuntimeError("sensitive stack details")

    class _Registry:
        def get_plugin_webhooks(self, plugin_name: str) -> dict[str, dict]:
            _ = plugin_name
            return {
                "/plugins/demo/test": {"handler": _raise_handler},
            }

    monkeypatch.setattr(
        "app.plugins.registry.ExtensionRegistry.get_instance",
        lambda *_args, **_kwargs: _Registry(),
    )
    monkeypatch.setattr("app.plugins.webhook_dispatcher.settings.DEBUG", False, raising=False)

    response = await webhook_dispatcher("demo", "test", request)

    assert response.status_code == 500
    payload = json.loads(response.body)
    assert payload["error"] == "Internal server error"


@pytest.mark.asyncio
async def test_webhook_dispatcher_returns_404_when_runtime_gate_denies_license(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _build_request()
    db = AsyncMock()

    class _SessionContext:
        async def __aenter__(self):
            return db

        async def __aexit__(self, exc_type, exc, tb):
            _ = (exc_type, exc, tb)
            return False

    monkeypatch.setattr("app.core.database.async_session_factory", lambda: _SessionContext())
    monkeypatch.setattr(
        "app.plugins.webhook_dispatcher.evaluate_plugin_runtime_gate",
        AsyncMock(return_value=_gate_result({}, allowed=False, reason_code="license_inactive")),
    )

    response = await webhook_dispatcher("demo", "test", request)

    assert response.status_code == 404
    payload = json.loads(response.body)
    assert "not found or disabled" in payload["error"]
