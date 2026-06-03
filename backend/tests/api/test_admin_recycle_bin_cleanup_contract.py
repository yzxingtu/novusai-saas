"""Test type: behavioral
Scope: admin recycle-bin cleanup API parameter contract.
Mock strategy: mock Celery dispatch only; exercise route parameter handling.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.admin import recycle_bin as recycle_bin_api
from app.exceptions import ValidationException


@pytest.mark.asyncio
@pytest.mark.parametrize("retired_param", ["retention_days", "retentionDays"])
async def test_recycle_bin_cleanup_rejects_retired_retention_days_query(
    retired_param: str,
) -> None:
    request = SimpleNamespace(query_params={retired_param: "30"})

    with pytest.raises(ValidationException, match="retention"):
        await recycle_bin_api.recycle_bin_cleanup(
            request=request,
            db=SimpleNamespace(),
            admin=SimpleNamespace(id=1),
        )


@pytest.mark.asyncio
async def test_recycle_bin_cleanup_dispatches_stage_retention_kwargs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatched: dict[str, object] = {}

    class _Task:
        @staticmethod
        def delay(**kwargs):
            dispatched.update(kwargs)
            return SimpleNamespace(id="cleanup-task")

    monkeypatch.setattr("app.tasks.recycle_bin.cleanup_recycle_bin", _Task)
    request = SimpleNamespace(query_params={})

    response = await recycle_bin_api.recycle_bin_cleanup(
        request=request,
        db=SimpleNamespace(),
        admin=SimpleNamespace(id=1),
        module_retention_days=15,
        global_retention_days=45,
    )

    assert dispatched == {
        "module_retention_days": 15,
        "global_retention_days": 45,
    }
    assert response["data"] == {"task_id": "cleanup-task"}
