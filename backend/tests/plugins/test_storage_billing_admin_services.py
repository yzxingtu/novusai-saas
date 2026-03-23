from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.responses import Response

from app.plugins.module_loader import load_plugin_module


def _make_count_result(value: int) -> MagicMock:
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


def _make_scalar_none_result() -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    return result


@pytest.mark.asyncio
async def test_storage_billing_provider_profiles_preserve_existing_secrets() -> None:
    module = load_plugin_module("storage-billing", "services.profile_service")
    assert module is not None

    current_config = {
        "providers": {
            "tencent-cos": {
                "enabled": True,
                "profile_code": "tencent-default",
                "bill_source": "describe_bill_detail",
                "region": "ap-shanghai",
                "secret_id": "sid-old",
                "secret_key": "sk-old",
                "bill_bucket": "bill-bucket",
                "bill_prefix": "daily/",
                "account_identifier": "acct-1",
            }
        }
    }
    persisted_config = {
        "providers": {
            "qiniu-kodo": {
                "enabled": False,
                "profile_code": "qiniu-default",
                "bill_source": "finance_api",
                "access_key": "",
                "secret_key": "",
                "account_identifier": "",
            },
            "aliyun-oss": {
                "enabled": False,
                "profile_code": "aliyun-default",
                "bill_source": "oss_subscription",
                "region": "",
                "access_key_id": "",
                "access_key_secret": "",
                "bill_bucket": "",
                "bill_prefix": "",
                "account_identifier": "",
            },
            "tencent-cos": {
                "enabled": True,
                "profile_code": "tencent-default",
                "bill_source": "cos_bill_bucket",
                "region": "ap-shanghai",
                "secret_id": "sid-old",
                "secret_key": "sk-new",
                "bill_bucket": "bill-bucket",
                "bill_prefix": "daily/",
                "account_identifier": "acct-1",
            },
        }
    }

    ctx = MagicMock()
    ctx.get_config = AsyncMock(side_effect=[current_config, persisted_config])
    ctx.update_config = AsyncMock()
    host = MagicMock()
    host.get_plugin_runtime_summary = AsyncMock(
        return_value=[{"name": "tencent-cos", "enabled": True}]
    )

    service = module.StorageBillingProviderProfileService(ctx, host_read=host)
    result = await service.save_provider_profiles(
        {
            "providers": {
                "tencent-cos": {
                    "enabled": True,
                    "region": "ap-shanghai",
                    "secret_id": "",
                    "secret_key": "sk-new",
                    "bill_bucket": "bill-bucket",
                }
            }
        }
    )

    saved_config = ctx.update_config.await_args.args[0]
    assert saved_config["providers"]["tencent-cos"]["secret_id"] == "sid-old"
    assert saved_config["providers"]["tencent-cos"]["secret_key"] == "sk-new"
    assert result["providers"]["tencent-cos"]["secret_id"] == ""
    assert result["providers"]["tencent-cos"]["configured_secret_fields"]["secret_key"] is True


@pytest.mark.asyncio
async def test_storage_billing_provider_profiles_read_legacy_flat_config() -> None:
    module = load_plugin_module("storage-billing", "services.profile_service")
    assert module is not None

    ctx = MagicMock()
    ctx.get_config = AsyncMock(
        return_value={
            "tencent_enabled": True,
            "tencent_profile_code": "legacy-profile",
            "tencent_bill_source": "describe_bill_detail",
            "tencent_region": "ap-guangzhou",
            "tencent_secret_id": "legacy-sid",
            "tencent_secret_key": "legacy-skey",
            "tencent_bill_bucket": "legacy-bucket",
        }
    )
    host = MagicMock()
    host.get_plugin_runtime_summary = AsyncMock(
        return_value=[{"name": "tencent-cos", "enabled": True}]
    )

    service = module.StorageBillingProviderProfileService(ctx, host_read=host)
    result = await service.list_provider_profiles()

    profile = result["providers"]["tencent-cos"]
    assert profile["enabled"] is True
    assert profile["profile_code"] == "legacy-profile"
    assert profile["region"] == "ap-guangzhou"
    assert profile["configured_secret_fields"]["secret_id"] is True


