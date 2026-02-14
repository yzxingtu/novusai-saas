"""
AI 适配器扩展点

允许插件注册新的 AI 供应商适配器（如 Anthropic、Google Gemini 等）
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, TYPE_CHECKING

from app.plugins.base import BasePlugin

if TYPE_CHECKING:
    from app.ai.adapters.base import BaseAdapter


class AdapterPlugin(BasePlugin):
    """
    AI 适配器插件接口

    继承此类来注册新的 AI 供应商适配器。
    PluginManager 启用插件时会调用 get_adapter_class() 获取适配器类，
    并将 get_provider_info() 返回的供应商信息注册到系统中。

    使用示例::

        class AnthropicPlugin(AdapterPlugin):
            @property
            def name(self) -> str:
                return "novusai-anthropic-adapter"

            @property
            def display_name(self) -> str:
                return "Anthropic Claude"

            @property
            def version(self) -> str:
                return "1.0.0"

            def get_adapter_class(self) -> type[BaseAdapter]:
                from my_plugin.adapter import AnthropicAdapter
                return AnthropicAdapter

            def get_provider_info(self) -> dict[str, Any]:
                return {
                    "name": "anthropic",
                    "display_name": "Anthropic",
                    "icon": "lucide:brain",
                    "models": [
                        {"code": "claude-3-opus", "name": "Claude 3 Opus"},
                    ],
                }
    """

    @abstractmethod
    def get_adapter_class(self) -> type[BaseAdapter]:
        """
        返回适配器类

        该类必须继承 app.ai.adapters.base.BaseAdapter。
        PluginManager 将在需要时实例化该类。

        Returns:
            BaseAdapter 子类
        """
        ...

    @abstractmethod
    def get_provider_info(self) -> dict[str, Any]:
        """
        返回供应商信息

        用于在管理端展示供应商卡片和可用模型列表。

        Returns:
            供应商信息字典，包含：
            - name: 供应商唯一标识
            - display_name: 显示名称
            - icon: 图标（Lucide 图标名或 URL）
            - models: 模型列表 [{"code": "...", "name": "..."}]
            - base_url: 默认 API 地址（可选）
            - supports: 支持的功能 {"chat": True, "embedding": True, ...}（可选）
        """
        ...

    def get_supported_features(self) -> dict[str, bool]:
        """
        返回适配器支持的功能集

        默认实现，子类可覆盖以声明更精确的能力。

        Returns:
            功能字典
        """
        return {
            "chat": True,
            "streaming": True,
            "function_calling": False,
            "vision": False,
            "embedding": False,
        }


__all__ = ["AdapterPlugin"]
