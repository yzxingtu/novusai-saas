from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.enums.common import RecycleStageEnum
from app.tasks import recycle_bin as recycle_bin_task


class _AsyncSessionContext:
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_run_cleanup_promotes_module_stage_then_deletes_global_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    queues = {
        ("tenant", "agents", RecycleStageEnum.MODULE.value): [
            [{"id": 1, "tenant_id": 7}],
            [],
        ],
        ("tenant", "agents", RecycleStageEnum.GLOBAL.value): [
            [{"id": 2, "tenant_id": 7}],
            [],
        ],
        ("admin", "tenants", RecycleStageEnum.MODULE.value): [
            [{"id": 3, "tenant_id": None}],
            [],
        ],
        ("admin", "tenants", RecycleStageEnum.GLOBAL.value): [
            [{"id": 4, "tenant_id": None}],
            [],
        ],
    }

    monkeypatch.setattr(
        recycle_bin_task,
        "_task_async_session",
        lambda: _AsyncSessionContext(db),
    )
    monkeypatch.setattr(
        recycle_bin_task,
        "get_module_codes_for_side",
        lambda side: ["agents"] if side == "tenant" else ["tenants"],
    )

    async def fake_fetch_expired_rows(
        db,
        *,
        module_code: str,
        side: str,
        recycle_stage: str,
        cutoff,
        limit: int = 100,
    ):
        _ = (db, cutoff, limit)
        return queues[(side, module_code, recycle_stage)].pop(0)

    async def fake_promote_rows(db, *, module_code: str, side: str, rows):
        _ = (db, module_code, side)
        return len(rows)

    async def fake_delete_rows(db, *, module_code: str, side: str, rows):
        _ = (db, module_code, side)
        return len(rows)

    monkeypatch.setattr(
        recycle_bin_task,
        "_fetch_expired_rows",
        fake_fetch_expired_rows,
    )
    monkeypatch.setattr(
        recycle_bin_task,
        "_promote_rows",
        AsyncMock(side_effect=fake_promote_rows),
    )
    monkeypatch.setattr(
        recycle_bin_task,
        "_permanently_delete_rows",
        AsyncMock(side_effect=fake_delete_rows),
    )

    result = await recycle_bin_task._run_cleanup(
        module_retention_days=30,
        global_retention_days=30,
    )

    assert result["total_promoted"] == 2
    assert result["total_deleted"] == 2
    assert result["promote_details"] == {
        "tenant:agents": 1,
        "admin:tenants": 1,
    }
    assert result["delete_details"] == {
        "tenant:agents": 1,
        "admin:tenants": 1,
    }


def test_cleanup_recycle_bin_uses_explicit_stage_retention_days(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_cleanup = AsyncMock(
        return_value={
            "total_promoted": 0,
            "total_deleted": 0,
            "promote_details": {},
            "delete_details": {},
            "module_retention_days": 15,
            "global_retention_days": 45,
        }
    )
    monkeypatch.setattr(recycle_bin_task, "_run_cleanup", run_cleanup)

    result = recycle_bin_task.cleanup_recycle_bin.run(
        module_retention_days=15,
        global_retention_days=45,
    )

    run_cleanup.assert_awaited_once_with(
        module_retention_days=15,
        global_retention_days=45,
    )
    assert result["module_retention_days"] == 15
    assert result["global_retention_days"] == 45


def test_cleanup_recycle_bin_rejects_retired_retention_days_parameter() -> None:
    with pytest.raises(TypeError):
        recycle_bin_task.cleanup_recycle_bin.run(retention_days=15)
