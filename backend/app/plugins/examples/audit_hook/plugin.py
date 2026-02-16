"""
Audit Hook Plugin — HookPlugin 示例

演示如何创建一个事件钩子插件，订阅系统事件并记录审计日志。

订阅事件：
- ConversationCompleted: 对话完成时记录 token 消耗
- ToolCallFailed: 工具调用失败时记录错误
- AgentCreated: 智能体创建时记录
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from app.core.logging import LogManager
from app.plugins.context import PluginContext
from app.plugins.extensions.hook_plugin import EventHandler, HookPlugin

if TYPE_CHECKING:
    from app.ai.events.types import BaseEvent

logger = LogManager.get_logger("app")


class AuditHookPlugin(HookPlugin):
    """
    审计日志钩子插件

    订阅关键系统事件，将事件信息记录到日志中。
    实际生产中可将日志写入数据库、发送到外部审计系统等。
    """

    @property
    def name(self) -> str:
        return "audit-hook"

    @property
    def display_name(self) -> str:
        return "Audit Hook"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Subscribes to system events and logs audit information"

    @property
    def author(self) -> str:
        return "NovusAI"

    def get_event_handlers(
        self,
    ) -> list[tuple[type[BaseEvent], EventHandler, int]]:
        """
        返回事件处理器列表

        Returns:
            [(event_type, handler, priority), ...]
            priority: 数值越小越先执行，100 表示较低优先级
        """
        from app.ai.events.types import (
            AgentCreated,
            ConversationCompleted,
            ToolCallFailed,
        )

        return [
            (ConversationCompleted, self._on_conversation_completed, 100),
            (ToolCallFailed, self._on_tool_call_failed, 100),
            (AgentCreated, self._on_agent_created, 100),
        ]

    async def _on_conversation_completed(self, event: Any) -> None:
        """对话完成事件处理：记录 token 消耗"""
        logger.info(
            "[AuditHook] Conversation completed: "
            "conversation_id=%s total_tokens=%s",
            getattr(event, "conversation_id", "?"),
            getattr(event, "total_tokens", 0),
        )

    async def _on_tool_call_failed(self, event: Any) -> None:
        """工具调用失败事件处理：记录错误信息"""
        logger.info(
            "[AuditHook] Tool call failed: "
            "conversation_id=%s tool=%s error=%s",
            getattr(event, "conversation_id", "?"),
            getattr(event, "tool_name", "?"),
            getattr(event, "error", ""),
        )

    async def _on_agent_created(self, event: Any) -> None:
        """智能体创建事件处理：记录创建信息"""
        logger.info(
            "[AuditHook] Agent created: agent_id=%s name=%s",
            getattr(event, "agent_id", "?"),
            getattr(event, "agent_name", "?"),
        )

    async def on_enable(self, ctx: PluginContext) -> None:
        """插件启用时的回调"""
        if ctx.logger:
            ctx.logger.info("AuditHookPlugin enabled — subscribing to events")

    async def on_disable(self, ctx: PluginContext) -> None:
        """插件禁用时的回调"""
        if ctx.logger:
            ctx.logger.info("AuditHookPlugin disabled — events unsubscribed")
