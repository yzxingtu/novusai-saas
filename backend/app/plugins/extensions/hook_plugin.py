"""
事件钩子扩展点

允许插件订阅和响应系统事件
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, Callable, Coroutine, TYPE_CHECKING

from app.plugins.base import BasePlugin

if TYPE_CHECKING:
    from app.ai.events.types import BaseEvent

# 事件处理器类型
EventHandler = Callable[[Any], Coroutine[Any, Any, None]]


class HookPlugin(BasePlugin):
    """
    事件钩子插件接口

    继承此类来订阅系统事件（如智能体创建、对话完成、工具调用等）。
    PluginManager 启用插件时会调用 get_event_handlers() 获取处理器映射，
    并注册到 EventBus 中。

    使用示例::

        class AuditPlugin(HookPlugin):
            @property
            def name(self) -> str:
                return "novusai-audit-hook"

            @property
            def display_name(self) -> str:
                return "Audit Logger"

            @property
            def version(self) -> str:
                return "1.0.0"

            def get_event_handlers(self) -> list[tuple[type[BaseEvent], EventHandler, int]]:
                from app.ai.events.types import ConversationCompleted
                return [
                    (ConversationCompleted, self._on_conversation_completed, 100),
                ]

            async def _on_conversation_completed(self, event):
                # 记录审计日志...
                pass
    """

    @abstractmethod
    def get_event_handlers(
        self,
    ) -> list[tuple[type[BaseEvent], EventHandler, int]]:
        """
        返回事件处理器列表

        每个元素是一个三元组：
        - event_type: 要订阅的事件类型（BaseEvent 子类）
        - handler: 异步处理函数 async def handler(event) -> None
        - priority: 优先级（数值越小越先执行，默认 0）

        Returns:
            [(event_type, handler, priority), ...]
        """
        ...


__all__ = ["HookPlugin", "EventHandler"]
