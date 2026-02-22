"""
API 端点扩展点

允许插件注册自定义 API 路由。支持单组路由（向后兼容）和多组路由（双端插件）。
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.plugins.base import BasePlugin

if TYPE_CHECKING:
    from fastapi import APIRouter


@dataclass
class RouteGroup:
    """
    路由组定义

    一个插件可声明多个路由组，每组有独立的认证级别和前缀。
    route_manager 会将每组分别挂载到对应的 URL 路径下。

    Attributes:
        router: FastAPI APIRouter 实例
        auth_level: 认证级别（public/auth_only/admin_only/tenant_auth）
        prefix: 路由子前缀（默认空）
        tags: OpenAPI 文档标签
    """

    router: APIRouter
    auth_level: str = "auth_only"
    prefix: str = ""
    tags: list[str] = field(default_factory=list)


class ApiPlugin(BasePlugin):
    """
    API 端点插件接口

    支持两种路由声明方式：

    **方式一：单组路由（向后兼容）**

    覆盖 ``get_router()`` + ``get_auth_level()``，适合只需挂载到一个端的插件::

        class WebhookPlugin(ApiPlugin):
            def get_router(self) -> APIRouter:
                router = APIRouter()
                @router.post("/receive")
                async def receive(payload: dict):
                    return {"status": "ok"}
                return router

            def get_auth_level(self) -> str:
                return "tenant_auth"

    **方式二：多组路由（双端插件）**

    覆盖 ``get_route_groups()``，适合需要同时提供 admin + tenant 端点的插件::

        class MyDualEndpointPlugin(ApiPlugin):
            def get_route_groups(self) -> list[RouteGroup]:
                return [
                    RouteGroup(
                        router=self._tenant_router(),
                        auth_level="tenant_auth",
                        tags=["Plugin: MyPlugin (Tenant)"],
                    ),
                    RouteGroup(
                        router=self._admin_router(),
                        auth_level="admin_only",
                        tags=["Plugin: MyPlugin (Admin)"],
                    ),
                ]
    """

    # ========================================
    # 多组路由接口（推荐）
    # ========================================

    def get_route_groups(self) -> list[RouteGroup]:
        """
        返回路由组列表

        每组包含独立的 router、auth_level、prefix、tags。
        route_manager 会将每组分别挂载到对应的 URL 路径下：

        - ``auth_level="tenant_auth"`` → ``/tenant/plugins/{name}{prefix}/``
        - ``auth_level="admin_only"`` 或 ``"auth_only"`` → ``/admin/plugins/{name}{prefix}/``
        - ``auth_level="public"`` → ``/plugins/{name}{prefix}/``

        默认实现：将 get_router() + get_auth_level() 包装为单组（向后兼容）。
        插件可覆盖此方法提供多组路由。

        Returns:
            RouteGroup 列表
        """
        return [
            RouteGroup(
                router=self.get_router(),
                auth_level=self.get_auth_level(),
                prefix=self.get_route_prefix(),
                tags=self.get_route_tags(),
            )
        ]

    # ========================================
    # 单组路由接口（向后兼容）
    # ========================================

    @abstractmethod
    def get_router(self) -> APIRouter:
        """
        返回 FastAPI 路由器（单组模式）

        Returns:
            FastAPI APIRouter 实例
        """
        ...

    def get_route_prefix(self) -> str:
        """
        返回路由前缀（单组模式）

        默认为空字符串。可覆盖以添加子路径（如 "/webhooks"）。
        """
        return ""

    def get_route_tags(self) -> list[str]:
        """
        返回 OpenAPI 文档标签（单组模式）
        """
        return [f"Plugin: {self.display_name}"]

    def get_auth_level(self) -> str:
        """
        返回路由认证级别（单组模式）

        - ``"public"``: 无需认证
        - ``"auth_only"``: 需要活跃平台管理员（默认）
        - ``"admin_only"``: 需要超级管理员
        - ``"tenant_auth"``: 需要活跃租户管理员
        """
        return "auth_only"


__all__ = ["ApiPlugin", "RouteGroup"]
