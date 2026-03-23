"""Tenant APIs for storage billing plugin. / 对象存储对账计费插件企业端接口。"""

from __future__ import annotations

from fastapi import Request

from ..periods import parse_optional_billing_date, parse_optional_period_type
from ..services.binding_service import StorageBillingBindingService
from ..services.reconciliation_service import StorageBillingOverviewService


async def get_current_statement(request: Request, ctx) -> dict:
    """Return current tenant statement snapshot. / 返回当前企业账单快照。"""
    period_type = parse_optional_period_type(request.query_params.get("period_type"))
    billing_date = parse_optional_billing_date(request.query_params.get("billing_date"))

    service = StorageBillingOverviewService.from_context(ctx)
    kwargs = {
        "tenant_id": ctx.get_current_tenant_id(),
        "billing_date": billing_date,
        "request_id": ctx.get_request_id(),
    }
    if period_type:
        kwargs["period_type"] = period_type
    return await service.build_tenant_statement(
        **kwargs,
    )


async def list_statements(request: Request, ctx) -> dict:
    """Return recent tenant statements. / 返回企业最近账单列表。"""
    raw_limit = request.query_params.get("limit", "30")
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        limit = 30

    service = StorageBillingOverviewService.from_context(ctx)
    return await service.list_tenant_statements(
        tenant_id=ctx.get_current_tenant_id(),
        limit=limit,
    )


async def list_statement_charges(request: Request, ctx) -> dict:
    """Return tenant charges for a billing date. / 返回企业指定账期明细。"""
    period_type = parse_optional_period_type(request.query_params.get("period_type"))
    billing_date = parse_optional_billing_date(request.query_params.get("billing_date"))

    service = StorageBillingOverviewService.from_context(ctx)
    kwargs = {
        "tenant_id": ctx.get_current_tenant_id(),
        "billing_date": billing_date,
    }
    if period_type:
        kwargs["period_type"] = period_type
    return await service.list_tenant_statement_charges(**kwargs)


async def export_statement_charges(request: Request, ctx):
    """Export tenant charges for a billing date. / 导出企业指定账期明细。"""
    period_type = parse_optional_period_type(request.query_params.get("period_type"))
    billing_date = parse_optional_billing_date(request.query_params.get("billing_date"))

    service = StorageBillingOverviewService.from_context(ctx)
    kwargs = {
        "tenant_id": ctx.get_current_tenant_id(),
        "billing_date": billing_date,
    }
    if period_type:
        kwargs["period_type"] = period_type
    return await service.export_tenant_statement_charges_csv(**kwargs)


async def get_prerequisites(request: Request, ctx) -> dict:
    _ = request
    service = StorageBillingBindingService.from_context(ctx)
    return await service.get_tenant_prerequisites(ctx.get_current_tenant_id())
