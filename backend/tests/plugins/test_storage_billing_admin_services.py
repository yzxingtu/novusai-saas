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
async def test_storage_billing_provider_profiles_persist_only_billing_fields() -> None:
    module = load_plugin_module("storage-billing", "services.profile_service")
    assert module is not None

    current_config = {
        "providers": {
            "tencent-cos": {
                "enabled": True,
                "profile_code": "tencent-default",
                "bill_source": "describe_bill_detail",
                "account_identifier": "acct-1",
            }
        }
    }

    ctx = MagicMock()
    ctx.get_config = AsyncMock(return_value=current_config)
    ctx.update_config = AsyncMock()
    host = MagicMock()
    host.get_plugin_runtime_summary = AsyncMock(
        return_value=[{"name": "tencent-cos", "enabled": True}]
    )
    host.get_platform_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "apply_quota": True,
            "storage_config": {
                "driver": "tencent-cos",
                "root_path": "cos-bucket",
                "base_url": "https://cos.example.com",
                "options": {
                    "region": "ap-shanghai",
                    "secret_id": "sid-old",
                    "secret_key": "sk-old",
                },
            },
        }
    )

    service = module.StorageBillingProviderProfileService(ctx, host_read=host)
    await service.save_provider_profiles(
        {
            "providers": {
                "tencent-cos": {
                    "enabled": True,
                    "bill_source": "describe_bill_detail",
                    "account_identifier": "acct-2",
                }
            }
        }
    )

    saved_config = ctx.update_config.await_args.args[0]
    assert saved_config["providers"]["tencent-cos"] == {
        "enabled": True,
        "profile_code": "tencent-default",
        "bill_source": "describe_bill_detail",
        "account_identifier": "acct-2",
    }
    assert "secret_id" not in saved_config["providers"]["tencent-cos"]
    assert "secret_key" not in saved_config["providers"]["tencent-cos"]


