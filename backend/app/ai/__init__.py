"""
AI Gateway Module
AI 网关模块

Unified AI call interface with multi-provider adapters and SSE streaming.
提供统一的 AI 调用接口，支持多供应商适配和 SSE 流式响应。
"""

# Export unified data types / 导出统一数据类型
from app.ai.adapters import AdapterRegistry

# Export adapters / 导出适配器
from app.ai.adapters.base import BaseAdapter

# Export agent quota & concurrency control / 导出智能体配额与并发控制
from app.ai.agent_quota import (
    AgentConcurrencyExceeded,
    AgentConcurrencyLimiter,
    AgentQuotaConfig,
    AgentQuotaExceeded,
    AgentQuotaManager,
)

# Export execution engine / 导出执行引擎
from app.ai.engine import ExecutionDispatcher

# Export events & hooks / 导出事件与钩子系统
from app.ai.events import EventBus, HookRegistry, get_event_bus, get_hook_registry

# Export unified exceptions / 导出统一异常
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

# Export gateway / 导出网关
from app.ai.gateway import AIGateway

# Export SSE streaming response / 导出 SSE 流式响应
from app.ai.sse import SSEChunkEncoder, SSEStreamingResponse

# Export tool execution sandbox / 导出工具执行沙箱
from app.ai.tools import ToolSandbox
from app.ai.types import (
    ChatChunk,
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    ImageResponse,
)

__all__ = [
    # Data types / 数据类型
    "ChatMessage",
    "ChatResponse",
    "ChatChunk",
    "EmbeddingResponse",
    "ImageResponse",
    # SSE streaming / SSE 流式响应
    "SSEChunkEncoder",
    "SSEStreamingResponse",
    # Adapters / 适配器
    "BaseAdapter",
    "AdapterRegistry",
    # Gateway / 网关
    "AIGateway",
    # Exceptions / 异常
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
    # Events & hooks / 事件与钩子
    "EventBus",
    "get_event_bus",
    "HookRegistry",
    "get_hook_registry",
    # Tool sandbox / 工具沙箱
    "ToolSandbox",
    # Agent quota & concurrency / 智能体配额与并发
    "AgentQuotaConfig",
    "AgentQuotaManager",
    "AgentQuotaExceeded",
    "AgentConcurrencyLimiter",
    "AgentConcurrencyExceeded",
    # Execution engine / 执行引擎
    "ExecutionDispatcher",
]
