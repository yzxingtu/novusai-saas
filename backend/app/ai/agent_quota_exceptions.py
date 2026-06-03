"""
Agent quota exceptions / 智能体配额异常
"""

from app.exceptions.base import BusinessException


class AgentQuotaExceeded(BusinessException):
    """Agent quota exceeded exception / 智能体配额超出异常"""

    code = 4293
    status_code = 429
    default_message = "ai.error.quota_exceeded_default"

    def __init__(
        self, message: str, quota_type: str = "", current: int = 0, limit: int = 0
    ):
        super().__init__(message=message)
        self.quota_type = quota_type
        self.current = current
        self.limit = limit


class AgentConcurrencyExceeded(BusinessException):
    """Agent concurrency exceeded exception / 智能体并发超出异常"""

    code = 4294
    status_code = 429
    default_message = "ai.agent.concurrency_exceeded"

    def __init__(self, message: str, retry_after: int = 5):
        super().__init__(message=message)
        self.retry_after = retry_after


__all__ = ["AgentQuotaExceeded", "AgentConcurrencyExceeded"]
