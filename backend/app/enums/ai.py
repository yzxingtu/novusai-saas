"""
AI 相关枚举模块

定义 AI 供应商、模型类型、调用状态等枚举
"""

from app.enums.base import LabeledStrEnum


class ProviderTypeEnum(LabeledStrEnum):
    """AI 供应商类型枚举"""
    
    OPENAI_COMPATIBLE = ("openai_compatible", "enum.ai_provider.type.openai_compatible")
    CUSTOM = ("custom", "enum.ai_provider.type.custom")


class ModelTypeEnum(LabeledStrEnum):
    """AI 模型类型枚举"""
    
    CHAT = ("chat", "enum.ai_model.type.chat")
    COMPLETION = ("completion", "enum.ai_model.type.completion")
    EMBEDDING = ("embedding", "enum.ai_model.type.embedding")
    IMAGE = ("image", "enum.ai_model.type.image")


class RequestTypeEnum(LabeledStrEnum):
    """AI 调用请求类型枚举"""
    
    CHAT = ("chat", "enum.ai_request.type.chat")
    COMPLETION = ("completion", "enum.ai_request.type.completion")
    EMBEDDING = ("embedding", "enum.ai_request.type.embedding")
    IMAGE = ("image", "enum.ai_request.type.image")


class CallStatusEnum(LabeledStrEnum):
    """AI 调用状态枚举"""
    
    SUCCESS = ("success", "enum.ai_call.status.success")
    FAILED = ("failed", "enum.ai_call.status.failed")
    TIMEOUT = ("timeout", "enum.ai_call.status.timeout")


class QuotaTypeEnum(LabeledStrEnum):
    """AI 配额类型枚举"""
    
    HARD = ("hard", "enum.ai_quota.type.hard")
    SOFT = ("soft", "enum.ai_quota.type.soft")


class QuotaPeriodEnum(LabeledStrEnum):
    """AI 配额周期枚举"""
    
    DAILY = ("daily", "enum.ai_quota.period.daily")
    MONTHLY = ("monthly", "enum.ai_quota.period.monthly")


class UserTypeEnum(LabeledStrEnum):
    """AI 用户类型枚举"""
    
    TENANT_ADMIN = ("tenant_admin", "enum.ai_user.type.tenant_admin")


__all__ = [
    "ProviderTypeEnum",
    "ModelTypeEnum",
    "RequestTypeEnum",
    "CallStatusEnum",
    "QuotaTypeEnum",
    "QuotaPeriodEnum",
    "UserTypeEnum",
]
