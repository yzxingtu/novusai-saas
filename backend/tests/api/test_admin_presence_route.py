from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.api.admin import admin_router


def _get_endpoint(path: str, method: str):
    for route in admin_router.routes:
        if getattr(route, "path", None) == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found: {method} {path}")


@pytest.mark.asyncio
async def test_admin_tenant_user_presence_returns_tenant_scoped_payload() -> None:
    endpoint = _get_endpoint("/ws/presence/tenant/{tenant_id}/users", "GET")

    with patch(
        "app.api.admin.ws.PresenceManager.get_online_details",
        AsyncMock(return_value={7: {"connections": 2}, 11: {"connections": 1}}),
    ) as get_online_details:
        response = await endpoint(
            tenant_id=42,
            admin=SimpleNamespace(id=1),
        )

    get_online_details.assert_awaited_once_with("tenant_user", 42)
    assert response["code"] == 0
    assert response["data"] == {
        "online_ids": [7, 11],
        "total_online": 2,
        "tenant_id": 42,
        "details": {
            "7": {"connections": 2},
            "11": {"connections": 1},
        },
    }
