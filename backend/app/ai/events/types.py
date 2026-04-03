"""
Event Type Definitions / 事件类型定义

Defines all event types used in the agent engine.
定义智能体引擎中使用的所有事件类型。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.base_model import utc_now

# ============================================
# Event Base Class / 事件基类
# ============================================


@dataclass
class BaseEvent:
    """
    Event Base Class / 事件基类

    All events must inherit this class. Contains common metadata.
    所有事件必须继承此类。包含通用元信息。
    """

    tenant_id: int
    timestamp: datetime = field(default_factory=lambda: utc_now())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        """Event type name (class name) / 事件类型名称（类名）"""
        return self.__class__.__name__


# ============================================
# Agent Lifecycle Events / 智能体生命周期事件
# ============================================


@dataclass
class AgentCreated(BaseEvent):
    """Agent created event / 智能体创建事件"""

    agent_id: int = 0
    agent_name: str = ""


@dataclass
class AgentPublished(BaseEvent):
    """Agent published event / 智能体发布事件"""

    agent_id: int = 0
    version: int = 0


@dataclass
class AgentDisabled(BaseEvent):
    """Agent disabled event / 智能体禁用事件"""

    agent_id: int = 0


# ============================================
# Conversation Events / 对话事件
# ============================================


@dataclass
class ConversationStarted(BaseEvent):
    """Conversation started event / 对话开始事件"""

    conversation_id: int = 0
    agent_id: int = 0
    user_id: int | None = None


@dataclass
class MessageAdded(BaseEvent):
    """Message added event / 消息添加事件"""

    conversation_id: int = 0
    message_id: int = 0
    role: str = ""
    token_count: int = 0


@dataclass
class ConversationCompleted(BaseEvent):
    """Conversation completed event (one round of interaction finished) / 对话完成事件（一轮交互结束）"""

    conversation_id: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0


# ============================================
# Tool Call Events / 工具调用事件
# ============================================


@dataclass
class ToolCallRequested(BaseEvent):
    """Tool call requested event / 工具调用请求事件"""

    conversation_id: int = 0
    tool_name: str = ""
    tool_call_id: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallCompleted(BaseEvent):
    """Tool call completed event / 工具调用完成事件"""

    conversation_id: int = 0
    tool_name: str = ""
    tool_call_id: str = ""
    result: str = ""
    duration_ms: int = 0


@dataclass
class ToolCallFailed(BaseEvent):
    """Tool call failed event / 工具调用失败事件"""

    conversation_id: int = 0
    tool_name: str = ""
    tool_call_id: str = ""
    error: str = ""


# ============================================
# Quota & Rate Limiting Events / 配额与限流事件
# ============================================


@dataclass
class QuotaWarning(BaseEvent):
    """Quota warning event / 配额预警事件"""

    agent_id: int = 0
    usage_percent: float = 0.0
    threshold: int = 80


@dataclass
class QuotaExceeded(BaseEvent):
    """Quota exceeded event / 配额超限事件"""

    agent_id: int = 0
    quota_type: str = ""  # soft / hard / 软或硬配额


# ============================================
# Execution Engine Events / 执行引擎事件
# ============================================


@dataclass
class ExecutionStarted(BaseEvent):
    """Execution started event / 执行开始事件"""

    conversation_id: int = 0
    agent_id: int = 0
    execution_mode: str = ""


@dataclass
class ExecutionCompleted(BaseEvent):
    """Execution completed event / 执行完成事件"""

    conversation_id: int = 0
    agent_id: int = 0
    total_tokens: int = 0
    duration_ms: int = 0


@dataclass
class ExecutionFailed(BaseEvent):
    """Execution failed event / 执行失败事件"""

    conversation_id: int = 0
    agent_id: int = 0
    error: str = ""
    error_type: str = ""


# ============================================
# Agent Extended Events / 智能体扩展事件
# ============================================


@dataclass
class AgentUpdated(BaseEvent):
    """Agent updated event / 智能体更新事件"""

    agent_id: int = 0
    updated_fields: list[str] = field(default_factory=list)


@dataclass
class AgentDeleted(BaseEvent):
    """Agent deleted event / 智能体删除事件"""

    agent_id: int = 0


# ============================================
# Skill Events / 技能事件
# ============================================


@dataclass
class SkillCreated(BaseEvent):
    """Skill created event / 技能创建事件"""

    skill_id: int = 0
    skill_name: str = ""
    skill_type: str = ""


@dataclass
class SkillUpdated(BaseEvent):
    """Skill updated event / 技能更新事件"""

    skill_id: int = 0
    updated_fields: list[str] = field(default_factory=list)


@dataclass
class SkillDeleted(BaseEvent):
    """Skill deleted event / 技能删除事件"""

    skill_id: int = 0


# ============================================
# Conversation Extended Events / 对话扩展事件
# ============================================


@dataclass
class ConversationCreated(BaseEvent):
    """Conversation created event / 对话创建事件"""

    conversation_id: int = 0
    agent_id: int = 0
    user_id: int | None = None


@dataclass
class MessageCreated(BaseEvent):
    """Message created event / 消息创建事件"""

    conversation_id: int = 0
    message_id: int = 0
    role: str = ""
    content_length: int = 0


# ============================================
# Plugin Lifecycle Events / 插件生命周期事件
# ============================================


@dataclass
class PluginInstalled(BaseEvent):
    """Plugin installed event / 插件安装事件"""

    plugin_name: str = ""
    plugin_version: str = ""


@dataclass
class PluginEnabled(BaseEvent):
    """Plugin enabled event / 插件启用事件"""

    plugin_name: str = ""


@dataclass
class PluginDisabled(BaseEvent):
    """Plugin disabled event / 插件禁用事件"""

    plugin_name: str = ""


@dataclass
class PluginUninstalled(BaseEvent):
    """Plugin uninstalled event / 插件卸载事件"""

    plugin_name: str = ""


# ============================================
# Knowledge Base Events / 知识库事件
# ============================================


@dataclass
class KnowledgeBaseUpdated(BaseEvent):
    """Knowledge base updated event / 知识库更新事件"""

    knowledge_base_id: int = 0
    action: str = ""  # created / updated / deleted / 创建或更新或删除


@dataclass
class DocumentUploaded(BaseEvent):
    """Document uploaded event / 文档上传事件"""

    knowledge_base_id: int = 0
    document_id: int = 0
    file_name: str = ""


# ============================================
# Model Call Events / 模型调用事件
# ============================================


@dataclass
class ModelCallCompleted(BaseEvent):
    """Model call completed event / 模型调用完成事件"""

    provider: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0


__all__ = [
    "BaseEvent",
    # Agent / 智能体
    "AgentCreated",
    "AgentPublished",
    "AgentDisabled",
    "AgentUpdated",
    "AgentDeleted",
    # Skill / 技能
    "SkillCreated",
    "SkillUpdated",
    "SkillDeleted",
    # Conversation / 对话
    "ConversationStarted",
    "ConversationCreated",
    "MessageAdded",
    "MessageCreated",
    "ConversationCompleted",
    # Tool / 工具
    "ToolCallRequested",
    "ToolCallCompleted",
    "ToolCallFailed",
    # Quota / 配额
    "QuotaWarning",
    "QuotaExceeded",
    # Execution / 执行
    "ExecutionStarted",
    "ExecutionCompleted",
    "ExecutionFailed",
    # Plugin / 插件
    "PluginInstalled",
    "PluginEnabled",
    "PluginDisabled",
    "PluginUninstalled",
    # Knowledge Base / 知识库
    "KnowledgeBaseUpdated",
    "DocumentUploaded",
    # Model / 模型
    "ModelCallCompleted",
]
