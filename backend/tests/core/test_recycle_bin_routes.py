from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import APIRouter

from app.api.admin.periodic_tasks import router as admin_periodic_tasks_router
from app.core.recycle_bin import (
    register_admin_recycle_bin_routes,
    register_tenant_recycle_bin_routes,
)
from app.enums.common import DeleteLevelEnum, RecycleStageEnum


class _RouteService:
    instances: list["_RouteService"] = []

    def __init__(self, db, tenant_id: int | None = None):
        self.db = db
        self.tenant_id = tenant_id
        self.count_deleted = AsyncMock(return_value=3)
        self.query_deleted_list = AsyncMock(return_value=([], 0))
        self.restore = AsyncMock(return_value=SimpleNamespace(id=1))
        self.promote_to_global = AsyncMock(return_value=SimpleNamespace(id=1))
        self.batch_promote_to_global = AsyncMock(return_value=2)
        self.preview_delete = AsyncMock(
            return_value={
                "blocked": False,
                "blockers": [],
                "cascade_soft": [],
                "cascade_delete": [],
                "nullify": [],
            }
        )
        self.__class__.instances.append(self)

    @classmethod
    def reset(cls) -> None:
        cls.instances.clear()


def _get_endpoint(router: APIRouter, path: str, method: str):
    for route in router.routes:
        if getattr(route, "path", None) == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found: {method} {path}")


@pytest.mark.asyncio
async def test_tenant_recycle_bin_routes_use_module_stage_filters() -> None:
    _RouteService.reset()
    router = APIRouter()
    register_tenant_recycle_bin_routes(router, _RouteService, "agent")

    db = AsyncMock()
    db.commit = AsyncMock()
    request = MagicMock()
    tenant_admin = SimpleNamespace(tenant_id=42)
    query = SimpleNamespace(page=2, size=10)

    count_endpoint = _get_endpoint(router, "/recycle-bin/count", "GET")
    await count_endpoint(request, db, tenant_admin)
    count_service = _RouteService.instances[-1]
    count_service.count_deleted.assert_awaited_once_with(
        delete_level=DeleteLevelEnum.TENANT.value,
        recycle_stage=RecycleStageEnum.MODULE.value,
    )
    assert count_service.tenant_id == 42

    list_endpoint = _get_endpoint(router, "/recycle-bin", "GET")
    response = await list_endpoint(request, db, tenant_admin, query)
    list_service = _RouteService.instances[-1]
    list_service.query_deleted_list.assert_awaited_once_with(
        spec=query,
        delete_level=DeleteLevelEnum.TENANT.value,
        recycle_stage=RecycleStageEnum.MODULE.value,
    )
    assert list_service.tenant_id == 42
    assert response["data"]["page"] == 2
    assert response["data"]["page_size"] == 10


@pytest.mark.asyncio
async def test_admin_recycle_bin_routes_promote_single_delete_to_global() -> None:
    _RouteService.reset()
    router = APIRouter()
    register_admin_recycle_bin_routes(router, _RouteService, "tenant")

    db = AsyncMock()
    db.commit = AsyncMock()
    request = MagicMock()
    admin = SimpleNamespace(id=1)

    delete_endpoint = _get_endpoint(router, "/recycle-bin/{item_id}", "DELETE")
    response = await delete_endpoint(request, db, 9, admin)

    service = _RouteService.instances[-1]
    service.promote_to_global.assert_awaited_once_with(9)
    db.commit.assert_awaited_once()
    assert response["code"] == 0


def test_admin_recycle_bin_static_batch_routes_precede_dynamic_item_routes() -> None:
    router = APIRouter()
    register_admin_recycle_bin_routes(router, _RouteService, "tenant")

    paths = [route.path for route in router.routes]

    assert paths.index("/recycle-bin/batch") < paths.index("/recycle-bin/{item_id}")
    assert paths.index("/recycle-bin/batch-restore") < paths.index(
        "/recycle-bin/{item_id}/restore"
    )


def test_admin_periodic_task_controller_registers_recycle_bin_before_task_id_routes() -> None:
    paths = [route.path for route in admin_periodic_tasks_router.routes]

    assert paths.index("/periodic-tasks/recycle-bin") < paths.index(
        "/periodic-tasks/{task_id}"
    )
    assert paths.index("/periodic-tasks/recycle-bin/count") < paths.index(
        "/periodic-tasks/{task_id}"
    )
