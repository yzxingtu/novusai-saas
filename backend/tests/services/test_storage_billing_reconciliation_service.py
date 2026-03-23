from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.exceptions import BusinessException
from app.plugins.module_loader import load_plugin_module


def _make_scalars_result(items):
    result = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = items
    result.scalars.return_value = scalars
    return result


def _make_scalar_one_or_none_result(item):
    result = MagicMock()
    result.scalar_one_or_none.return_value = item
    return result


class _FakeReconciliationDb:
    def __init__(self) -> None:
        self.added = []
        self.deleted = []
        self._next_id = 1

    def add(self, row) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        for row in self.added:
            if getattr(row, "id", None) is None:
                row.id = self._next_id
                self._next_id += 1

    async def execute(self, *args, **kwargs):
        _ = args, kwargs
        return _make_scalars_result([])

    async def delete(self, row) -> None:
        self.deleted.append(row)


class _FakeTencentResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class _FakeTencentClient:
    def __init__(self, payload):
        self._payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, *args, **kwargs):
        return _FakeTencentResponse(self._payload)


@pytest.mark.asyncio
async def test_tencent_official_bill_adapter_normalizes_bill_detail(monkeypatch) -> None:
    module = load_plugin_module("storage-billing", "providers.tencent")
    assert module is not None

    payload = {
        "Response": {
            "Total": 1,
            "Context": "",
            "DetailSet": [
                {
                    "BillDay": "2026-03-21 00:00:00",
                    "BusinessCode": "p_cos",
                    "BusinessCodeName": "COS对象存储",
                    "ResourceId": "tenant-a-bucket-1250000000",
                    "ResourceName": "tenant-a-bucket",
                    "PayerUin": "10001",
                    "ComponentSet": [
                        {
                            "ComponentCodeName": "公网下行流量",
                            "ItemCodeName": "公网下行流量",
                            "RealCost": "0.88000000",
                            "UsedAmount": "2",
                            "UsedAmountUnit": "GB",
                            "ComponentConfig": [
                                {"Name": "存储桶", "Value": "tenant-a-bucket"}
                            ],
                        }
                    ],
                    "Tags": [{"TagKey": "tenant", "TagValue": "alpha"}],
                }
            ],
        }
    }

    monkeypatch.setattr(
        module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeTencentClient(payload),
    )

    adapter = module.TencentCosOfficialBillAdapter()
    result = await adapter.fetch_official_bill(
        module.BillingFetchRequest(
            billing_date=date(2026, 3, 21),
            driver_code="tencent-cos",
            profile={
                "bill_source": "describe_bill_detail",
                "secret_id": "sid",
                "secret_key": "skey",
                "region": "ap-shanghai",
            },
        )
    )

    assert result.source_status == "fetched"
    assert len(result.charge_items) == 1
    assert result.charge_items[0].charge_basis == "egress_traffic"
    assert result.charge_items[0].bucket_name == "tenant-a-bucket"
    assert result.charge_items[0].usage_bytes == 2 * 1024 * 1024 * 1024
    assert result.amount_total == Decimal("0.88000000")


@pytest.mark.asyncio
async def test_reconciliation_service_rebuilds_daily_charges_from_binding() -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    model_module = load_plugin_module("storage-billing", "models")
    provider_base = load_plugin_module("storage-billing", "providers.base")
    assert module is not None
    assert model_module is not None
    assert provider_base is not None

    source_row = model_module.StorageProviderBillSource(
        run_id=1,
        provider_code="tencent-cos",
        driver_code="tencent-cos",
        billing_date=date(2026, 3, 21),
        source_status="fetched",
    )
    source_row.id = 7

    binding = model_module.StorageTenantBinding(
        tenant_id=9,
        provider_code="tencent-cos",
        driver_code="tencent-cos",
        provider_profile_code="tencent-default",
        billing_mode="official_reconciled",
        scope_type="bucket",
        scope_value="tenant-a-bucket",
        bucket_name="tenant-a-bucket",
        validation_status="valid",
        entitlement_snapshot_json={},
        metadata_json={},
        is_active=True,
    )
    binding.id = 12

    charge_item = provider_base.BillingChargeItem(
        charge_basis="egress_traffic",
        amount_total=Decimal("1.250000"),
        usage_bytes=1024,
        currency="CNY",
        resource_id="tenant-a-bucket-1250000000",
        resource_name="tenant-a-bucket",
        bucket_name="tenant-a-bucket",
        details_json={"bucket_aliases": ["tenant-a-bucket", "tenant-a-bucket-1250000000"]},
    )

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _make_scalars_result([]),
            _make_scalars_result([binding]),
        ]
    )
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()

    service = module.StorageBillingReconciliationService(db, host_read=None)
    summary = await service._replace_daily_charges_for_source(
        source_row=source_row,
        charge_items=[charge_item],
    )

    assert summary["matched_items"] == 1
    assert summary["written_charge_rows"] == 1

    written_row = db.add.call_args.args[0]
    assert isinstance(written_row, model_module.StorageTenantDailyCharge)
    assert written_row.tenant_id == 9
    assert written_row.provider_code == "tencent-cos"
    assert written_row.source_id == 7
    assert written_row.usage_bytes == 1024
    assert written_row.amount_total == Decimal("1.250000")
    assert written_row.details_json["binding_ids"] == [12]


