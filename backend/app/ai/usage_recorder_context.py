"""
Usage metering context / 用量计量上下文
"""

import dataclasses
from datetime import date

from app.ai.quota_models import QuotaCheckResult
from app.ai.rate_limiter import RateLimitReservation


@dataclasses.dataclass(frozen=True)
class UsageMeteringContext:
    """
    Usage metering context / 用量计量上下文

    Captures request-start values so response completion can update the same
    rate-limit and quota buckets deterministically.
    保存请求开始时的计量上下文，确保响应阶段写回同一组限流/配额桶。
    """

    request_minute_key: int | None = None
    request_stat_date: date | None = None
    quota_check: QuotaCheckResult = QuotaCheckResult()
    rate_limit_reservation: RateLimitReservation | None = None


__all__ = ["UsageMeteringContext"]
