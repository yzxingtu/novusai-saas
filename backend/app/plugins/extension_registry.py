"""
插件扩展点注册表

负责管理插件扩展点的注册和注销（Adapter、Hook、Tool、Skill、Api）。
从 PluginManager 提取，降低 God Object 复杂度。
"""

from __future__ import annotations

from typing import Any

from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import ConflictException
from app.plugins.base import BasePlugin
from app.plugins.context import PluginContext
from app.plugins.extensions.adapter_plugin import AdapterPlugin
from app.plugins.extensions.api_plugin import ApiPlugin
from app.plugins.extensions.hook_plugin import HookPlugin
from app.plugins.extensions.skill_plugin import SkillPlugin
from app.plugins.extensions.tool_plugin import ToolPlugin
from app.plugins.route_manager import PluginRouteManager

logger = LogManager.get_logger("app")


class ExtensionRegistry:
    """
    插件扩展点注册表

    职责：
    - 注册/注销 Adapter、Hook、Tool、Skill、Api 扩展点
    - 维护扩展点映射关系
    - 提供 Skill 查询接口
    """

    def __init__(self, route_manager: PluginRouteManager) -> None:
        self._route_manager = route_manager
        # provider_type -> plugin_name
        self._plugin_adapters: dict[str, str] = {}
        # tool_name -> plugin_name
        self._plugin_tools: dict[str, str] = {}
        # skill_type -> plugin_name
        self._plugin_skills: dict[str, str] = {}
        # skill_type -> SkillPlugin instance
        self._skill_instances: dict[str, SkillPlugin] = {}

    # ========================================
    # 注册 / 注销
    # ========================================

    def register(self, instance: BasePlugin, ctx: PluginContext) -> None:
        """启用时注册扩展点到对应的系统组件"""
        if isinstance(instance, AdapterPlugin):
            from app.ai.adapters import AdapterRegistry
            provider_info = instance.get_provider_info()
            provider_type = provider_info.get("name", instance.name)
            adapter_class = instance.get_adapter_class()
            AdapterRegistry.register(provider_type, adapter_class)
            self._plugin_adapters[provider_type] = instance.name
            logger.info(
                "Adapter plugin registered: %s -> %s",
                provider_type, adapter_class.__name__,
            )

        if isinstance(instance, HookPlugin) and ctx.event_bus:
            for event_type, handler, priority in instance.get_event_handlers():
                ctx.event_bus.subscribe(event_type, handler, priority)
                logger.debug(
                    "Hook registered: %s -> %s",
                    event_type.__name__, handler.__qualname__,
                )

        if isinstance(instance, ToolPlugin) and ctx.tool_registry:
            for tool_def in instance.get_tool_definitions():
                ctx.tool_registry.register(tool_def)
                self._plugin_tools[tool_def.name] = instance.name
                logger.debug("Tool registered: %s (plugin=%s)", tool_def.name, instance.name)

        if isinstance(instance, SkillPlugin):
            skill_type = instance.get_skill_type()
            existing_owner = self._plugin_skills.get(skill_type)
            if existing_owner and existing_owner != instance.name:
                raise ConflictException(
                    _("plugin.skill_type_conflict"),
                )
            self._plugin_skills[skill_type] = instance.name
            self._skill_instances[skill_type] = instance
            logger.info(
                "Skill plugin registered: type=%s plugin=%s",
                skill_type, instance.name,
            )

        if isinstance(instance, ApiPlugin) and self._route_manager.app is not None:
            self._route_manager.mount_plugin_routes(instance)

    def unregister(self, instance: BasePlugin, ctx: PluginContext) -> None:
        """禁用时从系统组件中注销扩展点"""
        if isinstance(instance, AdapterPlugin):
            from app.ai.adapters import AdapterRegistry
            provider_info = instance.get_provider_info()
            provider_type = provider_info.get("name", instance.name)
            AdapterRegistry.unregister(provider_type)
            self._plugin_adapters.pop(provider_type, None)
            logger.info("Adapter plugin unregistered: %s", provider_type)

        if isinstance(instance, HookPlugin) and ctx.event_bus:
            for event_type, handler, _priority in instance.get_event_handlers():
                ctx.event_bus.unsubscribe(event_type, handler)
                logger.debug(
                    "Hook unregistered: %s -> %s",
                    event_type.__name__, handler.__qualname__,
                )

        if isinstance(instance, ToolPlugin) and ctx.tool_registry:
            for tool_def in instance.get_tool_definitions():
                ctx.tool_registry.unregister(tool_def.name)
                self._plugin_tools.pop(tool_def.name, None)
                logger.debug("Tool unregistered: %s (plugin=%s)", tool_def.name, instance.name)

        if isinstance(instance, SkillPlugin):
            skill_type = instance.get_skill_type()
            self._plugin_skills.pop(skill_type, None)
            self._skill_instances.pop(skill_type, None)
            logger.info(
                "Skill plugin unregistered: type=%s plugin=%s",
                skill_type, instance.name,
            )

        if isinstance(instance, ApiPlugin) and self._route_manager.app is not None:
            self._route_manager.unmount_plugin_routes(instance)

    # ========================================
    # 查询
    # ========================================

    def get_plugin_tools(self) -> dict[str, str]:
        """获取所有已注册的工具插件映射"""
        return dict(self._plugin_tools)

    def get_plugin_adapters(self) -> dict[str, str]:
        """获取所有已注册的适配器插件映射"""
        return dict(self._plugin_adapters)

    def get_adapter_plugin_info(self, provider_type: str) -> dict[str, Any] | None:
        """获取适配器插件的 provider_info"""
        from app.plugins.loader import PluginLoader
        plugin_name = self._plugin_adapters.get(provider_type)
        if not plugin_name:
            return None
        # 需要从外部传入 loader 来获取实例，这里使用 get_plugin_manager
        from app.plugins.manager import get_plugin_manager
        instance = get_plugin_manager().loader.get_instance(plugin_name)
        if not instance or not isinstance(instance, AdapterPlugin):
            return None
        return instance.get_provider_info()

    def get_plugin_skill_types(self) -> dict[str, str]:
        """获取所有已注册的插件 Skill 类型"""
        return dict(self._plugin_skills)

    def get_skill_plugin(self, skill_type: str) -> SkillPlugin | None:
        """根据 Skill 类型获取对应的 SkillPlugin 实例"""
        return self._skill_instances.get(skill_type)

    def get_all_skill_metadata(self) -> list[dict[str, Any]]:
        """获取所有已注册的插件 Skill 元数据"""
        return [inst.get_skill_metadata() for inst in self._skill_instances.values()]

    def is_plugin_skill_type(self, skill_type: str) -> bool:
        """判断给定的 Skill 类型是否由插件提供"""
        return skill_type in self._plugin_skills


__all__ = ["ExtensionRegistry"]