@pytest.mark.asyncio
async def test_reconciliation_service_marks_completed_with_gaps_for_not_implemented_source(
    monkeypatch,
) -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    provider_base = load_plugin_module("storage-billing", "providers.base")
    assert module is not None
    assert provider_base is not None

    db = _FakeReconciliationDb()
    service = module.StorageBillingReconciliationService(db, host_read=None)

    monkeypatch.setattr(
        service,
        "_get_billable_drivers",
        AsyncMock(return_value=[{"code": "qiniu-kodo", "plugin_status": "enabled"}]),
    )
    monkeypatch.setattr(
        service,
        "_fetch_provider_result",
        AsyncMock(
            return_value=provider_base.BillingFetchResult(
                provider_code="qiniu-kodo",
                driver_code="qiniu-kodo",
                billing_date=date(2026, 3, 21),
                source_status="not_implemented",
                error_message="finance api is not available for this account",
                raw_payload_json={"provider": "qiniu-kodo"},
            )
        ),
    )
    monkeypatch.setattr(
        service,
        "rebuild_tenant_statements_for_billing_date",
        AsyncMock(return_value=0),
    )

    result = await service.run_daily_reconciliation(date(2026, 3, 21))

    assert result["run"]["status"] == "completed_with_gaps"
    assert result["run"]["summary"]["source_status_counts"] == {"not_implemented": 1}
    assert result["sources"][0]["source_status"] == "not_implemented"


@pytest.mark.asyncio
async def test_reconciliation_service_rejects_invalid_manual_billing_date() -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    assert module is not None

    service = module.StorageBillingReconciliationService(AsyncMock(), host_read=None)

    with pytest.raises(BusinessException, match="billing_date"):
        await service.trigger_manual_run({"billing_date": "2026/03/21"})


@pytest.mark.asyncio
async def test_reconciliation_service_rejects_invalid_qiniu_billing_month() -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    assert module is not None

    service = module.StorageBillingReconciliationService(AsyncMock(), host_read=None)

    with pytest.raises(BusinessException, match="billing_month"):
        await service.trigger_qiniu_monthly_settlement({"billing_month": "2026-13"})


