from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.responses import Response

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


@pytest.mark.asyncio
async def test_storage_billing_tenant_endpoints_delegate_to_service(
    monkeypatch,
) -> None:
    module = load_plugin_module("storage-billing", "api.tenant")
    assert module is not None

    overview_service = AsyncMock()
    overview_service.build_tenant_statement = AsyncMock(
        return_value={"statement": {"id": 1}}
    )
    overview_service.list_tenant_statements = AsyncMock(
        return_value={"items": [{"id": 2}], "total": 1, "limit": 15}
    )
    overview_service.list_tenant_statement_charges = AsyncMock(
        return_value={"items": [{"id": 3}], "total": 1, "billing_date": "2026-03-22"}
    )
    overview_service.export_tenant_statement_charges_csv = AsyncMock(
        return_value=Response(content=b"id\n3\n", media_type="text/csv")
    )

    binding_service = AsyncMock()
    binding_service.ensure_tenant_billing_ready = AsyncMock(
        return_value={"prerequisites": {"ready": True}}
    )
    binding_service.get_tenant_prerequisites = AsyncMock(
        return_value={
            "ok": True,
            "provider_capabilities": {
                "tencent-cos": {
                    "scheduled_daily_supported": True,
                    "supported_period_types": ["daily"],
                }
            },
        }
    )

    overview_factory = MagicMock()
    overview_factory.from_context.return_value = overview_service
    monkeypatch.setattr(module, "StorageBillingOverviewService", overview_factory)

    binding_factory = MagicMock()
    binding_factory.from_context.return_value = binding_service
    monkeypatch.setattr(module, "StorageBillingBindingService", binding_factory)

    ctx = MagicMock()
    ctx.get_current_tenant_id.return_value = 9
    ctx.get_request_id.return_value = "req-tenant-1"

    current_request = MagicMock()
    current_request.query_params = {"billing_date": "2026-03-22"}
    current_result = await module.get_current_statement(current_request, ctx)

    list_request = MagicMock()
    list_request.query_params = {"limit": "15"}
    list_result = await module.list_statements(list_request, ctx)

    charges_request = MagicMock()
    charges_request.query_params = {"billing_date": "2026-03-22"}
    charges_result = await module.list_statement_charges(charges_request, ctx)

    export_request = MagicMock()
    export_request.query_params = {"billing_date": "2026-03-22"}
    export_result = await module.export_statement_charges(export_request, ctx)

    prereq_request = MagicMock()
    prereq_result = await module.get_prerequisites(prereq_request, ctx)

    assert current_result["statement"]["id"] == 1
    assert binding_service.ensure_tenant_billing_ready.await_count == 4
    overview_service.build_tenant_statement.assert_awaited_once_with(
        tenant_id=9,
        billing_date=date(2026, 3, 22),
        request_id="req-tenant-1",
    )

    assert list_result["items"][0]["id"] == 2
    overview_service.list_tenant_statements.assert_awaited_once_with(
        tenant_id=9,
        limit=15,
    )

    assert charges_result["items"][0]["id"] == 3
    overview_service.list_tenant_statement_charges.assert_awaited_once_with(
        tenant_id=9,
        billing_date=date(2026, 3, 22),
    )
    assert export_result.media_type == "text/csv"
    overview_service.export_tenant_statement_charges_csv.assert_awaited_once_with(
        tenant_id=9,
        billing_date=date(2026, 3, 22),
    )

    assert prereq_result["ok"] is True
    binding_service.get_tenant_prerequisites.assert_awaited_once_with(9)
    assert (
        prereq_result["provider_capabilities"]["tencent-cos"][
            "scheduled_daily_supported"
        ]
        is True
    )
    assert prereq_result["provider_capabilities"]["tencent-cos"][
        "supported_period_types"
    ] == ["daily"]


