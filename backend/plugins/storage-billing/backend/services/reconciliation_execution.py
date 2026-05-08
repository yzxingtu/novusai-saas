"""Execution and allocation internals for storage-billing reconciliation."""

from __future__ import annotations

import inspect
from collections import Counter
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.core.base_model import utc_now
from app.core.logging import get_logger

from ..constants import (
    EXCLUDED_DRIVERS,
    SUPPORTED_CLOUD_DRIVERS,
    get_provider_implemented_bill_sources,
)
from ..models import (
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
from .reconciliation_shared import (
    _SCOPE_MATCH_PRIORITY,
    DAILY_RECONCILIATION_CRON,
    OFFICIAL_BILLING_LAG_DAYS,
    QINIU_MONTHLY_SETTLEMENT_CRON,
    _normalize_period_fields,
    _period_label,
    _read_platform_storage_context,
    _serialize_allocation_row_snapshot,
    _serialize_binding_audit,
    _serialize_charge_item,
    _serialize_run,
    _serialize_source,
    _stringify,
    _to_bool,
)

logger = get_logger(__name__)


class StorageBillingReconciliationExecutionMixin:
    """Core execution and allocation methods for reconciliation runs."""

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
        (
            normalized_period_type,
            normalized_billing_date,
            normalized_period_start,
            normalized_period_end,
        ) = _normalize_period_fields(
            billing_date=billing_date,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
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

            (
                result_period_type,
                result_billing_date,
                result_period_start,
                result_period_end,
            ) = _normalize_period_fields(
                billing_date=result.billing_date,
                period_type=result.period_type,
                period_start=result.period_start,
                period_end=result.period_end,
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
                    source_row.source_status
                    == StorageBillingSourceStatusEnum.FETCHED.value
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
        elif status_counter.get(
            StorageBillingSourceStatusEnum.NOT_IMPLEMENTED.value, 0
        ) or status_counter.get(
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
                if normalized_period_type == "daily"
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
            (
                await self._db.execute(
                    select(StorageTenantDailyCharge).where(
                        StorageTenantDailyCharge.period_type == period_type,
                        StorageTenantDailyCharge.billing_date == billing_date,
                        StorageTenantDailyCharge.is_deleted.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )

        existing_statements = (
            (
                await self._db.execute(
                    select(StorageTenantStatement).where(
                        StorageTenantStatement.period_type == period_type,
                        StorageTenantStatement.billing_date == billing_date,
                        StorageTenantStatement.is_deleted.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )

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

    async def rebuild_tenant_statements_for_billing_date(
        self, billing_date: date
    ) -> int:
        return await self.rebuild_tenant_statements_for_period(
            period_type="daily",
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
                raw_payload_json={
                    "provider_profile": profile,
                    "validation": validation,
                },
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
                raw_payload_json={
                    "provider_profile": profile,
                    "validation": validation,
                },
            )

        if validation["errors"]:
            source_status = StorageBillingSourceStatusEnum.FAILED.value
            if _stringify(
                profile.get("bill_source")
            ) not in get_provider_implemented_bill_sources(driver_code):
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
                raw_payload_json={
                    "provider_profile": profile,
                    "validation": validation,
                },
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
        (
            source_period_type,
            source_billing_date,
            source_period_start,
            source_period_end,
        ) = _normalize_period_fields(
            billing_date=source_row.billing_date,
            period_type=getattr(source_row, "period_type", None),
            period_start=getattr(source_row, "period_start", None),
            period_end=getattr(source_row, "period_end", None),
        )
        existing_rows = (
            (
                await self._db.execute(
                    select(StorageTenantDailyCharge).where(
                        StorageTenantDailyCharge.provider_code
                        == source_row.provider_code,
                        StorageTenantDailyCharge.period_type == source_period_type,
                        StorageTenantDailyCharge.billing_date == source_billing_date,
                        StorageTenantDailyCharge.is_deleted.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
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
            (
                await self._db.execute(
                    select(StorageTenantBinding).where(
                        StorageTenantBinding.provider_code == source_row.provider_code,
                        StorageTenantBinding.is_active.is_(True),
                        StorageTenantBinding.validation_status
                        == StorageBillingValidationStatusEnum.VALID.value,
                        StorageTenantBinding.is_deleted.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
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
            (
                await self._db.execute(
                    select(StorageProviderBillSource)
                    .where(
                        StorageProviderBillSource.run_id == run_id,
                        StorageProviderBillSource.provider_code == provider_code,
                        StorageProviderBillSource.period_type == period_type,
                        StorageProviderBillSource.billing_date == billing_date,
                        StorageProviderBillSource.is_deleted.is_(False),
                    )
                    .order_by(StorageProviderBillSource.id)
                )
            )
            .scalars()
            .all()
        )

        existing_rows = (
            (
                await self._db.execute(
                    select(StorageTenantDailyCharge).where(
                        StorageTenantDailyCharge.provider_code == provider_code,
                        StorageTenantDailyCharge.period_type == period_type,
                        StorageTenantDailyCharge.billing_date == billing_date,
                        StorageTenantDailyCharge.is_deleted.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
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
                        "source_ids": sorted(
                            item for item in value["source_ids"] if item is not None
                        ),
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
            logger.warning(
                "Storage billing reconciliation blocked: host readers are missing "
                "for provider={}",
                provider_code,
            )
            return []

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
            logger.warning(
                "Storage billing reconciliation blocked: tenant host readers are "
                "missing for provider={}",
                provider_code,
            )
            return []

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
                    dict(tenant_snapshot)
                    if isinstance(tenant_snapshot, Mapping)
                    else {}
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
            tenant_storage_mode = (
                _stringify(tenant_storage_context.get("storage_mode")) or "platform"
            )
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
            if (
                binding.scope_type == "bucket"
                and scope_value
                and scope_value in bucket_aliases
            ):
                matched_by_scope.setdefault("bucket", []).append(binding)
                continue
            if (
                binding.scope_type == "domain"
                and scope_value
                and scope_value == _stringify(item.domain_name)
            ):
                matched_by_scope.setdefault("domain", []).append(binding)
                continue
            if (
                binding.scope_type == "account"
                and scope_value
                and scope_value in account_aliases
            ):
                matched_by_scope.setdefault("account", []).append(binding)
                continue
            if (
                binding.scope_type == "tag"
                and _stringify(binding.tag_key)
                and item.tag_values.get(_stringify(binding.tag_key))
                == _stringify(binding.tag_value)
            ):
                matched_by_scope.setdefault("tag", []).append(binding)

        if not matched_by_scope:
            return []

        selected_scope = min(
            matched_by_scope,
            key=lambda scope: _SCOPE_MATCH_PRIORITY.get(scope, 999),
        )
        return matched_by_scope[selected_scope]
