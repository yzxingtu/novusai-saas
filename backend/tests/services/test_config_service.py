"""ConfigService tests."""

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
