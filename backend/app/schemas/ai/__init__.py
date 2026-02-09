"""
AI 相关 Schema 模块

包含 AI 供应商、模型、API Key、调用日志等 Schema
"""

from app.schemas.ai.provider import (
    AIProviderCreate,
    AIProviderUpdate,
    AIProviderResponse,
)
from app.schemas.ai.model import (
    AIModelCreate,
    AIModelUpdate,
    AIModelResponse,
)
from app.schemas.ai.api_key import (
    ProviderApiKeyCreate,
    ProviderApiKeyUpdate,
    ProviderApiKeyResponse,
)
from app.schemas.ai.call_log import (
    AICallLogResponse,
    AICallLogSummary,
)

__all__ = [
    # Provider
    "AIProviderCreate",
    "AIProviderUpdate",
    "AIProviderResponse",
    # Model
    "AIModelCreate",
    "AIModelUpdate",
    "AIModelResponse",
    # API Key
    "ProviderApiKeyCreate",
    "ProviderApiKeyUpdate",
    "ProviderApiKeyResponse",
    # Call Log
    "AICallLogResponse",
    "AICallLogSummary",
]
