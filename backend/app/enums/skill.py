"""
Skill-domain enums.
"""

from app.enums.base import LabeledStrEnum


class SkillSourceTypeEnum(LabeledStrEnum):
    """Skill source type / 技能来源类型"""

    PLATFORM_BUILTIN = ("platform_builtin", "enum.skill.source.platform_builtin")
    PLUGIN = ("plugin", "enum.skill.source.plugin")
    CUSTOM = ("custom", "enum.skill.source.custom")


class SkillStatusEnum(LabeledStrEnum):
    """Skill status / 技能状态"""

    DRAFT = ("draft", "enum.skill.status.draft")
    ACTIVE = ("active", "enum.skill.status.active")
    DISABLED = ("disabled", "enum.skill.status.disabled")


class SkillResourceTypeEnum(LabeledStrEnum):
    """Skill resource type / 技能资源类型"""

    REFERENCE = ("reference", "enum.skill.resource.reference")
    EXAMPLE = ("example", "enum.skill.resource.example")
    SCRIPT = ("script", "enum.skill.resource.script")
    OTHER = ("other", "enum.skill.resource.other")


class CapabilityExecutorTypeEnum(LabeledStrEnum):
    """Capability executor type / 能力执行器类型"""

    BUILTIN = ("builtin", "enum.capability.executor.builtin")
    PLUGIN = ("plugin", "enum.capability.executor.plugin")
    HTTP = ("http", "enum.capability.executor.http")
    EMAIL = ("email", "enum.capability.executor.email")
    CODE_EXECUTION = ("code_execution", "enum.capability.executor.code_execution")


class CapabilityStatusEnum(LabeledStrEnum):
    """Capability status / 能力状态"""

    ACTIVE = ("active", "enum.capability.status.active")
    DISABLED = ("disabled", "enum.capability.status.disabled")


class SkillActivationModeEnum(LabeledStrEnum):
    """Skill capability activation mode / 技能能力激活模式"""

    DEFAULT = ("default", "enum.skill.activation.default")
    ON_DEMAND = ("on_demand", "enum.skill.activation.on_demand")


__all__ = [
    "SkillSourceTypeEnum",
    "SkillStatusEnum",
    "SkillResourceTypeEnum",
    "CapabilityExecutorTypeEnum",
    "CapabilityStatusEnum",
    "SkillActivationModeEnum",
]
