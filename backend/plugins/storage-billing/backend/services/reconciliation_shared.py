"""Shared helpers for storage billing reconciliation services.
/ 对象存储对账服务共享辅助能力。
"""

from __future__ import annotations

import csv
import inspect
import io
import json
from collections.abc import Awaitable, Callable, Mapping
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import quote

from fastapi.responses import Response

from ..constants import DEFAULT_OFFICIAL_BILLING_LAG_DAYS
from ..models import (
    StorageBillingPeriodTypeEnum,
    StorageBillingRun,
    StorageBillingRunStatusEnum,
    StorageProviderBillSource,
    StorageTenantBinding,
    StorageTenantDailyCharge,
    StorageTenantStatement,
)
from ..periods import (
    parse_optional_period_type,
    resolve_billing_date,
    resolve_billing_month,
)
from ..providers import BillingChargeItem

DAILY_RECONCILIATION_CRON = "0 3 * * *"
QINIU_MONTHLY_SETTLEMENT_CRON = "0 3 6 * *"
OFFICIAL_BILLING_LAG_DAYS = DEFAULT_OFFICIAL_BILLING_LAG_DAYS
PLUGIN_NAME = "storage-billing"
_SCOPE_MATCH_PRIORITY = {
    "bucket": 1,
    "domain": 2,
    "account": 3,
    "tag": 4,
}


class _ConfigContext:
    def __init__(
        self,
        config_loader: Callable[[], Awaitable[dict[str, Any]]],
        host_read: Any | None,
    ) -> None:
        self._config_loader = config_loader
        self.host = host_read

    async def get_config(self) -> dict[str, Any]:
        return await self._config_loader()


