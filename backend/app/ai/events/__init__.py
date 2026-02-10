"""
事件与钩子系统

提供智能体引擎的事件总线（pub/sub 通知）和钩子系统（拦截/修改上下文）
"""

from app.ai.events.types import (
    BaseEvent,
    AgentCreated,
    AgentPublished,
    AgentDisabled,
    ConversationStarted,
    MessageAdded,
    ConversationCompleted,
    ToolCallRequested,
    ToolCallCompleted,
    ToolCallFailed,
    QuotaWarning,
    QuotaExceeded,
    ExecutionStarted,
    ExecutionCompleted,
    ExecutionFailed,
)
from app.ai.events.bus import EventBus, EventHandler, get_event_bus
from app.ai.events.hooks import (
    HookPoint,
    HookHandler,
    HookRegistry,
    get_hook_registry,
)

__all__ = [
    # 事件基类与具体事件
    "BaseEvent",
    "AgentCreated",
    "AgentPublished",
    "AgentDisabled",
    "ConversationStarted",
    "MessageAdded",
    "ConversationCompleted",
    "ToolCallRequested",
    "ToolCallCompleted",
    "ToolCallFailed",
    "QuotaWarning",
    "QuotaExceeded",
    "ExecutionStarted",
    "ExecutionCompleted",
    "ExecutionFailed",
    # 事件总线
    "EventBus",
    "EventHandler",
    "get_event_bus",
    # 钩子系统
    "HookPoint",
    "HookHandler",
    "HookRegistry",
    "get_hook_registry",
]