@pytest.mark.asyncio
async def test_storage_billing_tenant_endpoints_forward_period_type(
    monkeypatch,
) -> None:
    module = load_plugin_module("storage-billing", "api.tenant")
    assert module is not None

    overview_service = AsyncMock()
    overview_service.build_tenant_statement = AsyncMock(
        return_value={"statement": {"id": 1}}
    )
    overview_service.list_tenant_statement_charges = AsyncMock(
        return_value={"items": [{"id": 3}], "total": 1, "billing_date": "2026-03-22"}
    )
    overview_service.export_tenant_statement_charges_csv = AsyncMock(
        return_value=Response(content=b"id\n3\n", media_type="text/csv")
    )

    binding_service = AsyncMock()
    binding_service.ensure_tenant_billing_ready = AsyncMock(
        return_value={"prerequisites": {"ready": True}}
    )
    binding_service.get_tenant_prerequisites = AsyncMock(return_value={"ok": True})

    overview_factory = MagicMock()
    overview_factory.from_context.return_value = overview_service
    monkeypatch.setattr(module, "StorageBillingOverviewService", overview_factory)

    binding_factory = MagicMock()
    binding_factory.from_context.return_value = binding_service
    monkeypatch.setattr(module, "StorageBillingBindingService", binding_factory)

    ctx = MagicMock()
    ctx.get_current_tenant_id.return_value = 9
    ctx.get_request_id.return_value = "req-tenant-1"

    request = MagicMock()
    request.query_params = {"billing_date": "2026-03-22", "period_type": "monthly"}
    await module.get_current_statement(request, ctx)
    overview_service.build_tenant_statement.assert_awaited_once_with(
        tenant_id=9,
        billing_date=date(2026, 3, 22),
        request_id="req-tenant-1",
        period_type="monthly",
    )

    charges_request = MagicMock()
    charges_request.query_params = {
        "billing_date": "2026-03-22",
        "period_type": "monthly",
    }
    await module.list_statement_charges(charges_request, ctx)
    overview_service.list_tenant_statement_charges.assert_awaited_once_with(
        tenant_id=9,
        billing_date=date(2026, 3, 22),
        period_type="monthly",
    )

    export_request = MagicMock()
    export_request.query_params = {
        "billing_date": "2026-03-22",
        "period_type": "monthly",
    }
    await module.export_statement_charges(export_request, ctx)
    overview_service.export_tenant_statement_charges_csv.assert_awaited_once_with(
        tenant_id=9,
        billing_date=date(2026, 3, 22),
        period_type="monthly",
    )
    assert binding_service.ensure_tenant_billing_ready.await_count == 3


@pytest.mark.asyncio
async def test_storage_billing_tenant_endpoints_block_when_prerequisites_not_ready(
    monkeypatch,
) -> None:
    module = load_plugin_module("storage-billing", "api.tenant")
    assert module is not None

    overview_service = AsyncMock()
    overview_factory = MagicMock()
    overview_factory.from_context.return_value = overview_service
    monkeypatch.setattr(module, "StorageBillingOverviewService", overview_factory)

    binding_service = AsyncMock()
    binding_service.ensure_tenant_billing_ready = AsyncMock(
        side_effect=BusinessException(
            message="Storage billing is not ready for the current tenant.",
            data={"missing_reasons": ["provider_profile_disabled"]},
        )
    )
    binding_factory = MagicMock()
    binding_factory.from_context.return_value = binding_service
    monkeypatch.setattr(module, "StorageBillingBindingService", binding_factory)

    ctx = MagicMock()
    ctx.get_current_tenant_id.return_value = 9
    ctx.get_request_id.return_value = "req-tenant-blocked"

    request = MagicMock()
    request.query_params = {}

    with pytest.raises(BusinessException, match="not ready"):
        await module.get_current_statement(request, ctx)

    overview_factory.from_context.assert_not_called()


@pytest.mark.asyncio
async def test_storage_billing_tenant_endpoints_reject_invalid_billing_date(
    monkeypatch,
) -> None:
    module = load_plugin_module("storage-billing", "api.tenant")
    assert module is not None

    overview_factory = MagicMock()
    monkeypatch.setattr(module, "StorageBillingOverviewService", overview_factory)

    ctx = MagicMock()
    request = MagicMock()
    request.query_params = {"billing_date": "2026/03/22"}

    with pytest.raises(BusinessException, match="billing_date"):
        await module.get_current_statement(request, ctx)

    overview_factory.from_context.assert_not_called()


@pytest.mark.asyncio
async def test_storage_billing_tenant_endpoints_reject_invalid_period_type(
    monkeypatch,
) -> None:
    module = load_plugin_module("storage-billing", "api.tenant")
    assert module is not None

    overview_factory = MagicMock()
    monkeypatch.setattr(module, "StorageBillingOverviewService", overview_factory)

    ctx = MagicMock()
    request = MagicMock()
    request.query_params = {"period_type": "weekly"}

    with pytest.raises(BusinessException, match="period_type"):
        await module.get_current_statement(request, ctx)

    overview_factory.from_context.assert_not_called()


@pytest.mark.asyncio
async def test_storage_billing_overview_service_lists_recent_statements() -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    models = load_plugin_module("storage-billing", "models")
    assert module is not None
    assert models is not None

    latest = models.StorageTenantStatement(
        tenant_id=33,
        billing_date=date(2026, 3, 22),
        status="generated",
        currency="CNY",
        amount_total=Decimal("1.230000"),
        charge_count=2,
        summary_json={"provider_codes": ["aliyun-oss"]},
    )
    latest.id = 11

    previous = models.StorageTenantStatement(
        tenant_id=33,
        billing_date=date(2026, 3, 21),
        status="published",
        currency="CNY",
        amount_total=Decimal("0.880000"),
        charge_count=1,
        summary_json={"provider_codes": ["tencent-cos"]},
    )
    previous.id = 10

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_make_scalars_result([latest, previous]))

    service = module.StorageBillingOverviewService(db, host_read=None)
    result = await service.list_tenant_statements(tenant_id=33, limit=5)

    assert result["tenant_id"] == 33
    assert result["total"] == 2
    assert result["limit"] == 5
    assert result["items"][0]["billing_date"] == "2026-03-22"
    assert result["items"][1]["status"] == "published"


