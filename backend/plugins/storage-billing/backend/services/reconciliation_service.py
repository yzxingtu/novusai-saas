"""Storage billing services. / 对象存储对账计费服务。"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Awaitable, Callable, Mapping
from datetime import date, timedelta
from decimal import Decimal
import io
import inspect
import json
from typing import Any
from urllib.parse import quote
from fastapi.responses import Response
from sqlalchemy import desc, func, select

from app.core.base_model import utc_now
from app.core.i18n import _
from app.core.logging import get_logger
from app.exceptions import BusinessException, NotFoundException
from app.models.system.plugin import Plugin
from app.plugins.crypto import decrypt_plugin_config

from ..constants import (
    DEFAULT_OFFICIAL_BILLING_LAG_DAYS,
    EXCLUDED_DRIVERS,
    PROVIDER_DAILY_RECONCILIATION_RULES,
    SUPPORTED_CLOUD_DRIVERS,
    get_provider_bill_source_capability,
    get_provider_daily_reconciliation_rule,
    get_provider_implemented_bill_sources,
)
from ..models import (
    StorageBillingPeriodTypeEnum,
    StorageBillingRun,
    StorageBillingRunStatusEnum,
    StorageBillingSourceStatusEnum,
    StorageBillingStatementStatusEnum,
    StorageBillingValidationStatusEnum,
    StorageProviderBillSource,
    StorageTenantBinding,
    StorageTenantDailyCharge,
    StorageTenantStatement,
)
from ..providers import (
    BillingChargeItem,
    BillingFetchRequest,
    BillingFetchResult,
    get_provider_adapter,
)
from ..periods import parse_optional_period_type, resolve_billing_date, resolve_billing_month
from .profile_service import StorageBillingProviderProfileService

DAILY_RECONCILIATION_CRON = "0 3 * * *"
QINIU_MONTHLY_SETTLEMENT_CRON = "0 3 6 * *"
OFFICIAL_BILLING_LAG_DAYS = DEFAULT_OFFICIAL_BILLING_LAG_DAYS
PLUGIN_NAME = "storage-billing"
logger = get_logger(__name__)
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


def _normalize_host_storage_context(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(payload or {})
    raw_storage_config = raw.get("storage_config")
    storage_config = dict(raw_storage_config or {}) if isinstance(raw_storage_config, Mapping) else {}
    options = storage_config.get("options")
    storage_config["options"] = dict(options or {}) if isinstance(options, Mapping) else {}
    return {
        "storage_mode": str(raw.get("storage_mode") or "platform").strip() or "platform",
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
    return (_month_start(value).replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(
        days=1
    )


def _normalize_period_fields(
    *,
    billing_date: date,
    period_type: str | None = None,
    period_start: date | None = None,
    period_end: date | None = None,
) -> tuple[str, date, date, date]:
    normalized_type = _stringify(period_type) or StorageBillingPeriodTypeEnum.DAILY.value
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
        "requested_scope": dict(row.requested_scope_json or {}),
        "summary": dict(row.summary_json or {}),
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
    return {
        "id": row.id,
        "source_key": row.source_key,
        "run_id": row.run_id,
        "provider_code": row.provider_code,
        "driver_code": row.driver_code,
        "period_type": period_type,
        "billing_date": billing_date.isoformat(),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "period_label": _period_label(period_type, period_start, period_end),
        "source_status": row.source_status,
        "source_ref": row.source_ref,
        "currency": row.currency,
        "amount_total": _serialize_decimal(row.amount_total),
        "usage_bytes": row.usage_bytes,
        "fetched_at": row.fetched_at.isoformat() if row.fetched_at else None,
        "error_message": row.error_message,
        "raw_payload_json": dict(row.raw_payload_json or {}),
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
        "currency": row.currency,
        "amount_total": _serialize_decimal(row.amount_total),
        "charge_count": row.charge_count,
        "summary": dict(row.summary_json or {}),
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "published_at": row.published_at.isoformat() if row.published_at else None,
    }


def _serialize_daily_charge(
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
    payload = {
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
        "statement_id": row.statement_id,
        "details": dict(row.details_json or {}),
    }
    if source is not None:
        payload.update(
            {
                "run_id": source.run_id,
                "source_key": source.source_key,
                "source_ref": source.source_ref,
                "source_status": source.source_status,
            }
        )
    return payload


def _summarize_daily_charges(rows: list[StorageTenantDailyCharge]) -> dict[str, Any]:
    amount_total = Decimal("0")
    usage_total = 0
    provider_totals: dict[tuple[str, str], dict[str, Any]] = {}
    charge_basis_totals: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        amount_total += row.amount_total or Decimal("0")
        usage_total += row.usage_bytes or 0

        provider_key = (row.provider_code, row.currency)
        provider_entry = provider_totals.setdefault(
            provider_key,
            {
                "provider_code": row.provider_code,
                "currency": row.currency,
                "amount_total": Decimal("0"),
                "usage_bytes": 0,
                "charge_count": 0,
            },
        )
        provider_entry["amount_total"] += row.amount_total or Decimal("0")
        provider_entry["usage_bytes"] += row.usage_bytes or 0
        provider_entry["charge_count"] += 1

        basis_key = (row.charge_basis, row.currency)
        basis_entry = charge_basis_totals.setdefault(
            basis_key,
            {
                "charge_basis": row.charge_basis,
                "currency": row.currency,
                "amount_total": Decimal("0"),
                "usage_bytes": 0,
                "charge_count": 0,
            },
        )
        basis_entry["amount_total"] += row.amount_total or Decimal("0")
        basis_entry["usage_bytes"] += row.usage_bytes or 0
        basis_entry["charge_count"] += 1

    return {
        "amount_total": _serialize_decimal(amount_total),
        "total_usage_bytes": usage_total,
        "provider_totals": [
            {
                **item,
                "amount_total": _serialize_decimal(item["amount_total"]),
            }
            for item in sorted(
                provider_totals.values(),
                key=lambda value: (-value["usage_bytes"], value["provider_code"]),
            )
        ],
        "charge_basis_totals": [
            {
                **item,
                "amount_total": _serialize_decimal(item["amount_total"]),
            }
            for item in sorted(
                charge_basis_totals.values(),
                key=lambda value: (-value["usage_bytes"], value["charge_basis"]),
            )
        ],
    }


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return _serialize_decimal(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _build_csv_response(
    *,
    filename: str,
    fieldnames: list[str],
    rows: list[dict[str, Any]],
) -> Response:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_value(row.get(field)) for field in fieldnames})
    csv_bytes = output.getvalue().encode("utf-8-sig")
    return Response(
        content=csv_bytes,
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
    details = dict(row.details_json or {})
    period_type, billing_date, period_start, period_end = _normalize_period_fields(
        billing_date=row.billing_date,
        period_type=getattr(row, "period_type", None),
        period_start=getattr(row, "period_start", None),
        period_end=getattr(row, "period_end", None),
    )
    return {
        "id": row.id,
        "run_id": source.run_id if source is not None else "",
        "period_type": period_type,
        "billing_date": billing_date.isoformat(),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "period_label": _period_label(period_type, period_start, period_end),
        "tenant_id": row.tenant_id,
        "provider_code": row.provider_code,
        "driver_code": row.driver_code,
        "charge_basis": row.charge_basis,
        "usage_bytes": row.usage_bytes,
        "amount_total": _serialize_decimal(row.amount_total),
        "currency": row.currency,
        "source_id": row.source_id,
        "source_key": source.source_key if source is not None else "",
        "source_ref": source.source_ref if source is not None else "",
        "source_status": source.source_status if source is not None else "",
        "statement_id": row.statement_id,
        "binding_ids": ",".join(str(item) for item in (details.get("binding_ids") or [])),
        "scope_values": ",".join(str(item) for item in (details.get("scope_values") or [])),
        "item_count": details.get("item_count", ""),
        "details_json": details,
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
        "details": dict(details or {}),
    }


def _hydrate_snapshot_charge_row(
    source: StorageProviderBillSource,
    payload: Mapping[str, Any],
) -> StorageTenantDailyCharge:
    period_type, billing_date, period_start, period_end = _normalize_period_fields(
        billing_date=source.billing_date,
        period_type=getattr(source, "period_type", None),
        period_start=getattr(source, "period_start", None),
        period_end=getattr(source, "period_end", None),
    )
    row = StorageTenantDailyCharge(
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
        details_json=dict(payload.get("details") or {}),
    )
    row.id = None
    row.statement_id = None
    return row


def _sort_charge_rows(rows: list[StorageTenantDailyCharge]) -> list[StorageTenantDailyCharge]:
    return sorted(
        rows,
        key=lambda row: (
            -(row.amount_total or Decimal("0")),
            -(row.usage_bytes or 0),
            row.tenant_id,
            row.provider_code,
            row.charge_basis,
            row.id or 0,
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


class StorageBillingOverviewService:
    """Read-only overview helpers. / 只读概览服务。"""

    def __init__(self, db: Any | None, host_read: Any | None = None) -> None:
        self._db = db
        self._host_read = host_read

    @classmethod
    def from_context(cls, ctx) -> "StorageBillingOverviewService":
        return cls(
            db=_get_plugin_db(ctx),
            host_read=getattr(ctx, "host", None),
        )

    async def _load_tenant_statement(
        self,
        *,
        tenant_id: int | None,
        billing_date: date | None = None,
        period_type: str | None = None,
    ) -> StorageTenantStatement | None:
        if self._db is None or tenant_id is None:
            return None

        normalized_period_type = parse_optional_period_type(period_type)
        stmt = select(StorageTenantStatement).where(
            StorageTenantStatement.tenant_id == tenant_id,
            StorageTenantStatement.is_deleted.is_(False),
        )
        if billing_date is not None:
            stmt = stmt.where(StorageTenantStatement.billing_date == billing_date)
        if normalized_period_type:
            stmt = stmt.where(StorageTenantStatement.period_type == normalized_period_type)
        stmt = stmt.order_by(
            desc(StorageTenantStatement.period_end),
            desc(StorageTenantStatement.billing_date),
            desc(StorageTenantStatement.id),
        )
        return (await self._db.execute(stmt.limit(1))).scalar_one_or_none()

    async def _load_tenant_daily_charge_rows(
        self,
        *,
        tenant_id: int | None,
        billing_date: date | None,
        period_type: str | None = None,
    ) -> list[StorageTenantDailyCharge]:
        if self._db is None or tenant_id is None or billing_date is None:
            return []
        normalized_period_type = parse_optional_period_type(period_type)
        return (
            await self._db.execute(
                select(StorageTenantDailyCharge)
                .where(
                    StorageTenantDailyCharge.tenant_id == tenant_id,
                    StorageTenantDailyCharge.billing_date == billing_date,
                    StorageTenantDailyCharge.period_type
                    == (
                        normalized_period_type or StorageBillingPeriodTypeEnum.DAILY.value
                    ),
                    StorageTenantDailyCharge.is_deleted.is_(False),
                )
                .order_by(
                    desc(StorageTenantDailyCharge.amount_total),
                    desc(StorageTenantDailyCharge.usage_bytes),
                    StorageTenantDailyCharge.provider_code,
                    StorageTenantDailyCharge.charge_basis,
                    StorageTenantDailyCharge.id,
                )
            )
        ).scalars().all()

    async def _load_plugin_config(self) -> dict[str, Any]:
        if self._db is None:
            return {}
        result = await self._db.execute(
            select(Plugin.config, Plugin.manifest).where(
                Plugin.name == PLUGIN_NAME,
                Plugin.is_deleted.is_(False),
            )
        )
        row = result.one_or_none()
        if row is None:
            return {}

        config = row[0] or {}
        manifest = row[1] or {}
        config_schema = manifest.get("config_schema") if isinstance(manifest, dict) else None
        if config_schema:
            config = decrypt_plugin_config(config, config_schema)
        return dict(config or {})

    async def build_admin_overview(self) -> dict[str, Any]:
        enabled_drivers = []
        related_plugins = []
        platform_storage_context = _normalize_host_storage_context({})
        if self._host_read is not None:
            enabled_drivers = await self._host_read.get_enabled_storage_drivers()
            related_plugins = await self._host_read.get_plugin_runtime_summary(
                ["storage-billing", "qiniu-kodo", "aliyun-oss", "tencent-cos"]
            )
            platform_storage_context = await _read_platform_storage_context(self._host_read)

        active_storage_driver = str(
            dict(platform_storage_context.get("storage_config") or {}).get("driver") or ""
        ).strip()

        latest_runs: list[dict[str, Any]] = []
        statement_total = 0
        charge_total = 0
        binding_total = 0
        provider_profiles: dict[str, Any] = {"providers": {}}
        if self._db is not None:
            latest_runs_result = await self._db.execute(
                select(StorageBillingRun)
                .where(StorageBillingRun.is_deleted.is_(False))
                .order_by(
                    desc(StorageBillingRun.period_end),
                    desc(StorageBillingRun.billing_date),
                    desc(StorageBillingRun.id),
                )
                .limit(10)
            )
            latest_runs = [_serialize_run(item) for item in latest_runs_result.scalars().all()]
            statement_total = int(
                (
                    await self._db.execute(
                        select(func.count(StorageTenantStatement.id)).where(
                            StorageTenantStatement.is_deleted.is_(False)
                        )
                    )
                ).scalar_one()
                or 0
            )
            charge_total = int(
                (
                    await self._db.execute(
                        select(func.count(StorageTenantDailyCharge.id)).where(
                            StorageTenantDailyCharge.is_deleted.is_(False)
                        )
                    )
                ).scalar_one()
                or 0
            )
            binding_total = int(
                (
                    await self._db.execute(
                        select(func.count(StorageTenantBinding.id)).where(
                            StorageTenantBinding.is_deleted.is_(False)
                        )
                    )
                ).scalar_one()
                or 0
            )
            profile_service = StorageBillingProviderProfileService(
                _ConfigContext(self._load_plugin_config, self._host_read),
                host_read=self._host_read,
            )
            try:
                provider_profiles = await profile_service.list_provider_profiles()
            except Exception:
                provider_profiles = {"providers": {}}

        provider_capabilities = {
            provider: {
                "settlement_mode": dict(profile).get("settlement_mode"),
                "settlement_cycle": dict(profile).get("settlement_cycle"),
                "strict_reconciliation_supported": dict(profile).get(
                    "strict_reconciliation_supported"
                ),
                "manual_pull_supported": dict(profile).get("manual_pull_supported"),
                "scheduled_daily_supported": dict(profile).get("scheduled_daily_supported"),
                "supported_period_types": list(
                    dict(profile).get("supported_period_types") or []
                ),
                "official_billing_lag_days": dict(profile).get("official_billing_lag_days"),
                "official_target_rule": dict(profile).get("official_target_rule"),
                "capability_message": dict(profile).get("capability_message"),
            }
            for provider, profile in dict(provider_profiles.get("providers") or {}).items()
        }
        daily_provider_rules = {
            provider: {
                **get_provider_daily_reconciliation_rule(provider),
                "cron": DAILY_RECONCILIATION_CRON,
                "local_time": "03:00",
            }
            for provider in PROVIDER_DAILY_RECONCILIATION_RULES
        }

        return {
            "mode": "official_bill_reconciliation",
            "billable_drivers": SUPPORTED_CLOUD_DRIVERS,
            "excluded_drivers": EXCLUDED_DRIVERS,
            "reconciliation_schedule": {
                "cron": DAILY_RECONCILIATION_CRON,
                "local_time": "03:00",
                "official_billing_lag_days": None,
                "official_target_rule": "per-provider",
                "provider_rules": daily_provider_rules,
            },
            "provider_schedules": {
                "daily": {
                    "cron": DAILY_RECONCILIATION_CRON,
                    "local_time": "03:00",
                    "provider_codes": ["aliyun-oss", "tencent-cos"],
                    "provider_rules": daily_provider_rules,
                },
                "qiniu_monthly": {
                    "cron": QINIU_MONTHLY_SETTLEMENT_CRON,
                    "local_time": "03:00",
                    "provider_codes": ["qiniu-kodo"],
                },
            },
            "provider_capabilities": provider_capabilities,
            "host_snapshot": {
                "enabled_storage_drivers": enabled_drivers,
                "active_storage_driver": active_storage_driver or None,
                "platform_storage_context": platform_storage_context,
                "related_plugins": related_plugins,
            },
            "ledger_snapshot": {
                "latest_runs": latest_runs,
                "statement_total": statement_total,
                "daily_charge_total": charge_total,
                "binding_total": binding_total,
            },
            "status": "m2_tencent_collector",
        }

    async def build_tenant_statement(
        self,
        *,
        tenant_id: int | None,
        billing_date: date | None = None,
        period_type: str | None = None,
        request_id: str = "",
    ) -> dict[str, Any]:
        normalized_period_type = parse_optional_period_type(period_type)
        statement = await self._load_tenant_statement(
            tenant_id=tenant_id,
            billing_date=billing_date,
            period_type=normalized_period_type,
        )

        return {
            "tenant_id": tenant_id,
            "request_id": request_id,
            "billable_drivers": SUPPORTED_CLOUD_DRIVERS,
            "excluded_drivers": EXCLUDED_DRIVERS,
            "charge_local_storage": False,
            "statement": _serialize_statement(statement) if statement else None,
            "statement_status": statement.status if statement else "pending_provider_ingestion",
            "message": (
                "No settled tenant statement is available yet."
                if statement is None
                else "Tenant statement loaded from plugin-owned ledger."
            ),
        }

    async def list_tenant_statements(
        self,
        *,
        tenant_id: int | None,
        limit: int = 30,
    ) -> dict[str, Any]:
        safe_limit = max(1, min(100, int(limit)))
        if self._db is None or tenant_id is None:
            return {
                "tenant_id": tenant_id,
                "items": [],
                "total": 0,
                "limit": safe_limit,
            }

        rows = (
            await self._db.execute(
                select(StorageTenantStatement)
                .where(
                    StorageTenantStatement.tenant_id == tenant_id,
                    StorageTenantStatement.is_deleted.is_(False),
                )
                .order_by(
                    desc(StorageTenantStatement.period_end),
                    desc(StorageTenantStatement.billing_date),
                    desc(StorageTenantStatement.id),
                )
                .limit(safe_limit)
            )
        ).scalars().all()
        return {
            "tenant_id": tenant_id,
            "items": [_serialize_statement(item) for item in rows],
            "total": len(rows),
            "limit": safe_limit,
        }

    async def list_tenant_statement_charges(
        self,
        *,
        tenant_id: int | None,
        billing_date: date | None = None,
        period_type: str | None = None,
    ) -> dict[str, Any]:
        normalized_period_type = parse_optional_period_type(period_type)
        statement = await self._load_tenant_statement(
            tenant_id=tenant_id,
            billing_date=billing_date,
            period_type=normalized_period_type,
        )
        resolved_billing_date = billing_date or (
            statement.billing_date if statement is not None else None
        )

        if self._db is None or tenant_id is None or resolved_billing_date is None:
            return {
                "tenant_id": tenant_id,
                "period_type": normalized_period_type or "",
                "billing_date": resolved_billing_date.isoformat()
                if resolved_billing_date is not None
                else None,
                "statement": _serialize_statement(statement) if statement else None,
                "items": [],
                "total": 0,
                "summary": _summarize_daily_charges([]),
                "message": "No settled tenant statement is available yet.",
            }

        rows = await self._load_tenant_daily_charge_rows(
            tenant_id=tenant_id,
            billing_date=resolved_billing_date,
            period_type=statement.period_type
            if statement is not None
            else normalized_period_type,
        )
        return {
            "tenant_id": tenant_id,
            "period_type": statement.period_type if statement is not None else normalized_period_type,
            "billing_date": resolved_billing_date.isoformat(),
            "statement": _serialize_statement(statement) if statement else None,
            "items": [_serialize_daily_charge(item) for item in rows],
            "total": len(rows),
            "summary": _summarize_daily_charges(rows),
            "message": (
                "Tenant charge rows loaded from plugin-owned ledger."
                if rows
                else "No tenant charge rows were generated for this billing date."
            ),
        }

    async def export_tenant_statement_charges_csv(
        self,
        *,
        tenant_id: int | None,
        billing_date: date | None = None,
        period_type: str | None = None,
    ) -> Response:
        normalized_period_type = parse_optional_period_type(period_type)
        result = await self.list_tenant_statement_charges(
            tenant_id=tenant_id,
            billing_date=billing_date,
            period_type=normalized_period_type,
        )
        resolved_billing_date = result.get("billing_date") or "latest"
        parsed_billing_date = (
            date.fromisoformat(resolved_billing_date)
            if isinstance(resolved_billing_date, str) and resolved_billing_date != "latest"
            else None
        )
        charge_rows = await self._load_tenant_daily_charge_rows(
            tenant_id=tenant_id,
            billing_date=parsed_billing_date,
            period_type=_stringify(result.get("period_type")),
        )
        rows = [
            {
                "statement_status": result.get("statement", {}).get("status")
                if isinstance(result.get("statement"), dict)
                else "",
                "period_type": _stringify(result.get("period_type")),
                **_serialize_daily_charge_csv_row(row),
            }
            for row in charge_rows
        ]
        return _build_csv_response(
            filename=f"storage_billing_tenant_{tenant_id or 'unknown'}_{resolved_billing_date}_charges.csv",
            fieldnames=[
                "id",
                "period_type",
                "billing_date",
                "tenant_id",
                "statement_status",
                "provider_code",
                "driver_code",
                "charge_basis",
                "usage_bytes",
                "amount_total",
                "currency",
                "source_id",
                "statement_id",
                "binding_ids",
                "scope_values",
                "item_count",
                "details_json",
            ],
            rows=rows,
        )


class StorageBillingReconciliationService:
    """Reconciliation operations backed by plugin-owned tables.
    / 基于插件自有表的对账服务。
    """

    def __init__(
        self,
        db: Any,
        *,
        host_read: Any | None = None,
        operator_id: int | None = None,
    ) -> None:
        self._db = db
        self._host_read = host_read
        self._operator_id = operator_id
        self._profile_service = StorageBillingProviderProfileService(
            _ConfigContext(self._load_plugin_config, host_read),
            host_read=host_read,
        )

    @classmethod
    def from_context(cls, ctx) -> "StorageBillingReconciliationService":
        return cls(
            db=_get_plugin_db(ctx),
            host_read=getattr(ctx, "host", None),
            operator_id=getattr(ctx, "get_current_user_id", lambda: None)(),
        )

    async def trigger_manual_run(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        request_payload = dict(payload or {})
        if request_payload.get("billing_date") in {None, ""}:
            return await self._run_provider_specific_daily_reconciliation(
                trigger_type="manual",
                requested_scope=request_payload,
                provider_codes=request_payload.get("provider_codes"),
            )
        billing_date = _resolve_billing_date(
            request_payload.get("billing_date"),
            default_offset_days=OFFICIAL_BILLING_LAG_DAYS,
        )
        return await self._execute_reconciliation(
            billing_date=billing_date,
            period_type=StorageBillingPeriodTypeEnum.DAILY.value,
            period_start=billing_date,
            period_end=billing_date,
            trigger_type="manual",
            requested_scope=request_payload,
            provider_codes=request_payload.get("provider_codes"),
        )

    async def run_daily_reconciliation(self, billing_date: date | None = None) -> dict[str, Any]:
        if billing_date is None:
            return await self._run_provider_specific_daily_reconciliation(
                trigger_type="schedule",
                requested_scope={"job": "daily_reconciliation"},
                provider_codes=None,
            )

        target_date = _resolve_billing_date(
            billing_date,
            default_offset_days=OFFICIAL_BILLING_LAG_DAYS,
        )
        return await self._execute_reconciliation(
            billing_date=target_date,
            period_type=StorageBillingPeriodTypeEnum.DAILY.value,
            period_start=target_date,
            period_end=target_date,
            trigger_type="schedule",
            requested_scope={
                "job": "daily_reconciliation",
                "official_billing_lag_days": OFFICIAL_BILLING_LAG_DAYS,
                "official_target_rule": f"D-{OFFICIAL_BILLING_LAG_DAYS}",
            },
        )

    async def _run_provider_specific_daily_reconciliation(
        self,
        *,
        trigger_type: str,
        requested_scope: dict[str, Any],
        provider_codes: list[str] | str | None,
    ) -> dict[str, Any]:
        billable_drivers = await self._get_billable_drivers(
            period_type=StorageBillingPeriodTypeEnum.DAILY.value,
            provider_codes=provider_codes,
        )
        if not billable_drivers:
            return {
                "run": {
                    "id": None,
                    "status": StorageBillingRunStatusEnum.SKIPPED.value,
                    "trigger_type": trigger_type,
                    "period_type": StorageBillingPeriodTypeEnum.DAILY.value,
                    "provider_codes": [],
                    "requested_scope": dict(requested_scope or {}),
                    "summary": {
                        "driver_count": 0,
                        "run_count": 0,
                        "statement_count": 0,
                        "source_status_counts": {},
                        "providers": [],
                        "excluded_drivers": EXCLUDED_DRIVERS,
                    },
                },
                "runs": [],
                "sources": [],
                "billable_drivers": [],
                "excluded_drivers": EXCLUDED_DRIVERS,
                "schedule": DAILY_RECONCILIATION_CRON,
                "provider_plans": [],
            }

        if len(billable_drivers) == 1:
            provider_code = _stringify(billable_drivers[0].get("code"))
            rule = get_provider_daily_reconciliation_rule(provider_code)
            lag_days = int(rule.get("official_billing_lag_days") or OFFICIAL_BILLING_LAG_DAYS)
            target_date = _resolve_billing_date(
                None,
                default_offset_days=lag_days,
            )
            return await self._execute_reconciliation(
                billing_date=target_date,
                period_type=StorageBillingPeriodTypeEnum.DAILY.value,
                period_start=target_date,
                period_end=target_date,
                trigger_type=trigger_type,
                requested_scope={
                    **dict(requested_scope or {}),
                    "provider_codes": [provider_code],
                    "scheduled_provider_code": provider_code,
                    "official_billing_lag_days": lag_days,
                    "official_target_rule": _stringify(rule.get("official_target_rule"))
                    or f"D-{lag_days}",
                },
                provider_codes=[provider_code],
            )

        provider_plans: list[dict[str, Any]] = []
        runs: list[dict[str, Any]] = []
        sources: list[dict[str, Any]] = []
        provider_summaries: list[dict[str, Any]] = []
        status_counter: Counter[str] = Counter()
        statement_count = 0
        aggregate_billable_drivers: list[dict[str, Any]] = []

        for driver in billable_drivers:
            provider_code = _stringify(driver.get("code"))
            if not provider_code:
                continue
            rule = get_provider_daily_reconciliation_rule(provider_code)
            lag_days = int(rule.get("official_billing_lag_days") or OFFICIAL_BILLING_LAG_DAYS)
            target_date = _resolve_billing_date(
                None,
                default_offset_days=lag_days,
            )
            provider_plans.append(
                {
                    "provider_code": provider_code,
                    "billing_date": target_date.isoformat(),
                    "official_billing_lag_days": lag_days,
                    "official_target_rule": _stringify(rule.get("official_target_rule"))
                    or f"D-{lag_days}",
                    "cron": DAILY_RECONCILIATION_CRON,
                    "local_time": "03:00",
                }
            )
            result = await self._execute_reconciliation(
                billing_date=target_date,
                period_type=StorageBillingPeriodTypeEnum.DAILY.value,
                period_start=target_date,
                period_end=target_date,
                trigger_type=trigger_type,
                requested_scope={
                    **dict(requested_scope or {}),
                    "provider_codes": [provider_code],
                    "scheduled_provider_code": provider_code,
                    "official_billing_lag_days": lag_days,
                    "official_target_rule": _stringify(rule.get("official_target_rule"))
                    or f"D-{lag_days}",
                },
                provider_codes=[provider_code],
            )
            run_payload = dict(result.get("run") or {})
            runs.append(run_payload)
            sources.extend(list(result.get("sources") or []))
            aggregate_billable_drivers.extend(list(result.get("billable_drivers") or []))

            run_summary = dict(run_payload.get("summary") or {})
            status_counter.update(dict(run_summary.get("source_status_counts") or {}))
            statement_count += int(run_summary.get("statement_count") or 0)

            provider_summary = dict((run_summary.get("providers") or [{}])[0] or {})
            provider_summary.update(
                {
                    "run_id": run_payload.get("id"),
                    "billing_date": run_payload.get("billing_date"),
                    "period_label": run_payload.get("period_label"),
                    "run_status": run_payload.get("status"),
                    "official_billing_lag_days": lag_days,
                    "official_target_rule": _stringify(rule.get("official_target_rule"))
                    or f"D-{lag_days}",
                }
            )
            provider_summaries.append(provider_summary)

        aggregate_status = _aggregate_run_status(
            [_stringify(item.get("status")) for item in runs if _stringify(item.get("status"))]
        )
        unique_billable_drivers = []
        seen_driver_codes: set[str] = set()
        for driver in aggregate_billable_drivers:
            driver_code = _stringify(dict(driver).get("code"))
            if not driver_code or driver_code in seen_driver_codes:
                continue
            seen_driver_codes.add(driver_code)
            unique_billable_drivers.append(driver)

        return {
            "run": {
                "id": None,
                "status": aggregate_status,
                "trigger_type": trigger_type,
                "period_type": StorageBillingPeriodTypeEnum.DAILY.value,
                "provider_codes": [item["provider_code"] for item in provider_plans],
                "requested_scope": {
                    **dict(requested_scope or {}),
                    "provider_plans": provider_plans,
                },
                "summary": {
                    "driver_count": len(provider_plans),
                    "run_count": len(runs),
                    "statement_count": statement_count,
                    "source_status_counts": dict(status_counter),
                    "providers": provider_summaries,
                    "excluded_drivers": EXCLUDED_DRIVERS,
                },
            },
            "runs": runs,
            "sources": sources,
            "billable_drivers": unique_billable_drivers,
            "excluded_drivers": EXCLUDED_DRIVERS,
            "schedule": DAILY_RECONCILIATION_CRON,
            "provider_plans": provider_plans,
        }

    async def run_qiniu_monthly_settlement(
        self,
        billing_month: date | None = None,
    ) -> dict[str, Any]:
        target_month = _resolve_billing_month(billing_month)
        period_start = _month_start(target_month)
        period_end = _month_end(target_month)
        return await self._execute_reconciliation(
            billing_date=period_start,
            period_type=StorageBillingPeriodTypeEnum.MONTHLY.value,
            period_start=period_start,
            period_end=period_end,
            trigger_type="schedule_monthly",
            requested_scope={
                "job": "qiniu_monthly_settlement",
                "provider_codes": ["qiniu-kodo"],
                "billing_month": period_start.strftime("%Y-%m"),
            },
            provider_codes=["qiniu-kodo"],
        )

    async def trigger_qiniu_monthly_settlement(
        self,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_payload = dict(payload or {})
        target_month = _resolve_billing_month(request_payload.get("billing_month"))
        period_start = _month_start(target_month)
        period_end = _month_end(target_month)
        request_payload["provider_codes"] = ["qiniu-kodo"]
        request_payload["billing_month"] = period_start.strftime("%Y-%m")
        return await self._execute_reconciliation(
            billing_date=period_start,
            period_type=StorageBillingPeriodTypeEnum.MONTHLY.value,
            period_start=period_start,
            period_end=period_end,
            trigger_type="manual_qiniu_monthly",
            requested_scope=request_payload,
            provider_codes=["qiniu-kodo"],
        )

    async def list_runs(self, *, limit: int = 20) -> dict[str, Any]:
        safe_limit = max(1, min(100, int(limit)))
        result = await self._db.execute(
            select(StorageBillingRun)
            .where(StorageBillingRun.is_deleted.is_(False))
            .order_by(
                desc(StorageBillingRun.period_end),
                desc(StorageBillingRun.billing_date),
                desc(StorageBillingRun.id),
            )
            .limit(safe_limit)
        )
        rows = result.scalars().all()
        return {
            "items": [_serialize_run(item) for item in rows],
            "total": len(rows),
            "limit": safe_limit,
        }

    async def get_run_detail(self, run_id: int) -> dict[str, Any]:
        run = (
            await self._db.execute(
                select(StorageBillingRun).where(
                    StorageBillingRun.id == run_id,
                    StorageBillingRun.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if run is None:
            raise NotFoundException(message="Storage billing reconciliation run not found.")

        sources = (
            await self._db.execute(
                select(StorageProviderBillSource).where(
                    StorageProviderBillSource.run_id == run_id,
                    StorageProviderBillSource.is_deleted.is_(False),
                ).order_by(
                    StorageProviderBillSource.provider_code,
                    StorageProviderBillSource.id,
                )
            )
        ).scalars().all()
        return {
            "run": _serialize_run(run),
            "sources": [_serialize_source(item) for item in sources],
        }

    async def _load_run_charge_context(
        self,
        *,
        run_id: int,
        provider_code: str | None = None,
        source_id: int | None = None,
        tenant_id: int | None = None,
    ) -> tuple[
        StorageBillingRun,
        dict[int, StorageProviderBillSource],
        list[StorageTenantDailyCharge],
    ]:
        run = (
            await self._db.execute(
                select(StorageBillingRun).where(
                    StorageBillingRun.id == run_id,
                    StorageBillingRun.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if run is None:
            raise NotFoundException(message="Storage billing reconciliation run not found.")

        normalized_provider_code = _stringify(provider_code) or None
        source_stmt = select(StorageProviderBillSource).where(
            StorageProviderBillSource.run_id == run_id,
            StorageProviderBillSource.is_deleted.is_(False),
        )
        if normalized_provider_code is not None:
            source_stmt = source_stmt.where(
                StorageProviderBillSource.provider_code == normalized_provider_code
            )
        if source_id is not None:
            source_stmt = source_stmt.where(StorageProviderBillSource.id == source_id)

        sources = (await self._db.execute(source_stmt)).scalars().all()
        source_map = {item.id: item for item in sources if item.id is not None}
        if not source_map:
            return run, {}, []

        snapshot_rows = self._load_snapshot_charge_rows(
            list(source_map.values()),
            tenant_id=tenant_id,
        )
        if snapshot_rows is not None:
            return run, source_map, _sort_charge_rows(snapshot_rows)

        charge_stmt = select(StorageTenantDailyCharge).where(
            StorageTenantDailyCharge.is_deleted.is_(False),
            StorageTenantDailyCharge.source_id.in_(list(source_map)),
        )
        if tenant_id is not None:
            charge_stmt = charge_stmt.where(StorageTenantDailyCharge.tenant_id == tenant_id)
        charge_stmt = charge_stmt.order_by(
            desc(StorageTenantDailyCharge.amount_total),
            desc(StorageTenantDailyCharge.usage_bytes),
            StorageTenantDailyCharge.tenant_id,
            StorageTenantDailyCharge.provider_code,
            StorageTenantDailyCharge.charge_basis,
            StorageTenantDailyCharge.id,
        )
        rows = (await self._db.execute(charge_stmt)).scalars().all()
        return run, source_map, rows

    def _load_snapshot_charge_rows(
        self,
        sources: list[StorageProviderBillSource],
        *,
        tenant_id: int | None = None,
    ) -> list[StorageTenantDailyCharge] | None:
        snapshot_rows: list[StorageTenantDailyCharge] = []
        snapshot_available = True

        for source in sources:
            raw_payload = dict(source.raw_payload_json or {})
            if "allocation_rows" not in raw_payload:
                snapshot_available = False
                break
            for item in list(raw_payload.get("allocation_rows") or []):
                if not isinstance(item, Mapping):
                    continue
                row = _hydrate_snapshot_charge_row(source, item)
                if tenant_id is not None and row.tenant_id != tenant_id:
                    continue
                snapshot_rows.append(row)

        if not snapshot_available:
            return None
        return snapshot_rows

    async def list_run_charges(
        self,
        *,
        run_id: int,
        provider_code: str | None = None,
        source_id: int | None = None,
        tenant_id: int | None = None,
    ) -> dict[str, Any]:
        run, source_map, rows = await self._load_run_charge_context(
            run_id=run_id,
            provider_code=provider_code,
            source_id=source_id,
            tenant_id=tenant_id,
        )
        run_payload = _serialize_run(run)
        return {
            "run": run_payload,
            "run_id": run.id,
            "period_type": run_payload["period_type"],
            "billing_date": run_payload["billing_date"],
            "period_start": run_payload["period_start"],
            "period_end": run_payload["period_end"],
            "period_label": run_payload["period_label"],
            "filters": {
                "provider_code": _stringify(provider_code) or None,
                "source_id": source_id,
                "tenant_id": tenant_id,
            },
            "items": [
                _serialize_daily_charge(
                    item,
                    source=source_map.get(item.source_id or 0),
                )
                for item in rows
            ],
            "total": len(rows),
            "summary": _summarize_daily_charges(rows),
            "source_total": len(source_map),
        }

    async def export_run_charges_csv(
        self,
        *,
        run_id: int,
        provider_code: str | None = None,
        source_id: int | None = None,
        tenant_id: int | None = None,
    ) -> Response:
        run, source_map, rows = await self._load_run_charge_context(
            run_id=run_id,
            provider_code=provider_code,
            source_id=source_id,
            tenant_id=tenant_id,
        )
        csv_rows = [
            _serialize_daily_charge_csv_row(
                row,
                source=source_map.get(row.source_id or 0),
            )
            for row in rows
        ]
        return _build_csv_response(
            filename=f"storage_billing_run_{run.id}_{run.billing_date.isoformat()}_charges.csv",
            fieldnames=[
                "id",
                "run_id",
                "period_type",
                "billing_date",
                "period_start",
                "period_end",
                "period_label",
                "tenant_id",
                "provider_code",
                "driver_code",
                "charge_basis",
                "usage_bytes",
                "amount_total",
                "currency",
                "source_id",
                "source_key",
                "source_ref",
                "source_status",
                "statement_id",
                "binding_ids",
                "scope_values",
                "item_count",
                "details_json",
            ],
            rows=csv_rows,
        )

    async def _execute_reconciliation(
        self,
        *,
        billing_date: date,
        period_type: str,
        period_start: date,
        period_end: date,
        trigger_type: str,
        requested_scope: dict[str, Any],
        provider_codes: list[str] | None = None,
    ) -> dict[str, Any]:
        normalized_period_type, normalized_billing_date, normalized_period_start, normalized_period_end = (
            _normalize_period_fields(
                billing_date=billing_date,
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
            )
        )
        run = StorageBillingRun(
            period_type=normalized_period_type,
            billing_date=normalized_billing_date,
            period_start=normalized_period_start,
            period_end=normalized_period_end,
            trigger_type=trigger_type,
            status=StorageBillingRunStatusEnum.RUNNING.value,
            provider_codes_json=[],
            requested_scope_json=requested_scope,
            summary_json={},
            operator_id=self._operator_id,
            started_at=utc_now(),
        )
        self._db.add(run)
        await self._db.flush()

        billable_drivers = await self._get_billable_drivers(
            period_type=normalized_period_type,
            provider_codes=provider_codes,
        )
        run.provider_codes_json = [item["code"] for item in billable_drivers]

        source_rows: list[StorageProviderBillSource] = []
        provider_summaries: list[dict[str, Any]] = []
        status_counter: Counter[str] = Counter()

        for driver in billable_drivers:
            result = await self._fetch_provider_result(
                driver_code=str(driver.get("code") or "").strip(),
                billing_date=normalized_billing_date,
                period_type=normalized_period_type,
                period_start=normalized_period_start,
                period_end=normalized_period_end,
                requested_scope=requested_scope,
            )

            result_period_type, result_billing_date, result_period_start, result_period_end = (
                _normalize_period_fields(
                    billing_date=result.billing_date,
                    period_type=result.period_type,
                    period_start=result.period_start,
                    period_end=result.period_end,
                )
            )

            source_row = StorageProviderBillSource(
                run_id=run.id,
                provider_code=result.provider_code,
                driver_code=result.driver_code,
                period_type=result_period_type,
                billing_date=result_billing_date,
                period_start=result_period_start,
                period_end=result_period_end,
                source_status=result.source_status,
                source_ref=result.source_ref,
                currency=result.currency,
                amount_total=result.amount_total,
                usage_bytes=result.usage_bytes,
                raw_payload_json=result.raw_payload_json,
                fetched_at=utc_now(),
                error_message=result.error_message,
            )
            self._db.add(source_row)
            await self._db.flush()

            allocation_result = {
                "matched_items": 0,
                "unmatched_items": 0,
                "ambiguous_items": 0,
                "written_charge_rows": 0,
                "unmatched_item_samples": [],
                "ambiguous_item_samples": [],
            }
            should_rebuild_live_charges = result.source_status in {
                StorageBillingSourceStatusEnum.FETCHED.value,
                StorageBillingSourceStatusEnum.EMPTY.value,
            }
            if should_rebuild_live_charges:
                allocation_result = await self._replace_daily_charges_for_source(
                    source_row=source_row,
                    charge_items=result.charge_items,
                )
                allocation_summary = {
                    "matched_items": allocation_result["matched_items"],
                    "unmatched_items": allocation_result["unmatched_items"],
                    "ambiguous_items": allocation_result["ambiguous_items"],
                    "written_charge_rows": allocation_result["written_charge_rows"],
                }
                if (
                    source_row.source_status == StorageBillingSourceStatusEnum.FETCHED.value
                    and (
                        allocation_result["unmatched_items"] > 0
                        or allocation_result["ambiguous_items"] > 0
                    )
                ):
                    source_row.source_status = (
                        StorageBillingSourceStatusEnum.COMPLETED_WITH_GAPS.value
                    )
            else:
                allocation_summary = {
                    "matched_items": allocation_result["matched_items"],
                    "unmatched_items": allocation_result["unmatched_items"],
                    "ambiguous_items": allocation_result["ambiguous_items"],
                    "written_charge_rows": allocation_result["written_charge_rows"],
                }
            source_row.raw_payload_json = {
                **dict(source_row.raw_payload_json or {}),
                "allocation_summary": allocation_summary,
                "allocation_rows": list(allocation_result.get("allocation_rows") or []),
                "allocation_audit": {
                    "unmatched_item_samples": list(
                        allocation_result.get("unmatched_item_samples") or []
                    ),
                    "ambiguous_item_samples": list(
                        allocation_result.get("ambiguous_item_samples") or []
                    ),
                },
            }
            if should_rebuild_live_charges:
                await self._db.flush()
                await self._rebuild_provider_live_charges_for_run_scope(
                    run_id=run.id,
                    provider_code=source_row.provider_code,
                    period_type=result_period_type,
                    billing_date=result_billing_date,
                    period_start=result_period_start,
                    period_end=result_period_end,
                )
                await self._db.flush()

            provider_summaries.append(
                {
                    "provider_code": result.provider_code,
                    "source_status": source_row.source_status,
                    "charge_item_count": len(result.charge_items),
                    **allocation_summary,
                }
            )
            source_rows.append(source_row)
            status_counter[source_row.source_status] += 1

        statement_count = await self.rebuild_tenant_statements_for_period(
            period_type=normalized_period_type,
            billing_date=normalized_billing_date,
            period_start=normalized_period_start,
            period_end=normalized_period_end,
        )

        if not billable_drivers:
            run.status = StorageBillingRunStatusEnum.SKIPPED.value
        elif status_counter.get(StorageBillingSourceStatusEnum.FAILED.value, 0):
            run.status = StorageBillingRunStatusEnum.FAILED.value
        elif status_counter.get(StorageBillingSourceStatusEnum.NOT_IMPLEMENTED.value, 0) or status_counter.get(
            StorageBillingSourceStatusEnum.COMPLETED_WITH_GAPS.value,
            0,
        ):
            run.status = StorageBillingRunStatusEnum.COMPLETED_WITH_GAPS.value
        else:
            run.status = StorageBillingRunStatusEnum.COMPLETED.value

        run.summary_json = {
            "driver_count": len(billable_drivers),
            "source_status_counts": dict(status_counter),
            "statement_count": statement_count,
            "excluded_drivers": EXCLUDED_DRIVERS,
            "providers": provider_summaries,
        }
        run.completed_at = utc_now()
        await self._db.flush()

        logger.info(
            (
                "Storage billing reconciliation finished: "
                "period_type={} billing_date={} trigger={} run_id={} status={}"
            ),
            normalized_period_type,
            normalized_billing_date,
            trigger_type,
            run.id,
            run.status,
        )

        return {
            "run": _serialize_run(run),
            "sources": [_serialize_source(item) for item in source_rows],
            "billable_drivers": billable_drivers,
            "excluded_drivers": EXCLUDED_DRIVERS,
            "schedule": (
                DAILY_RECONCILIATION_CRON
                if normalized_period_type == StorageBillingPeriodTypeEnum.DAILY.value
                else QINIU_MONTHLY_SETTLEMENT_CRON
            ),
            "official_billing_lag_days": requested_scope.get(
                "official_billing_lag_days",
                OFFICIAL_BILLING_LAG_DAYS,
            ),
            "official_target_rule": requested_scope.get("official_target_rule"),
        }

    async def rebuild_tenant_statements_for_period(
        self,
        *,
        period_type: str,
        billing_date: date,
        period_start: date,
        period_end: date,
    ) -> int:
        rows = (
            await self._db.execute(
                select(StorageTenantDailyCharge).where(
                    StorageTenantDailyCharge.period_type == period_type,
                    StorageTenantDailyCharge.billing_date == billing_date,
                    StorageTenantDailyCharge.is_deleted.is_(False),
                )
            )
        ).scalars().all()

        existing_statements = (
            await self._db.execute(
                select(StorageTenantStatement).where(
                    StorageTenantStatement.period_type == period_type,
                    StorageTenantStatement.billing_date == billing_date,
                    StorageTenantStatement.is_deleted.is_(False),
                )
            )
        ).scalars().all()

        if not rows:
            for statement in existing_statements:
                await self._db.delete(statement)
            await self._db.flush()
            return 0

        grouped: dict[int, list[StorageTenantDailyCharge]] = {}
        for row in rows:
            grouped.setdefault(row.tenant_id, []).append(row)

        existing_map = {item.tenant_id: item for item in existing_statements}
        for tenant_id, items in grouped.items():
            amount_total = sum((item.amount_total or Decimal("0")) for item in items)
            statement = existing_map.get(tenant_id)
            if statement is None:
                statement = StorageTenantStatement(
                    tenant_id=tenant_id,
                    period_type=period_type,
                    billing_date=billing_date,
                    period_start=period_start,
                    period_end=period_end,
                )
                self._db.add(statement)
                await self._db.flush()

            statement.is_deleted = False
            statement.period_type = period_type
            statement.billing_date = billing_date
            statement.period_start = period_start
            statement.period_end = period_end
            statement.status = StorageBillingStatementStatusEnum.GENERATED.value
            statement.amount_total = amount_total
            statement.charge_count = len(items)
            statement.summary_json = {
                "provider_codes": sorted({item.provider_code for item in items}),
                "driver_codes": sorted({item.driver_code for item in items}),
                "total_usage_bytes": sum(item.usage_bytes or 0 for item in items),
                "period_label": _period_label(period_type, period_start, period_end),
            }
            statement.generated_at = utc_now()
            for item in items:
                item.statement_id = statement.id

        for tenant_id, statement in existing_map.items():
            if tenant_id not in grouped:
                await self._db.delete(statement)

        await self._db.flush()
        return len(grouped)

    async def rebuild_tenant_statements_for_billing_date(self, billing_date: date) -> int:
        return await self.rebuild_tenant_statements_for_period(
            period_type=StorageBillingPeriodTypeEnum.DAILY.value,
            billing_date=billing_date,
            period_start=billing_date,
            period_end=billing_date,
        )

    async def _fetch_provider_result(
        self,
        *,
        driver_code: str,
        billing_date: date,
        period_type: str,
        period_start: date,
        period_end: date,
        requested_scope: dict[str, Any],
    ) -> BillingFetchResult:
        adapter = get_provider_adapter(driver_code)
        if adapter is None:
            return BillingFetchResult(
                provider_code=driver_code,
                driver_code=driver_code,
                billing_date=billing_date,
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
                source_status=StorageBillingSourceStatusEnum.SKIPPED.value,
                error_message="No official billing adapter registered for this driver.",
                raw_payload_json={"driver_code": driver_code},
            )

        profile = await self._profile_service.get_provider_runtime_profile(driver_code)
        validation = await self._profile_service.validate_provider_profile(driver_code)
        supported_period_types = {
            _stringify(value)
            for value in (profile.get("supported_period_types") or [])
            if _stringify(value)
        }

        if not profile.get("enabled"):
            return BillingFetchResult(
                provider_code=driver_code,
                driver_code=driver_code,
                billing_date=billing_date,
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
                source_status=StorageBillingSourceStatusEnum.SKIPPED.value,
                error_message="Provider profile is disabled.",
                raw_payload_json={"provider_profile": profile, "validation": validation},
            )

        if _stringify(period_type) not in supported_period_types:
            return BillingFetchResult(
                provider_code=driver_code,
                driver_code=driver_code,
                billing_date=billing_date,
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
                source_status=StorageBillingSourceStatusEnum.NOT_IMPLEMENTED.value,
                error_message=(
                    f"Provider '{driver_code}' does not support period type '{period_type}'."
                ),
                raw_payload_json={"provider_profile": profile, "validation": validation},
            )

        if validation["errors"]:
            source_status = StorageBillingSourceStatusEnum.FAILED.value
            if _stringify(profile.get("bill_source")) not in get_provider_implemented_bill_sources(
                driver_code
            ):
                source_status = StorageBillingSourceStatusEnum.NOT_IMPLEMENTED.value
            return BillingFetchResult(
                provider_code=driver_code,
                driver_code=driver_code,
                billing_date=billing_date,
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
                source_status=source_status,
                error_message="; ".join(validation["errors"]),
                raw_payload_json={"provider_profile": profile, "validation": validation},
            )

        return await adapter.fetch_official_bill(
            BillingFetchRequest(
                billing_date=billing_date,
                driver_code=driver_code,
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
                profile=profile,
                request_scope=requested_scope,
            )
        )

    async def _replace_daily_charges_for_source(
        self,
        *,
        source_row: StorageProviderBillSource,
        charge_items: list[BillingChargeItem],
    ) -> dict[str, Any]:
        source_period_type, source_billing_date, source_period_start, source_period_end = (
            _normalize_period_fields(
                billing_date=source_row.billing_date,
                period_type=getattr(source_row, "period_type", None),
                period_start=getattr(source_row, "period_start", None),
                period_end=getattr(source_row, "period_end", None),
            )
        )
        existing_rows = (
            await self._db.execute(
                select(StorageTenantDailyCharge).where(
                    StorageTenantDailyCharge.provider_code == source_row.provider_code,
                    StorageTenantDailyCharge.period_type == source_period_type,
                    StorageTenantDailyCharge.billing_date == source_billing_date,
                    StorageTenantDailyCharge.is_deleted.is_(False),
                )
            )
        ).scalars().all()
        for row in existing_rows:
            await self._db.delete(row)

        if not charge_items:
            await self._db.flush()
            return {
                "matched_items": 0,
                "unmatched_items": 0,
                "ambiguous_items": 0,
                "written_charge_rows": 0,
                "unmatched_item_samples": [],
                "ambiguous_item_samples": [],
            }

        bindings = (
            await self._db.execute(
                select(StorageTenantBinding).where(
                    StorageTenantBinding.provider_code == source_row.provider_code,
                    StorageTenantBinding.is_active.is_(True),
                    StorageTenantBinding.validation_status
                    == StorageBillingValidationStatusEnum.VALID.value,
                    StorageTenantBinding.is_deleted.is_(False),
                )
            )
        ).scalars().all()
        bindings = await self._filter_live_eligible_bindings(
            bindings,
            provider_code=source_row.provider_code,
        )

        aggregated: dict[tuple[int, str, str], dict[str, Any]] = {}
        matched_items = 0
        unmatched_items = 0
        ambiguous_items = 0
        unmatched_item_samples: list[dict[str, Any]] = []
        ambiguous_item_samples: list[dict[str, Any]] = []

        for item in charge_items:
            matched_bindings = self._match_bindings(item, bindings)
            if not matched_bindings:
                unmatched_items += 1
                if len(unmatched_item_samples) < 10:
                    unmatched_item_samples.append(_serialize_charge_item(item))
                continue
            if len(matched_bindings) > 1:
                ambiguous_items += 1
                if len(ambiguous_item_samples) < 10:
                    ambiguous_item_samples.append(
                        {
                            "item": _serialize_charge_item(item),
                            "matched_bindings": [
                                _serialize_binding_audit(binding)
                                for binding in matched_bindings
                            ],
                        }
                    )
                continue

            binding = matched_bindings[0]
            matched_items += 1
            key = (binding.tenant_id, item.charge_basis, item.currency)
            current = aggregated.setdefault(
                key,
                {
                    "tenant_id": binding.tenant_id,
                    "charge_basis": item.charge_basis,
                    "currency": item.currency,
                    "usage_bytes": 0,
                    "amount_total": Decimal("0"),
                    "binding_ids": set(),
                    "scope_values": set(),
                    "items": [],
                },
            )
            current["usage_bytes"] += item.usage_bytes
            current["amount_total"] += item.amount_total
            current["binding_ids"].add(binding.id)
            current["scope_values"].add(binding.scope_value)
            current["items"].append(_serialize_charge_item(item))

        for value in aggregated.values():
            row_details = {
                "binding_ids": sorted(value["binding_ids"]),
                "scope_values": sorted(value["scope_values"]),
                "item_count": len(value["items"]),
                "items": value["items"],
            }
            self._db.add(
                StorageTenantDailyCharge(
                    tenant_id=value["tenant_id"],
                    period_type=source_period_type,
                    billing_date=source_billing_date,
                    period_start=source_period_start,
                    period_end=source_period_end,
                    provider_code=source_row.provider_code,
                    driver_code=source_row.driver_code,
                    charge_basis=value["charge_basis"],
                    usage_bytes=value["usage_bytes"],
                    amount_total=value["amount_total"],
                    currency=value["currency"],
                    source_id=source_row.id,
                    details_json=row_details,
                )
            )
            value["details"] = row_details

        await self._db.flush()
        return {
            "matched_items": matched_items,
            "unmatched_items": unmatched_items,
            "ambiguous_items": ambiguous_items,
            "written_charge_rows": len(aggregated),
            "allocation_rows": [
                _serialize_allocation_row_snapshot(
                    tenant_id=value["tenant_id"],
                    charge_basis=value["charge_basis"],
                    currency=value["currency"],
                    usage_bytes=value["usage_bytes"],
                    amount_total=value["amount_total"],
                    details=dict(value.get("details") or {}),
                )
                for value in aggregated.values()
            ],
            "unmatched_item_samples": unmatched_item_samples,
            "ambiguous_item_samples": ambiguous_item_samples,
        }

    async def _rebuild_provider_live_charges_for_run_scope(
        self,
        *,
        run_id: int,
        provider_code: str,
        period_type: str,
        billing_date: date,
        period_start: date,
        period_end: date,
    ) -> None:
        sources = (
            await self._db.execute(
                select(StorageProviderBillSource).where(
                    StorageProviderBillSource.run_id == run_id,
                    StorageProviderBillSource.provider_code == provider_code,
                    StorageProviderBillSource.period_type == period_type,
                    StorageProviderBillSource.billing_date == billing_date,
                    StorageProviderBillSource.is_deleted.is_(False),
                ).order_by(StorageProviderBillSource.id)
            )
        ).scalars().all()

        existing_rows = (
            await self._db.execute(
                select(StorageTenantDailyCharge).where(
                    StorageTenantDailyCharge.provider_code == provider_code,
                    StorageTenantDailyCharge.period_type == period_type,
                    StorageTenantDailyCharge.billing_date == billing_date,
                    StorageTenantDailyCharge.is_deleted.is_(False),
                )
            )
        ).scalars().all()
        for row in existing_rows:
            await self._db.delete(row)

        merged: dict[tuple[int, str, str], dict[str, Any]] = {}
        for source in sources:
            raw_payload = dict(source.raw_payload_json or {})
            for item in list(raw_payload.get("allocation_rows") or []):
                if not isinstance(item, Mapping):
                    continue
                tenant_id = int(item.get("tenant_id") or 0)
                charge_basis = _stringify(item.get("charge_basis"))
                currency = _stringify(item.get("currency")) or source.currency
                if tenant_id <= 0 or not charge_basis or not currency:
                    continue
                details = dict(item.get("details") or {})
                key = (tenant_id, charge_basis, currency)
                current = merged.setdefault(
                    key,
                    {
                        "tenant_id": tenant_id,
                        "charge_basis": charge_basis,
                        "currency": currency,
                        "usage_bytes": 0,
                        "amount_total": Decimal("0"),
                        "binding_ids": set(),
                        "scope_values": set(),
                        "source_ids": set(),
                        "items": [],
                    },
                )
                current["usage_bytes"] += int(item.get("usage_bytes") or 0)
                current["amount_total"] += Decimal(str(item.get("amount_total") or "0"))
                current["binding_ids"].update(details.get("binding_ids") or [])
                current["scope_values"].update(details.get("scope_values") or [])
                current["source_ids"].add(source.id)
                current["items"].extend(list(details.get("items") or []))

        driver_code = _stringify(sources[0].driver_code) if sources else provider_code
        for value in merged.values():
            self._db.add(
                StorageTenantDailyCharge(
                    tenant_id=value["tenant_id"],
                    period_type=period_type,
                    billing_date=billing_date,
                    period_start=period_start,
                    period_end=period_end,
                    provider_code=provider_code,
                    driver_code=driver_code,
                    charge_basis=value["charge_basis"],
                    usage_bytes=value["usage_bytes"],
                    amount_total=value["amount_total"],
                    currency=value["currency"],
                    source_id=None,
                    details_json={
                        "binding_ids": sorted(value["binding_ids"]),
                        "scope_values": sorted(value["scope_values"]),
                        "source_ids": sorted(item for item in value["source_ids"] if item is not None),
                        "item_count": len(value["items"]),
                        "items": list(value["items"]),
                    },
                )
            )

    async def _filter_live_eligible_bindings(
        self,
        bindings: list[StorageTenantBinding],
        *,
        provider_code: str,
    ) -> list[StorageTenantBinding]:
        if not bindings:
            return []
        if self._host_read is None:
            return list(bindings)

        platform_storage_context = await _read_platform_storage_context(self._host_read)
        active_storage_driver = _stringify(
            dict(platform_storage_context.get("storage_config") or {}).get("driver")
        )
        if (
            not active_storage_driver
            or active_storage_driver in EXCLUDED_DRIVERS
            or active_storage_driver not in SUPPORTED_CLOUD_DRIVERS
            or active_storage_driver != _stringify(provider_code)
        ):
            return []

        snapshot_reader = getattr(self._host_read, "get_tenant_plan_snapshot", None)
        storage_reader = getattr(self._host_read, "get_tenant_storage_context", None)
        if not callable(snapshot_reader) or not callable(storage_reader):
            return list(bindings)

        tenant_snapshot_cache: dict[int, dict[str, Any]] = {}
        tenant_storage_cache: dict[int, dict[str, Any]] = {}
        eligible: list[StorageTenantBinding] = []

        for binding in bindings:
            tenant_id = int(binding.tenant_id or 0)
            if tenant_id <= 0:
                continue

            if tenant_id not in tenant_snapshot_cache:
                tenant_snapshot = snapshot_reader(tenant_id)
                if inspect.isawaitable(tenant_snapshot):
                    tenant_snapshot = await tenant_snapshot
                tenant_snapshot_cache[tenant_id] = (
                    dict(tenant_snapshot) if isinstance(tenant_snapshot, Mapping) else {}
                )

            snapshot = tenant_snapshot_cache[tenant_id]
            features = dict(dict(snapshot.get("plan") or {}).get("features") or {})
            if not _to_bool(features.get("storage_billing_enabled")):
                continue

            if tenant_id not in tenant_storage_cache:
                tenant_storage = storage_reader(tenant_id)
                if inspect.isawaitable(tenant_storage):
                    tenant_storage = await tenant_storage
                tenant_storage_cache[tenant_id] = (
                    dict(tenant_storage) if isinstance(tenant_storage, Mapping) else {}
                )

            tenant_storage_context = tenant_storage_cache[tenant_id]
            tenant_storage_mode = _stringify(tenant_storage_context.get("storage_mode")) or "platform"
            if tenant_storage_mode != "platform":
                continue

            eligible.append(binding)

        return eligible

    def _match_bindings(
        self,
        item: BillingChargeItem,
        bindings: list[StorageTenantBinding],
    ) -> list[StorageTenantBinding]:
        bucket_aliases = {
            _stringify(item.bucket_name),
            _stringify(item.resource_id),
            _stringify(item.resource_name),
            *[
                _stringify(alias)
                for alias in (item.details_json or {}).get("bucket_aliases", [])
            ],
        }
        account_aliases = {_stringify(item.account_identifier)}
        matched_by_scope: dict[str, list[StorageTenantBinding]] = {}

        for binding in bindings:
            scope_value = _stringify(binding.scope_value)
            if binding.scope_type == "bucket" and scope_value and scope_value in bucket_aliases:
                matched_by_scope.setdefault("bucket", []).append(binding)
                continue
            if (
                binding.scope_type == "domain"
                and scope_value
                and scope_value == _stringify(item.domain_name)
            ):
                matched_by_scope.setdefault("domain", []).append(binding)
                continue
            if binding.scope_type == "account" and scope_value and scope_value in account_aliases:
                matched_by_scope.setdefault("account", []).append(binding)
                continue
            if (
                binding.scope_type == "tag"
                and _stringify(binding.tag_key)
                and item.tag_values.get(_stringify(binding.tag_key)) == _stringify(binding.tag_value)
            ):
                matched_by_scope.setdefault("tag", []).append(binding)

        if not matched_by_scope:
            return []

        selected_scope = min(
            matched_by_scope,
            key=lambda scope: _SCOPE_MATCH_PRIORITY.get(scope, 999),
        )
        return matched_by_scope[selected_scope]

    async def _load_plugin_config(self) -> dict[str, Any]:
        result = await self._db.execute(
            select(Plugin.config, Plugin.manifest).where(
                Plugin.name == PLUGIN_NAME,
                Plugin.is_deleted.is_(False),
            )
        )
        row = result.one_or_none()
        if row is None:
            return {}

        config = row[0] or {}
        manifest = row[1] or {}
        config_schema = manifest.get("config_schema") if isinstance(manifest, dict) else None
        if config_schema:
            config = decrypt_plugin_config(config, config_schema)
        return dict(config or {})

    async def _get_billable_drivers(
        self,
        *,
        period_type: str,
        provider_codes: list[str] | str | None = None,
    ) -> list[dict[str, Any]]:
        if self._host_read is None:
            return []

        raw_provider_codes = (
            [provider_codes]
            if isinstance(provider_codes, str)
            else list(provider_codes or [])
        )
        requested_codes = {
            _stringify(item)
            for item in raw_provider_codes
            if _stringify(item)
        }
        platform_storage_context = await _read_platform_storage_context(self._host_read)
        active_storage_driver = _stringify(
            dict(platform_storage_context.get("storage_config") or {}).get("driver")
        )
        if not active_storage_driver:
            return []
        if active_storage_driver in EXCLUDED_DRIVERS:
            return []
        if active_storage_driver and active_storage_driver not in SUPPORTED_CLOUD_DRIVERS:
            return []

        drivers = await self._host_read.get_enabled_storage_drivers()
        result: list[dict[str, Any]] = []
        for item in drivers:
            code = str(item.get("code") or "").strip()
            if code in EXCLUDED_DRIVERS:
                continue
            if code not in SUPPORTED_CLOUD_DRIVERS:
                continue
            if not item.get("is_available", True):
                continue
            if active_storage_driver and code != active_storage_driver:
                continue
            if requested_codes and code not in requested_codes:
                continue
            profile = await self._profile_service.get_provider_runtime_profile(code)
            supported_period_types = {
                _stringify(value)
                for value in (profile.get("supported_period_types") or [])
                if _stringify(value)
            }
            if _stringify(period_type) not in supported_period_types:
                continue
            result.append(item)
        return result


__all__ = [
    "DAILY_RECONCILIATION_CRON",
    "OFFICIAL_BILLING_LAG_DAYS",
    "QINIU_MONTHLY_SETTLEMENT_CRON",
    "StorageBillingOverviewService",
    "StorageBillingReconciliationService",
    "_get_plugin_db",
]
