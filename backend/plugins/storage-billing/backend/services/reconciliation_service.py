"""Storage billing reconciliation facade. / 对象存储对账服务门面。"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from .profile_service import StorageBillingProviderProfileService
from .reconciliation_driver_support import (
    StorageBillingReconciliationDriverSupportMixin,
)
from .reconciliation_execution import StorageBillingReconciliationExecutionMixin
from .reconciliation_overview_service import StorageBillingOverviewService
from .reconciliation_run_queries import StorageBillingReconciliationRunQueryMixin
from .reconciliation_schedule import StorageBillingReconciliationScheduleMixin
from .reconciliation_shared import (
    DAILY_RECONCILIATION_CRON,
    OFFICIAL_BILLING_LAG_DAYS,
    PLUGIN_NAME,
    QINIU_MONTHLY_SETTLEMENT_CRON,
    _ConfigContext,
    _get_plugin_db,
    _resolve_billing_date,
    _resolve_billing_month,
)


class StorageBillingReconciliationService(
    StorageBillingReconciliationDriverSupportMixin,
    StorageBillingReconciliationExecutionMixin,
    StorageBillingReconciliationRunQueryMixin,
    StorageBillingReconciliationScheduleMixin,
):
    """Reconciliation operations facade backed by plugin-owned tables."""

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
    def from_context(cls, ctx) -> StorageBillingReconciliationService:
        return cls(
            db=_get_plugin_db(ctx),
            host_read=getattr(ctx, "host", None),
            operator_id=getattr(ctx, "get_current_user_id", lambda: None)(),
        )

    @staticmethod
    def _resolve_billing_date(
        raw_value: object | None,
        *,
        default_offset_days: int = 1,
    ):
        return _resolve_billing_date(
            raw_value,
            default_offset_days=default_offset_days,
        )

    @staticmethod
    def _resolve_billing_month(raw_value: object | None):
        return _resolve_billing_month(raw_value)


__all__ = [
    "DAILY_RECONCILIATION_CRON",
    "OFFICIAL_BILLING_LAG_DAYS",
    "PLUGIN_NAME",
    "QINIU_MONTHLY_SETTLEMENT_CRON",
    "StorageBillingOverviewService",
    "StorageBillingReconciliationService",
    "_ConfigContext",
    "_get_plugin_db",
    "_resolve_billing_date",
    "_resolve_billing_month",
    "timedelta",
]