@pytest.mark.asyncio
async def test_trigger_manual_run_without_billing_date_fans_out_provider_specific_rules(
    monkeypatch,
) -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    assert module is not None

    service = module.StorageBillingReconciliationService(AsyncMock(), host_read=None)
    monkeypatch.setattr(
        service,
        "_get_billable_drivers",
        AsyncMock(
            return_value=[
                {"code": "aliyun-oss", "is_available": True},
                {"code": "tencent-cos", "is_available": True},
            ]
        ),
    )
    monkeypatch.setattr(
        module,
        "_resolve_billing_date",
        lambda raw_value, default_offset_days=1: date(2026, 3, 24)
        - module.timedelta(days=default_offset_days),
    )
    service._execute_reconciliation = AsyncMock(
        side_effect=[
            {
                "run": {
                    "id": 301,
                    "status": "completed",
                    "billing_date": "2026-03-21",
                    "period_label": "2026-03-21",
                    "summary": {
                        "statement_count": 1,
                        "source_status_counts": {"fetched": 1},
                        "providers": [{"provider_code": "aliyun-oss", "source_status": "fetched"}],
                    },
                },
                "sources": [],
                "billable_drivers": [{"code": "aliyun-oss", "is_available": True}],
            },
            {
                "run": {
                    "id": 302,
                    "status": "completed",
                    "billing_date": "2026-03-22",
                    "period_label": "2026-03-22",
                    "summary": {
                        "statement_count": 1,
                        "source_status_counts": {"fetched": 1},
                        "providers": [{"provider_code": "tencent-cos", "source_status": "fetched"}],
                    },
                },
                "sources": [],
                "billable_drivers": [{"code": "tencent-cos", "is_available": True}],
            },
        ]
    )

    result = await service.trigger_manual_run({})

    assert result["run"]["status"] == "completed"
    assert result["run"]["summary"]["run_count"] == 2
    assert result["provider_plans"][0]["provider_code"] == "aliyun-oss"
    assert result["provider_plans"][0]["official_target_rule"] == "D-3"
    assert result["provider_plans"][1]["provider_code"] == "tencent-cos"
    assert result["provider_plans"][1]["official_target_rule"] == "D-2"

    first_call = service._execute_reconciliation.await_args_list[0].kwargs
    second_call = service._execute_reconciliation.await_args_list[1].kwargs
    assert first_call["trigger_type"] == "manual"
    assert first_call["billing_date"] == date(2026, 3, 21)
    assert first_call["provider_codes"] == ["aliyun-oss"]
    assert first_call["requested_scope"]["official_target_rule"] == "D-3"
    assert second_call["trigger_type"] == "manual"
    assert second_call["billing_date"] == date(2026, 3, 22)
    assert second_call["provider_codes"] == ["tencent-cos"]
    assert second_call["requested_scope"]["official_target_rule"] == "D-2"


@pytest.mark.asyncio
async def test_trigger_manual_run_without_billing_date_returns_skipped_when_no_daily_provider_resolves(
    monkeypatch,
) -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    assert module is not None

    service = module.StorageBillingReconciliationService(AsyncMock(), host_read=None)
    monkeypatch.setattr(
        service,
        "_get_billable_drivers",
        AsyncMock(return_value=[]),
    )

    result = await service.trigger_manual_run({})

    assert result["run"]["status"] == "skipped"
    assert result["run"]["summary"]["run_count"] == 0
    assert result["provider_plans"] == []


@pytest.mark.asyncio
async def test_trigger_manual_run_without_billing_date_defaults_single_provider(
    monkeypatch,
) -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    assert module is not None

    service = module.StorageBillingReconciliationService(AsyncMock(), host_read=None)
    monkeypatch.setattr(
        service,
        "_get_billable_drivers",
        AsyncMock(return_value=[{"code": "aliyun-oss", "is_available": True}]),
    )
    monkeypatch.setattr(
        module,
        "_resolve_billing_date",
        lambda raw_value, default_offset_days=1: date(2026, 3, 24)
        - module.timedelta(days=default_offset_days),
    )
    service._execute_reconciliation = AsyncMock(return_value={"run": {"id": 201, "status": "completed"}})

    result = await service.trigger_manual_run({})

    assert result["run"]["id"] == 201
    service._execute_reconciliation.assert_awaited_once()
    kwargs = service._execute_reconciliation.await_args.kwargs
    assert kwargs["billing_date"] == date(2026, 3, 21)
    assert kwargs["provider_codes"] == ["aliyun-oss"]
    assert kwargs["requested_scope"]["official_target_rule"] == "D-3"


