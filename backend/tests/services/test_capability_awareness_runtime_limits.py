"""
Test type: behavioral
中文: 范围是租户动态能力感知运行时配置归一化。
EN: Scope is tenant dynamic capability-awareness runtime config normalization.
中文: Mock 依赖为 ConfigService，只隔离配置读取传输，断言真实归一化结果。
EN: Mocked dependency is ConfigService; only config transport is isolated while
real normalization output is asserted.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.ai.capability_awareness_config import (
    MAX_CAPABILITY_ITEMS_PER_CATEGORY,
    get_tenant_capability_awareness_settings,
)


@pytest.mark.asyncio
async def test_capability_awareness_runtime_limit_caps_above_metadata_max() -> None:
    config_service = AsyncMock()
    config_service.get_tenant_config = AsyncMock(
        side_effect=[
            True,
            "concise",
            str(MAX_CAPABILITY_ITEMS_PER_CATEGORY + 900),
        ],
    )

    with patch(
        "app.services.ai.capability_awareness_config.ConfigService",
        return_value=config_service,
    ):
        settings = await get_tenant_capability_awareness_settings(object(), 7)

    assert settings.max_capability_items_per_category == (
        MAX_CAPABILITY_ITEMS_PER_CATEGORY
    )
