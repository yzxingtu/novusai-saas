from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.plugins.module_loader import load_plugin_module


def _make_host(**overrides):
    host = SimpleNamespace(
        get_enabled_storage_drivers=AsyncMock(return_value=[]),
        get_plugin_runtime_summary=AsyncMock(return_value=[]),
        get_platform_storage_context=AsyncMock(
            return_value={
                "storage_mode": "platform",
                "apply_quota": True,
                "storage_config": {
                    "driver": "local",
                    "root_path": "storage",
                    "base_url": None,
                    "options": {},
                },
            }
        ),
    )
    for key, value in overrides.items():
        setattr(host, key, value)
    return host


@pytest.mark.asyncio
async def test_list_provider_profiles_uses_platform_storage_context_and_masks_secrets():
    module = load_plugin_module("storage-billing", "services.profile_service")
    assert module is not None

    host = _make_host(
        get_plugin_runtime_summary=AsyncMock(
            return_value=[{"name": "qiniu-kodo", "enabled": True}]
        ),
        get_platform_storage_context=AsyncMock(
            return_value={
                "storage_mode": "platform",
                "apply_quota": True,
                "storage_config": {
                    "driver": "qiniu-kodo",
                    "root_path": "bucket-main",
                    "base_url": "https://cdn.example.com",
                    "options": {
                        "access_key": "ak-plain",
                        "secret_key": "sk-plain",
                    },
                },
            }
        ),
    )

    ctx = SimpleNamespace(
        get_config=AsyncMock(
            return_value={
                "qiniu_enabled": True,
                "qiniu_profile_code": "qiniu-main",
                "qiniu_account_identifier": "account-main",
            }
        ),
        host=host,
    )

    payload = await module.StorageBillingProviderProfileService.from_context(
        ctx
    ).list_provider_profiles()

    qiniu = payload["providers"]["qiniu-kodo"]
    assert qiniu["enabled"] is True
    assert qiniu["profile_code"] == "qiniu-main"
    assert qiniu["configured_fields"]["access_key"] is True
    assert qiniu["configured_fields"]["secret_key"] is True
    assert "access_key" not in qiniu
    assert qiniu["driver_enabled"] is True
    assert qiniu["storage_context"]["current_driver"] == "qiniu-kodo"
    assert qiniu["storage_context"]["driver_match"] is True


@pytest.mark.asyncio
async def test_save_provider_profiles_persists_only_billing_fields():
    module = load_plugin_module("storage-billing", "services.profile_service")
    assert module is not None

    host = _make_host(
        get_plugin_runtime_summary=AsyncMock(
            return_value=[{"name": "aliyun-oss", "enabled": True}]
        ),
        get_platform_storage_context=AsyncMock(
            return_value={
                "storage_mode": "platform",
                "apply_quota": True,
                "storage_config": {
                    "driver": "aliyun-oss",
                    "root_path": "bucket-main",
                    "base_url": "https://oss.example.com",
                    "options": {
                        "access_key_id": "existing-id",
                        "access_key_secret": "existing-secret",
                        "region": "cn-hangzhou",
                    },
                },
            }
        ),
    )

    ctx = SimpleNamespace(
        get_config=AsyncMock(
            return_value={
                "aliyun_enabled": True,
                "aliyun_profile_code": "aliyun-default",
                "aliyun_access_key_secret": "legacy-secret",
                "providers": {
                    "aliyun-oss": {
                        "enabled": True,
                        "profile_code": "aliyun-default",
                        "bill_source": "bss_openapi",
                        "account_identifier": "",
                        "access_key_secret": "nested-legacy-secret",
                    }
                },
            }
        ),
        update_config=AsyncMock(),
        host=host,
    )

    service = module.StorageBillingProviderProfileService.from_context(ctx)
    await service.save_provider_profiles(
        {
            "providers": {
                "aliyun-oss": {
                    "enabled": True,
                    "account_identifier": "payer-1",
                    "access_key_secret": "should-be-ignored",
                    "region": "should-be-ignored",
                }
            }
        }
    )

    saved = ctx.update_config.await_args.args[0]
    assert saved["providers"]["aliyun-oss"] == {
        "enabled": True,
        "profile_code": "aliyun-default",
        "bill_source": "bss_openapi",
        "account_identifier": "payer-1",
    }
    assert "aliyun_access_key_secret" not in saved
    assert "access_key_secret" not in saved["providers"]["aliyun-oss"]
    assert "region" not in saved["providers"]["aliyun-oss"]


@pytest.mark.asyncio
async def test_validate_provider_profile_reads_required_fields_from_platform_storage_context():
    module = load_plugin_module("storage-billing", "services.profile_service")
    assert module is not None

    host = _make_host(
        get_plugin_runtime_summary=AsyncMock(
            return_value=[{"name": "tencent-cos", "enabled": True}]
        ),
        get_platform_storage_context=AsyncMock(
            return_value={
                "storage_mode": "platform",
                "apply_quota": True,
                "storage_config": {
                    "driver": "tencent-cos",
                    "root_path": "cos-bucket",
                    "base_url": "https://cos.example.com",
                    "options": {
                        "region": "ap-shanghai",
                    },
                },
            }
        ),
    )

    ctx = SimpleNamespace(
        get_config=AsyncMock(
            return_value={
                "tencent_enabled": True,
                "tencent_profile_code": "tencent-default",
            }
        ),
        host=host,
    )

    result = await module.StorageBillingProviderProfileService.from_context(
        ctx
    ).validate_provider_profile("tencent-cos")

    assert result["status"] == "invalid"
    assert "Missing required field: secret_id" in result["errors"]
    assert "Missing required field: secret_key" in result["errors"]
    assert result["storage_driver_match"] is True


@pytest.mark.asyncio
async def test_validate_provider_profile_returns_invalid_when_driver_plugin_disabled():
    module = load_plugin_module("storage-billing", "services.profile_service")
    assert module is not None

    host = _make_host(
        get_plugin_runtime_summary=AsyncMock(
            return_value=[{"name": "tencent-cos", "enabled": False}]
        ),
        get_platform_storage_context=AsyncMock(
            return_value={
                "storage_mode": "platform",
                "apply_quota": True,
                "storage_config": {
                    "driver": "tencent-cos",
                    "root_path": "cos-bucket",
                    "base_url": "https://cos.example.com",
                    "options": {
                        "region": "ap-shanghai",
                        "secret_id": "sid",
                        "secret_key": "skey",
                    },
                },
            }
        ),
    )

    ctx = SimpleNamespace(
        get_config=AsyncMock(
            return_value={
                "tencent_enabled": True,
                "tencent_profile_code": "tencent-default",
            }
        ),
        host=host,
    )

    result = await module.StorageBillingProviderProfileService.from_context(
        ctx
    ).validate_provider_profile("tencent-cos")

    assert result["status"] == "invalid"
    assert (
        "Required storage driver plugin 'tencent-cos' is not enabled."
        in result["errors"]
    )