@pytest.mark.asyncio
async def test_storage_billing_overview_service_lists_statement_charges() -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    models = load_plugin_module("storage-billing", "models")
    assert module is not None
    assert models is not None

    statement = models.StorageTenantStatement(
        tenant_id=44,
        billing_date=date(2026, 3, 22),
        status="generated",
        currency="CNY",
        amount_total=Decimal("1.500000"),
        charge_count=2,
        summary_json={"provider_codes": ["aliyun-oss", "tencent-cos"]},
    )
    statement.id = 21

    charge_a = models.StorageTenantDailyCharge(
        tenant_id=44,
        billing_date=date(2026, 3, 22),
        provider_code="aliyun-oss",
        driver_code="aliyun-oss",
        charge_basis="egress_traffic",
        usage_bytes=2048,
        amount_total=Decimal("1.200000"),
        currency="CNY",
        source_id=7,
        statement_id=21,
        details_json={"binding_ids": [1], "scope_values": ["tenant-a-bucket"]},
    )
    charge_a.id = 101

    charge_b = models.StorageTenantDailyCharge(
        tenant_id=44,
        billing_date=date(2026, 3, 22),
        provider_code="tencent-cos",
        driver_code="tencent-cos",
        charge_basis="cdn_origin_egress",
        usage_bytes=512,
        amount_total=Decimal("0.300000"),
        currency="CNY",
        source_id=8,
        statement_id=21,
        details_json={"binding_ids": [2], "scope_values": ["cdn.example.com"]},
    )
    charge_b.id = 102

    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _make_scalar_one_or_none_result(statement),
            _make_scalars_result([charge_a, charge_b]),
        ]
    )

    service = module.StorageBillingOverviewService(db, host_read=None)
    result = await service.list_tenant_statement_charges(tenant_id=44)

    assert result["tenant_id"] == 44
    assert result["billing_date"] == "2026-03-22"
    assert result["statement"]["id"] == 21
    assert result["total"] == 2
    assert result["items"][0]["provider_code"] == "aliyun-oss"
    assert result["items"][0]["details"]["binding_ids"] == [1]
    assert result["summary"]["amount_total"] == "1.500000"
    assert result["summary"]["total_usage_bytes"] == 2560
    assert result["summary"]["provider_totals"][0]["provider_code"] == "aliyun-oss"
    assert (
        result["summary"]["charge_basis_totals"][0]["charge_basis"] == "egress_traffic"
    )


@pytest.mark.asyncio
async def test_storage_billing_overview_service_returns_empty_statement_charges_without_statement() -> (
    None
):
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    assert module is not None

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_make_scalar_one_or_none_result(None))

    service = module.StorageBillingOverviewService(db, host_read=None)
    result = await service.list_tenant_statement_charges(tenant_id=55)

    assert result["tenant_id"] == 55
    assert result["billing_date"] is None
    assert result["statement"] is None
    assert result["items"] == []
    assert result["summary"]["amount_total"] == "0"


@pytest.mark.asyncio
async def test_storage_billing_overview_service_exports_statement_charges_csv() -> None:
    module = load_plugin_module("storage-billing", "services.reconciliation_service")
    models = load_plugin_module("storage-billing", "models")
    assert module is not None
    assert models is not None

    statement = models.StorageTenantStatement(
        tenant_id=66,
        billing_date=date(2026, 3, 23),
        status="generated",
        currency="CNY",
        amount_total=Decimal("0.450000"),
        charge_count=1,
        summary_json={},
    )
    statement.id = 31

    charge = models.StorageTenantDailyCharge(
        tenant_id=66,
        billing_date=date(2026, 3, 23),
        provider_code="tencent-cos",
        driver_code="tencent-cos",
        charge_basis="egress_traffic",
        usage_bytes=1024,
        amount_total=Decimal("0.450000"),
        currency="CNY",
        source_id=17,
        statement_id=31,
        details_json={
            "binding_ids": [9],
            "scope_values": ["tenant-66-bucket"],
            "item_count": 1,
        },
    )
    charge.id = 501

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
        billing_date=date(2026, 3, 23),
    )

    body = response.body.decode("utf-8-sig")
    assert response.media_type == "text/csv; charset=utf-8"
    assert "tenant_id" in body
    assert "tencent-cos" in body
    assert "generated" in body
