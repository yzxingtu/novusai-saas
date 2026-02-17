"""
事件总线

提供异步 pub/sub 事件分发机制，支持优先级和错误隔离
"""

import asyncio
import threading
from collections import defaultdict
from typing import Any, Callable, Coroutine

from app.ai.events.types import BaseEvent
from app.core.logging import LogManager

logger = LogManager.get_logger("ai.event_bus")

# 事件处理器类型：接收 BaseEvent 子类，返回 None
EventHandler = Callable[[BaseEvent], Coroutine[Any, Any, None]]


class _Subscription:
    """订阅记录，包含处理器和优先级"""

    __slots__ = ("handler", "priority")

    def __init__(self, handler: EventHandler, priority: int = 0):
        self.handler = handler
        self.priority = priority


class EventBus:
    """
    事件总线（进程内）

    特性：
    - 异步处理器（async def handler(event)）
    - 按优先级排序（数值越小越先执行）
    - 错误隔离（单个处理器异常不影响其他处理器）
    - 支持通配符订阅（BaseEvent 接收所有事件）
    - 线程安全的单例模式

    使用示例：
        bus = EventBus.get_instance()
        bus.subscribe(AgentCreated, my_handler, priority=10)
        await bus.publish(AgentCreated(tenant_id=1, agent_id=42))
    """

    _instance: "EventBus | None" = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        # event_type -> sorted list of _Subscription
        self._subscribers: dict[type[BaseEvent], list[_Subscription]] = defaultdict(list)
        # 保持 fire-and-forget task 引用，防止 GC 中断执行
        self._background_tasks: set[asyncio.Task] = set()

    @classmethod
    def get_instance(cls) -> "EventBus":
        """获取单例实例（线程安全）"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """重置单例（仅用于测试）"""
        cls._instance = None

    # ========================================
    # 订阅
    # ========================================

    def subscribe(
        self,
        event_type: type[BaseEvent],
        handler: EventHandler,
        priority: int = 0,
    ) -> None:
        """
        订阅事件

        Args:
            event_type: 事件类型（BaseEvent 子类）
            handler: 异步处理函数
            priority: 优先级（数值越小越先执行，默认 0）
        """
        sub = _Subscription(handler, priority)
        subs = self._subscribers[event_type]
        subs.append(sub)
        # 按优先级排序
        subs.sort(key=lambda s: s.priority)

        logger.debug(
            "Event handler subscribed: %s -> %s (priority=%d)",
            event_type.__name__,
            handler.__qualname__,
            priority,
        )

    def unsubscribe(
        self,
        event_type: type[BaseEvent],
        handler: EventHandler,
    ) -> bool:
        """
        取消订阅

        Args:
            event_type: 事件类型
            handler: 要移除的处理函数

        Returns:
            是否成功移除
        """
        subs = self._subscribers.get(event_type, [])
        before = len(subs)
        self._subscribers[event_type] = [
            s for s in subs if s.handler is not handler
        ]
        removed = before - len(self._subscribers[event_type])

        if removed > 0:
            logger.debug(
                "Event handler unsubscribed: %s -> %s",
                event_type.__name__,
                handler.__qualname__,
            )
        return removed > 0

    # ========================================
    # 发布
    # ========================================

    async def publish(self, event: BaseEvent) -> None:
        """
        发布事件（串行执行所有处理器）

        错误隔离：单个处理器异常会被捕获并记录，不影响其他处理器

        Args:
            event: 事件实例
        """
        event_type = type(event)
        handlers_called = 0

        # 收集匹配的订阅：精确类型 + BaseEvent 通配
        subscriptions: list[_Subscription] = []
        subscriptions.extend(self._subscribers.get(event_type, []))
        if event_type is not BaseEvent:
            subscriptions.extend(self._subscribers.get(BaseEvent, []))

        # 合并后重新按优先级排序
        subscriptions.sort(key=lambda s: s.priority)

        for sub in subscriptions:
            try:
                await sub.handler(event)
                handlers_called += 1
            except Exception as exc:
                logger.error(
                    "Event handler error: %s in %s: %s",
                    event_type.__name__,
                    sub.handler.__qualname__,
                    str(exc),
                    exc_info=True,
                )

        if handlers_called > 0:
            logger.debug(
                "Event dispatched: %s -> %d handlers",
                event_type.__name__,
                handlers_called,
            )

    async def publish_nowait(self, event: BaseEvent) -> None:
        """
        发布事件（fire-and-forget，不等待处理器完成）

        适用于不关心处理结果的场景。
        保存 Task 引用以防止 GC 在执行中回收。

        Args:
            event: 事件实例
        """
        task = asyncio.create_task(self.publish(event))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    # ========================================
    # 工具方法
    # ========================================

    def has_subscribers(self, event_type: type[BaseEvent]) -> bool:
        """检查事件类型是否有订阅者"""
        return len(self._subscribers.get(event_type, [])) > 0

    def subscriber_count(self, event_type: type[BaseEvent]) -> int:
        """获取事件类型的订阅者数量"""
        return len(self._subscribers.get(event_type, []))

    def clear(self) -> None:
        """清除所有订阅（仅用于测试）"""
        self._subscribers.clear()


# 全局便捷函数
def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    return EventBus.get_instance()


__all__ = ["EventBus", "EventHandler", "get_event_bus"]
