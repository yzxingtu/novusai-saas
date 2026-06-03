"""
计费相关枚举模块 / Billing Enum Module

定义企业套餐计费相关的枚举
Defines tenant plan billing related enums.
"""

from app.enums.base import LabeledStrEnum


class BillingCycle(LabeledStrEnum):
    """Billing Cycle Enum / 计费周期枚举"""

    MONTHLY = ("monthly", "enum.billing_cycle.monthly")
    YEARLY = ("yearly", "enum.billing_cycle.yearly")
    LIFETIME = ("lifetime", "enum.billing_cycle.lifetime")
    CUSTOM = ("custom", "enum.billing_cycle.custom")


__all__ = [
    "BillingCycle",
]
