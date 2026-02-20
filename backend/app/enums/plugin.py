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


class PluginStatusEnum(LabeledStrEnum):
    """插件状态枚举"""

    INSTALLED = ("installed", "enum.plugin_status.installed")
    ENABLED = ("enabled", "enum.plugin_status.enabled")
    DISABLED = ("disabled", "enum.plugin_status.disabled")
    ERROR = ("error", "enum.plugin_status.error")


__all__ = [
    "PluginTypeEnum",
    "PluginStatusEnum",
]
