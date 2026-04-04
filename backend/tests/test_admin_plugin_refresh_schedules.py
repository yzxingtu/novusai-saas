from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.admin.plugins import AdminPluginController


def _get_endpoint(path: str, method: str):
    router = AdminPluginController.get_router()
    for route in router.routes:
      if getattr(route, "path", None) == path and method in route.methods:
          return route.endpoint
    raise AssertionError(f"Route not found: {method} {path}")


@pytest.mark.asyncio
async def test_admin_refresh_plugin_schedules_calls_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(AdminPluginController, "_instance", None)
    monkeypatch.setattr(AdminPluginController, "_router", None)

    service = SimpleNamespace(
        refresh_plugin_schedules=AsyncMock(
            return_value={
                "mode": "recover_error",
                "plugin_id": 8,
                "plugin_name": "demo-plugin",
                "task_count": 2,
            }
        )
    )
    monkeypatch.setattr(
        AdminPluginController,
        "get_service",
        lambda _self, _db: service,
    )

    endpoint = _get_endpoint("/plugins/{plugin_id}/refresh-schedules", "POST")
    db = AsyncMock()
    db.commit = AsyncMock()
    admin = SimpleNamespace(id=3)

    response = await endpoint(8, db, admin)

    service.refresh_plugin_schedules.assert_awaited_once_with(8, operator_id=3)
    db.commit.assert_awaited_once()
    assert response["message"]
    assert response["data"]["mode"] == "recover_error"
