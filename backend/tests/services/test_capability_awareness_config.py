from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


def test_tenant_ai_group_registers_capability_awareness_configs() -> None:
    from app.configs.definitions import register_all_configs
    from app.configs.registry import config_registry

    register_all_configs()
    group = config_registry.get_group("tenant_ai")

    assert group is not None
    assert [config.key for config in group.configs] == [
        "tenant_ai_enable_dynamic_capability_awareness",
        "tenant_ai_capability_description_style",
        "tenant_ai_max_capability_items_per_category",
    ]


@pytest.mark.asyncio
async def test_get_tenant_capability_awareness_settings_uses_defaults() -> None:
    from app.services.ai.capability_awareness_config import (
        TenantCapabilityAwarenessSettings,
        get_tenant_capability_awareness_settings,
    )

    config_service = AsyncMock()
    config_service.get_tenant_config = AsyncMock(
        side_effect=[None, None, None],
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "app.services.ai.capability_awareness_config.ConfigService",
            lambda _db: config_service,
        )
        settings = await get_tenant_capability_awareness_settings(object(), 7)

    assert settings == TenantCapabilityAwarenessSettings()


@pytest.mark.asyncio
async def test_get_tenant_capability_awareness_settings_normalizes_values() -> None:
    from app.services.ai.capability_awareness_config import (
        get_tenant_capability_awareness_settings,
    )

    config_service = AsyncMock()
    config_service.get_tenant_config = AsyncMock(
        side_effect=["false", "verbose", "0"],
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "app.services.ai.capability_awareness_config.ConfigService",
            lambda _db: config_service,
        )
        settings = await get_tenant_capability_awareness_settings(object(), 7)

    assert settings.enable_dynamic_capability_awareness is False
    assert settings.capability_description_style == "detailed"
    assert settings.max_capability_items_per_category == 1
