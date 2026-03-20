"""
智能体相关枚举模块 / Agent Enum Module

定义智能体状态、执行模式、工具类型、对话状态、消息角色等枚举
Defines agent status, execution mode, tool type, conversation status, message role enums.
"""

from app.enums.base import LabeledStrEnum


class AgentStatusEnum(LabeledStrEnum):
    """Agent Status Enum / 智能体状态枚举"""

    DRAFT = ("draft", "enum.agent.status.draft")
    PUBLISHED = ("published", "enum.agent.status.published")
    DISABLED = ("disabled", "enum.agent.status.disabled")


class AgentExecutionModeEnum(LabeledStrEnum):
    """Agent Execution Mode Enum / 智能体执行模式枚举"""

    CONVERSATION = ("conversation", "enum.agent.execution_mode.conversation")
    TASK = ("task", "enum.agent.execution_mode.task")
    BATCH = ("batch", "enum.agent.execution_mode.batch")
    API = ("api", "enum.agent.execution_mode.api")
    ROUTER = ("router", "enum.agent.execution_mode.router")


class AgentOwnerTypeEnum(LabeledStrEnum):
    """Agent Owner Type Enum / 智能体归属类型枚举"""

    PLATFORM = ("platform", "enum.agent.owner_type.platform")
    TENANT = ("tenant", "enum.agent.owner_type.tenant")


class AgentDistributionModeEnum(LabeledStrEnum):
    """Agent Distribution Mode Enum / 智能体分发模式枚举"""

    INTERNAL = ("internal", "enum.agent.distribution_mode.internal")
    ALL_TENANTS = ("all_tenants", "enum.agent.distribution_mode.all_tenants")
    ASSIGNED_TENANTS = ("assigned_tenants", "enum.agent.distribution_mode.assigned_tenants")
    OWNER_ONLY = ("owner_only", "enum.agent.distribution_mode.owner_only")


class AgentPublicationAccessTypeEnum(LabeledStrEnum):
    """Tenant Agent Publication Access Type Enum / 企业用户发布访问类型枚举"""

    ALL_USERS = ("all_users", "enum.agent.publication_access_type.all_users")
    TENANT_USER_ROLES = ("tenant_user_roles", "enum.agent.publication_access_type.tenant_user_roles")
    ORG_NODE = ("org_node", "enum.agent.publication_access_type.org_node")
    SPECIFIC_USERS = ("specific_users", "enum.agent.publication_access_type.specific_users")


class MemorySceneEnum(LabeledStrEnum):
    """Session Memory Scene Enum / 会话记忆场景枚举"""

    AI_CHAT_PAGE = ("ai_chat_page", "enum.agent.memory_scene.ai_chat_page")
    ADMIN_CHAT = ("admin_chat", "enum.agent.memory_scene.admin_chat")
    PLUGIN = ("plugin", "enum.agent.memory_scene.plugin")
    AI_GATEWAY = ("ai_gateway", "enum.agent.memory_scene.ai_gateway")
    UNKNOWN = ("unknown", "enum.agent.memory_scene.unknown")


class MemoryChannelEnum(LabeledStrEnum):
    """Session Memory Channel Enum / 会话记忆渠道枚举"""

    TENANT_CHAT = ("tenant_chat", "enum.agent.memory_channel.tenant_chat")
    ADMIN_CHAT = ("admin_chat", "enum.agent.memory_channel.admin_chat")
    USER_CHAT = ("user_chat", "enum.agent.memory_channel.user_chat")
    PLUGIN = ("plugin", "enum.agent.memory_channel.plugin")
    SYSTEM = ("system", "enum.agent.memory_channel.system")


class ToolTypeEnum(LabeledStrEnum):
    """Agent Tool Type Enum / 智能体工具类型枚举"""

    TOOLKIT = ("toolkit", "enum.agent.tool_type.toolkit")
    BUILTIN = ("builtin", "enum.agent.tool_type.builtin")
    TEXT_TO_SQL = ("text_to_sql", "enum.agent.tool_type.text_to_sql")
    DATA_CREATE = ("data_create", "enum.agent.tool_type.data_create")
    DATA_UPDATE = ("data_update", "enum.agent.tool_type.data_update")
    DATA_DELETE = ("data_delete", "enum.agent.tool_type.data_delete")
    HTTP = ("http", "enum.agent.tool_type.http")
    EMAIL = ("email", "enum.agent.tool_type.email")
    CODE_EXECUTION = ("code_execution", "enum.agent.tool_type.code_execution")


class ConversationStatusEnum(LabeledStrEnum):
    """Conversation Status Enum / 对话状态枚举"""

    ACTIVE = ("active", "enum.agent.conversation_status.active")
    ARCHIVED = ("archived", "enum.agent.conversation_status.archived")


class MessageRoleEnum(LabeledStrEnum):
    """Message Role Enum / 对话消息角色枚举"""

    SYSTEM = ("system", "enum.agent.message_role.system")
    USER = ("user", "enum.agent.message_role.user")
    ASSISTANT = ("assistant", "enum.agent.message_role.assistant")
    TOOL = ("tool", "enum.agent.message_role.tool")


class AgentVisibilityEnum(LabeledStrEnum):
    """Agent Visibility Enum / 智能体可见性枚举"""

    PUBLIC = ("public", "enum.agent.visibility.public")
    PRIVATE = ("private", "enum.agent.visibility.private")


