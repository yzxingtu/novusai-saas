"""
Tenant plan preflight registry.
/ 企业套餐前置校验注册表

Provides a host-level blocking registry for plan/tenant entitlement checks.
Used before plan create/update and tenant plan assignment flows.
/ 提供宿主级的阻断式校验注册表，
/ 用于套餐创建/更新与企业绑定套餐之前的统一前置校验。
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any, Awaitable, Callable, Literal, TypedDict


class TenantPlanPreflightPayload(TypedDict):
    """Preflight payload for plan/tenant operations. / 套餐/企业操作的前置校验载荷。"""

    operation: Literal[
        "plan_create",
        "plan_update",
        "tenant_create",
        "tenant_plan_switch",
    ]
    plan_id: int | None
    tenant_id: int | None
    features: dict[str, Any]
    quota: dict[str, Any]
    context: dict[str, Any]


class TenantPlanPreflightResult(TypedDict):
    """Preflight result contract. / 前置校验结果契约。"""

    allowed: bool
    reason_code: str
    message: str
    details: dict[str, Any]


TenantPlanPreflightHandler = Callable[
    [TenantPlanPreflightPayload],
    Awaitable[TenantPlanPreflightResult | None],
]


@dataclass(slots=True)
class _RegisteredTenantPlanPreflightHandler:
    owner: str
    handler: TenantPlanPreflightHandler
    priority: int


class TenantPlanPreflightRegistry:
    """Singleton registry for blocking tenant plan preflight handlers.
    / 阻断式套餐前置校验处理器单例注册表。
    """

    _instance: "TenantPlanPreflightRegistry | None" = None
    _instance_lock: Lock = Lock()

    def __init__(self) -> None:
        self._handlers: list[_RegisteredTenantPlanPreflightHandler] = []
        self._lock = Lock()

    @classmethod
    def get_instance(cls) -> "TenantPlanPreflightRegistry":
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
        handler: TenantPlanPreflightHandler,
        *,
        priority: int = 50,
    ) -> None:
        """Register a preflight handler. / 注册前置校验处理器。"""
        with self._lock:
            self._handlers = [
                item
                for item in self._handlers
                if not (item.owner == owner and item.handler == handler)
            ]
            self._handlers.append(
                _RegisteredTenantPlanPreflightHandler(
                    owner=owner,
                    handler=handler,
                    priority=priority,
                )
            )
            self._handlers.sort(key=lambda item: item.priority)

    def unregister(
        self,
        owner: str,
        handler: TenantPlanPreflightHandler | None = None,
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

    def list_handlers(self) -> list[dict[str, Any]]:
        """Return a safe handler summary. / 返回安全的处理器摘要。"""
        with self._lock:
            return [
                {
                    "owner": item.owner,
                    "priority": item.priority,
                }
                for item in self._handlers
            ]

    async def run(
        self,
        payload: TenantPlanPreflightPayload,
    ) -> TenantPlanPreflightResult:
        """Run handlers in priority order and stop on first denial.
        / 按优先级执行处理器，遇到首个拒绝结果立即停止。
        """
        with self._lock:
            handlers = list(self._handlers)

        for item in handlers:
            result = await item.handler(payload)
            if not result:
                continue
            if not result.get("allowed", True):
                return {
                    "allowed": False,
                    "reason_code": str(result.get("reason_code") or "preflight_denied"),
                    "message": str(result.get("message") or ""),
                    "details": dict(result.get("details") or {}),
                }

        return {
            "allowed": True,
            "reason_code": "allowed",
            "message": "",
            "details": {},
        }


def get_tenant_plan_preflight_registry() -> TenantPlanPreflightRegistry:
    """Get singleton registry. / 获取单例注册表。"""
    return TenantPlanPreflightRegistry.get_instance()


async def run_tenant_plan_preflight(
    payload: TenantPlanPreflightPayload,
) -> TenantPlanPreflightResult:
    """Convenience runner. / 便捷执行入口。"""
    from app.plugins.feature_entitlement_guards import (
        ensure_feature_entitlement_guards_registered,
    )

    ensure_feature_entitlement_guards_registered()
    registry = get_tenant_plan_preflight_registry()
    return await registry.run(payload)


__all__ = [
    "TenantPlanPreflightPayload",
    "TenantPlanPreflightResult",
    "TenantPlanPreflightHandler",
    "TenantPlanPreflightRegistry",
    "get_tenant_plan_preflight_registry",
    "run_tenant_plan_preflight",
]
