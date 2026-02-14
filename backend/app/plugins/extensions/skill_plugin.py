"""
Skill 扩展点

允许插件注册自定义 Skill 类型，供 Agent 绑定和调用。

与 ToolPlugin 的区别：
- ToolPlugin 直接注册 ToolDefinition 到 ToolRegistry
- SkillPlugin 注册 Skill 类型，通过 SkillResolver 解析为 ToolDefinition

SkillPlugin 是更高层的抽象，一个 Skill 可产生多个 ToolDefinition。
未来 SkillResolver / Sandbox 会检测插件 Skill 类型并委托给插件处理。
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, TYPE_CHECKING

from app.plugins.base import BasePlugin

if TYPE_CHECKING:
    from app.ai.tools.types import ToolDefinition
    from app.plugins.context import PluginContext


class SkillPlugin(BasePlugin):
    """
    Skill 插件接口

    继承此类来注册自定义 Skill 类型。
    PluginManager 启用插件时会注册 skill_type，
    未来 SkillResolver 和 Sandbox 会委托给插件处理。

    使用示例::

        class SlackPlugin(SkillPlugin):
            @property
            def name(self) -> str:
                return "novusai-slack"

            @property
            def display_name(self) -> str:
                return "Slack Notification"

            @property
            def version(self) -> str:
                return "1.0.0"

            def get_skill_type(self) -> str:
                return "slack"

            def get_skill_display_name(self) -> str:
                return "Slack 通知"

            def get_skill_icon(self) -> str:
                return "lucide:message-square"

            def get_skill_config_schema(self) -> dict:
                return {
                    "type": "object",
                    "properties": {
                        "webhook_url": {"type": "string", "title": "Webhook URL"},
                        "default_channel": {"type": "string", "title": "Default Channel"},
                    },
                    "required": ["webhook_url"],
                }

            def resolve(self, skill_config: dict) -> list[ToolDefinition]:
                from app.ai.tools.types import ToolDefinition
                return [
                    ToolDefinition(
                        name="send_slack_message",
                        description="Send a message to Slack",
                        parameters={...},
                    ),
                ]

            async def execute(self, tool_name, arguments, context):
                # Execute the tool call
                ...
    """

    @abstractmethod
    def get_skill_type(self) -> str:
        """
        返回 Skill 类型标识

        在 SkillTypeEnum 中注册的唯一标识。
        例如: "slack", "jira", "github"

        Returns:
            Skill 类型字符串
        """
        ...

    def get_skill_display_name(self) -> str:
        """
        返回 Skill 类型的显示名称

        用于前端 Skill 创建表单中的类型选择。
        默认返回插件 display_name。

        Returns:
            显示名称
        """
        return self.display_name

    def get_skill_icon(self) -> str:
        """
        返回 Skill 类型的图标

        用于前端 Skill 列表和选择器中展示。
        默认返回插件 icon。

        Returns:
            Lucide 图标名或 URL
        """
        return self.icon

    @abstractmethod
    def get_skill_config_schema(self) -> dict[str, Any]:
        """
        返回 Skill 配置的 JSON Schema

        当用户创建该类型的 Skill 时，前端根据此 Schema
        动态渲染配置表单。

        例如 Slack Skill 的配置包括 webhook_url、default_channel 等。

        Returns:
            JSON Schema dict
        """
        ...

    @abstractmethod
    def resolve(
        self,
        skill_config: dict[str, Any],
    ) -> list[ToolDefinition]:
        """
        将 Skill 配置解析为 ToolDefinition 列表

        SkillResolver 调用此方法，将一个 Skill 转换为 LLM 可调用的
        ToolDefinition 列表。一个 Skill 可产生多个 ToolDefinition。

        Args:
            skill_config: Skill 的配置（来自 Skill.config 字段）

        Returns:
            ToolDefinition 列表
        """
        ...

    @abstractmethod
    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: PluginContext,
    ) -> dict[str, Any] | str:
        """
        执行工具调用

        Sandbox 检测到插件工具时，委托给此方法执行。

        Args:
            tool_name: 工具名称（与 resolve() 返回的 ToolDefinition.name 对应）
            arguments: LLM 传入的参数
            context: 执行上下文（ExecutionContext 或 PluginContext）

        Returns:
            工具执行结果（将被序列化为字符串返回给 LLM）
        """
        ...

    def get_skill_metadata(self) -> dict[str, Any]:
        """
        返回完整的 Skill 类型元数据

        供 PluginManager 和前端使用。

        Returns:
            元数据字典
        """
        return {
            "skill_type": self.get_skill_type(),
            "display_name": self.get_skill_display_name(),
            "icon": self.get_skill_icon(),
            "config_schema": self.get_skill_config_schema(),
            "plugin_name": self.name,
            "plugin_version": self.version,
        }


__all__ = ["SkillPlugin"]
