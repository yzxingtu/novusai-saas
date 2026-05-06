"""
Test type: behavioral
Scope: ConfigService resolves config IDs against canonical groups and validates
metadata-shaped config values before write.
Mocked dependencies: Async DB session only; SQLAlchemy statement construction
and ConfigService cache/routing logic execute real code.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.configs.meta import ConfigMeta, max_value, min_value, option
from app.configs.service import ConfigService, _config_id_cache
from app.enums.config import ConfigValueType
from app.enums.error_code import ErrorCode
from app.exceptions import BusinessException


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


def test_config_value_validation_normalizes_number_and_enforces_bounds() -> None:
    """
    中文: 测试类型 behavioral；配置保存会按元数据归一化数字并执行 min/max。
    EN: Test type behavioral; config writes normalize numbers and enforce min/max.
    中文: 无 mock。
    EN: No mocks.
    """
    service = ConfigService(MagicMock())
    meta = ConfigMeta(
        key="tenant_ai_max_capability_items_per_category",
        name_key="shared.config.tenant.tenant_ai_max_capability_items_per_category",
        value_type=ConfigValueType.NUMBER,
        validation_rules=[min_value(1), max_value(50)],
    )

    assert service._normalize_and_validate_config_value(meta, "20") == 20

    with pytest.raises(BusinessException) as exc_info:
        service._normalize_and_validate_config_value(meta, "0")

    assert exc_info.value.code == ErrorCode.CONFIG_VALIDATION_FAILED


def test_config_value_validation_rejects_unknown_select_option() -> None:
    """
    中文: 测试类型 behavioral；select 配置只能保存声明过的选项。
    EN: Test type behavioral; select configs only accept declared options.
    中文: 无 mock。
    EN: No mocks.
    """
    service = ConfigService(MagicMock())
    meta = ConfigMeta(
        key="tenant_ai_capability_description_style",
        name_key="shared.config.tenant.tenant_ai_capability_description_style",
        value_type=ConfigValueType.SELECT,
        options=[
            option("detailed", "shared.config.tenant_options.style.detailed"),
            option("concise", "shared.config.tenant_options.style.concise"),
        ],
    )

    assert service._normalize_and_validate_config_value(meta, "concise") == "concise"

    with pytest.raises(BusinessException) as exc_info:
        service._normalize_and_validate_config_value(meta, "verbose")

    assert exc_info.value.code == ErrorCode.CONFIG_VALIDATION_FAILED


def test_config_value_validation_normalizes_boolean_and_tag_values() -> None:
    """
    中文: 测试类型 behavioral；boolean 与 tag 类型按后端存储契约归一化。
    EN: Test type behavioral; boolean and tag values normalize to backend storage contracts.
    中文: 无 mock。
    EN: No mocks.
    """
    service = ConfigService(MagicMock())
    boolean_meta = ConfigMeta(
        key="tenant_ai_enable_dynamic_capability_awareness",
        name_key="shared.config.tenant.tenant_ai_enable_dynamic_capability_awareness",
        value_type=ConfigValueType.BOOLEAN,
    )
    tag_meta = ConfigMeta(
        key="tenant_storage_allowed_extensions",
        name_key="shared.config.tenant.tenant_storage_allowed_extensions",
        value_type=ConfigValueType.TAG,
        tag_separator=",",
    )

    assert service._normalize_and_validate_config_value(boolean_meta, "false") is False
    assert (
        service._normalize_and_validate_config_value(
            tag_meta,
            ["jpg", " png ", ""],
        )
        == "jpg,png"
    )
