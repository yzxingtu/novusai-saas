"""
AI 网关模块

提供统一的 AI 调用接口，支持多供应商适配和 SSE 流式响应
"""

# 导出统一数据类型
from app.ai.types import (
    ChatMessage,
    ChatResponse,
    ChatChunk,
    EmbeddingResponse,
    ImageResponse,
)

# 导出 SSE 流式响应
from app.ai.sse import SSEChunkEncoder, SSEStreamingResponse

# 导出适配器
from app.ai.adapters.base import BaseAdapter
from app.ai.adapters import AdapterRegistry

# 导出网关
from app.ai.gateway import AIGateway

# 导出统一异常
from app.ai.exceptions import (
    AIGatewayError,
    ProviderError,
    ProviderRateLimitError,
    ProviderAuthError,
    ModelNotFoundError,
    ProviderTimeoutError,
    ProviderConnectionError,
    ContentFilterError,
    ContextLengthExceededError,
    is_retryable,
)

# 导出事件与钩子系统
from app.ai.events import EventBus, get_event_bus, HookRegistry, get_hook_registry

# 导出工具执行沙箱
from app.ai.tools import ToolSandbox

# 导出智能体配额与并发控制
from app.ai.agent_quota import (
    AgentQuotaConfig,
    AgentQuotaManager,
    AgentQuotaExceeded,
    AgentConcurrencyLimiter,
    AgentConcurrencyExceeded,
)

# 导出执行引擎
from app.ai.engine import ExecutionDispatcher

__all__ = [
    # 数据类型
    "ChatMessage",
    "ChatResponse",
    "ChatChunk",
    "EmbeddingResponse",
    "ImageResponse",
    # SSE 流式响应
    "SSEChunkEncoder",
    "SSEStreamingResponse",
    # 适配器
    "BaseAdapter",
    "AdapterRegistry",
    # 网关
    "AIGateway",
    # 异常
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
    # 事件与钩子
    "EventBus",
    "get_event_bus",
    "HookRegistry",
    "get_hook_registry",
    # 工具沙箱
    "ToolSandbox",
    # 智能体配额与并发
    "AgentQuotaConfig",
    "AgentQuotaManager",
    "AgentQuotaExceeded",
    "AgentConcurrencyLimiter",
    "AgentConcurrencyExceeded",
    # 执行引擎
    "ExecutionDispatcher",
]
