from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.admin.skill_packages import AdminSkillPackageController
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
        )

    skill_service.get_binding_select_options.assert_awaited_once_with(
        agent_id=59,
        search="calendar",
        package_id=8,
        page=2,
        page_size=20,
        include_system=True,
    )
    assert response["code"] == 0
    assert response["data"]["page"] == 2


@pytest.mark.asyncio
async def test_select_skill_packages_uses_paginated_contract() -> None:
    endpoint = next(
        route.endpoint
        for route in AdminSkillPackageController.get_router().routes
        if getattr(route, "path", None) == "/ai/skill-packages/select"
        and "GET" in route.methods
    )

    db = AsyncMock()
    request = MagicMock()
    admin = SimpleNamespace(id=1)

    package_service = MagicMock()
    package_service.get_select_options = AsyncMock(
        return_value={
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
            "has_more": False,
        }
    )

    with patch(
        "app.api.admin.skill_packages.AdminSkillPackageService",
        return_value=package_service,
    ):
        response = await endpoint(
            request,
            db,
            admin,
            search="weather",
            include_system=False,
            page=1,
            page_size=20,
        )

    package_service.get_select_options.assert_awaited_once_with(
        search="weather",
        limit=100,
        page=1,
        page_size=20,
        is_system=False,
    )
    assert response["code"] == 0
    assert response["data"]["page"] == 1