@pytest.mark.asyncio
async def test_storage_billing_provider_profiles_read_legacy_flat_billing_config_only() -> (
    None
):
    module = load_plugin_module("storage-billing", "services.profile_service")
    assert module is not None

    ctx = MagicMock()
    ctx.get_config = AsyncMock(
        return_value={
            "tencent_enabled": True,
            "tencent_profile_code": "legacy-profile",
            "tencent_bill_source": "describe_bill_detail",
            "tencent_bill_bucket": "legacy-bucket",
            "tencent_account_identifier": "acct-legacy",
        }
    )
    host = MagicMock()
    host.get_plugin_runtime_summary = AsyncMock(
        return_value=[{"name": "tencent-cos", "enabled": True}]
    )
    host.get_platform_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "apply_quota": True,
            "storage_config": {
                "driver": "tencent-cos",
                "root_path": "cos-bucket",
                "base_url": "https://cos.example.com",
                "options": {
                    "region": "ap-guangzhou",
                    "secret_id": "sid-host",
                    "secret_key": "skey-host",
                },
            },
        }
    )

    service = module.StorageBillingProviderProfileService(ctx, host_read=host)
    result = await service.list_provider_profiles()

    profile = result["providers"]["tencent-cos"]
    assert profile["enabled"] is True
    assert profile["profile_code"] == "legacy-profile"
    assert "bill_bucket" not in profile
    assert profile["account_identifier"] == "acct-legacy"
    assert profile["region"] == "ap-guangzhou"
    assert profile["configured_secret_fields"]["secret_id"] is True
    assert "secret_id" not in profile


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
    host.get_platform_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "apply_quota": True,
            "storage_config": {
                "driver": "tencent-cos",
                "root_path": "tenant-9-bucket",
                "base_url": "https://cos.example.com",
                "options": {
                    "region": "ap-shanghai",
                    "secret_id": "sid",
                    "secret_key": "skey",
                },
            },
        }
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
    host.get_platform_storage_context = AsyncMock(
        return_value={
            "storage_mode": "platform",
            "apply_quota": True,
            "storage_config": {
                "driver": "qiniu-kodo",
                "root_path": "tenant-10-bucket",
                "base_url": "https://cdn.example.com",
                "options": {
                    "access_key": "ak",
                    "secret_key": "sk",
                },
            },
        }
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
    assert (
        "Qiniu official_pass_through is not supported in phase 1."
        in result["validation"]["errors"]
    )


@pytest.mark.asyncio
async def test_storage_billing_admin_run_endpoints_delegate_to_service(
    monkeypatch,
) -> None:
    module = load_plugin_module("storage-billing", "api.admin")
    assert module is not None

    service = AsyncMock()
    service.list_runs = AsyncMock(
        return_value={"items": [{"id": 11}], "limit": 10, "total": 1}
    )
    service.get_run_detail = AsyncMock(return_value={"run": {"id": 11}, "sources": []})
    service.list_run_charges = AsyncMock(
        return_value={"items": [{"id": 21}], "total": 1}
    )
    service.export_run_charges_csv = AsyncMock(
        return_value=Response(content=b"id\n21\n", media_type="text/csv")
    )

    reconciliation_service = MagicMock()
    reconciliation_service.from_context.return_value = service
    monkeypatch.setattr(
        module, "StorageBillingReconciliationService", reconciliation_service
    )

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
    charges_result = await module.list_reconciliation_run_charges(
        charges_request, MagicMock()
    )

    export_request = MagicMock()
    export_request.path_params = {"run_id": "11"}
    export_request.query_params = {
        "provider_code": "aliyun-oss",
        "source_id": "31",
        "tenant_id": "9",
    }
    export_result = await module.export_reconciliation_run_charges(
        export_request, MagicMock()
    )

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
async def test_storage_billing_run_qiniu_monthly_settlement_endpoint(
    monkeypatch,
) -> None:
    module = load_plugin_module("storage-billing", "api.admin")
    assert module is not None

    service = AsyncMock()
    service.trigger_qiniu_monthly_settlement = AsyncMock(return_value={"status": "ok"})

    reconciliation_service = MagicMock()
    reconciliation_service.from_context.return_value = service
    monkeypatch.setattr(
        module, "StorageBillingReconciliationService", reconciliation_service
    )

    request = MagicMock()
    request.headers = {"content-type": "application/json"}
    request.json = AsyncMock(return_value={"billing_month": "2026-03"})

    result = await module.run_qiniu_monthly_settlement(request, MagicMock())

    assert result["status"] == "ok"
    service.trigger_qiniu_monthly_settlement.assert_awaited_once_with(
        {"billing_month": "2026-03"}
    )


@pytest.mark.asyncio
async def test_storage_billing_run_reconciliation_endpoint_forwards_payload(
    monkeypatch,
) -> None:
    module = load_plugin_module("storage-billing", "api.admin")
    assert module is not None

    service = AsyncMock()
    service.trigger_manual_run = AsyncMock(
        return_value={"status": "ok", "run": {"id": 17}}
    )

    reconciliation_service = MagicMock()
    reconciliation_service.from_context.return_value = service
    monkeypatch.setattr(
        module, "StorageBillingReconciliationService", reconciliation_service
    )

    request = MagicMock()
    request.headers = {"content-type": "application/json"}
    request.json = AsyncMock(
        return_value={
            "billing_date": "2026-03-21",
            "provider_codes": ["aliyun-oss"],
        }
    )

    result = await module.run_reconciliation(request, MagicMock())

    assert result["status"] == "ok"
    service.trigger_manual_run.assert_awaited_once_with(
        {
            "billing_date": "2026-03-21",
            "provider_codes": ["aliyun-oss"],
        }
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


@pytest.mark.asyncio
async def test_admin_overview_includes_provider_metadata(monkeypatch) -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    models = load_plugin_module("storage-billing", "models")
    assert module is not None
    assert models is not None

    run = models.StorageBillingRun(
        billing_date=date(2026, 3, 21),
        status="completed",
        trigger_type="schedule",
    )
    run.provider_codes_json = ["qiniu-kodo"]
    run.summary_json = {"driver_count": 1}

    latest_result = MagicMock()
    latest_scalars = MagicMock()
    latest_scalars.all.return_value = [run]
    latest_result.scalars.return_value = latest_scalars

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            latest_result,
            _make_count_result(0),
            _make_count_result(0),
            _make_count_result(0),
        ]
    )

    host = MagicMock()
    host.get_enabled_storage_drivers = AsyncMock(return_value=[])
    host.get_plugin_runtime_summary = AsyncMock(return_value=[])

    stub_profile_service = MagicMock()
    stub_profile_service.list_provider_profiles = AsyncMock(
        return_value={
            "providers": {
                "qiniu-kodo": {
                    "settlement_mode": "monthly_settled",
                    "settlement_cycle": "monthly",
                    "manual_pull_supported": True,
                    "strict_reconciliation_supported": False,
                    "scheduled_daily_supported": False,
                    "supported_period_types": ["monthly"],
                    "capability_message": "OK",
                }
            }
        }
    )
    monkeypatch.setattr(
        module,
        "StorageBillingProviderProfileService",
        MagicMock(return_value=stub_profile_service),
    )

    service = module.StorageBillingOverviewService(db, host_read=host)
    overview = await service.build_admin_overview()

    capabilities = overview["provider_capabilities"].get("qiniu-kodo", {})
    assert capabilities["manual_pull_supported"] is True
    assert capabilities["settlement_mode"] == "monthly_settled"
    assert overview["reconciliation_schedule"]["official_billing_lag_days"] is None
    assert (
        overview["provider_schedules"]["daily"]["provider_rules"]["aliyun-oss"][
            "official_target_rule"
        ]
        == "D-3"
    )
    assert (
        overview["provider_schedules"]["daily"]["provider_rules"]["tencent-cos"][
            "official_target_rule"
        ]
        == "D-2"
    )
    assert overview["provider_schedules"]["qiniu_monthly"]["provider_codes"] == [
        "qiniu-kodo"
    ]
