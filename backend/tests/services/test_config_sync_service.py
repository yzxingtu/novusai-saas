"""
Test type: behavioral
Scope: ConfigSyncService preserves stored values when a config key moves to a
new canonical group and the old row becomes deprecated.
Mocked dependencies: Async DB session only; sync branching and value-copy
construction execute real code.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.configs.meta import ConfigMeta
from app.configs.sync import ConfigSyncService
from app.enums.config import ConfigScope
from app.models.system.config import SystemConfigValue


def _scalars_result(items: list[object]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


@pytest.mark.asyncio
async def test_sync_configs_migrates_values_from_rehomed_duplicate_key(
    mock_db,
) -> None:
    config_meta = ConfigMeta(
        key="tenant_domain_suffix",
        name_key="config.platform.tenant_domain_suffix.name",
        scope=ConfigScope.ADMIN_ONLY,
        default_value=".app.novusai.com",
    )
    config_meta.set_group_code("platform_domain")
    registry = SimpleNamespace(get_all_configs=lambda: [config_meta])
    service = ConfigSyncService(mock_db, registry=registry)
    legacy_config = SimpleNamespace(
        id=3,
        group_id=1,
        key="tenant_domain_suffix",
        is_visible=True,
    )
    canonical_config = SimpleNamespace(
        id=7,
        group_id=2,
        key="tenant_domain_suffix",
        is_visible=True,
    )
    source_value = SimpleNamespace(tenant_id=0, value='".tenant.example.com"')
    mock_db.execute.side_effect = [
        _scalars_result(
            [
                SimpleNamespace(id=1, code="platform_general"),
                SimpleNamespace(id=2, code="platform_domain"),
            ]
        ),
        _scalars_result([legacy_config, canonical_config]),
        _scalars_result([source_value]),
        _scalars_result([]),
    ]

    stats = await service.sync_configs()

    migrated_values = [
        call.args[0]
        for call in mock_db.add.call_args_list
        if isinstance(call.args[0], SystemConfigValue)
    ]
    assert stats["updated"] == 1
    assert stats["deprecated"] == 1
    assert stats["migrated_values"] == 1
    assert legacy_config.is_visible is False
    assert len(migrated_values) == 1
    assert migrated_values[0].config_id == 7
    assert migrated_values[0].tenant_id == 0
    assert migrated_values[0].value == '".tenant.example.com"'