@pytest.mark.asyncio
async def test_storage_billing_create_binding_validates_tenant_context() -> None:
    module = load_plugin_module("storage-billing", "services.binding_service")
    assert module is not None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_make_scalar_none_result())
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()

    ctx = MagicMock()
    ctx.get_db = MagicMock(return_value=mock_db)
    ctx.get_config = AsyncMock(
        return_value={
            "providers": {
                "tencent-cos": {
                    "enabled": True,
                    "profile_code": "tencent-default",
                    "bill_source": "describe_bill_detail",
                    "region": "ap-shanghai",
                    "secret_id": "sid",
                    "secret_key": "skey",
                    "bill_bucket": "bill-bucket",
                    "bill_prefix": "daily/",
                    "account_identifier": "acct-1",
                }
            }
        }
    )
    host = MagicMock()
    host.get_tenant_plan_snapshot = AsyncMock(
        return_value={
            "tenant_id": 9,
            "plan": {"features": {"storage_billing_enabled": True}},
        }
    )
    host.get_tenant_storage_context = AsyncMock(
        return_value={"storage_config": {"driver": "tencent-cos"}}
    )
    host.get_plugin_runtime_summary = AsyncMock(
        return_value=[{"name": "tencent-cos", "enabled": True}]
    )

    service = module.StorageBillingBindingService(ctx, host_read=host)
    result = await service.create_binding(
        {
            "tenant_id": 9,
            "provider_code": "tencent-cos",
            "billing_mode": "official_pass_through",
            "scope_type": "bucket",
            "bucket_name": "tenant-9-bucket",
            "is_active": True,
        }
    )

    assert result["ok"] is True
    assert result["binding"]["provider_profile_code"] == "tencent-default"
    assert result["binding"]["scope_value"] == "tenant-9-bucket"
    assert result["validation"]["status"] == "valid"


@pytest.mark.asyncio
async def test_storage_billing_binding_rejects_qiniu_pass_through() -> None:
    module = load_plugin_module("storage-billing", "services.binding_service")
    assert module is not None

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=_make_scalar_none_result())
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()

    ctx = MagicMock()
    ctx.get_db = MagicMock(return_value=mock_db)
    ctx.get_config = AsyncMock(
        return_value={
            "providers": {
                "qiniu-kodo": {
                    "enabled": True,
                    "profile_code": "qiniu-default",
                    "bill_source": "finance_api",
                    "access_key": "ak",
                    "secret_key": "sk",
                    "account_identifier": "acct-2",
                }
            }
        }
    )
    host = MagicMock()
    host.get_tenant_plan_snapshot = AsyncMock(
        return_value={
            "tenant_id": 10,
            "plan": {"features": {"storage_billing_enabled": True}},
        }
    )
    host.get_tenant_storage_context = AsyncMock(
        return_value={"storage_config": {"driver": "qiniu-kodo"}}
    )
    host.get_plugin_runtime_summary = AsyncMock(
        return_value=[{"name": "qiniu-kodo", "enabled": True}]
    )

    service = module.StorageBillingBindingService(ctx, host_read=host)
    result = await service.create_binding(
        {
            "tenant_id": 10,
            "provider_code": "qiniu-kodo",
            "billing_mode": "official_pass_through",
            "scope_type": "account",
            "account_identifier": "acct-2",
            "is_active": True,
        }
    )

    assert result["ok"] is True
    assert result["validation"]["status"] == "invalid"
    assert "Qiniu official_pass_through is not supported in phase 1." in result["validation"]["errors"]


