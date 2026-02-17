"""
插件加载器

负责插件类的动态导入、实例化和缓存管理。
从 PluginManager 提取，降低 God Object 复杂度。
"""

from __future__ import annotations

import importlib

from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.plugin import PluginTypeEnum
from app.exceptions import BusinessException
from app.plugins.base import BasePlugin
from app.plugins.extensions.adapter_plugin import AdapterPlugin
from app.plugins.extensions.api_plugin import ApiPlugin
from app.plugins.extensions.hook_plugin import HookPlugin
from app.plugins.extensions.skill_plugin import SkillPlugin
from app.plugins.extensions.tool_plugin import ToolPlugin

logger = LogManager.get_logger("app")


def resolve_plugin_type(plugin_instance: BasePlugin) -> str:
    """根据插件实例的类型推断 plugin_type"""
    type_map: list[tuple[type, str]] = [
        (AdapterPlugin, PluginTypeEnum.ADAPTER.value),
        (ToolPlugin, PluginTypeEnum.TOOL.value),
        (HookPlugin, PluginTypeEnum.HOOK.value),
        (ApiPlugin, PluginTypeEnum.API.value),
        (SkillPlugin, PluginTypeEnum.SKILL.value),
    ]
    types_found: list[str] = []
    for cls, type_val in type_map:
        if isinstance(plugin_instance, cls):
            types_found.append(type_val)

    if len(types_found) == 0:
        return PluginTypeEnum.COMPOSITE.value
    if len(types_found) == 1:
        return types_found[0]
    return PluginTypeEnum.COMPOSITE.value


class PluginLoader:
    """
    插件加载器

    职责：
    - 从 entry_point 动态导入插件类
    - 实例化并缓存插件实例
    - 管理实例生命周期（获取/缓存/移除）
    """

    def __init__(self) -> None:
        # plugin_name -> loaded BasePlugin instance (in-memory cache)
        self._instances: dict[str, BasePlugin] = {}

    # ========================================
    # 动态加载
    # ========================================

    @staticmethod
    def load_plugin_class(entry_point: str) -> type[BasePlugin]:
        """
        从 entry_point 路径动态加载插件类

        Args:
            entry_point: 完整 Python 路径（如 app.plugins.anthropic.main.AnthropicPlugin）

        Returns:
            BasePlugin 子类

        Raises:
            BusinessException: 加载失败
        """
        try:
            module_path, class_name = entry_point.rsplit(".", 1)
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
        except (ValueError, ModuleNotFoundError, AttributeError) as exc:
            raise BusinessException(
                _("plugin.entry_point_not_found", entry_point=entry_point)
            ) from exc

        if not isinstance(cls, type) or not issubclass(cls, BasePlugin):
            raise BusinessException(
                _("plugin.entry_point_not_found", entry_point=entry_point)
            )

        return cls

    def get_or_load_instance(self, name: str, entry_point: str) -> BasePlugin:
        """
        获取已缓存的插件实例，或动态加载并缓存

        Args:
            name: 插件名称
            entry_point: 入口点路径

        Returns:
            BasePlugin 实例
        """
        if name in self._instances:
            return self._instances[name]

        plugin_cls = self.load_plugin_class(entry_point)
        instance = plugin_cls()
        self._instances[name] = instance
        return instance

    # ========================================
    # 缓存管理
    # ========================================

    def get_instance(self, name: str) -> BasePlugin | None:
        """获取已缓存的插件实例"""
        return self._instances.get(name)

    def set_instance(self, name: str, instance: BasePlugin) -> None:
        """缓存插件实例"""
        self._instances[name] = instance

    def pop_instance(self, name: str) -> BasePlugin | None:
        """移除并返回已缓存的插件实例"""
        return self._instances.pop(name, None)

    def has_instance(self, name: str) -> bool:
        """检查是否已缓存某插件实例"""
        return name in self._instances

    @property
    def instances(self) -> dict[str, BasePlugin]:
        """获取所有已缓存的插件实例（只读副本）"""
        return dict(self._instances)


__all__ = ["PluginLoader", "resolve_plugin_type"]
