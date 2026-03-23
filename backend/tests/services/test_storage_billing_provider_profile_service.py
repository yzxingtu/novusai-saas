from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.plugins.module_loader import load_plugin_module


@pytest.mark.asyncio
async def test_list_provider_profiles_masks_secrets_and_reports_driver_state():
    module = load_plugin_module("storage-billing", "services.profile_service")
    assert module is not None

    ctx = AsyncMock()
    ctx.get_config = AsyncMock(
        return_value={
            "qiniu_enabled": True,
            "qiniu_profile_code": "qiniu-main",
            "qiniu_access_key": "ak-plain",
            "qiniu_secret_key": "sk-plain",
        }
    )
    ctx.host.get_enabled_storage_drivers = AsyncMock(
        return_value=[
            {
                "code": "qiniu-kodo",
                "is_available": True,
                "plugin_name": "qiniu-kodo",
                "plugin_status": "enabled",
            }
        ]
    )

    payload = await module.StorageBillingProviderProfileService.from_context(ctx).list_provider_profiles()

    qiniu = payload["providers"]["qiniu-kodo"]
    assert qiniu["enabled"] is True
    assert qiniu["profile_code"] == "qiniu-main"
    assert qiniu["configured_fields"]["access_key"] is True
    assert qiniu["configured_fields"]["secret_key"] is True
    assert "access_key" not in qiniu
    assert qiniu["driver_enabled"] is True


@pytest.mark.asyncio
async def test_save_provider_profiles_preserves_existing_secret_when_blank():
    module = load_plugin_module("storage-billing", "services.profile_service")
    assert module is not None

    ctx = AsyncMock()
    ctx.get_config = AsyncMock(
        return_value={
            "aliyun_enabled": True,
            "aliyun_profile_code": "aliyun-default",
            "aliyun_access_key_secret": "existing-secret",
            "aliyun_access_key_id": "existing-id",
        }
    )
    ctx.update_config = AsyncMock()
    ctx.host.get_enabled_storage_drivers = AsyncMock(return_value=[])

    service = module.StorageBillingProviderProfileService.from_context(ctx)
    await service.save_provider_profiles(
        {
            "providers": {
                "aliyun-oss": {
                    "bill_bucket": "billing-bucket",
                    "access_key_secret": "",
                }
            }
        }
    )

    saved = ctx.update_config.await_args.args[0]
    assert saved["providers"]["aliyun-oss"]["access_key_secret"] == "existing-secret"
    assert saved["providers"]["aliyun-oss"]["bill_bucket"] == "billing-bucket"
    assert "aliyun_access_key_secret" not in saved


@pytest.mark.asyncio
async def test_validate_provider_profile_returns_invalid_when_required_fields_missing():
    module = load_plugin_module("storage-billing", "services.profile_service")
    assert module is not None

    ctx = AsyncMock()
    ctx.get_config = AsyncMock(
        return_value={
            "tencent_enabled": True,
            "tencent_profile_code": "tencent-default",
        }
    )
    ctx.host.get_enabled_storage_drivers = AsyncMock(
        return_value=[
            {
                "code": "tencent-cos",
                "is_available": False,
                "plugin_name": "tencent-cos",
                "plugin_status": "disabled",
            }
        ]
    )

    result = await module.StorageBillingProviderProfileService.from_context(ctx).validate_provider_profile(
        "tencent-cos"
    )

    assert result["status"] == "invalid"
    assert result["errors"]
