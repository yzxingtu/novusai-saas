"""
事件与钩子系统

提供智能体引擎的事件总线（pub/sub 通知）和钩子系统（拦截/修改上下文）
"""

from app.ai.events.bus import EventBus, EventHandler, get_event_bus
from app.ai.events.hooks import (
    HookHandler,
    HookPoint,
    HookRegistry,
    get_hook_registry,
)
from app.ai.events.types import (
    AgentCreated,
    AgentDeleted,
    AgentDisabled,
    AgentPublished,
    AgentUpdated,
    BaseEvent,
    ConversationCompleted,
    ConversationCreated,
    ConversationStarted,
    DocumentUploaded,
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionStarted,
    KnowledgeBaseUpdated,
    MessageAdded,
    MessageCreated,
    ModelCallCompleted,
    PluginDisabled,
    PluginEnabled,
    PluginInstalled,
    PluginUninstalled,
    QuotaExceeded,
    QuotaWarning,
    SkillCreated,
    SkillDeleted,
    SkillUpdated,
    ToolCallCompleted,
    ToolCallFailed,
    ToolCallRequested,
)

__all__ = [
    # 事件基类
    "BaseEvent",
    # 智能体
    "AgentCreated", "AgentPublished", "AgentDisabled",
    "AgentUpdated", "AgentDeleted",
    # 技能
    "SkillCreated", "SkillUpdated", "SkillDeleted",
    # 对话
    "ConversationStarted", "ConversationCreated",
    "MessageAdded", "MessageCreated", "ConversationCompleted",
    # 工具
    "ToolCallRequested", "ToolCallCompleted", "ToolCallFailed",
    # 配额
    "QuotaWarning", "QuotaExceeded",
    # 执行
    "ExecutionStarted", "ExecutionCompleted", "ExecutionFailed",
    # 插件
    "PluginInstalled", "PluginEnabled", "PluginDisabled", "PluginUninstalled",
    # 知识库
    "KnowledgeBaseUpdated", "DocumentUploaded",
    # 模型
    "ModelCallCompleted",
    # 事件总线
    "EventBus", "EventHandler", "get_event_bus",
    # 钩子系统
    "HookPoint", "HookHandler", "HookRegistry", "get_hook_registry",
]
