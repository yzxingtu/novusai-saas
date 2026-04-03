from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.services.conftest import make_mock_model


def _make_agent(**overrides):
    defaults = {
        "id": 55,
        "source_plugin": "novusdoc",
        "scope": "all_tenants",
    }
    defaults.update(overrides)
    return make_mock_model(**defaults)


def _make_plugin(**overrides):
    defaults = {
        "id": 1087,
        "name": "novusdoc",
        "display_name": "文档管理",
        "scope": "admin_and_selected_tenants",
    }
    defaults.update(overrides)
    return make_mock_model(**defaults)


class TestPluginManagedAgentSyncService:
    @pytest.mark.asyncio
    async def test_sync_from_agent_update_replaces_plugin_assignments(self) -> None:
        from app.services.system.plugin_managed_agent_sync_service import (
            PluginManagedAgentSyncService,
        )

        service = PluginManagedAgentSyncService.__new__(PluginManagedAgentSyncService)
        service._assignment_repo = AsyncMock()
        service._require_source_plugin = AsyncMock(return_value=_make_plugin())
        service._apply_agent_distribution = AsyncMock()

        agent = _make_agent()
        result = await service.sync_from_agent_update(agent, [2, 1, 2])

        service._assignment_repo.sync_assignments.assert_awaited_once_with(
            "plugin",
            1087,
            [1, 2],
        )
        service._apply_agent_distribution.assert_awaited_once_with(
            agent,
            target_scope="admin_and_selected_tenants",
            tenant_ids=[1, 2],
        )
        assert result == [1, 2]

    @pytest.mark.asyncio
    async def test_sync_from_agent_update_uses_existing_plugin_assignments_when_ids_omitted(
        self,
    ) -> None:
        from app.services.system.plugin_managed_agent_sync_service import (
            PluginManagedAgentSyncService,
        )

        service = PluginManagedAgentSyncService.__new__(PluginManagedAgentSyncService)
        service._assignment_repo = AsyncMock()
        service._require_source_plugin = AsyncMock(return_value=_make_plugin())
        service._get_assigned_tenant_ids = AsyncMock(return_value=[9, 11])
        service._apply_agent_distribution = AsyncMock()

        agent = _make_agent()
        result = await service.sync_from_agent_update(agent, None)

        service._assignment_repo.sync_assignments.assert_not_called()
        service._apply_agent_distribution.assert_awaited_once_with(
            agent,
            target_scope="admin_and_selected_tenants",
            tenant_ids=[9, 11],
        )
        assert result == [9, 11]

    @pytest.mark.asyncio
    async def test_sync_agents_for_plugin_mirrors_assignments_to_all_source_agents(self) -> None:
        from app.services.system.plugin_managed_agent_sync_service import (
            PluginManagedAgentSyncService,
        )

        service = PluginManagedAgentSyncService.__new__(PluginManagedAgentSyncService)
        service._plugin_repo = AsyncMock()
        service._plugin_repo.get_by_id = AsyncMock(return_value=_make_plugin())
        service._get_assigned_tenant_ids = AsyncMock(return_value=[1])
        service._apply_agent_distribution = AsyncMock()
        service.db = AsyncMock()
        result_proxy = MagicMock()
        result_proxy.scalars.return_value.all.return_value = [
            _make_agent(id=55),
            _make_agent(id=56),
        ]
        service.db.execute = AsyncMock(return_value=result_proxy)

        count = await service.sync_agents_for_plugin(1087)

        assert count == 2
        assert service._apply_agent_distribution.await_count == 2

    def test_normalize_tenant_ids_rejects_non_assignment_scope(self) -> None:
        from app.exceptions import BusinessException
        from app.services.system.plugin_managed_agent_sync_service import (
            PluginManagedAgentSyncService,
        )

        with pytest.raises(BusinessException):
            PluginManagedAgentSyncService._normalize_tenant_ids("all_tenants", [1])
