"""
事件类型定义

定义智能体引擎中使用的所有事件类型
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ============================================
# 事件基类
# ============================================

@dataclass
class BaseEvent:
    """
    事件基类

    所有事件必须继承此类。包含通用元信息。
    """

    tenant_id: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        """事件类型名称（类名）"""
        return self.__class__.__name__


# ============================================
# 智能体生命周期事件
# ============================================

@dataclass
class AgentCreated(BaseEvent):
    """智能体创建事件"""
    agent_id: int = 0
    agent_name: str = ""


@dataclass
class AgentPublished(BaseEvent):
    """智能体发布事件"""
    agent_id: int = 0
    version: int = 0


@dataclass
class AgentDisabled(BaseEvent):
    """智能体禁用事件"""
    agent_id: int = 0


# ============================================
# 对话事件
# ============================================

@dataclass
class ConversationStarted(BaseEvent):
    """对话开始事件"""
    conversation_id: int = 0
    agent_id: int = 0
    user_id: int | None = None


@dataclass
class MessageAdded(BaseEvent):
    """消息添加事件"""
    conversation_id: int = 0
    message_id: int = 0
    role: str = ""
    token_count: int = 0


@dataclass
class ConversationCompleted(BaseEvent):
    """对话完成事件（一轮交互结束）"""
    conversation_id: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0


# ============================================
# 工具调用事件
# ============================================

@dataclass
class ToolCallRequested(BaseEvent):
    """工具调用请求事件"""
    conversation_id: int = 0
    tool_name: str = ""
    tool_call_id: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCallCompleted(BaseEvent):
    """工具调用完成事件"""
    conversation_id: int = 0
    tool_name: str = ""
    tool_call_id: str = ""
    result: Any = None
    duration_ms: int = 0


@dataclass
class ToolCallFailed(BaseEvent):
    """工具调用失败事件"""
    conversation_id: int = 0
    tool_name: str = ""
    tool_call_id: str = ""
    error: str = ""


# ============================================
# 配额与限流事件
# ============================================

@dataclass
class QuotaWarning(BaseEvent):
    """配额预警事件"""
    agent_id: int = 0
    usage_percent: float = 0.0
    threshold: int = 80


@dataclass
class QuotaExceeded(BaseEvent):
    """配额超限事件"""
    agent_id: int = 0
    quota_type: str = ""  # soft / hard


# ============================================
# 执行引擎事件
# ============================================

@dataclass
class ExecutionStarted(BaseEvent):
    """执行开始事件"""
    conversation_id: int = 0
    agent_id: int = 0
    execution_mode: str = ""


@dataclass
class ExecutionCompleted(BaseEvent):
    """执行完成事件"""
    conversation_id: int = 0
    agent_id: int = 0
    total_tokens: int = 0
    duration_ms: int = 0


@dataclass
class ExecutionFailed(BaseEvent):
    """执行失败事件"""
    conversation_id: int = 0
    agent_id: int = 0
    error: str = ""
    error_type: str = ""


__all__ = [
    "BaseEvent",
    # 智能体
    "AgentCreated",
    "AgentPublished",
    "AgentDisabled",
    # 对话
    "ConversationStarted",
    "MessageAdded",
    "ConversationCompleted",
    # 工具
    "ToolCallRequested",
    "ToolCallCompleted",
    "ToolCallFailed",
    # 配额
    "QuotaWarning",
    "QuotaExceeded",
    # 执行
    "ExecutionStarted",
    "ExecutionCompleted",
    "ExecutionFailed",
]