@pytest.mark.asyncio
async def test_run_daily_reconciliation_uses_provider_specific_lag_rules(monkeypatch) -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    assert module is not None

    service = module.StorageBillingReconciliationService(AsyncMock(), host_read=MagicMock())
    monkeypatch.setattr(
        service,
        "_get_billable_drivers",
        AsyncMock(
            return_value=[
                {"code": "aliyun-oss", "is_available": True},
                {"code": "tencent-cos", "is_available": True},
            ]
        ),
    )
    monkeypatch.setattr(
        module,
        "_resolve_billing_date",
        lambda raw_value, default_offset_days=1: date(2026, 3, 24)
        - module.timedelta(days=default_offset_days),
    )
    service._execute_reconciliation = AsyncMock(
        side_effect=[
            {
                "run": {
                    "id": 101,
                    "status": "completed",
                    "billing_date": "2026-03-21",
                    "period_label": "2026-03-21",
                    "summary": {
                        "statement_count": 1,
                        "source_status_counts": {"fetched": 1},
                        "providers": [{"provider_code": "aliyun-oss", "source_status": "fetched"}],
                    },
                },
                "sources": [],
                "billable_drivers": [{"code": "aliyun-oss", "is_available": True}],
            },
            {
                "run": {
                    "id": 102,
                    "status": "completed",
                    "billing_date": "2026-03-22",
                    "period_label": "2026-03-22",
                    "summary": {
                        "statement_count": 2,
                        "source_status_counts": {"fetched": 1},
                        "providers": [{"provider_code": "tencent-cos", "source_status": "fetched"}],
                    },
                },
                "sources": [],
                "billable_drivers": [{"code": "tencent-cos", "is_available": True}],
            },
        ]
    )

    result = await service.run_daily_reconciliation()

    assert result["run"]["status"] == "completed"
    assert result["run"]["summary"]["run_count"] == 2
    assert result["provider_plans"][0]["provider_code"] == "aliyun-oss"
    assert result["provider_plans"][0]["official_target_rule"] == "D-3"
    assert result["provider_plans"][0]["billing_date"] == "2026-03-21"
    assert result["provider_plans"][1]["provider_code"] == "tencent-cos"
    assert result["provider_plans"][1]["official_target_rule"] == "D-2"
    assert result["provider_plans"][1]["billing_date"] == "2026-03-22"

    first_call = service._execute_reconciliation.await_args_list[0].kwargs
    second_call = service._execute_reconciliation.await_args_list[1].kwargs
    assert first_call["trigger_type"] == "schedule"
    assert first_call["provider_codes"] == ["aliyun-oss"]
    assert first_call["requested_scope"]["official_billing_lag_days"] == 3
    assert first_call["requested_scope"]["official_target_rule"] == "D-3"
    assert second_call["provider_codes"] == ["tencent-cos"]
    assert second_call["requested_scope"]["official_billing_lag_days"] == 2
    assert second_call["requested_scope"]["official_target_rule"] == "D-2"


@pytest.mark.asyncio
async def test_overview_service_rejects_invalid_period_type() -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    assert module is not None

    service = module.StorageBillingOverviewService(db=None, host_read=None)

    with pytest.raises(BusinessException, match="period_type"):
        await service.build_tenant_statement(
            tenant_id=9,
            period_type="weekly",
        )


@pytest.mark.asyncio
async def test_reconciliation_service_prefers_bucket_scope_over_account_scope() -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    model_module = load_plugin_module("storage-billing", "models")
    provider_base = load_plugin_module("storage-billing", "providers.base")
    assert module is not None
    assert model_module is not None
    assert provider_base is not None

    source_row = model_module.StorageProviderBillSource(
        run_id=1,
        provider_code="tencent-cos",
        driver_code="tencent-cos",
        billing_date=date(2026, 3, 22),
        source_status="fetched",
    )
    source_row.id = 8

    bucket_binding = model_module.StorageTenantBinding(
        tenant_id=101,
        provider_code="tencent-cos",
        driver_code="tencent-cos",
        provider_profile_code="tencent-default",
        billing_mode="official_reconciled",
        scope_type="bucket",
        scope_value="tenant-a-bucket",
        bucket_name="tenant-a-bucket",
        validation_status="valid",
        entitlement_snapshot_json={},
        metadata_json={},
        is_active=True,
    )
    bucket_binding.id = 31

    account_binding = model_module.StorageTenantBinding(
        tenant_id=202,
        provider_code="tencent-cos",
        driver_code="tencent-cos",
        provider_profile_code="tencent-default",
        billing_mode="official_reconciled",
        scope_type="account",
        scope_value="acct-123",
        account_identifier="acct-123",
        validation_status="valid",
        entitlement_snapshot_json={},
        metadata_json={},
        is_active=True,
    )
    account_binding.id = 32

    charge_item = provider_base.BillingChargeItem(
        charge_basis="egress_traffic",
        amount_total=Decimal("0.990000"),
        usage_bytes=4096,
        currency="CNY",
        resource_id="tenant-a-bucket-1250000000",
        resource_name="tenant-a-bucket",
        bucket_name="tenant-a-bucket",
        account_identifier="acct-123",
        details_json={"bucket_aliases": ["tenant-a-bucket", "tenant-a-bucket-1250000000"]},
    )

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _make_scalars_result([]),
            _make_scalars_result([bucket_binding, account_binding]),
        ]
    )
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()

    service = module.StorageBillingReconciliationService(db, host_read=None)
    summary = await service._replace_daily_charges_for_source(
        source_row=source_row,
        charge_items=[charge_item],
    )

    assert summary["matched_items"] == 1
    assert summary["ambiguous_items"] == 0
    written_row = db.add.call_args.args[0]
    assert written_row.tenant_id == 101
    assert written_row.details_json["binding_ids"] == [31]