@pytest.mark.asyncio
async def test_storage_billing_admin_run_endpoints_delegate_to_service(monkeypatch) -> None:
    module = load_plugin_module("storage-billing", "api.admin")
    assert module is not None

    service = AsyncMock()
    service.list_runs = AsyncMock(return_value={"items": [{"id": 11}], "limit": 10, "total": 1})
    service.get_run_detail = AsyncMock(return_value={"run": {"id": 11}, "sources": []})
    service.list_run_charges = AsyncMock(return_value={"items": [{"id": 21}], "total": 1})
    service.export_run_charges_csv = AsyncMock(
        return_value=Response(content=b"id\n21\n", media_type="text/csv")
    )

    reconciliation_service = MagicMock()
    reconciliation_service.from_context.return_value = service
    monkeypatch.setattr(module, "StorageBillingReconciliationService", reconciliation_service)

    list_request = MagicMock()
    list_request.query_params = {"limit": "10"}
    list_result = await module.list_reconciliation_runs(list_request, MagicMock())

    detail_request = MagicMock()
    detail_request.path_params = {"run_id": "11"}
    detail_result = await module.get_reconciliation_run(detail_request, MagicMock())

    charges_request = MagicMock()
    charges_request.path_params = {"run_id": "11"}
    charges_request.query_params = {
        "provider_code": "aliyun-oss",
        "source_id": "31",
        "tenant_id": "9",
    }
    charges_result = await module.list_reconciliation_run_charges(charges_request, MagicMock())

    export_request = MagicMock()
    export_request.path_params = {"run_id": "11"}
    export_request.query_params = {
        "provider_code": "aliyun-oss",
        "source_id": "31",
        "tenant_id": "9",
    }
    export_result = await module.export_reconciliation_run_charges(export_request, MagicMock())

    assert list_result["items"][0]["id"] == 11
    service.list_runs.assert_awaited_once_with(limit=10)
    assert detail_result["run"]["id"] == 11
    service.get_run_detail.assert_awaited_once_with(11)
    assert charges_result["items"][0]["id"] == 21
    service.list_run_charges.assert_awaited_once_with(
        run_id=11,
        provider_code="aliyun-oss",
        source_id=31,
        tenant_id=9,
    )
    assert export_result.media_type == "text/csv"
    service.export_run_charges_csv.assert_awaited_once_with(
        run_id=11,
        provider_code="aliyun-oss",
        source_id=31,
        tenant_id=9,
    )


@pytest.mark.asyncio
async def test_admin_overview_includes_latest_runs_and_counts(monkeypatch) -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    models = load_plugin_module("storage-billing", "models")
    assert module is not None
    assert models is not None

    run = models.StorageBillingRun(
        billing_date=date(2026, 3, 21),
        status="completed",
        trigger_type="schedule",
    )
    run.provider_codes_json = ["aliyun-oss"]
    run.summary_json = {"driver_count": 1}

    latest_result = MagicMock()
    latest_scalars = MagicMock()
    latest_scalars.all.return_value = [run]
    latest_result.scalars.return_value = latest_scalars

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            latest_result,
            _make_count_result(3),
            _make_count_result(4),
            _make_count_result(5),
        ]
    )

    host = MagicMock()
    host.get_enabled_storage_drivers = AsyncMock(
        return_value=[{"code": "aliyun-oss", "is_available": True}]
    )
    host.get_plugin_runtime_summary = AsyncMock(
        return_value=[{"name": "aliyun-oss", "enabled": True}]
    )

    service = module.StorageBillingOverviewService(db, host_read=host)
    overview = await service.build_admin_overview()

    latest = overview["ledger_snapshot"]["latest_runs"][0]
    assert latest["billing_date"] == "2026-03-21"
    assert overview["ledger_snapshot"]["statement_total"] == 3
    assert overview["ledger_snapshot"]["daily_charge_total"] == 4
    assert overview["ledger_snapshot"]["binding_total"] == 5
