"""
AI quota exceptions / AI 配额异常
"""

from app.exceptions.base import BusinessException


class QuotaExceeded(BusinessException):
    """Quota exceeded exception / 配额超出异常"""

    code = 4291
    status_code = 429
    default_message = "ai.error.quota_exceeded_default"


__all__ = ["QuotaExceeded"]