@pytest.mark.asyncio
async def test_reconciliation_service_returns_allocation_audit_samples() -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    model_module = load_plugin_module("storage-billing", "models")
    provider_base = load_plugin_module("storage-billing", "providers.base")
    assert module is not None
    assert model_module is not None
    assert provider_base is not None

    source_row = model_module.StorageProviderBillSource(
        run_id=1,
        provider_code="aliyun-oss",
        driver_code="aliyun-oss",
        billing_date=date(2026, 3, 22),
        source_status="fetched",
    )
    source_row.id = 9

    binding_a = model_module.StorageTenantBinding(
        tenant_id=301,
        provider_code="aliyun-oss",
        driver_code="aliyun-oss",
        provider_profile_code="aliyun-default",
        billing_mode="official_reconciled",
        scope_type="bucket",
        scope_value="shared-bucket",
        bucket_name="shared-bucket",
        validation_status="valid",
        entitlement_snapshot_json={},
        metadata_json={},
        is_active=True,
    )
    binding_a.id = 41

    binding_b = model_module.StorageTenantBinding(
        tenant_id=302,
        provider_code="aliyun-oss",
        driver_code="aliyun-oss",
        provider_profile_code="aliyun-default",
        billing_mode="official_reconciled",
        scope_type="bucket",
        scope_value="shared-bucket",
        bucket_name="shared-bucket",
        validation_status="valid",
        entitlement_snapshot_json={},
        metadata_json={},
        is_active=True,
    )
    binding_b.id = 42

    unmatched_item = provider_base.BillingChargeItem(
        charge_basis="egress_traffic",
        amount_total=Decimal("0.100000"),
        usage_bytes=100,
        currency="CNY",
        bucket_name="unbound-bucket",
        resource_name="unbound-bucket",
    )
    ambiguous_item = provider_base.BillingChargeItem(
        charge_basis="egress_traffic",
        amount_total=Decimal("0.200000"),
        usage_bytes=200,
        currency="CNY",
        bucket_name="shared-bucket",
        resource_name="shared-bucket",
        details_json={"bucket_aliases": ["shared-bucket"]},
    )

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _make_scalars_result([]),
            _make_scalars_result([binding_a, binding_b]),
        ]
    )
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()

    service = module.StorageBillingReconciliationService(db, host_read=None)
    summary = await service._replace_daily_charges_for_source(
        source_row=source_row,
        charge_items=[unmatched_item, ambiguous_item],
    )

    assert summary["matched_items"] == 0
    assert summary["unmatched_items"] == 1
    assert summary["ambiguous_items"] == 1
    assert summary["written_charge_rows"] == 0
    assert summary["unmatched_item_samples"][0]["bucket_name"] == "unbound-bucket"
    assert summary["ambiguous_item_samples"][0]["matched_bindings"][0]["scope_value"] == "shared-bucket"


@pytest.mark.asyncio
async def test_reconciliation_run_includes_allocation_summary(monkeypatch) -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    provider_base = load_plugin_module("storage-billing", "providers.base")
    assert module is not None
    assert provider_base is not None

    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock(return_value=_make_scalars_result([]))
    db.delete = AsyncMock()

    service = module.StorageBillingReconciliationService(db, host_read=None)
    fake_summary = {
        "matched_items": 2,
        "unmatched_items": 1,
        "ambiguous_items": 1,
        "written_charge_rows": 1,
        "unmatched_item_samples": [],
        "ambiguous_item_samples": [],
    }

    monkeypatch.setattr(
        service,
        "_get_billable_drivers",
        AsyncMock(return_value=[{"code": "aliyun-oss", "is_available": True}]),
    )
    monkeypatch.setattr(
        service,
        "_fetch_provider_result",
        AsyncMock(
            return_value=provider_base.BillingFetchResult(
                provider_code="aliyun-oss",
                driver_code="aliyun-oss",
                billing_date=date(2026, 3, 25),
                source_status="fetched",
                charge_items=[
                    provider_base.BillingChargeItem(
                        charge_basis="egress_traffic",
                        amount_total=Decimal("0.5"),
                    )
                ],
            )
        ),
    )
    monkeypatch.setattr(
        service,
        "_replace_daily_charges_for_source",
        AsyncMock(return_value=fake_summary),
    )
    monkeypatch.setattr(
        service,
        "rebuild_tenant_statements_for_billing_date",
        AsyncMock(return_value=0),
    )

    result = await service.run_daily_reconciliation(date(2026, 3, 25))

    provider_summary = result["run"]["summary"]["providers"][0]
    assert provider_summary["matched_items"] == 2
    assert provider_summary["unmatched_items"] == 1
    assert provider_summary["ambiguous_items"] == 1
    assert provider_summary["written_charge_rows"] == 1

    allocation_payload = result["sources"][0]["raw_payload_json"]
    assert allocation_payload["allocation_summary"] == {
        "matched_items": 2,
        "unmatched_items": 1,
        "ambiguous_items": 1,
        "written_charge_rows": 1,
    }
    audit = allocation_payload["allocation_audit"]
    assert audit["unmatched_item_samples"] == []
    assert audit["ambiguous_item_samples"] == []