def _normalize_host_storage_context(
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    raw = dict(payload or {})
    raw_storage_config = raw.get("storage_config")
    storage_config = (
        dict(raw_storage_config or {})
        if isinstance(raw_storage_config, Mapping)
        else {}
    )
    options = storage_config.get("options")
    storage_config["options"] = (
        dict(options or {}) if isinstance(options, Mapping) else {}
    )
    return {
        "storage_mode": str(raw.get("storage_mode") or "platform").strip()
        or "platform",
        "apply_quota": bool(raw.get("apply_quota", True)),
        "storage_config": {
            "driver": str(storage_config.get("driver") or "").strip(),
            "root_path": storage_config.get("root_path"),
            "base_url": storage_config.get("base_url"),
            "options": dict(storage_config.get("options") or {}),
        },
    }


async def _read_platform_storage_context(host_read: Any | None) -> dict[str, Any]:
    if host_read is None:
        return _normalize_host_storage_context({})

    reader = getattr(host_read, "get_platform_storage_context", None)
    if not callable(reader):
        return _normalize_host_storage_context({})

    if inspect.iscoroutinefunction(reader):
        payload = await reader()
    else:
        payload = reader()
    if not isinstance(payload, Mapping):
        return _normalize_host_storage_context({})
    return _normalize_host_storage_context(payload)


def _serialize_decimal(value: Decimal | None) -> str:
    return str(value or Decimal("0"))


def _resolve_billing_date(
    raw_value: object | None,
    *,
    default_offset_days: int = 1,
) -> date:
    return resolve_billing_date(raw_value, default_offset_days=default_offset_days)


def _resolve_billing_month(raw_value: object | None) -> date:
    return resolve_billing_month(raw_value)


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _month_end(value: date) -> date:
    return (_month_start(value).replace(day=28) + timedelta(days=4)).replace(
        day=1
    ) - timedelta(days=1)


def _normalize_period_fields(
    *,
    billing_date: date,
    period_type: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> tuple[str, date, date, date]:
    normalized_type = (
        _stringify(period_type) or StorageBillingPeriodTypeEnum.DAILY.value
    )
    if normalized_type == StorageBillingPeriodTypeEnum.MONTHLY.value:
        normalized_start = _month_start(period_start or billing_date)
        normalized_end = _month_end(period_end or normalized_start)
        normalized_billing_date = _month_start(billing_date)
        return (
            StorageBillingPeriodTypeEnum.MONTHLY.value,
            normalized_billing_date,
            normalized_start,
            normalized_end,
        )

    normalized_billing_date = billing_date
    normalized_start = period_start or billing_date
    normalized_end = period_end or billing_date
    return (
        StorageBillingPeriodTypeEnum.DAILY.value,
        normalized_billing_date,
        normalized_start,
        normalized_end,
    )


def _period_label(period_type: str, period_start: date, period_end: date) -> str:
    if period_type == StorageBillingPeriodTypeEnum.MONTHLY.value:
        return period_start.strftime("%Y-%m")
    if period_start == period_end:
        return period_start.isoformat()
    return f"{period_start.isoformat()}~{period_end.isoformat()}"


def _get_plugin_db(ctx: object) -> Any:
    get_db = getattr(ctx, "get_db", None)
    if callable(get_db):
        if inspect.iscoroutinefunction(get_db):
            return getattr(get_db, "return_value", None)
        db = get_db()
        if inspect.isawaitable(db):
            return getattr(get_db, "return_value", None)
        return db

    db = getattr(ctx, "_db", None)
    if db is None:
        raise RuntimeError("Storage billing plugin requires plugin-owned DB access.")
    return db


def _stringify(value: Any) -> str:
    return str(value or "").strip()


def _to_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _serialize_charge_item(item: BillingChargeItem) -> dict[str, Any]:
    return {
        "charge_basis": item.charge_basis,
        "amount_total": _serialize_decimal(item.amount_total),
        "usage_bytes": item.usage_bytes,
        "currency": item.currency,
        "resource_id": item.resource_id,
        "resource_name": item.resource_name,
        "bucket_name": item.bucket_name,
        "domain_name": item.domain_name,
        "account_identifier": item.account_identifier,
        "tag_values": dict(item.tag_values or {}),
        "details_json": dict(item.details_json or {}),
    }


def _serialize_binding_audit(binding: StorageTenantBinding) -> dict[str, Any]:
    return {
        "id": binding.id,
        "tenant_id": binding.tenant_id,
        "provider_code": binding.provider_code,
        "scope_type": binding.scope_type,
        "scope_value": binding.scope_value,
    }


def _serialize_run(row: StorageBillingRun) -> dict[str, Any]:
    period_type, billing_date, period_start, period_end = _normalize_period_fields(
        billing_date=row.billing_date,
        period_type=getattr(row, "period_type", None),
        period_start=getattr(row, "period_start", None),
        period_end=getattr(row, "period_end", None),
    )
    return {
        "id": row.id,
        "run_key": row.run_key,
        "period_type": period_type,
        "billing_date": billing_date.isoformat(),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "period_label": _period_label(period_type, period_start, period_end),
        "trigger_type": row.trigger_type,
        "status": row.status,
        "provider_codes": list(row.provider_codes_json or []),
        "requested_scope": row.requested_scope_json or {},
        "summary": row.summary_json or {},
        "operator_id": row.operator_id,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "error_message": row.error_message,
    }


def _serialize_source(row: StorageProviderBillSource) -> dict[str, Any]:
    period_type, billing_date, period_start, period_end = _normalize_period_fields(
        billing_date=row.billing_date,
        period_type=getattr(row, "period_type", None),
        period_start=getattr(row, "period_start", None),
        period_end=getattr(row, "period_end", None),
    )
    allocation_summary = dict(
        dict(row.raw_payload_json or {}).get("allocation_summary") or {}
    )
    allocation_audit = dict(
        dict(row.raw_payload_json or {}).get("allocation_audit") or {}
    )
    return {
        "id": row.id,
        "run_id": row.run_id,
        "period_type": period_type,
        "billing_date": billing_date.isoformat(),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "period_label": _period_label(period_type, period_start, period_end),
        "provider_code": row.provider_code,
        "driver_code": row.driver_code,
        "source_status": row.source_status,
        "source_ref": row.source_ref,
        "currency": row.currency,
        "amount_total": _serialize_decimal(row.amount_total),
        "usage_bytes": row.usage_bytes,
        "raw_payload_json": row.raw_payload_json or {},
        "raw_payload": row.raw_payload_json or {},
        "allocation_summary": allocation_summary,
        "allocation_audit": allocation_audit,
        "error_message": row.error_message,
        "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
    }


def _serialize_statement(row: StorageTenantStatement) -> dict[str, Any]:
    period_type, billing_date, period_start, period_end = _normalize_period_fields(
        billing_date=row.billing_date,
        period_type=getattr(row, "period_type", None),
        period_start=getattr(row, "period_start", None),
        period_end=getattr(row, "period_end", None),
    )
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "period_type": period_type,
        "billing_date": billing_date.isoformat(),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "period_label": _period_label(period_type, period_start, period_end),
        "status": row.status,
        "amount_total": _serialize_decimal(row.amount_total),
        "currency": row.currency,
        "charge_count": row.charge_count,
        "summary": row.summary_json or {},
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
    }


def _serialize_daily_charge(
    row: StorageTenantDailyCharge,
    *,
    source: StorageProviderBillSource | None = None,
) -> dict[str, Any]:
    details = dict(row.details_json or {})
    period_type, billing_date, period_start, period_end = _normalize_period_fields(
        billing_date=row.billing_date,
        period_type=getattr(row, "period_type", None),
        period_start=getattr(row, "period_start", None),
        period_end=getattr(row, "period_end", None),
    )
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "period_type": period_type,
        "billing_date": billing_date.isoformat(),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "period_label": _period_label(period_type, period_start, period_end),
        "provider_code": row.provider_code,
        "driver_code": row.driver_code,
        "charge_basis": row.charge_basis,
        "usage_bytes": row.usage_bytes,
        "amount_total": _serialize_decimal(row.amount_total),
        "currency": row.currency,
        "source_id": row.source_id,
        "source_key": source.source_key if source is not None else None,
        "source_ref": source.source_ref if source is not None else None,
        "source_status": source.source_status if source is not None else None,
        "statement_id": row.statement_id,
        "details": details,
        "binding_ids": details.get("binding_ids") or [],
        "scope_values": details.get("scope_values") or [],
        "item_count": details.get("item_count") or len(details.get("items") or []),
        "details_json": details,
    }


