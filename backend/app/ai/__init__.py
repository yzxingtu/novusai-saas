"""
AI Gateway Module / AI 网关模块

Unified AI call interface with multi-provider adapters and SSE streaming.
提供统一的 AI 调用接口，支持多供应商适配和 SSE 流式响应。
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.ai.adapters import AdapterRegistry
    from app.ai.adapters.base import BaseAdapter
    from app.ai.agent_quota_concurrency import AgentConcurrencyLimiter
    from app.ai.agent_quota_config import AgentQuotaConfig
    from app.ai.agent_quota_exceptions import (
        AgentConcurrencyExceeded,
        AgentQuotaExceeded,
    )
    from app.ai.agent_quota_manager import AgentQuotaManager
    from app.ai.engine import ExecutionDispatcher
    from app.ai.events import EventBus, HookRegistry, get_event_bus, get_hook_registry
    from app.ai.exceptions import (
        AIGatewayError,
        ContentFilterError,
        ContextLengthExceededError,
        ModelNotFoundError,
        ProviderAuthError,
        ProviderConnectionError,
        ProviderError,
        ProviderRateLimitError,
        ProviderTimeoutError,
        is_retryable,
    )
    from app.ai.gateway import AIGateway
    from app.ai.runtime import (
        ProtocolExecutionPlan,
        TurnCommand,
        TurnExecutionResult,
    )
    from app.ai.sse import SSEChunkEncoder, SSEStreamingResponse
    from app.ai.tools import ToolSandbox
    from app.ai.types import (
        ChatChunk,
        ChatMessage,
        ChatResponse,
        EmbeddingResponse,
        ImageResponse,
    )

_EXPORT_MAP = {
    "AdapterRegistry": "app.ai.adapters",
    "BaseAdapter": "app.ai.adapters.base",
    "AgentConcurrencyExceeded": "app.ai.agent_quota_exceptions",
    "AgentConcurrencyLimiter": "app.ai.agent_quota_concurrency",
    "AgentQuotaConfig": "app.ai.agent_quota_config",
    "AgentQuotaExceeded": "app.ai.agent_quota_exceptions",
    "AgentQuotaManager": "app.ai.agent_quota_manager",
    "ExecutionDispatcher": "app.ai.engine",
    "EventBus": "app.ai.events",
    "HookRegistry": "app.ai.events",
    "get_event_bus": "app.ai.events",
    "get_hook_registry": "app.ai.events",
    "AIGatewayError": "app.ai.exceptions",
    "ContentFilterError": "app.ai.exceptions",
    "ContextLengthExceededError": "app.ai.exceptions",
    "ModelNotFoundError": "app.ai.exceptions",
    "ProviderAuthError": "app.ai.exceptions",
    "ProviderConnectionError": "app.ai.exceptions",
    "ProviderError": "app.ai.exceptions",
    "ProviderRateLimitError": "app.ai.exceptions",
    "ProviderTimeoutError": "app.ai.exceptions",
    "is_retryable": "app.ai.exceptions",
    "AIGateway": "app.ai.gateway",
    "ProtocolExecutionPlan": "app.ai.runtime",
    "TurnCommand": "app.ai.runtime",
    "TurnExecutionResult": "app.ai.runtime",
    "SSEChunkEncoder": "app.ai.sse",
    "SSEStreamingResponse": "app.ai.sse",
    "ToolSandbox": "app.ai.tools",
    "ChatChunk": "app.ai.types",
    "ChatMessage": "app.ai.types",
    "ChatResponse": "app.ai.types",
    "EmbeddingResponse": "app.ai.types",
    "ImageResponse": "app.ai.types",
}


def __getattr__(name: str) -> Any:
    module_path = _EXPORT_MAP.get(name)
    if not module_path:
        raise AttributeError(name)
    module = import_module(module_path)
    value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = [
    "ChatMessage",
    "ChatResponse",
    "ChatChunk",
    "EmbeddingResponse",
    "ImageResponse",
    "ProtocolExecutionPlan",
    "TurnCommand",
    "TurnExecutionResult",
    "SSEChunkEncoder",
    "SSEStreamingResponse",
    "BaseAdapter",
    "AdapterRegistry",
    "AIGateway",
    "AIGatewayError",
    "ProviderError",
    "ProviderRateLimitError",
    "ProviderAuthError",
    "ModelNotFoundError",
    "ProviderTimeoutError",
    "ProviderConnectionError",
    "ContentFilterError",
    "ContextLengthExceededError",
    "is_retryable",
    "EventBus",
    "get_event_bus",
    "HookRegistry",
    "get_hook_registry",
    "ToolSandbox",
    "AgentQuotaConfig",
    "AgentQuotaManager",
    "AgentQuotaExceeded",
    "AgentConcurrencyLimiter",
    "AgentConcurrencyExceeded",
    "ExecutionDispatcher",
]