@pytest.mark.asyncio
async def test_run_daily_reconciliation_uses_provider_specific_schedule_by_default(
    monkeypatch,
) -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    assert module is not None

    db = AsyncMock()
    service = module.StorageBillingReconciliationService(db, host_read=None)

    monkeypatch.setattr(
        service,
        "_get_billable_drivers",
        AsyncMock(
            return_value=[
                {"code": "aliyun-oss", "is_available": True},
                {"code": "tencent-cos", "is_available": True},
            ]
        ),
    )
    monkeypatch.setattr(
        module,
        "_resolve_billing_date",
        lambda raw_value, default_offset_days=1: date(2026, 3, 24)
        - module.timedelta(days=default_offset_days),
    )

    execute_mock = AsyncMock(
        side_effect=[
            {
                "run": {
                    "id": 11,
                    "status": "completed",
                    "billing_date": "2026-03-21",
                    "period_label": "2026-03-21",
                    "summary": {
                        "statement_count": 1,
                        "source_status_counts": {"fetched": 1},
                        "providers": [
                            {
                                "provider_code": "aliyun-oss",
                                "source_status": "fetched",
                                "charge_item_count": 1,
                                "matched_items": 1,
                                "unmatched_items": 0,
                                "ambiguous_items": 0,
                                "written_charge_rows": 1,
                            }
                        ],
                    },
                },
                "sources": [],
                "billable_drivers": [{"code": "aliyun-oss", "is_available": True}],
            },
            {
                "run": {
                    "id": 12,
                    "status": "completed",
                    "billing_date": "2026-03-22",
                    "period_label": "2026-03-22",
                    "summary": {
                        "statement_count": 2,
                        "source_status_counts": {"fetched": 1},
                        "providers": [
                            {
                                "provider_code": "tencent-cos",
                                "source_status": "fetched",
                                "charge_item_count": 2,
                                "matched_items": 2,
                                "unmatched_items": 0,
                                "ambiguous_items": 0,
                                "written_charge_rows": 2,
                            }
                        ],
                    },
                },
                "sources": [],
                "billable_drivers": [{"code": "tencent-cos", "is_available": True}],
            },
        ]
    )
    monkeypatch.setattr(service, "_execute_reconciliation", execute_mock)

    result = await service.run_daily_reconciliation()

    assert execute_mock.await_count == 2
    first_call = execute_mock.await_args_list[0].kwargs
    second_call = execute_mock.await_args_list[1].kwargs
    assert first_call["provider_codes"] == ["aliyun-oss"]
    assert first_call["billing_date"] == date(2026, 3, 21)
    assert first_call["requested_scope"]["official_target_rule"] == "D-3"
    assert second_call["provider_codes"] == ["tencent-cos"]
    assert second_call["billing_date"] == date(2026, 3, 22)
    assert second_call["requested_scope"]["official_target_rule"] == "D-2"

    assert result["run"]["status"] == "completed"
    assert result["run"]["summary"]["run_count"] == 2
    assert result["run"]["summary"]["statement_count"] == 3
    assert result["provider_plans"][0]["official_target_rule"] == "D-3"
    assert result["provider_plans"][1]["official_target_rule"] == "D-2"


