"""
工具执行器扩展点

允许插件注册新的工具类型，供智能体调用
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, TYPE_CHECKING

from app.plugins.base import BasePlugin

if TYPE_CHECKING:
    from app.ai.tools.types import ToolDefinition
    from app.plugins.context import PluginContext


class ToolPlugin(BasePlugin):
    """
    工具执行器插件接口

    继承此类来注册新的工具类型。
    PluginManager 启用插件时会调用 get_tool_definitions() 获取工具定义，
    并注册到 ToolRegistry 中。

    使用示例::

        class WeatherPlugin(ToolPlugin):
            @property
            def name(self) -> str:
                return "novusai-weather-tool"

            @property
            def display_name(self) -> str:
                return "Weather Tool"

            @property
            def version(self) -> str:
                return "1.0.0"

            def get_tool_definitions(self) -> list[ToolDefinition]:
                return [
                    ToolDefinition(
                        name="get_weather",
                        description="Get current weather for a location",
                        tool_type="weather",
                        parameters=[
                            ToolParameter(name="city", type="string",
                                          description="City name", required=True),
                        ],
                    ),
                ]

            async def execute(self, tool_name, arguments, ctx):
                city = arguments.get("city")
                # ... call weather API ...
                return {"temperature": 25, "condition": "sunny"}
    """

    @abstractmethod
    def get_tool_definitions(self) -> list[ToolDefinition]:
        """
        返回本插件提供的工具定义列表

        这些定义会被注册到 ToolRegistry，
        供智能体在对话中调用。

        Returns:
            ToolDefinition 列表
        """
        ...

    @abstractmethod
    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        ctx: PluginContext,
    ) -> dict[str, Any] | str:
        """
        执行工具调用

        Args:
            tool_name: 工具名称（与 get_tool_definitions 中的 name 对应）
            arguments: LLM 传入的参数
            ctx: 执行上下文（PluginContext 或 ExecutionContext）

        Returns:
            工具执行结果（将被序列化为字符串返回给 LLM）
        """
        ...

    def get_tool_type(self) -> str:
        """
        返回工具类型标识

        用于在 ToolRegistry 中区分不同来源的工具。
        默认返回插件名称。

        Returns:
            工具类型字符串
        """
        return self.name

    def get_config_schema(self) -> dict[str, Any] | None:
        """
        返回工具级别的配置 Schema

        与插件级别的 config_schema 不同，这是针对单个工具的配置。
        例如 HTTP 工具的 URL、method、headers 等。

        Returns:
            JSON Schema dict 或 None
        """
        return None


__all__ = ["ToolPlugin"]
