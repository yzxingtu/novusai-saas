"""
插件系统枚举

定义插件相关的状态、作用域、信任等级等枚举类
"""

from app.enums.base import LabeledStrEnum
from app.enums.common import ResourceScopeEnum


class PluginStatusEnum(LabeledStrEnum):
    """插件状态"""

    INSTALLED = ("installed", "enum.plugin_status.installed")
    ENABLED = ("enabled", "enum.plugin_status.enabled")
    DISABLED = ("disabled", "enum.plugin_status.disabled")
    ERROR = ("error", "enum.plugin_status.error")


# [DEPRECATED] PluginScopeEnum 已统一为 ResourceScopeEnum，保留别名兼容旧代码引用
PluginScopeEnum = ResourceScopeEnum


class PluginTierEnum(LabeledStrEnum):
    """插件信任等级"""

    OFFICIAL = ("official", "enum.plugin_tier.official")
    VERIFIED = ("verified", "enum.plugin_tier.verified")
    COMMUNITY = ("community", "enum.plugin_tier.community")


class PluginInstallSourceEnum(LabeledStrEnum):
    """插件安装来源"""

    LOCAL = ("local", "enum.plugin_install_source.local")
    MARKETPLACE = ("marketplace", "enum.plugin_install_source.marketplace")
    GIT = ("git", "enum.plugin_install_source.git")


class PluginPricingTypeEnum(LabeledStrEnum):
    """插件定价类型"""

    FREE = ("free", "enum.plugin_pricing.free")
    PAID = ("paid", "enum.plugin_pricing.paid")


class PluginLicenseTypeEnum(LabeledStrEnum):
    """License 类型"""

    TRIAL = ("trial", "enum.plugin_license.trial")
    PERPETUAL = ("perpetual", "enum.plugin_license.perpetual")


class PluginVersionStatusEnum(LabeledStrEnum):
    """插件版本状态"""

    ACTIVE = ("active", "enum.plugin_version_status.active")
    ARCHIVED = ("archived", "enum.plugin_version_status.archived")