@pytest.mark.asyncio
async def test_reconciliation_service_lists_run_charges() -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    models = load_plugin_module("storage-billing", "models")
    assert module is not None
    assert models is not None

    run = models.StorageBillingRun(
        billing_date=date(2026, 3, 23),
        status="completed",
        trigger_type="schedule",
    )
    run.id = 17
    run.provider_codes_json = ["aliyun-oss"]
    run.summary_json = {"statement_count": 1}

    source = models.StorageProviderBillSource(
        run_id=17,
        provider_code="aliyun-oss",
        driver_code="aliyun-oss",
        billing_date=date(2026, 3, 23),
        source_status="fetched",
        source_ref="bill-source-1",
    )
    source.id = 27
    source.source_key = "sbs-run-1"

    charge = models.StorageTenantDailyCharge(
        tenant_id=88,
        billing_date=date(2026, 3, 23),
        provider_code="aliyun-oss",
        driver_code="aliyun-oss",
        charge_basis="egress_traffic",
        usage_bytes=4096,
        amount_total=Decimal("3.600000"),
        currency="CNY",
        source_id=27,
        statement_id=91,
        details_json={"binding_ids": [4], "scope_values": ["bucket-a"], "item_count": 1},
    )
    charge.id = 101

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _make_scalar_one_or_none_result(run),
            _make_scalars_result([source]),
            _make_scalars_result([charge]),
        ]
    )

    service = module.StorageBillingReconciliationService(db, host_read=None)
    result = await service.list_run_charges(run_id=17)

    assert result["run"]["id"] == 17
    assert result["run_id"] == 17
    assert result["total"] == 1
    assert result["source_total"] == 1
    assert result["items"][0]["source_key"] == "sbs-run-1"
    assert result["items"][0]["details"]["binding_ids"] == [4]
    assert result["summary"]["amount_total"] == "3.600000"


@pytest.mark.asyncio
async def test_reconciliation_service_exports_run_charges_csv_with_headers() -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    models = load_plugin_module("storage-billing", "models")
    assert module is not None
    assert models is not None

    run = models.StorageBillingRun(
        billing_date=date(2026, 3, 23),
        status="completed",
        trigger_type="manual",
    )
    run.id = 18

    source = models.StorageProviderBillSource(
        run_id=18,
        provider_code="tencent-cos",
        driver_code="tencent-cos",
        billing_date=date(2026, 3, 23),
        source_status="fetched",
        source_ref="acct-1",
    )
    source.id = 28
    source.source_key = "sbs-run-2"

    charge = models.StorageTenantDailyCharge(
        tenant_id=99,
        billing_date=date(2026, 3, 23),
        provider_code="tencent-cos",
        driver_code="tencent-cos",
        charge_basis="cdn_origin_egress",
        usage_bytes=512,
        amount_total=Decimal("0.800000"),
        currency="CNY",
        source_id=28,
        statement_id=92,
        details_json={"binding_ids": [7], "scope_values": ["cdn.example.com"], "item_count": 2},
    )
    charge.id = 102

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _make_scalar_one_or_none_result(run),
            _make_scalars_result([source]),
            _make_scalars_result([charge]),
        ]
    )

    service = module.StorageBillingReconciliationService(db, host_read=None)
    response = await service.export_run_charges_csv(run_id=18)

    assert response.media_type == "text/csv; charset=utf-8"
    assert "storage_billing_run_18_2026-03-23_charges.csv" in response.headers["content-disposition"]
    body = response.body.decode("utf-8-sig")
    assert "run_id,period_type,billing_date,period_start,period_end,period_label,tenant_id,provider_code" in body
    assert ",18,daily,2026-03-23,2026-03-23,2026-03-23,2026-03-23,99,tencent-cos," in body
    assert "cdn.example.com" in body


