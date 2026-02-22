"""
插件路由管理器

负责 ApiPlugin 的路由挂载、卸载和认证依赖注入。
支持多组路由（双端插件可同时挂载 admin + tenant 路由）。
挂载后自动为缺少 RBAC 装饰器的端点注入 @auth_only 标记。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

from app.core.logging import LogManager
from app.plugins.extensions.api_plugin import ApiPlugin

logger = LogManager.get_logger("app")

# auth_level → URL base prefix
_AUTH_LEVEL_PREFIX: dict[str, str] = {
    "tenant_auth": "/tenant/plugins",
    "admin_only": "/admin/plugins",
    "auth_only": "/admin/plugins",
    "public": "/plugins",
}


class PluginRouteManager:
    """
    插件路由管理器

    职责：
    - 遍历 ApiPlugin.get_route_groups() 将每组路由分别挂载到 FastAPI 应用
    - 自动为缺少 _access_level 的端点注入 AUTH_ONLY 标记（防止 AccessControlMiddleware 拦截）
    - 支持多组路由的卸载
    - 根据认证级别注入 FastAPI 依赖
    """

    _AUTH_LEVEL_DEPS: dict[str, list] | None = None

    def __init__(self) -> None:
        self._plugin_routers: dict[str, list[str]] = {}
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
                get_current_active_tenant_admin,
            )
            cls._AUTH_LEVEL_DEPS = {
                "public": [],
                "auth_only": [Depends(get_current_active_admin)],
                "admin_only": [Depends(get_current_super_admin)],
                "tenant_auth": [Depends(get_current_active_tenant_admin)],
            }
        return cls._AUTH_LEVEL_DEPS.get(auth_level, cls._AUTH_LEVEL_DEPS["auth_only"])

    # ========================================
    # 挂载
    # ========================================

    def mount_plugin_routes(self, instance: ApiPlugin) -> None:
        """将 ApiPlugin 的所有路由组挂载到 FastAPI 应用

        遍历 get_route_groups() 返回的每组路由，分别挂载到对应的 URL 前缀下。
        挂载后自动为缺少 _access_level 的端点注入 AUTH_ONLY 标记。
        """
        plugin_name = instance.name
        if plugin_name in self._plugin_routers:
            logger.warning("Plugin routes already mounted: %s", plugin_name)
            return

        try:
            groups = instance.get_route_groups()
            prefixes: list[str] = []

            for group in groups:
                base = _AUTH_LEVEL_PREFIX.get(group.auth_level, "/admin/plugins")
                full_prefix = f"{base}/{plugin_name}{group.prefix}"
                deps = self._get_auth_deps(group.auth_level)
                tags = group.tags or [f"Plugin: {instance.display_name}"]

                self._app.include_router(
                    group.router,
                    prefix=full_prefix,
                    tags=tags,
                    dependencies=deps,
                )
                prefixes.append(full_prefix)

                # 自动为缺少 _access_level 的端点注入 AUTH_ONLY 标记
                self._inject_access_level(group.router)

                logger.info(
                    "API plugin route group mounted: %s -> %s (auth=%s)",
                    plugin_name, full_prefix, group.auth_level,
                )

            self._plugin_routers[plugin_name] = prefixes

            if len(prefixes) > 1:
                logger.info(
                    "API plugin mounted %d route groups: %s -> %s",
                    len(prefixes), plugin_name, prefixes,
                )
        except Exception as exc:
            logger.error(
                "Failed to mount plugin routes: %s: %s",
                plugin_name, exc, exc_info=True,
            )

    @staticmethod
    def _inject_access_level(router: "APIRouter") -> None:
        """为缺少 _access_level 标记的端点自动注入 AUTH_ONLY

        AccessControlMiddleware 检查每个端点的 _access_level 属性，
        未标记的端点会被返回 403。插件端点通常不使用 @action_* 装饰器，
        因此需要在挂载后自动补全标记。

        已有 @auth_only/@public/@action_* 装饰器的端点不会被覆盖。
        """
        from app.rbac.decorators import ACCESS_AUTH_ONLY

        for route in getattr(router, "routes", []):
            endpoint = getattr(route, "endpoint", None)
            if endpoint and not hasattr(endpoint, "_access_level"):
                endpoint._access_level = ACCESS_AUTH_ONLY

    # ========================================
    # 卸载
    # ========================================

    def unmount_plugin_routes(self, instance: ApiPlugin) -> None:
        """从 FastAPI 应用中移除 ApiPlugin 的所有路由组

        遍历该插件的所有挂载前缀，逐一匹配并移除路由。
        同时清除 OpenAPI schema 缓存。
        """
        from starlette.routing import Mount

        plugin_name = instance.name
        prefixes = self._plugin_routers.pop(plugin_name, None)
        if not prefixes:
            return

        try:
            original_count = len(self._app.routes)

            def _is_plugin_route(route: object) -> bool:
                path = getattr(route, "path", "")
                for prefix in prefixes:
                    if isinstance(path, str) and path.startswith(prefix):
                        return True
                    if isinstance(route, Mount) and isinstance(route.path, str):
                        if route.path.startswith(prefix):
                            return True
                return False

            self._app.routes[:] = [
                route for route in self._app.routes
                if not _is_plugin_route(route)
            ]
            removed = original_count - len(self._app.routes)

            self._app.openapi_schema = None

            if removed == 0:
                logger.warning(
                    "API plugin unmount: no routes matched prefixes %s for %s",
                    prefixes, plugin_name,
                )
            else:
                logger.info(
                    "API plugin routes unmounted: %s (%d routes removed from %d groups)",
                    plugin_name, removed, len(prefixes),
                )
        except Exception as exc:
            logger.error(
                "Failed to unmount plugin routes: %s: %s",
                plugin_name, exc, exc_info=True,
            )

    # ========================================
    # 查询
    # ========================================

    def get_plugin_routers(self) -> dict[str, list[str]]:
        """
        获取所有已挂载的插件路由映射

        Returns:
            plugin_name -> list[route_prefix] 的映射
        """
        return {k: list(v) for k, v in self._plugin_routers.items()}


__all__ = ["PluginRouteManager"]
