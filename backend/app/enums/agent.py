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
    ROUTER = ("router", "enum.agent.execution_mode.router")


class MemorySceneEnum(LabeledStrEnum):
    """会话记忆场景枚举"""

    AI_CHAT_PAGE = ("ai_chat_page", "enum.agent.memory_scene.ai_chat_page")
    ADMIN_CHAT = ("admin_chat", "enum.agent.memory_scene.admin_chat")
    PLUGIN = ("plugin", "enum.agent.memory_scene.plugin")
    AI_GATEWAY = ("ai_gateway", "enum.agent.memory_scene.ai_gateway")
    UNKNOWN = ("unknown", "enum.agent.memory_scene.unknown")


class MemoryChannelEnum(LabeledStrEnum):
    """会话记忆渠道枚举"""

    TENANT_CHAT = ("tenant_chat", "enum.agent.memory_channel.tenant_chat")
    ADMIN_CHAT = ("admin_chat", "enum.agent.memory_channel.admin_chat")
    USER_CHAT = ("user_chat", "enum.agent.memory_channel.user_chat")
    PLUGIN = ("plugin", "enum.agent.memory_channel.plugin")
    SYSTEM = ("system", "enum.agent.memory_channel.system")


class ToolTypeEnum(LabeledStrEnum):
    """智能体工具类型枚举"""

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


class ActionLevelEnum(LabeledStrEnum):
    """操作安全等级枚举"""

    READ = ("read", "enum.action_level.read")
    SAFE_WRITE = ("safe_write", "enum.action_level.safe_write")
    DANGEROUS = ("dangerous", "enum.action_level.dangerous")


class ActionTypeEnum(LabeledStrEnum):
    """操作类型枚举"""

    QUERY = ("query", "enum.action_type.query")
    ACTION = ("action", "enum.action_type.action")
    CONFIRM = ("confirm", "enum.action_type.confirm")


class ActionStatusEnum(LabeledStrEnum):
    """操作执行状态枚举"""

    SUCCESS = ("success", "enum.action_status.success")
    FAILED = ("failed", "enum.action_status.failed")
    REJECTED = ("rejected", "enum.action_status.rejected")
    PENDING_CONFIRM = ("pending_confirm", "enum.action_status.pending_confirm")


class ActionResultTypeEnum(LabeledStrEnum):
    """操作返回结果类型枚举"""

    RESULT = ("result", "enum.action_result_type.result")
    ERROR = ("error", "enum.action_result_type.error")
    GUIDANCE = ("guidance", "enum.action_result_type.guidance")
    CONFIRM_REQUIRED = ("confirm_required", "enum.action_result_type.confirm_required")


class ConfirmActionEnum(LabeledStrEnum):
    """操作确认动作枚举"""

    CONFIRM = ("confirm", "enum.confirm_action.confirm")
    CANCEL = ("cancel", "enum.confirm_action.cancel")


class SkillTypeEnum(LabeledStrEnum):
    """技能类型枚举"""

    KNOWLEDGE_BASE = ("knowledge_base", "enum.skill.type.knowledge_base")
    DATA_INTELLIGENCE = ("data_intelligence", "enum.skill.type.data_intelligence")
    TOOLKIT = ("toolkit", "enum.skill.type.toolkit")
    BUILTIN = ("builtin", "enum.skill.type.builtin")
    HTTP = ("http", "enum.skill.type.http")
    EMAIL = ("email", "enum.skill.type.email")
    CODE_EXECUTION = ("code_execution", "enum.skill.type.code_execution")



class ToolConsentModeEnum(LabeledStrEnum):
    """工具执行授权模式枚举"""

    AUTO = ("auto", "enum.tool_consent.auto")
    ASK = ("ask", "enum.tool_consent.ask")
    REJECT = ("reject", "enum.tool_consent.reject")


class BatchRunStatusEnum(LabeledStrEnum):
    """批处理运行状态枚举"""

    PENDING = ("pending", "enum.agent.batch_run_status.pending")
    RUNNING = ("running", "enum.agent.batch_run_status.running")
    COMPLETED = ("completed", "enum.agent.batch_run_status.completed")
    PARTIAL_FAILED = ("partial_failed", "enum.agent.batch_run_status.partial_failed")
    FAILED = ("failed", "enum.agent.batch_run_status.failed")
    CANCELLED = ("cancelled", "enum.agent.batch_run_status.cancelled")


def get_all_skill_types() -> set[str]:
    """
    获取所有有效的技能类型

    Returns:
        技能类型值的集合
    """
    return {e.value for e in SkillTypeEnum}


def get_skill_type_options() -> list[dict[str, str]]:
    """
    获取技能类型选项列表（供 API 返回）

    Returns:
        [{"value": "http", "label": "...", "source": "builtin"}]
    """
    options: list[dict[str, str]] = []
    for e in SkillTypeEnum:
        options.append({
            "value": e.value,
            "label": e.label,
            "source": "builtin",
        })
    return options



__all__ = [
    "AgentStatusEnum",
    "AgentExecutionModeEnum",
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
