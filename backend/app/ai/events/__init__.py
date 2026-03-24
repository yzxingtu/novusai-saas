"""
Event & Hook System / 事件与钩子系统

Provides event bus (pub/sub notifications) and hook system (intercept/modify context) for the agent engine.
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
    # 事件基类 / Base event
    "BaseEvent",
    # 智能体 / Agent
    "AgentCreated", "AgentPublished", "AgentDisabled",
    "AgentUpdated", "AgentDeleted",
    # 技能 / Skill
    "SkillCreated", "SkillUpdated", "SkillDeleted",
    # 对话 / Conversation
    "ConversationStarted", "ConversationCreated",
    "MessageAdded", "MessageCreated", "ConversationCompleted",
    # 工具 / Tool call
    "ToolCallRequested", "ToolCallCompleted", "ToolCallFailed",
    # 配额 / Quota
    "QuotaWarning", "QuotaExceeded",
    # 执行 / Execution
    "ExecutionStarted", "ExecutionCompleted", "ExecutionFailed",
    # 插件 / Plugin
    "PluginInstalled", "PluginEnabled", "PluginDisabled", "PluginUninstalled",
    # 知识库 / Knowledge base
    "KnowledgeBaseUpdated", "DocumentUploaded",
    # 模型 / Model
    "ModelCallCompleted",
    # 事件总线 / Event bus
    "EventBus", "EventHandler", "get_event_bus",
    # 钩子系统 / Hooks
    "HookPoint", "HookHandler", "HookRegistry", "get_hook_registry",
]