@pytest.mark.asyncio
async def test_overview_service_exports_tenant_statement_charges_csv() -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    models = load_plugin_module("storage-billing", "models")
    assert module is not None
    assert models is not None

    statement = models.StorageTenantStatement(
        tenant_id=66,
        billing_date=date(2026, 3, 22),
        status="generated",
        currency="CNY",
        amount_total=Decimal("1.500000"),
        charge_count=1,
        summary_json={},
    )
    statement.id = 31

    charge = models.StorageTenantDailyCharge(
        tenant_id=66,
        billing_date=date(2026, 3, 22),
        provider_code="aliyun-oss",
        driver_code="aliyun-oss",
        charge_basis="egress_traffic",
        usage_bytes=2048,
        amount_total=Decimal("1.500000"),
        currency="CNY",
        source_id=71,
        statement_id=31,
        details_json={"binding_ids": [3], "scope_values": ["tenant-bucket"], "item_count": 1},
    )
    charge.id = 201

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _make_scalar_one_or_none_result(statement),
            _make_scalars_result([charge]),
            _make_scalars_result([charge]),
        ]
    )

    service = module.StorageBillingOverviewService(db, host_read=None)
    response = await service.export_tenant_statement_charges_csv(
        tenant_id=66,
        billing_date=date(2026, 3, 22),
    )

    assert response.media_type == "text/csv; charset=utf-8"
    assert "storage_billing_tenant_66_2026-03-22_charges.csv" in response.headers["content-disposition"]
    body = response.body.decode("utf-8-sig")
    assert "statement_status,provider_code,driver_code" in body
    assert "generated,aliyun-oss,aliyun-oss" in body


@pytest.mark.asyncio
async def test_reconciliation_service_lists_run_charges_with_source_context() -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    models = load_plugin_module("storage-billing", "models")
    assert module is not None
    assert models is not None

    run = models.StorageBillingRun(
        billing_date=date(2026, 3, 25),
        status="completed",
        trigger_type="schedule",
    )
    run.id = 77

    source = models.StorageProviderBillSource(
        run_id=77,
        provider_code="aliyun-oss",
        driver_code="aliyun-oss",
        billing_date=date(2026, 3, 25),
        source_status="fetched",
        source_ref="aliyun-default:2026-03-25",
    )
    source.id = 701
    source.source_key = "sbs-run-701"

    charge = models.StorageTenantDailyCharge(
        tenant_id=901,
        billing_date=date(2026, 3, 25),
        provider_code="aliyun-oss",
        driver_code="aliyun-oss",
        charge_basis="egress_traffic",
        usage_bytes=4096,
        amount_total=Decimal("2.500000"),
        currency="CNY",
        source_id=701,
        statement_id=88,
        details_json={"binding_ids": [11], "scope_values": ["tenant-901-bucket"], "item_count": 1},
    )
    charge.id = 801

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _make_scalar_one_or_none_result(run),
            _make_scalars_result([source]),
            _make_scalars_result([charge]),
        ]
    )

    service = module.StorageBillingReconciliationService(db, host_read=None)
    result = await service.list_run_charges(run_id=77)

    assert result["run"]["id"] == 77
    assert result["total"] == 1
    assert result["items"][0]["tenant_id"] == 901
    assert result["items"][0]["source_key"] == "sbs-run-701"
    assert result["summary"]["amount_total"] == "2.500000"


@pytest.mark.asyncio
async def test_reconciliation_service_exports_run_charges_csv_with_body_fields() -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    models = load_plugin_module("storage-billing", "models")
    assert module is not None
    assert models is not None

    run = models.StorageBillingRun(
        billing_date=date(2026, 3, 25),
        status="completed",
        trigger_type="schedule",
    )
    run.id = 78

    source = models.StorageProviderBillSource(
        run_id=78,
        provider_code="tencent-cos",
        driver_code="tencent-cos",
        billing_date=date(2026, 3, 25),
        source_status="fetched",
        source_ref="tencent-default:2026-03-25",
    )
    source.id = 702
    source.source_key = "sbs-run-702"

    charge = models.StorageTenantDailyCharge(
        tenant_id=902,
        billing_date=date(2026, 3, 25),
        provider_code="tencent-cos",
        driver_code="tencent-cos",
        charge_basis="cdn_origin_egress",
        usage_bytes=2048,
        amount_total=Decimal("1.200000"),
        currency="CNY",
        source_id=702,
        statement_id=89,
        details_json={"binding_ids": [12], "scope_values": ["cdn.example.com"], "item_count": 1},
    )
    charge.id = 802

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _make_scalar_one_or_none_result(run),
            _make_scalars_result([source]),
            _make_scalars_result([charge]),
        ]
    )

    service = module.StorageBillingReconciliationService(db, host_read=None)
    response = await service.export_run_charges_csv(run_id=78)

    body = response.body.decode("utf-8-sig")
    assert response.media_type == "text/csv; charset=utf-8"
    assert "run_id" in body
    assert "tencent-cos" in body
    assert "cdn_origin_egress" in body
