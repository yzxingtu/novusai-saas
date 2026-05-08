"""
Plugin lifecycle guard registry.
/ 插件生命周期阻断注册表

Provides a host-level blocking registry for plugin disable/uninstall checks.
Used before destructive lifecycle operations are executed.
/ 提供宿主级的阻断式插件生命周期校验注册表，
/ 用于在禁用/卸载等破坏性操作真正执行前做统一检查。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from threading import Lock
from typing import Any, Literal, TypedDict


class PluginLifecycleGuardPayload(TypedDict):
    """Lifecycle guard payload. / 生命周期阻断校验载荷。"""

    operation: Literal["disable", "uninstall"]
    plugin_id: int
    plugin_name: str
    force: bool
    manifest: dict[str, Any]


class PluginLifecycleGuardResult(TypedDict):
    """Lifecycle guard result. / 生命周期阻断校验结果。"""

    allowed: bool
    reason_code: str
    message: str
    details: dict[str, Any]


PluginLifecycleGuardHandler = Callable[
    [PluginLifecycleGuardPayload],
    Awaitable[PluginLifecycleGuardResult | None],
]


@dataclass(slots=True)
class _RegisteredPluginLifecycleGuardHandler:
    owner: str
    handler: PluginLifecycleGuardHandler
    priority: int


class PluginLifecycleGuardRegistry:
    """Singleton registry for blocking lifecycle handlers.
    / 阻断式生命周期处理器单例注册表。
    """

    _instance: PluginLifecycleGuardRegistry | None = None
    _instance_lock: Lock = Lock()

    def __init__(self) -> None:
        self._handlers: list[_RegisteredPluginLifecycleGuardHandler] = []
        self._lock = Lock()

    @classmethod
    def get_instance(cls) -> PluginLifecycleGuardRegistry:
        if cls._instance is not None:
            return cls._instance
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Testing helper. / 测试辅助方法。"""
        with cls._instance_lock:
            cls._instance = None

    def register(
        self,
        owner: str,
        handler: PluginLifecycleGuardHandler,
        *,
        priority: int = 50,
    ) -> None:
        """Register a lifecycle guard. / 注册生命周期阻断处理器。"""
        with self._lock:
            self._handlers = [
                item
                for item in self._handlers
                if not (item.owner == owner and item.handler == handler)
            ]
            self._handlers.append(
                _RegisteredPluginLifecycleGuardHandler(
                    owner=owner,
                    handler=handler,
                    priority=priority,
                )
            )
            self._handlers.sort(key=lambda item: item.priority)

    def unregister(
        self,
        owner: str,
        handler: PluginLifecycleGuardHandler | None = None,
    ) -> None:
        """Unregister a handler or all handlers from an owner.
        / 注销指定处理器，或注销某 owner 的全部处理器。
        """
        with self._lock:
            self._handlers = [
                item
                for item in self._handlers
                if not (
                    item.owner == owner and (handler is None or item.handler == handler)
                )
            ]

    async def run(
        self,
        payload: PluginLifecycleGuardPayload,
    ) -> PluginLifecycleGuardResult:
        """Run lifecycle guards in priority order and stop on denial.
        / 按优先级执行生命周期阻断处理器，遇到拒绝立即停止。
        """
        with self._lock:
            handlers = list(self._handlers)

        for item in handlers:
            result = await item.handler(payload)
            if not result:
                continue
            if result.get("allowed") is not True:
                return {
                    "allowed": False,
                    "reason_code": str(
                        result.get("reason_code") or "lifecycle_blocked"
                    ),
                    "message": str(result.get("message") or ""),
                    "details": dict(result.get("details") or {}),
                }

        return {
            "allowed": True,
            "reason_code": "allowed",
            "message": "",
            "details": {},
        }


def get_plugin_lifecycle_guard_registry() -> PluginLifecycleGuardRegistry:
    """Get singleton registry. / 获取单例注册表。"""
    return PluginLifecycleGuardRegistry.get_instance()


async def run_plugin_lifecycle_guards(
    payload: PluginLifecycleGuardPayload,
) -> PluginLifecycleGuardResult:
    """Convenience runner. / 便捷执行入口。"""
    from app.plugins.feature_entitlement_guards import (
        ensure_feature_entitlement_guards_registered,
    )

    ensure_feature_entitlement_guards_registered()
    registry = get_plugin_lifecycle_guard_registry()
    return await registry.run(payload)


__all__ = [
    "PluginLifecycleGuardPayload",
    "PluginLifecycleGuardResult",
    "PluginLifecycleGuardHandler",
    "PluginLifecycleGuardRegistry",
    "get_plugin_lifecycle_guard_registry",
    "run_plugin_lifecycle_guards",
]
