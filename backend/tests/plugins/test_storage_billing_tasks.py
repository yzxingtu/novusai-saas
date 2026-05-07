from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.plugins.module_loader import load_plugin_module


class _FakeAsyncSession:
    def __init__(self, db) -> None:
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, exc_type, exc, tb):
        return None


@pytest.mark.asyncio
async def test_storage_billing_daily_task_commits_after_reconciliation(
    monkeypatch,
) -> None:
    module = load_plugin_module("storage-billing", "tasks")
    assert module is not None

    db = AsyncMock()
    captured = {}

    class _FakeService:
        def __init__(self, db, host_read=None) -> None:
            captured["db"] = db
            captured["host_read"] = host_read

        async def run_daily_reconciliation(self) -> dict:
            return {"run": {"status": "completed"}}

    monkeypatch.setattr(module, "async_session_factory", lambda: _FakeAsyncSession(db))
    monkeypatch.setattr(module, "HostReadFacade", lambda db: {"db": db})
    monkeypatch.setattr(module, "StorageBillingReconciliationService", _FakeService)

    result = await module.run_daily_reconciliation()

    assert result["run"]["status"] == "completed"
    assert captured["db"] is db
    assert captured["host_read"] == {"db": db}
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_storage_billing_qiniu_monthly_task_commits_after_reconciliation(
    monkeypatch,
) -> None:
    module = load_plugin_module("storage-billing", "tasks")
    assert module is not None

    db = AsyncMock()
    captured = {}

    class _FakeService:
        def __init__(self, db, host_read=None) -> None:
            captured["db"] = db
            captured["host_read"] = host_read

        async def run_qiniu_monthly_settlement(self) -> dict:
            return {"run": {"status": "completed", "period_type": "monthly"}}

    monkeypatch.setattr(module, "async_session_factory", lambda: _FakeAsyncSession(db))
    monkeypatch.setattr(module, "HostReadFacade", lambda db: {"db": db})
    monkeypatch.setattr(module, "StorageBillingReconciliationService", _FakeService)

    result = await module.run_qiniu_monthly_settlement()

    assert result["run"]["status"] == "completed"
    assert result["run"]["period_type"] == "monthly"
    assert captured["db"] is db
    assert captured["host_read"] == {"db": db}
    db.commit.assert_awaited_once()
