"""
Example Weather Tool Plugin

Demonstrates how to build a ToolPlugin for NovusAI.

Key concepts shown:
  - Plugin metadata (name, version, description, etc.)
  - Tool definitions for LLM function calling
  - Tool execution logic
  - Configuration schema (JSON Schema → dynamic form)
  - Lifecycle hooks (on_enable / on_disable)

To install for development:
  POST /admin/plugins/install
  { "entry_point": "app.plugins.examples.weather_tool.plugin.ExampleWeatherToolPlugin" }
"""

from __future__ import annotations

from typing import Any

from app.ai.tools.types import ToolDefinition
from app.plugins.context import PluginContext
from app.plugins.extensions.tool_plugin import ToolPlugin


class ExampleWeatherToolPlugin(ToolPlugin):
    """
    A weather lookup tool that AI agents can use to get current weather.

    This plugin registers a "get_weather" tool that the LLM can call
    during conversations. When called, it returns mock weather data
    (replace with real API calls in production).
    """

    # ========================================
    # Required metadata
    # ========================================

    @property
    def name(self) -> str:
        """Unique plugin identifier. Use lowercase + hyphens."""
        return "example-weather-tool"

    @property
    def display_name(self) -> str:
        """Human-readable name shown in the admin panel."""
        return "Weather Tool (Example)"

    @property
    def version(self) -> str:
        """Semantic version. Bump this when releasing updates."""
        return "1.0.0"

    # ========================================
    # Optional metadata
    # ========================================

    @property
    def description(self) -> str:
        return "An example tool plugin providing weather lookup for AI agents."

    @property
    def author(self) -> str:
        return "NovusAI Team"

    @property
    def icon(self) -> str:
        """Lucide icon name for UI display."""
        return "lucide:cloud-sun"

    @property
    def config_schema(self) -> dict[str, Any] | None:
        """
        JSON Schema for plugin configuration.

        The frontend SchemaForm component renders this as a dynamic form.
        Supported types: string, number, integer, boolean, enum, password, textarea.
        """
        return {
            "type": "object",
            "properties": {
                "api_key": {
                    "type": "string",
                    "title": "Weather API Key",
                    "description": "API key for the weather service",
                    "format": "password",
                },
                "default_unit": {
                    "type": "string",
                    "title": "Temperature Unit",
                    "enum": ["celsius", "fahrenheit"],
                    "default": "celsius",
                },
                "cache_ttl": {
                    "type": "integer",
                    "title": "Cache TTL (seconds)",
                    "minimum": 60,
                    "maximum": 3600,
                    "default": 300,
                },
            },
            "required": ["api_key"],
        }

    @property
    def default_config(self) -> dict[str, Any]:
        return {"default_unit": "celsius", "cache_ttl": 300}

    @property
    def required_permissions(self) -> list[str]:
        """Permissions the plugin needs. Shown to admin during install."""
        return ["http:outbound"]

    # ========================================
    # ToolPlugin interface
    # ========================================

    def get_tool_type(self) -> str:
        """
        Unique tool type identifier.

        This is registered in the dynamic tool type enum and appears
        in the tool management UI.
        """
        return "weather"

    def get_tool_definitions(self) -> list[ToolDefinition]:
        """
        Define the tools this plugin provides.

        Each ToolDefinition maps to an OpenAI-compatible function calling spec.
        The LLM sees these definitions and can choose to call them.
        """
        return [
            ToolDefinition(
                name="get_weather",
                description="Get current weather information for a city or location.",
                parameters={
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name or coordinates (e.g. 'Beijing', 'Tokyo')",
                        },
                        "unit": {
                            "type": "string",
                            "description": "Temperature unit",
                            "enum": ["celsius", "fahrenheit"],
                        },
                    },
                    "required": ["location"],
                },
            ),
        ]

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        ctx: Any,
    ) -> Any:
        """
        Execute a tool call from the LLM.

        Args:
            tool_name: Which tool was called (matches ToolDefinition.name)
            arguments: Arguments the LLM provided
            ctx: Execution context (contains tenant info, config, etc.)

        Returns:
            Result data that will be sent back to the LLM.
        """
        if tool_name == "get_weather":
            return await self._get_weather(arguments)

        return {"error": f"Unknown tool: {tool_name}"}

    async def _get_weather(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Mock weather lookup.

        In a real plugin, you would:
        1. Read the API key from self.default_config or ctx.config
        2. Make an HTTP request to a weather API
        3. Parse and return the response
        """
        location = arguments.get("location", "Unknown")
        unit = arguments.get("unit", "celsius")

        # Mock response — replace with real API call
        return {
            "location": location,
            "temperature": 22 if unit == "celsius" else 72,
            "unit": unit,
            "condition": "Partly Cloudy",
            "humidity": 65,
            "wind_speed": "12 km/h",
            "source": "example-weather-tool (mock data)",
        }

    # ========================================
    # Lifecycle hooks
    # ========================================

    async def on_enable(self, ctx: PluginContext) -> None:
        """Called when the plugin is enabled."""
        if ctx.logger:
            ctx.logger.info("Weather tool plugin enabled")

    async def on_disable(self, ctx: PluginContext) -> None:
        """Called when the plugin is disabled."""
        if ctx.logger:
            ctx.logger.info("Weather tool plugin disabled")