def _summarize_daily_charges(rows: list[StorageTenantDailyCharge]) -> dict[str, Any]:
    amount_total = Decimal("0")
    usage_total = 0
    provider_codes: set[str] = set()
    tenant_ids: set[int] = set()
    source_ids: set[int] = set()
    provider_totals: dict[str, dict[str, Any]] = {}
    charge_basis_totals: dict[str, dict[str, Any]] = {}

    for row in rows:
        row_amount = row.amount_total or Decimal("0")
        row_usage = row.usage_bytes or 0
        provider_code = _stringify(row.provider_code)
        charge_basis = _stringify(row.charge_basis)

        amount_total += row_amount
        usage_total += row_usage
        provider_codes.add(provider_code)
        if row.tenant_id is not None:
            tenant_ids.add(int(row.tenant_id))
        if row.source_id is not None:
            source_ids.add(int(row.source_id))

        if provider_code:
            provider_summary = provider_totals.setdefault(
                provider_code,
                {
                    "provider_code": provider_code,
                    "row_count": 0,
                    "usage_bytes": 0,
                    "amount_total": Decimal("0"),
                },
            )
            provider_summary["row_count"] += 1
            provider_summary["usage_bytes"] += row_usage
            provider_summary["amount_total"] += row_amount

        if charge_basis:
            charge_basis_summary = charge_basis_totals.setdefault(
                charge_basis,
                {
                    "charge_basis": charge_basis,
                    "row_count": 0,
                    "usage_bytes": 0,
                    "amount_total": Decimal("0"),
                },
            )
            charge_basis_summary["row_count"] += 1
            charge_basis_summary["usage_bytes"] += row_usage
            charge_basis_summary["amount_total"] += row_amount

    def _serialize_breakdown(
        items: dict[str, dict[str, Any]],
        key: str,
    ) -> list[dict[str, Any]]:
        serialized: list[dict[str, Any]] = []
        for item in items.values():
            serialized.append(
                {
                    key: item[key],
                    "row_count": item["row_count"],
                    "usage_bytes": item["usage_bytes"],
                    "amount_total": _serialize_decimal(item["amount_total"]),
                }
            )
        serialized.sort(
            key=lambda item: (
                -float(item["amount_total"]),
                -int(item["usage_bytes"]),
                str(item[key]),
            )
        )
        return serialized

    return {
        "row_count": len(rows),
        "amount_total": _serialize_decimal(amount_total),
        "total_usage_bytes": usage_total,
        "usage_bytes_total": usage_total,
        "provider_totals": _serialize_breakdown(
            provider_totals,
            "provider_code",
        ),
        "charge_basis_totals": _serialize_breakdown(
            charge_basis_totals,
            "charge_basis",
        ),
        "provider_codes": sorted(code for code in provider_codes if code),
        "tenant_count": len(tenant_ids),
        "source_count": len(source_ids),
    }


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (date,)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return _serialize_decimal(value)
    return str(value)


def _build_csv_response(
    *,
    filename: str,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> Response:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})
    content = buffer.getvalue()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": _content_disposition_attachment(filename),
        },
    )


def _serialize_daily_charge_csv_row(
    row: StorageTenantDailyCharge,
    *,
    source: StorageProviderBillSource | None = None,
) -> dict[str, Any]:
    period_type, billing_date, period_start, period_end = _normalize_period_fields(
        billing_date=row.billing_date,
        period_type=getattr(row, "period_type", None),
        period_start=getattr(row, "period_start", None),
        period_end=getattr(row, "period_end", None),
    )
    payload = _serialize_daily_charge(row, source=source)
    return {
        "id": payload["id"],
        "run_id": source.run_id if source is not None else None,
        "period_type": period_type,
        "billing_date": billing_date.isoformat(),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "period_label": _period_label(period_type, period_start, period_end),
        "tenant_id": payload["tenant_id"],
        "provider_code": payload["provider_code"],
        "driver_code": payload["driver_code"],
        "charge_basis": payload["charge_basis"],
        "usage_bytes": payload["usage_bytes"],
        "amount_total": payload["amount_total"],
        "currency": payload["currency"],
        "source_id": payload["source_id"],
        "source_key": payload["source_key"],
        "source_ref": payload["source_ref"],
        "source_status": payload["source_status"],
        "statement_id": payload["statement_id"],
        "binding_ids": json.dumps(payload["binding_ids"], ensure_ascii=False),
        "scope_values": json.dumps(payload["scope_values"], ensure_ascii=False),
        "item_count": payload["item_count"],
        "details_json": json.dumps(payload["details_json"], ensure_ascii=False),
    }


