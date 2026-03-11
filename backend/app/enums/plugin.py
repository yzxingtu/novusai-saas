"""
插件系统枚举 / Plugin System Enums

定义插件相关的状态、作用域、信任等级等枚举类
Defines plugin status, scope, trust tier and other enum classes.
"""

from app.enums.base import LabeledStrEnum
from app.enums.common import ResourceScopeEnum


class PluginStatusEnum(LabeledStrEnum):
    """Plugin Status Enum / 插件状态枚举"""

    INSTALLED = ("installed", "enum.plugin_status.installed")
    ENABLED = ("enabled", "enum.plugin_status.enabled")
    DISABLED = ("disabled", "enum.plugin_status.disabled")
    ERROR = ("error", "enum.plugin_status.error")


# [DEPRECATED] PluginScopeEnum unified to ResourceScopeEnum, alias kept for backward compat / PluginScopeEnum 已统一为 ResourceScopeEnum，保留别名兼容旧代码引用
PluginScopeEnum = ResourceScopeEnum


class PluginTierEnum(LabeledStrEnum):
    """Plugin Trust Tier Enum / 插件信任等级枚举"""

    OFFICIAL = ("official", "enum.plugin_tier.official")
    VERIFIED = ("verified", "enum.plugin_tier.verified")
    COMMUNITY = ("community", "enum.plugin_tier.community")


class PluginInstallSourceEnum(LabeledStrEnum):
    """Plugin Install Source Enum / 插件安装来源枚举"""

    LOCAL = ("local", "enum.plugin_install_source.local")
    MARKETPLACE = ("marketplace", "enum.plugin_install_source.marketplace")
    GIT = ("git", "enum.plugin_install_source.git")


class PluginPricingTypeEnum(LabeledStrEnum):
    """Plugin Pricing Type Enum / 插件定价类型枚举"""

    FREE = ("free", "enum.plugin_pricing.free")
    PAID = ("paid", "enum.plugin_pricing.paid")


class PluginLicenseTypeEnum(LabeledStrEnum):
    """License Type Enum / License 类型枚举"""

    TRIAL = ("trial", "enum.plugin_license.trial")
    PERPETUAL = ("perpetual", "enum.plugin_license.perpetual")


class PluginVersionStatusEnum(LabeledStrEnum):
    """Plugin Version Status Enum / 插件版本状态枚举"""

    ACTIVE = ("active", "enum.plugin_version_status.active")
    ARCHIVED = ("archived", "enum.plugin_version_status.archived")


class FrontendSlotTypeEnum(LabeledStrEnum):
    """Plugin Frontend Slot Type Enum / 插件前端插槽类型枚举"""

    HEADER_WIDGET = ("header_widget", "enum.frontend_slot_type.header_widget")
    DASHBOARD_WIDGET = ("dashboard_widget", "enum.frontend_slot_type.dashboard_widget")
    SETTINGS_TAB = ("settings_tab", "enum.frontend_slot_type.settings_tab")
    FLOATING_PANEL = ("floating_panel", "enum.frontend_slot_type.floating_panel")
    STANDALONE_PAGE = ("standalone_page", "enum.frontend_slot_type.standalone_page")
    NOTIFICATION_UI = ("notification_ui", "enum.frontend_slot_type.notification_ui")
