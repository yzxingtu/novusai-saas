"""
Cross-plugin event bus (Plugin EventBus) / 跨插件事件总线

For async inter-plugin notifications (fire-and-forget), complementary to HookRegistry:
- HookRegistry: sync interception, can modify context data, supports BEFORE_*/AFTER_* pattern
- PluginEventBus: async notification, read-only, handler errors don't affect publisher
/
用于插件间异步通知（fire-and-forget），与 HookRegistry 互补：
- HookRegistry: 同步拦截，可修改上下文数据，支持 BEFORE_*/AFTER_* 模式
- PluginEventBus: 异步通知，只读，handler 异常不影响发布方

Naming convention / 命名规范：plugin.{source_plugin}.{event_name}
Payload fields / Payload 字段：source_plugin, event_name, tenant_id, timestamp + custom data

Design principles / 设计原则：
- Single handler error isolation / 单 handler 异常隔离
- Single handler timeout protection (default 30s) / 单 handler 超时保护
- Max payload size limit (default 1MB) / 最大 payload 大小限制
- Structured logging for each event dispatch / 结构化日志记录
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Default single handler timeout (seconds) / 默认单 handler 超时（秒）
_DEFAULT_HANDLER_TIMEOUT = 30.0

# Max payload size (bytes, rough estimate) / 最大 payload 大小（字节，粗略估算）
_MAX_PAYLOAD_SIZE = 1_048_576  # 1 MB


class PluginEventBus:
    """
    Cross-plugin event bus (singleton) / 跨插件事件总线（单例）

    Difference from HookRegistry / 与 HookRegistry 的区别：
    - Hook: sync interception chain, handler can modify context dict, serial by priority
      / 同步拦截链，handler 可修改 context dict，按 priority 串行执行
    - PluginEvent: async notification, handler read-only, parallel execution, error isolation
      / 异步通知，handler 只读，并行执行，异常隔离

    Usage / 用法：
    - Publish / 发布: await bus.publish("plugin.novusdoc.document_saved", {...})
    - Subscribe / 订阅: bus.subscribe("plugin.novusdoc.document_saved", handler)
    - Unsubscribe / 取消: bus.unsubscribe("plugin.novusdoc.document_saved", handler)
    """

    _instance: PluginEventBus | None = None

    # Dead letter queue max capacity (in-memory ring buffer) / 死信队列最大容量（内存环形缓冲）
    _MAX_DEAD_LETTERS = 100

    def __init__(self) -> None:
        self._subscribers: dict[str, list[_Subscription]] = defaultdict(list)
        self._dead_letters: deque[dict[str, Any]] = deque(maxlen=self._MAX_DEAD_LETTERS)

    @classmethod
    def get_instance(cls) -> PluginEventBus:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def subscribe(
        self,
        event_name: str,
        handler: Callable[..., Any],
        plugin_name: str = "",
        priority: int = 100,
        timeout: float = _DEFAULT_HANDLER_TIMEOUT,
    ) -> None:
        """
        Subscribe to event / 订阅事件

        Args:
            event_name: Full event name (e.g. "plugin.novusdoc.document_saved") / 完整事件名
            handler: Async or sync handler function, signature (event_name, payload) -> None
                     / 异步或同步处理函数
            plugin_name: Subscriber plugin name (for logging and unregistration) / 订阅方插件名
            priority: Execution priority (lower number = higher priority) / 执行优先级
            timeout: Single handler timeout (seconds) / 单 handler 超时（秒）
        """
        sub = _Subscription(
            handler=handler,
            plugin_name=plugin_name,
            priority=priority,
            timeout=timeout,
        )
        subs = self._subscribers[event_name]

        # Dedup: same handler + plugin_name won't subscribe again / 去重：同 handler + plugin_name 不重复订阅
        for existing in subs:
            if existing.handler is handler and existing.plugin_name == plugin_name:
                return

        subs.append(sub)
        subs.sort(key=lambda s: s.priority)
        logger.info(
            "PluginEventBus: {} subscribed to '{}' (priority={})",
            plugin_name or "unknown", event_name, priority,
        )

    def unsubscribe(
        self,
        event_name: str,
        handler: Callable[..., Any] | None = None,
        plugin_name: str = "",
    ) -> int:
        """
        Unsubscribe / 取消订阅

        Args:
            event_name: Event name / 事件名
            handler: Specific handler (None removes all by plugin_name) / 具体 handler（None 则按 plugin_name 全部移除）
            plugin_name: Plugin name / 插件名

        Returns:
            Number of subscriptions removed / 移除的订阅数
        """
        subs = self._subscribers.get(event_name, [])
        before = len(subs)

        if handler:
            subs[:] = [s for s in subs if s.handler is not handler]
        elif plugin_name:
            subs[:] = [s for s in subs if s.plugin_name != plugin_name]

        removed = before - len(subs)
        if removed > 0:
            logger.info(
                "PluginEventBus: removed {} subscription(s) from '{}'",
                removed, event_name,
            )
        return removed

    def unsubscribe_all(self, plugin_name: str) -> int:
        """Remove all event subscriptions for a plugin / 移除某插件的所有事件订阅"""
        total_removed = 0
        for _event_name, subs in self._subscribers.items():
            before = len(subs)
            subs[:] = [s for s in subs if s.plugin_name != plugin_name]
            total_removed += before - len(subs)

        if total_removed > 0:
            logger.info(
                "PluginEventBus: removed all {} subscription(s) for plugin '{}'",
                total_removed, plugin_name,
            )
        return total_removed

    async def publish(
        self,
        event_name: str,
        payload: dict[str, Any] | None = None,
        source_plugin: str = "",
    ) -> dict[str, Any]:
        """
        Publish event (async notify all subscribers) / 发布事件（异步通知所有订阅者）

        Args:
            event_name: Full event name / 完整事件名
            payload: Event data (read-only, handlers should not modify) / 事件数据（只读）
            source_plugin: Publisher plugin name / 发布方插件名

        Returns:
            {"delivered": N, "failed": N, "errors": [...]}
        """
        subs = self._subscribers.get(event_name, [])
        if not subs:
            logger.debug(
                "PluginEventBus: no subscribers for '{}'", event_name,
            )
            return {"delivered": 0, "failed": 0, "errors": []}

        # Payload size check / Payload 大小检查
        safe_payload = dict(payload or {})
        safe_payload["_event_name"] = event_name
        safe_payload["_source_plugin"] = source_plugin
        safe_payload["_timestamp"] = time.time()

        try:
            payload_size = len(json.dumps(safe_payload, default=str).encode())
        except (TypeError, ValueError):
            payload_size = sys.getsizeof(str(safe_payload))
        if payload_size > _MAX_PAYLOAD_SIZE:
            logger.warning(
                "PluginEventBus: payload too large for '{}' ({} bytes, max {})",
                event_name, payload_size, _MAX_PAYLOAD_SIZE,
            )
            return {
                "delivered": 0,
                "failed": 0,
                "errors": [f"Payload too large: {payload_size} bytes"],
            }

        start = time.perf_counter()
        delivered = 0
        failed = 0
        errors: list[str] = []

        # Execute all handlers in parallel (error isolation) / 并行执行所有 handler（异常隔离）
        tasks = [
            self._invoke_handler(sub, event_name, safe_payload)
            for sub in subs
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed += 1
                err_msg = f"{subs[i].plugin_name}: {result}"
                errors.append(err_msg)
                logger.warning(
                    "PluginEventBus: handler failed for '{}' (plugin={}): {}",
                    event_name, subs[i].plugin_name, result,
                )
                # Record to dead letter queue / 记入死信队列
                self._record_dead_letter(
                    event_name, source_plugin, subs[i].plugin_name, str(result),
                )
            else:
                delivered += 1

        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "plugin_event: event={} source={} subscribers={} delivered={} "
            "failed=%d latency_ms=%d",
            event_name, source_plugin, len(subs),
            delivered, failed, latency_ms,
        )

        return {"delivered": delivered, "failed": failed, "errors": errors}

    @staticmethod
    async def _invoke_handler(
        sub: _Subscription,
        event_name: str,
        payload: dict[str, Any],
    ) -> None:
        """Execute single handler with timeout protection / 执行单个 handler，带超时保护"""
        if asyncio.iscoroutinefunction(sub.handler):
            await asyncio.wait_for(
                sub.handler(event_name, payload),
                timeout=sub.timeout,
            )
        else:
            await asyncio.wait_for(
                asyncio.to_thread(sub.handler, event_name, payload),
                timeout=sub.timeout,
            )

    def _record_dead_letter(
        self,
        event_name: str,
        source_plugin: str,
        handler_plugin: str,
        error: str,
    ) -> None:
        """Record failed event to dead letter queue (in-memory ring buffer, discards oldest on overflow) / 记录失败事件到死信队列"""
        entry = {
            "event": event_name,
            "source": source_plugin,
            "handler": handler_plugin,
            "error": error,
            "timestamp": time.time(),
        }
        self._dead_letters.append(entry)

    def get_dead_letters(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent dead letter records (for admin health page) / 获取最近的死信记录（供管理员健康页查看）"""
        return list(reversed(self._dead_letters[-limit:]))

    def clear_dead_letters(self) -> int:
        """Clear dead letter queue, return count of cleared items / 清空死信队列，返回清除的数量"""
        count = len(self._dead_letters)
        self._dead_letters.clear()
        return count

    def has_subscribers(self, event_name: str) -> bool:
        return bool(self._subscribers.get(event_name))

    def get_subscriber_count(self, event_name: str) -> int:
        return len(self._subscribers.get(event_name, []))


class _Subscription:
    """Internal subscription record / 内部订阅记录"""

    __slots__ = ("handler", "plugin_name", "priority", "timeout")

    def __init__(
        self,
        handler: Callable[..., Any],
        plugin_name: str,
        priority: int,
        timeout: float,
    ) -> None:
        self.handler = handler
        self.plugin_name = plugin_name
        self.priority = priority
        self.timeout = timeout


def get_plugin_event_bus() -> PluginEventBus:
    """Get global PluginEventBus instance / 获取全局 PluginEventBus 实例"""
    return PluginEventBus.get_instance()


__all__ = ["PluginEventBus", "get_plugin_event_bus"]
