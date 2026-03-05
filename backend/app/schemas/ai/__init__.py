"""
AI 相关 Schema 模块

包含 AI 供应商、模型、API Key、调用日志等 Schema
"""

from app.schemas.ai.agent import (
    AgentCreate,
    AgentListItem,
    AgentResponse,
    AgentUpdate,
)
from app.schemas.ai.api_key import (
    ProviderApiKeyCreate,
    ProviderApiKeyResponse,
    ProviderApiKeyUpdate,
)
from app.schemas.ai.batch_run import (
    BatchRunCreate,
    BatchRunProgress,
    BatchRunResponse,
)
from app.schemas.ai.call_log import (
    AICallLogResponse,
    AICallLogSummary,
)
from app.schemas.ai.conversation_message import (
    ConversationMessageCreate,
    ConversationMessageResponse,
)
from app.schemas.ai.model import (
    AIModelCreate,
    AIModelResponse,
    AIModelUpdate,
)
from app.schemas.ai.provider import (
    AIProviderCreate,
    AIProviderResponse,
    AIProviderUpdate,
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
    # Agent
    "AgentCreate",
    "AgentUpdate",
    "AgentResponse",
    "AgentListItem",
    # ConversationMessage
    "ConversationMessageCreate",
    "ConversationMessageResponse",
    # BatchRun
    "BatchRunCreate",
    "BatchRunResponse",
    "BatchRunProgress",
]
