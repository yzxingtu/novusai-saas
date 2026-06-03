from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.admin import recycle_bin as admin_recycle_bin
from app.enums.common import RecycleStageEnum


@pytest.mark.asyncio
async def test_admin_global_recycle_bin_list_queries_global_stage_without_level_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SimpleNamespace(
        query_deleted_list=AsyncMock(
            return_value=([SimpleNamespace(id=1)], 1),
        )
    )
    serialize_deleted_items = AsyncMock(return_value=[{"id": 1}])

    monkeypatch.setattr(
        admin_recycle_bin,
        "get_module_config",
        lambda module, side: {"module": module, "side": side},
    )
    monkeypatch.setattr(
        admin_recycle_bin,
        "get_service",
        lambda _module, _side, _db: service,
    )
    monkeypatch.setattr(
        admin_recycle_bin,
        "serialize_deleted_items",
        serialize_deleted_items,
    )

    query = SimpleNamespace(page=1, size=20)
    response = await admin_recycle_bin.recycle_bin_list(
        MagicMock(),
        AsyncMock(),
        SimpleNamespace(id=1),
        query,
        module="agents",
    )

    service.query_deleted_list.assert_awaited_once_with(
        spec=query,
        delete_level=None,
        recycle_stage=RecycleStageEnum.GLOBAL.value,
    )
    serialize_deleted_items.assert_awaited_once()
    assert response["data"]["items"] == [{"id": 1}]


@pytest.mark.asyncio
async def test_admin_global_recycle_bin_restore_and_clear_cover_all_delete_levels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SimpleNamespace(
        restore=AsyncMock(return_value=SimpleNamespace(id=9)),
        permanent_delete=AsyncMock(side_effect=[True, False]),
    )
    list_global_deleted_ids = AsyncMock(return_value=[3, 4])

    monkeypatch.setattr(
        admin_recycle_bin,
        "get_module_config",
        lambda module, side: {"module": module, "side": side},
    )
    monkeypatch.setattr(
        admin_recycle_bin,
        "get_service",
        lambda _module, _side, _db: service,
    )
    monkeypatch.setattr(
        admin_recycle_bin,
        "list_global_deleted_ids",
        list_global_deleted_ids,
    )

    db = AsyncMock()
    db.commit = AsyncMock()
    admin = SimpleNamespace(id=1)

    await admin_recycle_bin.recycle_bin_restore(
        MagicMock(),
        db,
        admin,
        module="agents",
        item_id=9,
    )

    service.restore.assert_awaited_once_with(
        9,
        recycle_stage=RecycleStageEnum.GLOBAL.value,
        delete_level=None,
    )

    response = await admin_recycle_bin.recycle_bin_clear_module(
        MagicMock(),
        db,
        admin,
        module="agents",
    )

    list_global_deleted_ids.assert_awaited_once_with(
        db,
        "agents",
        "admin",
        aggregate_all_levels=True,
    )
    assert service.permanent_delete.await_count == 2
    for call in service.permanent_delete.await_args_list:
        assert call.kwargs == {"delete_level": None}
    assert response["data"]["count"] == 1
