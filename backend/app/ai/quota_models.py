"""
AI quota contracts / AI 配额契约
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class QuotaMeteringItem:
    """
    Quota metering context item / 配额计量上下文项

    Captures which quota rule was applied at request-check time so response-time
    adjustment can update the same Redis bucket deterministically.
    捕获请求检查阶段实际命中的配额规则，确保响应阶段回写到同一 Redis bucket。
    """

    quota_id: int
    period: str
    quota_type: str
    tracking_model_id: int


@dataclass(frozen=True)
class QuotaCheckResult:
    """
    Quota check result / 配额检查结果

    Stores all effective quota rules applied to the request.
    存储本次请求命中的所有生效配额规则。
    """

    items: tuple[QuotaMeteringItem, ...] = ()


__all__ = ["QuotaMeteringItem", "QuotaCheckResult"]
