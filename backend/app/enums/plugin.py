"""
插件系统枚举

定义插件相关的状态、作用域、信任等级等枚举类
"""

from app.enums.base import LabeledStrEnum


class PluginStatusEnum(LabeledStrEnum):
    """插件状态"""

    INSTALLED = ("installed", "enum.plugin_status.installed")
    ENABLED = ("enabled", "enum.plugin_status.enabled")
    DISABLED = ("disabled", "enum.plugin_status.disabled")
    ERROR = ("error", "enum.plugin_status.error")


class PluginScopeEnum(LabeledStrEnum):
    """插件作用域（设计时决定，不可更改）"""

    ADMIN_ONLY = ("admin_only", "enum.plugin_scope.admin_only")
    ALL_TENANTS = ("all_tenants", "enum.plugin_scope.all_tenants")
    ASSIGNED_TENANTS = ("assigned_tenants", "enum.plugin_scope.assigned_tenants")
    ADMIN_AND_ALL = ("admin_and_all", "enum.plugin_scope.admin_and_all")
    ADMIN_AND_ASSIGNED = ("admin_and_assigned", "enum.plugin_scope.admin_and_assigned")


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
