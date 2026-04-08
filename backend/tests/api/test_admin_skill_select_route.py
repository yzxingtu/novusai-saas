from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.admin.skills import AdminSkillController


def _get_endpoint(path: str, method: str):
    router = AdminSkillController.get_router()
    for route in router.routes:
        if getattr(route, "path", None) == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found: {method} {path}")


@pytest.mark.asyncio
async def test_select_skills_for_binding_forwards_agent_id() -> None:
    endpoint = _get_endpoint("/ai/skills/select", "GET")

    db = AsyncMock()
    request = MagicMock()
    admin = SimpleNamespace(id=1)

    skill_service = MagicMock()
    skill_service.get_binding_select_options = AsyncMock(
        return_value={
            "items": [],
            "total": 0,
            "page": 2,
            "page_size": 20,
            "has_more": False,
        }
    )

    with patch(
        "app.api.admin.skills.AdminSkillService",
        return_value=skill_service,
    ):
        response = await endpoint(
            request,
            db,
            admin,
            search="calendar",
            agent_id=59,
            package_id=8,
            page=2,
            page_size=20,
            include_system=True,
            only_active=True,
        )

    skill_service.get_binding_select_options.assert_awaited_once_with(
        agent_id=59,
        search="calendar",
        package_id=8,
        page=2,
        page_size=20,
        include_system=True,
        only_active=True,
    )
    assert response["code"] == 0
    assert response["data"]["page"] == 2
