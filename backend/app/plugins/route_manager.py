"""
插件路由管理器

负责 ApiPlugin 的路由挂载、卸载和认证依赖注入。
从 PluginManager 提取，降低 God Object 复杂度。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

from app.core.logging import LogManager
from app.plugins.extensions.api_plugin import ApiPlugin

logger = LogManager.get_logger("app")


class PluginRouteManager:
    """
    插件路由管理器

    职责：
    - 将 ApiPlugin 的路由挂载到 FastAPI 应用
    - 从 FastAPI 应用中移除 ApiPlugin 的路由
    - 根据认证级别注入 FastAPI 依赖
    """

    _AUTH_LEVEL_DEPS: dict[str, list] | None = None

    def __init__(self) -> None:
        # plugin_name -> route prefix (ApiPlugin routes mounted to app)
        self._plugin_routers: dict[str, str] = {}
        # FastAPI app reference for dynamic route mounting
        self._app: FastAPI | None = None

    def set_app(self, app: FastAPI) -> None:
        """设置 FastAPI 应用引用"""
        self._app = app

    @property
    def app(self) -> FastAPI | None:
        """获取 FastAPI 应用引用"""
        return self._app

    @classmethod
    def _get_auth_deps(cls, auth_level: str) -> list:
        """根据认证级别返回 FastAPI 依赖列表"""
        if cls._AUTH_LEVEL_DEPS is None:
            from fastapi import Depends
            from app.core.deps import (
                get_current_active_admin,
                get_current_super_admin,
            )
            cls._AUTH_LEVEL_DEPS = {
                "public": [],
                "auth_only": [Depends(get_current_active_admin)],
                "admin_only": [Depends(get_current_super_admin)],
            }
        return cls._AUTH_LEVEL_DEPS.get(auth_level, cls._AUTH_LEVEL_DEPS["auth_only"])

    def mount_plugin_routes(self, instance: ApiPlugin) -> None:
        """将 ApiPlugin 的路由挂载到 FastAPI 应用

        根据插件的 ``get_auth_level()`` 返回值自动注入认证依赖：
        - ``public``: 无认证
        - ``auth_only``: 需要活跃管理员（默认）
        - ``admin_only``: 需要超级管理员
        """
        plugin_name = instance.name
        if plugin_name in self._plugin_routers:
            logger.warning("Plugin routes already mounted: %s", plugin_name)
            return

        try:
            router = instance.get_router()
            route_prefix = instance.get_route_prefix()
            tags = instance.get_route_tags()
            auth_level = instance.get_auth_level()
            full_prefix = f"/plugins/{plugin_name}{route_prefix}"

            deps = self._get_auth_deps(auth_level)
            self._app.include_router(
                router, prefix=full_prefix, tags=tags, dependencies=deps,
            )
            self._plugin_routers[plugin_name] = full_prefix
            logger.info(
                "API plugin routes mounted: %s -> %s (auth=%s)",
                plugin_name, full_prefix, auth_level,
            )
        except Exception as exc:
            logger.error(
                "Failed to mount plugin routes: %s: %s",
                plugin_name, exc, exc_info=True,
            )

    def unmount_plugin_routes(self, instance: ApiPlugin) -> None:
        """从 FastAPI 应用中移除 ApiPlugin 的路由

        同时处理 APIRoute 和 Mount 类型的路由对象，
        并清除 OpenAPI schema 缓存以确保 /docs 同步更新。
        """
        from starlette.routing import Mount

        plugin_name = instance.name
        full_prefix = self._plugin_routers.pop(plugin_name, None)
        if not full_prefix:
            return

        try:
            original_count = len(self._app.routes)

            def _is_plugin_route(route: object) -> bool:
                path = getattr(route, "path", "")
                if isinstance(path, str) and path.startswith(full_prefix):
                    return True
                if isinstance(route, Mount) and isinstance(route.path, str):
                    return route.path.startswith(full_prefix)
                return False

            self._app.routes[:] = [
                route for route in self._app.routes
                if not _is_plugin_route(route)
            ]
            removed = original_count - len(self._app.routes)

            # 清除 OpenAPI schema 缓存，确保 /docs 不再显示已卸载的路由
            self._app.openapi_schema = None

            if removed == 0:
                logger.warning(
                    "API plugin unmount: no routes matched prefix %s for %s",
                    full_prefix, plugin_name,
                )
            else:
                logger.info(
                    "API plugin routes unmounted: %s (%d routes removed, OpenAPI cache cleared)",
                    plugin_name, removed,
                )
        except Exception as exc:
            logger.error(
                "Failed to unmount plugin routes: %s: %s",
                plugin_name, exc, exc_info=True,
            )

    def get_plugin_routers(self) -> dict[str, str]:
        """
        获取所有已挂载的插件路由映射

        Returns:
            plugin_name -> route_prefix 的映射
        """
        return dict(self._plugin_routers)


__all__ = ["PluginRouteManager"]
