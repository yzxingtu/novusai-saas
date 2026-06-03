"""Storage billing overview service. / 对象存储计费概览服务。"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import desc, func, select

from app.models.system.plugin import Plugin
from app.plugins.crypto import decrypt_plugin_config

from ..constants import (
    EXCLUDED_DRIVERS,
    PROVIDER_DAILY_RECONCILIATION_RULES,
    SUPPORTED_CLOUD_DRIVERS,
    get_provider_daily_reconciliation_rule,
)
from ..models import (
    StorageBillingPeriodTypeEnum,
    StorageBillingRun,
    StorageTenantBinding,
    StorageTenantDailyCharge,
    StorageTenantStatement,
)
from .profile_service import StorageBillingProviderProfileService
from .reconciliation_shared import (
    DAILY_RECONCILIATION_CRON,
    PLUGIN_NAME,
    QINIU_MONTHLY_SETTLEMENT_CRON,
    _build_csv_response,
    _ConfigContext,
    _get_plugin_db,
    _normalize_host_storage_context,
    _read_platform_storage_context,
    _serialize_daily_charge,
    _serialize_daily_charge_csv_row,
    _serialize_run,
    _serialize_statement,
    _stringify,
    _summarize_daily_charges,
    parse_optional_period_type,
)


class StorageBillingOverviewService:
    """Read-only overview helpers. / 只读概览服务。"""

    def __init__(
        self,
        db: Any | None,
        host_read: Any | None = None,
        *,
        provider_profile_service_factory: Any | None = None,
    ) -> None:
        self._db = db
        self._host_read = host_read
        self._provider_profile_service_factory = (
            provider_profile_service_factory or StorageBillingProviderProfileService
        )

    @classmethod
    def from_context(cls, ctx) -> StorageBillingOverviewService:
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
            stmt = stmt.where(
                StorageTenantStatement.period_type == normalized_period_type
            )
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
            (
                await self._db.execute(
                    select(StorageTenantDailyCharge)
                    .where(
                        StorageTenantDailyCharge.tenant_id == tenant_id,
                        StorageTenantDailyCharge.billing_date == billing_date,
                        StorageTenantDailyCharge.period_type
                        == (
                            normalized_period_type
                            or StorageBillingPeriodTypeEnum.DAILY.value
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
            )
            .scalars()
            .all()
        )

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
        config_schema = (
            manifest.get("config_schema") if isinstance(manifest, dict) else None
        )
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
            platform_storage_context = await _read_platform_storage_context(
                self._host_read
            )

        active_storage_driver = str(
            dict(platform_storage_context.get("storage_config") or {}).get("driver")
            or ""
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
            latest_runs = [
                _serialize_run(item) for item in latest_runs_result.scalars().all()
            ]
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
            profile_service = self._provider_profile_service_factory(
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
                "scheduled_daily_supported": dict(profile).get(
                    "scheduled_daily_supported"
                ),
                "supported_period_types": list(
                    dict(profile).get("supported_period_types") or []
                ),
                "official_billing_lag_days": dict(profile).get(
                    "official_billing_lag_days"
                ),
                "official_target_rule": dict(profile).get("official_target_rule"),
                "capability_message": dict(profile).get("capability_message"),
            }
            for provider, profile in dict(
                provider_profiles.get("providers") or {}
            ).items()
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
            "statement_status": statement.status
            if statement
            else "pending_provider_ingestion",
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
            (
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
            )
            .scalars()
            .all()
        )
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
            "period_type": statement.period_type
            if statement is not None
            else normalized_period_type,
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
    ):
        normalized_period_type = parse_optional_period_type(period_type)
        result = await self.list_tenant_statement_charges(
            tenant_id=tenant_id,
            billing_date=billing_date,
            period_type=normalized_period_type,
        )
        resolved_billing_date = result.get("billing_date") or "latest"
        parsed_billing_date = (
            date.fromisoformat(resolved_billing_date)
            if isinstance(resolved_billing_date, str)
            and resolved_billing_date != "latest"
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
