"""Storage billing services. / 对象存储对账计费服务。"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "StorageBillingBindingService",
    "StorageBillingOverviewService",
    "StorageBillingProviderProfileService",
    "StorageBillingReconciliationService",
]


def __getattr__(name: str) -> Any:
    if name == "StorageBillingBindingService":
        return import_module(".binding_service", __name__).StorageBillingBindingService
    if name == "StorageBillingProviderProfileService":
        return import_module(".profile_service", __name__).StorageBillingProviderProfileService
    if name == "StorageBillingOverviewService":
        return import_module(".reconciliation_service", __name__).StorageBillingOverviewService
    if name == "StorageBillingReconciliationService":
        return import_module(".reconciliation_service", __name__).StorageBillingReconciliationService
    raise AttributeError(name)
