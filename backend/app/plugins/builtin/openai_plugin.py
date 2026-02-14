"""
OpenAI 兼容适配器内置插件

将现有 OpenAIAdapter 包装为内置 AdapterPlugin（is_system=True）。
保持现有 API 完全兼容，验证插件系统加载适配器的完整链路。
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.plugins.extensions.adapter_plugin import AdapterPlugin
from app.plugins.context import PluginContext

if TYPE_CHECKING:
    from app.ai.adapters.base import BaseAdapter


class OpenAIAdapterPlugin(AdapterPlugin):
    """
    OpenAI 兼容适配器内置插件

    包装现有 OpenAIAdapter，通过插件系统注册到 AdapterRegistry。
    标记为 is_system=True，不可卸载/禁用。
    """

    @property
    def name(self) -> str:
        return "novusai-openai-adapter"

    @property
    def display_name(self) -> str:
        return "OpenAI Compatible Adapter"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Built-in adapter for OpenAI API and compatible services (DeepSeek, Zhipu, Qwen, etc.)"

    @property
    def author(self) -> str:
        return "NovusAI"

    @property
    def icon(self) -> str:
        return "lucide:brain-circuit"

    @property
    def required_permissions(self) -> list[str]:
        return ["http:outbound"]

    def get_adapter_class(self) -> type[BaseAdapter]:
        from app.ai.adapters.openai_adapter import OpenAIAdapter
        return OpenAIAdapter

    def get_provider_info(self) -> dict[str, Any]:
        from app.enums.ai import ProviderTypeEnum
        return {
            "name": ProviderTypeEnum.OPENAI_COMPATIBLE.value,
            "display_name": "OpenAI Compatible",
            "icon": "lucide:brain-circuit",
            "base_url": "https://api.openai.com/v1",
            "supports": {
                "chat": True,
                "streaming": True,
                "function_calling": True,
                "vision": True,
                "embedding": True,
            },
        }

    def get_supported_features(self) -> dict[str, bool]:
        return {
            "chat": True,
            "streaming": True,
            "function_calling": True,
            "vision": True,
            "embedding": True,
        }

    async def on_install(self, ctx: PluginContext) -> None:
        if ctx.logger:
            ctx.logger.info("OpenAI compatible adapter plugin installed")

    async def on_enable(self, ctx: PluginContext) -> None:
        if ctx.logger:
            ctx.logger.info("OpenAI compatible adapter plugin enabled")

    async def on_disable(self, ctx: PluginContext) -> None:
        if ctx.logger:
            ctx.logger.warning("OpenAI compatible adapter plugin disabled (system plugin)")

    async def on_uninstall(self, ctx: PluginContext) -> None:
        if ctx.logger:
            ctx.logger.warning("OpenAI compatible adapter plugin uninstalled (system plugin)")


__all__ = ["OpenAIAdapterPlugin"]
