"""Read/query/export methods for reconciliation runs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi.responses import Response
from sqlalchemy import desc, select

from app.exceptions import NotFoundException

from ..models import (
    StorageBillingRun,
    StorageProviderBillSource,
    StorageTenantDailyCharge,
)
from .reconciliation_shared import (
    _build_csv_response,
    _hydrate_snapshot_charge_row,
    _serialize_daily_charge,
    _serialize_daily_charge_csv_row,
    _serialize_run,
    _serialize_source,
    _sort_charge_rows,
    _stringify,
    _summarize_daily_charges,
)


class StorageBillingReconciliationRunQueryMixin:
    """Run list/detail and charge query/export helpers."""

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
            raise NotFoundException(
                message="Storage billing reconciliation run not found."
            )

        sources = (
            (
                await self._db.execute(
                    select(StorageProviderBillSource)
                    .where(
                        StorageProviderBillSource.run_id == run_id,
                        StorageProviderBillSource.is_deleted.is_(False),
                    )
                    .order_by(
                        StorageProviderBillSource.provider_code,
                        StorageProviderBillSource.id,
                    )
                )
            )
            .scalars()
            .all()
        )
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
            raise NotFoundException(
                message="Storage billing reconciliation run not found."
            )

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
            charge_stmt = charge_stmt.where(
                StorageTenantDailyCharge.tenant_id == tenant_id
            )
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
