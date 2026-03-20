"""
AI 相关枚举模块 / AI Enum Module

定义 AI 供应商、模型类型、调用状态等枚举
Defines AI provider, model type, call status enums.
"""

from app.enums.base import LabeledStrEnum


class ProviderTypeEnum(LabeledStrEnum):
    """AI Provider Type Enum / AI 供应商类型枚举"""

    OPENAI_COMPATIBLE = ("openai_compatible", "enum.ai_provider.type.openai_compatible")
    CUSTOM = ("custom", "enum.ai_provider.type.custom")


class ModelTypeEnum(LabeledStrEnum):
    """AI Model Type Enum / AI 模型类型枚举"""

    CHAT = ("chat", "enum.ai_model.type.chat")
    COMPLETION = ("completion", "enum.ai_model.type.completion")
    EMBEDDING = ("embedding", "enum.ai_model.type.embedding")
    IMAGE = ("image", "enum.ai_model.type.image")


class RequestTypeEnum(LabeledStrEnum):
    """AI Request Type Enum / AI 调用请求类型枚举"""

    CHAT = ("chat", "enum.ai_request.type.chat")
    COMPLETION = ("completion", "enum.ai_request.type.completion")
    EMBEDDING = ("embedding", "enum.ai_request.type.embedding")
    IMAGE = ("image", "enum.ai_request.type.image")


class CallStatusEnum(LabeledStrEnum):
    """AI Call Status Enum / AI 调用状态枚举"""

    SUCCESS = ("success", "enum.ai_call.status.success")
    FAILED = ("failed", "enum.ai_call.status.failed")
    TIMEOUT = ("timeout", "enum.ai_call.status.timeout")


class QuotaTypeEnum(LabeledStrEnum):
    """AI Quota Type Enum / AI 配额类型枚举"""

    HARD = ("hard", "enum.ai_quota.type.hard")
    SOFT = ("soft", "enum.ai_quota.type.soft")


class QuotaPeriodEnum(LabeledStrEnum):
    """AI Quota Period Enum / AI 配额周期枚举"""

    DAILY = ("daily", "enum.ai_quota.period.daily")
    MONTHLY = ("monthly", "enum.ai_quota.period.monthly")


class UserTypeEnum(LabeledStrEnum):
    """AI User Type Enum / AI 用户类型枚举（与 call_log / audit 的 user_type 字符串对齐）"""

    ADMIN = ("admin", "enum.ai_user.type.admin")
    TENANT_ADMIN = ("tenant_admin", "enum.ai_user.type.tenant_admin")
    TENANT_USER = ("tenant_user", "enum.ai_user.type.tenant_user")


class ModelTierEnum(LabeledStrEnum):
    """AI Model Tier Enum (for multi-model routing) / AI 模型级别枚举（用于多模型路由策略）"""

    FAST = ("fast", "enum.ai_model.tier.fast")
    STANDARD = ("standard", "enum.ai_model.tier.standard")
    PREMIUM = ("premium", "enum.ai_model.tier.premium")


class ToolParameterTypeEnum(LabeledStrEnum):
    """Tool Parameter Type Enum / 工具参数类型枚举"""

    STRING = ("string", "enum.tool_parameter_type.string")
    INTEGER = ("integer", "enum.tool_parameter_type.integer")
    NUMBER = ("number", "enum.tool_parameter_type.number")
    BOOLEAN = ("boolean", "enum.tool_parameter_type.boolean")
    ARRAY = ("array", "enum.tool_parameter_type.array")
    OBJECT = ("object", "enum.tool_parameter_type.object")


__all__ = [
    "ProviderTypeEnum",
    "ModelTypeEnum",
    "ModelTierEnum",
    "RequestTypeEnum",
    "CallStatusEnum",
    "QuotaTypeEnum",
    "QuotaPeriodEnum",
    "UserTypeEnum",
    "ToolParameterTypeEnum",
]
