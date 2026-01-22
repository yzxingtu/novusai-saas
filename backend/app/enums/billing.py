"""
计费相关枚举模块

定义租户套餐计费相关的枚举
"""

from app.enums.base import StrEnum


class BillingCycle(StrEnum):
    """计费周期枚举"""
    
    MONTHLY = ("monthly", "enum.billing_cycle.monthly")
    YEARLY = ("yearly", "enum.billing_cycle.yearly")
    LIFETIME = ("lifetime", "enum.billing_cycle.lifetime")
    CUSTOM = ("custom", "enum.billing_cycle.custom")


__all__ = [
    "BillingCycle",
]
