"""
Anthropic Claude 适配器插件

示例外部插件，展示如何通过插件系统注册新的 AI 供应商适配器。
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.plugins.extensions.adapter_plugin import AdapterPlugin
from app.plugins.context import PluginContext

if TYPE_CHECKING:
    from app.ai.adapters.base import BaseAdapter


class AnthropicPlugin(AdapterPlugin):
    """
    Anthropic Claude 适配器插件

    支持 Claude 系列模型的 chat 和 stream_chat。
    不支持 embedding。
    """

    @property
    def name(self) -> str:
        return "novusai-anthropic-adapter"

    @property
    def display_name(self) -> str:
        return "Anthropic Claude"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Adapter plugin for Anthropic Claude models (Claude 3 Opus, Sonnet, Haiku)"

    @property
    def author(self) -> str:
        return "NovusAI"

    @property
    def icon(self) -> str:
        return "lucide:sparkles"

    @property
    def homepage(self) -> str | None:
        return "https://docs.anthropic.com"

    @property
    def required_permissions(self) -> list[str]:
        return ["http:outbound"]

    @property
    def config_schema(self) -> dict[str, Any] | None:
        return {
            "type": "object",
            "properties": {
                "api_key": {
                    "type": "string",
                    "title": "API Key",
                    "description": "Anthropic API key",
                    "format": "password",
                },
                "base_url": {
                    "type": "string",
                    "title": "Base URL",
                    "description": "API base URL (optional, for proxy)",
                    "default": "https://api.anthropic.com",
                },
                "default_model": {
                    "type": "string",
                    "title": "Default Model",
                    "description": "Default Claude model to use",
                    "default": "claude-sonnet-4-20250514",
                    "enum": [
                        "claude-sonnet-4-20250514",
                        "claude-3-5-sonnet-20241022",
                        "claude-3-5-haiku-20241022",
                        "claude-3-opus-20240229",
                    ],
                },
            },
            "required": ["api_key"],
        }

    @property
    def default_config(self) -> dict[str, Any]:
        return {
            "base_url": "https://api.anthropic.com",
            "default_model": "claude-sonnet-4-20250514",
        }

    def get_adapter_class(self) -> type[BaseAdapter]:
        from app.plugins.builtin.anthropic.adapter import AnthropicAdapter
        return AnthropicAdapter

    def get_provider_info(self) -> dict[str, Any]:
        return {
            "name": "anthropic",
            "display_name": "Anthropic Claude",
            "icon": "lucide:sparkles",
            "base_url": "https://api.anthropic.com",
            "models": [
                {"code": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
                {"code": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
                {"code": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku"},
                {"code": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
            ],
            "supports": {
                "chat": True,
                "streaming": True,
                "function_calling": True,
                "vision": True,
                "embedding": False,
            },
        }

    def get_supported_features(self) -> dict[str, bool]:
        return {
            "chat": True,
            "streaming": True,
            "function_calling": True,
            "vision": True,
            "embedding": False,
        }

    async def on_install(self, ctx: PluginContext) -> None:
        if ctx.logger:
            ctx.logger.info("Anthropic Claude adapter plugin installed")

    async def on_enable(self, ctx: PluginContext) -> None:
        if ctx.logger:
            ctx.logger.info("Anthropic Claude adapter plugin enabled")

    async def on_disable(self, ctx: PluginContext) -> None:
        if ctx.logger:
            ctx.logger.info("Anthropic Claude adapter plugin disabled")

    async def on_uninstall(self, ctx: PluginContext) -> None:
        if ctx.logger:
            ctx.logger.info("Anthropic Claude adapter plugin uninstalled")


__all__ = ["AnthropicPlugin"]
