"""
插件抽象基类

定义所有插件必须实现的生命周期方法和元数据接口
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.plugins.context import PluginContext


class BasePlugin(ABC):
    """
    插件抽象基类

    所有插件必须继承此类并实现必要的抽象方法。
    提供完整的生命周期钩子：

    - on_install: 插件首次安装时调用
    - on_enable: 插件启用时调用
    - on_disable: 插件禁用时调用
    - on_uninstall: 插件卸载时调用
    - on_upgrade: 插件版本升级时调用

    使用示例::

        class MyPlugin(BasePlugin):
            @property
            def name(self) -> str:
                return "my-plugin"

            @property
            def display_name(self) -> str:
                return "My Plugin"

            @property
            def version(self) -> str:
                return "1.0.0"

            async def on_enable(self, ctx: PluginContext) -> None:
                ctx.logger.info("MyPlugin enabled!")
    """

    # ========================================
    # 元数据（子类必须实现）
    # ========================================

    @property
    @abstractmethod
    def name(self) -> str:
        """插件唯一标识（如 novusai-anthropic-adapter）"""
        ...

    @property
    @abstractmethod
    def display_name(self) -> str:
        """插件显示名称"""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """插件版本号（semver）"""
        ...

    @property
    def description(self) -> str:
        """插件描述"""
        return ""

    @property
    def author(self) -> str:
        """插件作者"""
        return ""

    @property
    def homepage(self) -> str:
        """插件主页 URL"""
        return ""

    @property
    def icon(self) -> str:
        """插件图标（Lucide 图标名或 URL）"""
        return ""

    @property
    def config_schema(self) -> dict[str, Any] | None:
        """
        配置项 JSON Schema（用于前端动态表单渲染）

        Returns:
            JSON Schema dict 或 None（无配置项）
        """
        return None

    @property
    def default_config(self) -> dict[str, Any]:
        """插件默认配置"""
        return {}

    @property
    def required_permissions(self) -> list[str]:
        """
        插件所需的权限声明

        平台管理员安装时需要确认授予这些权限。
        示例: ["db:read", "http:outbound", "event:subscribe"]
        """
        return []

    @property
    def dependencies(self) -> dict[str, str]:
        """
        依赖的其他插件及版本要求

        格式: {"plugin-name": ">=1.0.0"}
        """
        return {}

    @property
    def conflicts(self) -> list[str]:
        """
        互斥的插件列表

        如果这些插件已启用，当前插件不可启用。
        """
        return []

    @property
    def platform_version(self) -> str | None:
        """最低平台版本要求（如 >=2.0.0）"""
        return None

    # ========================================
    # 生命周期钩子
    # ========================================

    async def on_install(self, ctx: PluginContext) -> None:
        """
        插件安装时调用

        适合执行：创建数据库表、初始化默认数据等一次性操作。

        Args:
            ctx: 插件运行时上下文
        """

    async def on_enable(self, ctx: PluginContext) -> None:
        """
        插件启用时调用

        适合执行：注册事件处理器、注册工具、挂载路由等。

        Args:
            ctx: 插件运行时上下文
        """

    async def on_disable(self, ctx: PluginContext) -> None:
        """
        插件禁用时调用

        适合执行：注销事件处理器、移除工具注册、卸载路由等。

        Args:
            ctx: 插件运行时上下文
        """

    async def on_uninstall(self, ctx: PluginContext) -> None:
        """
        插件卸载时调用

        适合执行：清理数据库表、删除文件等不可逆操作。

        Args:
            ctx: 插件运行时上下文
        """

    async def on_upgrade(
        self, ctx: PluginContext, from_version: str
    ) -> None:
        """
        插件版本升级时调用

        Args:
            ctx: 插件运行时上下文
            from_version: 升级前的版本号
        """

    # ========================================
    # 健康检查
    # ========================================

    async def health_check(self, ctx: PluginContext) -> dict[str, Any]:
        """
        插件健康检查（可选覆写）

        返回插件的运行状态信息。默认返回 healthy=True。
        子类可覆写以实现自定义检查（如外部 API 连通性）。

        Args:
            ctx: 插件运行时上下文

        Returns:
            健康状态字典，至少包含 healthy: bool
        """
        return {"healthy": True}

    # ========================================
    # 工具方法
    # ========================================

    def get_manifest(self) -> dict[str, Any]:
        """
        生成插件 manifest 字典

        返回插件的完整元数据，用于写入 plugins 表。

        Returns:
            manifest dict
        """
        return {
            "name": self.name,
            "display_name": self.display_name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "homepage": self.homepage,
            "icon": self.icon,
            "config_schema": self.config_schema,
            "default_config": self.default_config,
            "required_permissions": self.required_permissions,
            "dependencies": self.dependencies,
            "conflicts": self.conflicts,
            "platform_version": self.platform_version,
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} version={self.version!r}>"


__all__ = ["BasePlugin"]
