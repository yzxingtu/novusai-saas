"""Run scheduling/orchestration methods for storage-billing reconciliation."""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from ..constants import EXCLUDED_DRIVERS, get_provider_daily_reconciliation_rule
from ..models import StorageBillingPeriodTypeEnum, StorageBillingRunStatusEnum
from .reconciliation_shared import (
    DAILY_RECONCILIATION_CRON,
    OFFICIAL_BILLING_LAG_DAYS,
    _aggregate_run_status,
    _month_end,
    _month_start,
    _resolve_billing_date,
    _resolve_billing_month,
    _stringify,
)


class StorageBillingReconciliationScheduleMixin:
    """Public reconciliation run entrypoints and provider fan-out orchestration."""

    async def trigger_manual_run(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        request_payload = dict(payload or {})
        if request_payload.get("billing_date") in {None, ""}:
            return await self._run_provider_specific_daily_reconciliation(
                trigger_type="manual",
                requested_scope=request_payload,
                provider_codes=request_payload.get("provider_codes"),
            )
        billing_date = self._resolve_billing_date(
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

        target_date = self._resolve_billing_date(
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
            target_date = self._resolve_billing_date(
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
            target_date = self._resolve_billing_date(
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
        target_month = self._resolve_billing_month(billing_month)
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
