"""
API 端点扩展点

允许插件注册自定义 API 路由
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from app.plugins.base import BasePlugin

if TYPE_CHECKING:
    from fastapi import APIRouter


class ApiPlugin(BasePlugin):
    """
    API 端点插件接口

    继承此类来注册自定义 FastAPI 路由。
    PluginManager 启用插件时会调用 get_router() 获取路由器，
    并挂载到应用的 /plugins/{plugin_name}/ 路径下。

    使用示例::

        class WebhookPlugin(ApiPlugin):
            @property
            def name(self) -> str:
                return "novusai-webhook"

            @property
            def display_name(self) -> str:
                return "Webhook Receiver"

            @property
            def version(self) -> str:
                return "1.0.0"

            def get_router(self) -> APIRouter:
                from fastapi import APIRouter
                router = APIRouter()

                @router.post("/receive")
                async def receive_webhook(payload: dict):
                    # 处理 webhook...
                    return {"status": "ok"}

                return router

            def get_route_prefix(self) -> str:
                return "/webhooks"
    """

    @abstractmethod
    def get_router(self) -> APIRouter:
        """
        返回 FastAPI 路由器

        路由器中定义的所有端点将被挂载到
        /plugins/{plugin_name}{route_prefix}/ 路径下。

        Returns:
            FastAPI APIRouter 实例
        """
        ...

    def get_route_prefix(self) -> str:
        """
        返回路由前缀

        默认为空字符串，路由将直接挂载到 /plugins/{plugin_name}/ 下。
        可覆盖以添加子路径。

        Returns:
            路由前缀字符串（如 "/webhooks"）
        """
        return ""

    def get_route_tags(self) -> list[str]:
        """
        返回 OpenAPI 文档标签

        用于在 Swagger 文档中分组显示插件路由。

        Returns:
            标签列表
        """
        return [f"Plugin: {self.display_name}"]


__all__ = ["ApiPlugin"]
