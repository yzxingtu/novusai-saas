"""GET /ready 就绪探针测试 / Readiness probe tests.

验证：数据库可用时 200；session 工厂失败时 503（不依赖真实停库）。

Test type: structural
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.main import readiness_check


class _HealthyAsyncSession:
    def __init__(self) -> None:
        from unittest.mock import AsyncMock

        self.execute = AsyncMock(return_value=None)


class _HealthyAsyncSessionContext:
    def __init__(self) -> None:
        self.session = _HealthyAsyncSession()

    async def __aenter__(self) -> _HealthyAsyncSession:
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


class _BrokenAsyncSessionContext:
    async def __aenter__(self) -> object:
        raise OSError("simulated database unavailable")

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def _broken_async_session_factory():
    return _BrokenAsyncSessionContext()


@pytest.fixture
def app():
    app = FastAPI()
    app.get("/ready", tags=["Health"], response_model=None)(readiness_check)
    return app


def test_ready_ok_when_database_available(app, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.database.async_session_factory",
        lambda: _HealthyAsyncSessionContext(),
    )

    with TestClient(app) as client:
        resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("code") == 0
    assert body.get("data", {}).get("ready") is True
    assert body.get("data", {}).get("database") == "ok"


def test_ready_503_when_session_factory_raises(
    app, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.core.database.async_session_factory",
        _broken_async_session_factory,
    )

    with TestClient(app) as client:
        resp = client.get("/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body.get("code") == 5030
    assert body.get("message") == "not_ready"
    assert body.get("data", {}).get("database") == "unavailable"
