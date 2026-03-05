"""
跨插件事件总线（Plugin EventBus）

用于插件间异步通知（fire-and-forget），与 HookRegistry 互补：
- HookRegistry: 同步拦截，可修改上下文数据，支持 BEFORE_*/AFTER_* 模式
- PluginEventBus: 异步通知，只读，handler 异常不影响发布方

命名规范：plugin.{source_plugin}.{event_name}
Payload 字段：source_plugin, event_name, tenant_id, timestamp + 自定义 data

设计原则：
- 单 handler 异常隔离，不影响其他 handler 和发布方
- 单 handler 超时保护（默认 30s）
- 最大 payload 大小限制（默认 1MB）
- 结构化日志记录每次事件分发
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# 默认单 handler 超时（秒）
_DEFAULT_HANDLER_TIMEOUT = 30.0

# 最大 payload 大小（字节，粗略估算）
_MAX_PAYLOAD_SIZE = 1_048_576  # 1 MB


class PluginEventBus:
    """
    跨插件事件总线（单例）

    与 HookRegistry 的区别：
    - Hook: 同步拦截链，handler 可修改 context dict，按 priority 串行执行
    - PluginEvent: 异步通知，handler 只读，并行执行，异常隔离

    用法：
    - 发布: await bus.publish("plugin.novusdoc.document_saved", {...})
    - 订阅: bus.subscribe("plugin.novusdoc.document_saved", handler)
    - 取消: bus.unsubscribe("plugin.novusdoc.document_saved", handler)
    """

    _instance: PluginEventBus | None = None

    # 死信队列最大容量（内存环形缓冲）
    _MAX_DEAD_LETTERS = 100

    def __init__(self) -> None:
        self._subscribers: dict[str, list[_Subscription]] = defaultdict(list)
        self._dead_letters: list[dict[str, Any]] = []

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
        订阅事件

        Args:
            event_name: 完整事件名（如 "plugin.novusdoc.document_saved"）
            handler: 异步或同步处理函数，签名 (event_name, payload) -> None
            plugin_name: 订阅方插件名（用于日志和反注册）
            priority: 执行优先级（数字越小越优先）
            timeout: 单 handler 超时（秒）
        """
        sub = _Subscription(
            handler=handler,
            plugin_name=plugin_name,
            priority=priority,
            timeout=timeout,
        )
        subs = self._subscribers[event_name]

        # 去重：同 handler + plugin_name 不重复订阅
        for existing in subs:
            if existing.handler is handler and existing.plugin_name == plugin_name:
                return

        subs.append(sub)
        subs.sort(key=lambda s: s.priority)
        logger.info(
            "PluginEventBus: %s subscribed to '%s' (priority=%d)",
            plugin_name or "unknown", event_name, priority,
        )

    def unsubscribe(
        self,
        event_name: str,
        handler: Callable[..., Any] | None = None,
        plugin_name: str = "",
    ) -> int:
        """
        取消订阅

        Args:
            event_name: 事件名
            handler: 具体 handler（None 则按 plugin_name 全部移除）
            plugin_name: 插件名

        Returns:
            移除的订阅数
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
                "PluginEventBus: removed %d subscription(s) from '%s'",
                removed, event_name,
            )
        return removed

    def unsubscribe_all(self, plugin_name: str) -> int:
        """移除某插件的所有事件订阅"""
        total_removed = 0
        for _event_name, subs in self._subscribers.items():
            before = len(subs)
            subs[:] = [s for s in subs if s.plugin_name != plugin_name]
            total_removed += before - len(subs)

        if total_removed > 0:
            logger.info(
                "PluginEventBus: removed all %d subscription(s) for plugin '%s'",
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
        发布事件（异步通知所有订阅者）

        Args:
            event_name: 完整事件名
            payload: 事件数据（只读，handler 不应修改）
            source_plugin: 发布方插件名

        Returns:
            {"delivered": N, "failed": N, "errors": [...]}
        """
        subs = self._subscribers.get(event_name, [])
        if not subs:
            logger.debug(
                "PluginEventBus: no subscribers for '%s'", event_name,
            )
            return {"delivered": 0, "failed": 0, "errors": []}

        # Payload 大小检查
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
                "PluginEventBus: payload too large for '%s' (%d bytes, max %d)",
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

        # 并行执行所有 handler（异常隔离）
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
                    "PluginEventBus: handler failed for '%s' (plugin=%s): %s",
                    event_name, subs[i].plugin_name, result,
                )
                # 记入死信队列
                self._record_dead_letter(
                    event_name, source_plugin, subs[i].plugin_name, str(result),
                )
            else:
                delivered += 1

        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.info(
            "plugin_event: event=%s source=%s subscribers=%d delivered=%d "
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
        """执行单个 handler，带超时保护"""
        if asyncio.iscoroutinefunction(sub.handler):
            await asyncio.wait_for(
                sub.handler(event_name, payload),
                timeout=sub.timeout,
            )
        else:
            sub.handler(event_name, payload)

    def _record_dead_letter(
        self,
        event_name: str,
        source_plugin: str,
        handler_plugin: str,
        error: str,
    ) -> None:
        """记录失败事件到死信队列（内存环形缓冲，超容量丢弃最旧的）"""
        entry = {
            "event": event_name,
            "source": source_plugin,
            "handler": handler_plugin,
            "error": error,
            "timestamp": time.time(),
        }
        self._dead_letters.append(entry)
        if len(self._dead_letters) > self._MAX_DEAD_LETTERS:
            self._dead_letters = self._dead_letters[-self._MAX_DEAD_LETTERS:]

    def get_dead_letters(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取最近的死信记录（供管理员健康页查看）"""
        return list(reversed(self._dead_letters[-limit:]))

    def clear_dead_letters(self) -> int:
        """清空死信队列，返回清除的数量"""
        count = len(self._dead_letters)
        self._dead_letters.clear()
        return count

    def has_subscribers(self, event_name: str) -> bool:
        return bool(self._subscribers.get(event_name))

    def get_subscriber_count(self, event_name: str) -> int:
        return len(self._subscribers.get(event_name, []))


class _Subscription:
    """内部订阅记录"""

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
    """获取全局 PluginEventBus 实例"""
    return PluginEventBus.get_instance()


__all__ = ["PluginEventBus", "get_plugin_event_bus"]
