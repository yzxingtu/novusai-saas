"""Small facade modules used by PluginLifecycle composition."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.plugins.lifecycle import PluginLifecycle


class LifecycleGuardModule:
    """Lifecycle guard orchestration module / 生命周期守卫编排模块。"""

    def __init__(self, lifecycle: PluginLifecycle) -> None:
        self._lifecycle = lifecycle

    async def run(
        self,
        *,
        operation: str,
        plugin_id: int,
        plugin_name: str,
        force: bool,
        manifest: dict[str, Any] | None,
    ) -> None:
        await self._lifecycle._run_lifecycle_guards(
            operation=operation,
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            force=force,
            manifest=manifest,
        )


class LifecycleDependencyModule:
    """Dependency operations module / 依赖管理模块。"""

    def __init__(self, lifecycle: PluginLifecycle) -> None:
        self._lifecycle = lifecycle

    async def assert_plugin_dependencies_ready(
        self,
        manifest: object,
        *,
        plugin_name: str,
        require_enabled: bool,
        error_cls: type[Exception],
        action: str,
    ) -> None:
        await self._lifecycle._assert_plugin_dependencies_ready(
            manifest,
            plugin_name=plugin_name,
            require_enabled=require_enabled,
            error_cls=error_cls,
            action=action,
        )

    async def install_python_dependencies(
        self,
        plugin_name: str,
        requirements: list[str],
    ) -> list[str]:
        return await self._lifecycle._install_python_deps(plugin_name, requirements)

    async def uninstall_python_dependencies(
        self,
        plugin_name: str,
        requirements: list[str],
    ) -> list[str]:
        return await self._lifecycle._uninstall_python_deps(plugin_name, requirements)


class LifecyclePermissionModule:
    """Permission sync module / 权限同步模块。"""

    def __init__(self, lifecycle: PluginLifecycle) -> None:
        self._lifecycle = lifecycle

    async def restore(self, plugin_name: str) -> None:
        await self._lifecycle._restore_plugin_permissions(plugin_name)

    async def set_enabled(self, plugin_name: str, enabled: bool) -> int:
        return await self._lifecycle._set_plugin_permissions_enabled(
            plugin_name,
            enabled,
        )

    async def auto_grant_plan_menus(
        self,
        plugin_name: str,
        **kwargs: Any,
    ) -> None:
        await self._lifecycle._auto_grant_plugin_menus_to_plans(
            plugin_name,
            **kwargs,
        )

    async def revoke_plan_menus(self, plugin_name: str) -> None:
        await self._lifecycle._revoke_plugin_menus_from_plans(plugin_name)
