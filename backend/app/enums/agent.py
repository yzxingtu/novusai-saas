"""
智能体相关枚举模块

定义智能体状态、执行模式、工具类型、对话状态、消息角色等枚举
"""

from app.enums.base import LabeledStrEnum


class AgentStatusEnum(LabeledStrEnum):
    """智能体状态枚举"""

    DRAFT = ("draft", "enum.agent.status.draft")
    PUBLISHED = ("published", "enum.agent.status.published")
    DISABLED = ("disabled", "enum.agent.status.disabled")


class AgentExecutionModeEnum(LabeledStrEnum):
    """智能体执行模式枚举"""

    CONVERSATION = ("conversation", "enum.agent.execution_mode.conversation")
    TASK = ("task", "enum.agent.execution_mode.task")
    BATCH = ("batch", "enum.agent.execution_mode.batch")
    API = ("api", "enum.agent.execution_mode.api")


class ToolTypeEnum(LabeledStrEnum):
    """智能体工具类型枚举"""

    HTTP = ("http", "enum.agent.tool_type.http")
    DATABASE = ("database", "enum.agent.tool_type.database")
    EMAIL = ("email", "enum.agent.tool_type.email")
    CODE = ("code", "enum.agent.tool_type.code")
    BUILTIN = ("builtin", "enum.agent.tool_type.builtin")


class ConversationStatusEnum(LabeledStrEnum):
    """对话状态枚举"""

    ACTIVE = ("active", "enum.agent.conversation_status.active")
    ARCHIVED = ("archived", "enum.agent.conversation_status.archived")


class MessageRoleEnum(LabeledStrEnum):
    """对话消息角色枚举"""

    SYSTEM = ("system", "enum.agent.message_role.system")
    USER = ("user", "enum.agent.message_role.user")
    ASSISTANT = ("assistant", "enum.agent.message_role.assistant")
    TOOL = ("tool", "enum.agent.message_role.tool")


class AgentVisibilityEnum(LabeledStrEnum):
    """智能体可见性枚举"""

    PUBLIC = ("public", "enum.agent.visibility.public")
    PRIVATE = ("private", "enum.agent.visibility.private")


class AccessTypeEnum(LabeledStrEnum):
    """智能体访问类型枚举"""

    ALL_USERS = ("all_users", "enum.agent.access_type.all_users")
    ORG_NODE = ("org_node", "enum.agent.access_type.org_node")
    SPECIFIC_USERS = ("specific_users", "enum.agent.access_type.specific_users")
    API_ONLY = ("api_only", "enum.agent.access_type.api_only")


class InputVariableTypeEnum(LabeledStrEnum):
    """智能体输入变量类型枚举"""

    TEXT = ("text", "enum.agent.input_variable_type.text")
    NUMBER = ("number", "enum.agent.input_variable_type.number")
    SELECT = ("select", "enum.agent.input_variable_type.select")
    TEXTAREA = ("textarea", "enum.agent.input_variable_type.textarea")


class BatchRunStatusEnum(LabeledStrEnum):
    """批处理运行状态枚举"""

    PENDING = ("pending", "enum.agent.batch_run_status.pending")
    RUNNING = ("running", "enum.agent.batch_run_status.running")
    COMPLETED = ("completed", "enum.agent.batch_run_status.completed")
    PARTIAL_FAILED = ("partial_failed", "enum.agent.batch_run_status.partial_failed")
    FAILED = ("failed", "enum.agent.batch_run_status.failed")
    CANCELLED = ("cancelled", "enum.agent.batch_run_status.cancelled")


__all__ = [
    "AgentStatusEnum",
    "AgentExecutionModeEnum",
    "ToolTypeEnum",
    "ConversationStatusEnum",
    "MessageRoleEnum",
    "AgentVisibilityEnum",
    "AccessTypeEnum",
    "InputVariableTypeEnum",
    "BatchRunStatusEnum",
]
