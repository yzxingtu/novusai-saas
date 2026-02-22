"""
插件相关枚举
"""

from app.enums.base import LabeledStrEnum


class PluginTypeEnum(LabeledStrEnum):
    """插件类型枚举"""

    ADAPTER = ("adapter", "enum.plugin_type.adapter")
    TOOL = ("tool", "enum.plugin_type.tool")
    HOOK = ("hook", "enum.plugin_type.hook")
    API = ("api", "enum.plugin_type.api")
    SKILL = ("skill", "enum.plugin_type.skill")
    STORAGE = ("storage", "enum.plugin_type.storage")
    COMPOSITE = ("composite", "enum.plugin_type.composite")


class PluginScopeEnum(LabeledStrEnum):
    """插件作用域枚举"""

    PLATFORM_ONLY = ("platform_only", "enum.plugin_scope.platform_only")
    ALL_TENANTS = ("all_tenants", "enum.plugin_scope.all_tenants")
    ASSIGNED_TENANTS = ("assigned_tenants", "enum.plugin_scope.assigned_tenants")
    GLOBAL = ("global", "enum.plugin_scope.global")


class PluginStatusEnum(LabeledStrEnum):
    """插件状态枚举"""

    INSTALLED = ("installed", "enum.plugin_status.installed")
    ENABLED = ("enabled", "enum.plugin_status.enabled")
    DISABLED = ("disabled", "enum.plugin_status.disabled")
    ERROR = ("error", "enum.plugin_status.error")


class PluginCategoryEnum(LabeledStrEnum):
    """插件分类枚举"""

    AI_MODEL = ("ai_model", "enum.plugin_category.ai_model")
    AI_SKILL = ("ai_skill", "enum.plugin_category.ai_skill")
    STORAGE = ("storage", "enum.plugin_category.storage")
    NOTIFICATION = ("notification", "enum.plugin_category.notification")
    INTEGRATION = ("integration", "enum.plugin_category.integration")
    DEVTOOL = ("devtool", "enum.plugin_category.devtool")
    ANALYTICS = ("analytics", "enum.plugin_category.analytics")
    SECURITY = ("security", "enum.plugin_category.security")
    THEME = ("theme", "enum.plugin_category.theme")
    OTHER = ("other", "enum.plugin_category.other")


class PluginInstallSourceEnum(LabeledStrEnum):
    """插件安装来源枚举"""

    LOCAL = ("local", "enum.plugin_install_source.local")
    MARKETPLACE = ("marketplace", "enum.plugin_install_source.marketplace")
    BUILTIN = ("builtin", "enum.plugin_install_source.builtin")
    ENTRY_POINT = ("entry_point", "enum.plugin_install_source.entry_point")


__all__ = [
    "PluginTypeEnum",
    "PluginScopeEnum",
    "PluginStatusEnum",
    "PluginCategoryEnum",
    "PluginInstallSourceEnum",
]
