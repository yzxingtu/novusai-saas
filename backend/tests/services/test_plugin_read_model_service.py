from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.sql import Select

from app.repositories.system.plugin_repository import PluginRepository
from app.schemas.common.query import QuerySpec
from tests.services.conftest import make_scalar_result, make_scalars_result


def _make_plugin(**overrides):
    defaults = {
        "id": 7,
        "name": "demo-plugin",
        "display_name": "Demo Plugin",
        "manifest": {},
        "config": {},
        "status": "enabled",
        "scope": "admin",
    }
    defaults.update(overrides)
    plugin = MagicMock()
    for key, value in defaults.items():
        setattr(plugin, key, value)
    plugin.to_dict.return_value = defaults.copy()
    return plugin


def _make_plugin_service(mock_db):
    from app.services.system.plugin_service import PluginService

    service = PluginService.__new__(PluginService)
    service.db = mock_db
    service.repo = PluginRepository(mock_db)
    return service


@pytest.mark.asyncio
async def test_build_admin_plugin_list_uses_base_service_query_list(mock_db):
    from app.services.system.plugin_read_model_service import PluginReadModelService

    plugin = _make_plugin()
    mock_db.execute.side_effect = [
        make_scalar_result(1),
        make_scalars_result([plugin]),
    ]

    service = _make_plugin_service(mock_db)
    service.get_dependency_status = AsyncMock(return_value={"overall": "installed"})
    service.get_recovery_state = MagicMock(return_value={"state": "healthy"})

    read_model = PluginReadModelService(mock_db)
    read_model._plugin_service = service

    items, total = await read_model.build_admin_plugin_list(QuerySpec())

    assert total == 1
    assert items[0]["name"] == "demo-plugin"
    assert items[0]["dependency_status"] == {"overall": "installed"}
    assert items[0]["recovery_state"] == {"state": "healthy"}
    assert isinstance(mock_db.execute.await_args_list[0].args[0], Select)
    assert isinstance(mock_db.execute.await_args_list[1].args[0], Select)
    service.get_dependency_status.assert_awaited_once_with(plugin)
    service.get_recovery_state.assert_called_once_with(
        plugin,
        dependency_status={"overall": "installed"},
    )


@pytest.mark.asyncio
async def test_build_admin_plugin_detail_uses_base_service_get_by_id(mock_db):
    from app.services.system.plugin_read_model_service import PluginReadModelService

    plugin = _make_plugin()
    mock_db.execute.return_value = make_scalar_result(plugin)

    service = _make_plugin_service(mock_db)
    service.get_dependency_status = AsyncMock(return_value={"overall": "installed"})
    service.get_recovery_state = MagicMock(return_value={"state": "healthy"})
    service.get_readme = AsyncMock(return_value="# Demo")

    read_model = PluginReadModelService(mock_db)
    read_model._plugin_service = service

    payload = await read_model.build_admin_plugin_detail(7, locale="zh-CN")

    assert payload["id"] == 7
    assert payload["dependency_status"] == {"overall": "installed"}
    assert payload["recovery_state"] == {"state": "healthy"}
    assert payload["readme"] == "# Demo"
    assert isinstance(mock_db.execute.await_args.args[0], Select)
    service.get_dependency_status.assert_awaited_once_with(plugin)
    service.get_recovery_state.assert_called_once_with(
        plugin,
        dependency_status={"overall": "installed"},
    )
    service.get_readme.assert_awaited_once_with(7, locale="zh-CN")
