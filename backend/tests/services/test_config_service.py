"""
Test type: behavioral
Scope: ConfigService resolves config IDs against the canonical config registry
group before reading/writing values, avoiding stale cross-group duplicates.
Mocked dependencies: Async DB session only; SQLAlchemy statement construction
and ConfigService cache/routing logic execute real code.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.configs.service import ConfigService, _config_id_cache


@pytest.mark.asyncio
async def test_get_config_id_tolerates_duplicate_keys(mock_db) -> None:
    _config_id_cache.clear()
    service = ConfigService(mock_db)

    result = MagicMock()
    result.scalars.return_value.all.return_value = [11, 12]
    mock_db.execute.return_value = result

    config_id = await service._get_config_id("tenant_domain_suffix")

    assert config_id == 11


@pytest.mark.asyncio
async def test_get_config_id_filters_by_registered_group(mock_db) -> None:
    _config_id_cache.clear()
    registry = SimpleNamespace(
        get_config_by_key=lambda _key: SimpleNamespace(group_code="platform_domain")
    )
    service = ConfigService(mock_db, registry=registry)

    result = MagicMock()
    result.scalars.return_value.all.return_value = [7]
    mock_db.execute.return_value = result

    config_id = await service._get_config_id("tenant_domain_suffix")

    stmt = mock_db.execute.await_args.args[0]
    compiled_sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert config_id == 7
    assert "JOIN system_config_groups" in compiled_sql
    assert "system_config_groups.code = 'platform_domain'" in compiled_sql
