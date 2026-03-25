"""Storage billing services. / 对象存储对账计费服务。"""

from __future__ import annotations

__all__ = [
    "StorageBillingBindingService",
    "StorageBillingOverviewService",
    "StorageBillingProviderProfileService",
    "StorageBillingReconciliationService",
]


def __getattr__(name: str):
    if name == "StorageBillingBindingService":
        from .binding_service import StorageBillingBindingService

        return StorageBillingBindingService
    if name == "StorageBillingProviderProfileService":
        from .profile_service import StorageBillingProviderProfileService

        return StorageBillingProviderProfileService
    if name == "StorageBillingOverviewService":
        from .reconciliation_service import StorageBillingOverviewService

        return StorageBillingOverviewService
    if name == "StorageBillingReconciliationService":
        from .reconciliation_service import StorageBillingReconciliationService

        return StorageBillingReconciliationService
    raise AttributeError(name)