class AccessTypeEnum(LabeledStrEnum):
    """Agent Access Type Enum / 智能体访问类型枚举"""

    ALL_USERS = ("all_users", "enum.agent.access_type.all_users")
    ORG_NODE = ("org_node", "enum.agent.access_type.org_node")
    SPECIFIC_USERS = ("specific_users", "enum.agent.access_type.specific_users")
    API_ONLY = ("api_only", "enum.agent.access_type.api_only")


class InputVariableTypeEnum(LabeledStrEnum):
    """Agent Input Variable Type Enum / 智能体输入变量类型枚举"""

    TEXT = ("text", "enum.agent.input_variable_type.text")
    NUMBER = ("number", "enum.agent.input_variable_type.number")
    SELECT = ("select", "enum.agent.input_variable_type.select")
    TEXTAREA = ("textarea", "enum.agent.input_variable_type.textarea")


class ActionLevelEnum(LabeledStrEnum):
    """Action Safety Level Enum / 操作安全等级枚举"""

    READ = ("read", "enum.action_level.read")
    SAFE_WRITE = ("safe_write", "enum.action_level.safe_write")
    DANGEROUS = ("dangerous", "enum.action_level.dangerous")


class ActionTypeEnum(LabeledStrEnum):
    """Action Type Enum / 操作类型枚举"""

    QUERY = ("query", "enum.action_type.query")
    ACTION = ("action", "enum.action_type.action")
    CONFIRM = ("confirm", "enum.action_type.confirm")


class ActionStatusEnum(LabeledStrEnum):
    """Action Execution Status Enum / 操作执行状态枚举"""

    SUCCESS = ("success", "enum.action_status.success")
    FAILED = ("failed", "enum.action_status.failed")
    REJECTED = ("rejected", "enum.action_status.rejected")
    PENDING_CONFIRM = ("pending_confirm", "enum.action_status.pending_confirm")


class ActionResultTypeEnum(LabeledStrEnum):
    """Action Result Type Enum / 操作返回结果类型枚举"""

    RESULT = ("result", "enum.action_result_type.result")
    ERROR = ("error", "enum.action_result_type.error")
    GUIDANCE = ("guidance", "enum.action_result_type.guidance")
    CONFIRM_REQUIRED = ("confirm_required", "enum.action_result_type.confirm_required")


class ConfirmActionEnum(LabeledStrEnum):
    """Confirm Action Enum / 操作确认动作枚举"""

    CONFIRM = ("confirm", "enum.confirm_action.confirm")
    CANCEL = ("cancel", "enum.confirm_action.cancel")


class SkillTypeEnum(LabeledStrEnum):
    """Skill Type Enum / 技能类型枚举"""

    DATA_INTELLIGENCE = ("data_intelligence", "enum.skill.type.data_intelligence")
    TOOLKIT = ("toolkit", "enum.skill.type.toolkit")
    BUILTIN = ("builtin", "enum.skill.type.builtin")
    HTTP = ("http", "enum.skill.type.http")
    EMAIL = ("email", "enum.skill.type.email")
    CODE_EXECUTION = ("code_execution", "enum.skill.type.code_execution")



class ToolConsentModeEnum(LabeledStrEnum):
    """Tool Consent Mode Enum / 工具执行授权模式枚举"""

    AUTO = ("auto", "enum.tool_consent.auto")
    ASK = ("ask", "enum.tool_consent.ask")
    REJECT = ("reject", "enum.tool_consent.reject")


class BatchRunStatusEnum(LabeledStrEnum):
    """Batch Run Status Enum / 批处理运行状态枚举"""

    PENDING = ("pending", "enum.agent.batch_run_status.pending")
    RUNNING = ("running", "enum.agent.batch_run_status.running")
    COMPLETED = ("completed", "enum.agent.batch_run_status.completed")
    PARTIAL_FAILED = ("partial_failed", "enum.agent.batch_run_status.partial_failed")
    FAILED = ("failed", "enum.agent.batch_run_status.failed")
    CANCELLED = ("cancelled", "enum.agent.batch_run_status.cancelled")


def get_all_skill_types() -> set[str]:
    """
    Get all valid skill types / 获取所有有效的技能类型

    Returns:
        Set of skill type values / 技能类型值的集合
    """
    return {e.value for e in SkillTypeEnum}


def get_skill_type_options() -> list[dict[str, str]]:
    """
    Get skill type option list (for API response) / 获取技能类型选项列表（供 API 返回）

    Returns:
        [{"value": "http", "label": "...", "source": "builtin"}]
    """
    return [
        {"value": e.value, "label": e.label, "source": "builtin"}
        for e in SkillTypeEnum
    ]



__all__ = [
    "AgentStatusEnum",
    "AgentExecutionModeEnum",
    "AgentOwnerTypeEnum",
    "AgentDistributionModeEnum",
    "AgentPublicationAccessTypeEnum",
    "MemorySceneEnum",
    "MemoryChannelEnum",
    "ToolTypeEnum",
    "SkillTypeEnum",
    "ConversationStatusEnum",
    "MessageRoleEnum",
    "AgentVisibilityEnum",
    "AccessTypeEnum",
    "InputVariableTypeEnum",
    "ActionLevelEnum",
    "ActionTypeEnum",
    "ActionStatusEnum",
    "ActionResultTypeEnum",
    "ConfirmActionEnum",
    "ToolConsentModeEnum",
    "BatchRunStatusEnum",
    "get_all_skill_types",
    "get_skill_type_options",
]
