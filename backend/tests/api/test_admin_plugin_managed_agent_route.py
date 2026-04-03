from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.services.conftest import make_mock_model


def _get_endpoint(path: str, method: str):
    from app.api.admin.agents import AdminAgentController

    router = AdminAgentController.get_router()
    for route in router.routes:
        if getattr(route, "path", None) == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"Route not found: {method} {path}")


def _make_agent(**overrides):
    defaults = {
        "id": 55,
        "owner_tenant_id": None,
        "source_plugin": "novusdoc",
        "scope": "admin_and_selected_tenants",
        "name": "NovusDoc Writer",
        "avatar": "27",
        "description": "writer",
        "status": "published",
        "execution_mode": "conversation",
        "is_system": True,
        "model_id": 9,
        "memory_enabled": True,
        "input_variables": [],
        "published_version": None,
        "welcome_message": None,
        "suggested_questions": None,
        "created_at": "2026-03-14T19:51:24+00:00",
        "updated_at": "2026-03-21T13:30:54+00:00",
        "skill_grants": [],
    }
    defaults.update(overrides)
    agent = make_mock_model(**defaults)
    agent.model = SimpleNamespace(name="gpt-5.4-xhigh", code="gpt-5.4-xhigh")
    return agent


@pytest.mark.asyncio
async def test_list_agents_includes_source_plugin_metadata() -> None:
    endpoint = _get_endpoint("/ai/agents", "GET")

    db = AsyncMock()
    request = MagicMock()
    admin = SimpleNamespace(id=1)
    query = SimpleNamespace(page=1, size=20)
    agent = _make_agent()
    admin_service = MagicMock()
    admin_service.query_list = AsyncMock(return_value=([agent], 1))
    sync_service = MagicMock()
    sync_service.get_source_plugin_map = AsyncMock(
        return_value={
            "novusdoc": SimpleNamespace(
                name="novusdoc",
                display_name="文档管理",
                enabled=True,
                scope="admin_and_selected_tenants",
            )
        }
    )

    with patch(
        "app.api.admin.agents.AdminAgentService",
        return_value=admin_service,
    ), patch(
        "app.api.admin.agents.PluginManagedAgentSyncService",
        return_value=sync_service,
    ):
        response = await endpoint(request, db, admin, query)

    item = response["data"]["items"][0]
    assert item["source_plugin"] == "novusdoc"
    assert item["source_plugin_display_name"] == "文档管理"
    assert item["source_plugin_enabled"] is True
    assert item["source_plugin_scope"] == "admin_and_selected_tenants"


@pytest.mark.asyncio
async def test_get_agent_detail_uses_plugin_assignments_for_plugin_managed_agent() -> None:
    endpoint = _get_endpoint("/ai/agents/{agent_id}", "GET")

    db = AsyncMock()
    request = MagicMock()
    admin = SimpleNamespace(id=1)
    agent = _make_agent()
    agent.to_dict.return_value = {
        "id": 55,
        "name": "NovusDoc Writer",
        "scope": "admin_and_selected_tenants",
        "source_plugin": "novusdoc",
    }
    admin_service = MagicMock()
    admin_service.get_by_id = AsyncMock(return_value=agent)
    admin_service.get_memory_config = AsyncMock(
        return_value={"effective_memory_enabled": True}
    )
    sync_service = MagicMock()
    sync_service.get_source_plugin_map = AsyncMock(
        return_value={
            "novusdoc": SimpleNamespace(
                name="novusdoc",
                display_name="文档管理",
                enabled=True,
                scope="admin_and_selected_tenants",
            )
        }
    )
    sync_service.get_effective_agent_assignment_ids = AsyncMock(return_value=[1, 2])

    with patch(
        "app.api.admin.agents.AdminAgentService",
        return_value=admin_service,
    ), patch(
        "app.api.admin.agents.PluginManagedAgentSyncService",
        return_value=sync_service,
    ):
        response = await endpoint(request, db, 55, admin)

    assert response["data"]["source_plugin_display_name"] == "文档管理"
    assert response["data"]["assigned_tenant_ids"] == [1, 2]


@pytest.mark.asyncio
async def test_update_agent_rejects_scope_override_for_plugin_managed_system_agent() -> None:
    from app.exceptions import BusinessException
    from app.schemas.ai.agent import AdminAgentUpdate

    endpoint = _get_endpoint("/ai/agents/{agent_id}", "PUT")

    db = AsyncMock()
    request = MagicMock()
    admin = SimpleNamespace(id=1)
    agent = _make_agent(scope="admin_and_selected_tenants")
    admin_service = MagicMock()
    admin_service.get_by_id = AsyncMock(return_value=agent)
    sync_service = MagicMock()
    sync_service.get_source_plugin_map = AsyncMock(
        return_value={
            "novusdoc": SimpleNamespace(
                name="novusdoc",
                display_name="文档管理",
                enabled=True,
                scope="admin_and_selected_tenants",
            )
        }
    )

    with patch(
        "app.api.admin.agents.AdminAgentService",
        return_value=admin_service,
    ), patch(
        "app.api.admin.agents.PluginManagedAgentSyncService",
        return_value=sync_service,
    ), pytest.raises(BusinessException):
        await endpoint(
            request,
            db,
            55,
            admin,
            AdminAgentUpdate(scope="all_tenants"),
        )


@pytest.mark.asyncio
async def test_update_agent_syncs_plugin_assignments_from_tenant_ids() -> None:
    from app.schemas.ai.agent import AdminAgentUpdate

    endpoint = _get_endpoint("/ai/agents/{agent_id}", "PUT")

    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    request = MagicMock()
    admin = SimpleNamespace(id=1)
    current_agent = _make_agent(scope="all_tenants")
    updated_agent = _make_agent(scope="admin_and_selected_tenants")
    admin_service = MagicMock()
    admin_service.get_by_id = AsyncMock(return_value=current_agent)
    admin_service.update = AsyncMock(return_value=updated_agent)
    sync_service = MagicMock()
    sync_service.get_source_plugin_map = AsyncMock(
        return_value={
            "novusdoc": SimpleNamespace(
                name="novusdoc",
                display_name="文档管理",
                enabled=True,
                scope="admin_and_selected_tenants",
            )
        }
    )
    sync_service.sync_from_agent_update = AsyncMock(return_value=[1])

    with patch(
        "app.api.admin.agents.AdminAgentService",
        return_value=admin_service,
    ), patch(
        "app.api.admin.agents.PluginManagedAgentSyncService",
        return_value=sync_service,
    ):
        response = await endpoint(
            request,
            db,
            55,
            admin,
            AdminAgentUpdate(description="updated", tenant_ids=[1]),
        )

    admin_service.update.assert_awaited_once()
    sync_service.sync_from_agent_update.assert_awaited_once_with(updated_agent, [1])
    assert response["data"]["source_plugin_display_name"] == "文档管理"
