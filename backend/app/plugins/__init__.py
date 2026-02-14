"""
插件系统核心模块

提供插件基类、上下文、扩展点接口和生命周期管理
"""

from app.plugins.base import BasePlugin
from app.plugins.context import PluginContext
from app.plugins.extensions.adapter_plugin import AdapterPlugin
from app.plugins.extensions.tool_plugin import ToolPlugin
from app.plugins.extensions.hook_plugin import HookPlugin
from app.plugins.extensions.api_plugin import ApiPlugin
from app.plugins.extensions.skill_plugin import SkillPlugin
from app.plugins.manager import PluginManager, get_plugin_manager

__all__ = [
    "BasePlugin",
    "PluginContext",
    "AdapterPlugin",
    "ToolPlugin",
    "HookPlugin",
    "ApiPlugin",
    "SkillPlugin",
    "PluginManager",
    "get_plugin_manager",
]