def _serialize_allocation_row_snapshot(
    *,
    tenant_id: int,
    charge_basis: str,
    currency: str,
    usage_bytes: int,
    amount_total: Decimal,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "charge_basis": charge_basis,
        "currency": currency,
        "usage_bytes": usage_bytes,
        "amount_total": _serialize_decimal(amount_total),
        "details": details,
    }


def _hydrate_snapshot_charge_row(
    source: StorageProviderBillSource,
    payload: Mapping[str, Any],
) -> StorageTenantDailyCharge:
    period_type, billing_date, period_start, period_end = _normalize_period_fields(
        billing_date=source.billing_date,
        period_type=payload.get("period_type"),
        period_start=payload.get("period_start"),
        period_end=payload.get("period_end"),
    )
    details = dict(payload.get("details") or {})
    return StorageTenantDailyCharge(
        tenant_id=int(payload.get("tenant_id") or 0),
        period_type=period_type,
        billing_date=billing_date,
        period_start=period_start,
        period_end=period_end,
        provider_code=source.provider_code,
        driver_code=source.driver_code,
        charge_basis=_stringify(payload.get("charge_basis")),
        usage_bytes=int(payload.get("usage_bytes") or 0),
        amount_total=Decimal(str(payload.get("amount_total") or "0")),
        currency=_stringify(payload.get("currency")) or source.currency,
        source_id=source.id,
        statement_id=None,
        details_json=details,
    )


def _sort_charge_rows(
    rows: list[StorageTenantDailyCharge],
) -> list[StorageTenantDailyCharge]:
    return sorted(
        rows,
        key=lambda item: (
            -float(item.amount_total or Decimal("0")),
            -(item.usage_bytes or 0),
            item.tenant_id or 0,
            _stringify(item.provider_code),
            _stringify(item.charge_basis),
            item.id or 0,
        ),
    )


def _content_disposition_attachment(filename: str) -> str:
    try:
        filename.encode("ascii")
        return f'attachment; filename="{filename}"'
    except UnicodeEncodeError:
        encoded = quote(filename, safe="")
        return f"attachment; filename=\"document\"; filename*=UTF-8''{encoded}"


def _aggregate_run_status(statuses: list[str]) -> str:
    if not statuses:
        return StorageBillingRunStatusEnum.SKIPPED.value
    if StorageBillingRunStatusEnum.FAILED.value in statuses:
        return StorageBillingRunStatusEnum.FAILED.value
    if StorageBillingRunStatusEnum.COMPLETED_WITH_GAPS.value in statuses:
        return StorageBillingRunStatusEnum.COMPLETED_WITH_GAPS.value
    if StorageBillingRunStatusEnum.COMPLETED.value in statuses:
        return StorageBillingRunStatusEnum.COMPLETED.value
    return StorageBillingRunStatusEnum.SKIPPED.value


__all__ = [
    "DAILY_RECONCILIATION_CRON",
    "OFFICIAL_BILLING_LAG_DAYS",
    "PLUGIN_NAME",
    "QINIU_MONTHLY_SETTLEMENT_CRON",
    "_ConfigContext",
    "_SCOPE_MATCH_PRIORITY",
    "_aggregate_run_status",
    "_build_csv_response",
    "_content_disposition_attachment",
    "_csv_value",
    "_get_plugin_db",
    "_hydrate_snapshot_charge_row",
    "_month_end",
    "_month_start",
    "_normalize_host_storage_context",
    "_normalize_period_fields",
    "_period_label",
    "_read_platform_storage_context",
    "_resolve_billing_date",
    "_resolve_billing_month",
    "_serialize_allocation_row_snapshot",
    "_serialize_binding_audit",
    "_serialize_charge_item",
    "_serialize_daily_charge",
    "_serialize_daily_charge_csv_row",
    "_serialize_decimal",
    "_serialize_run",
    "_serialize_source",
    "_serialize_statement",
    "_sort_charge_rows",
    "_stringify",
    "_summarize_daily_charges",
    "_to_bool",
    "parse_optional_period_type",
]
