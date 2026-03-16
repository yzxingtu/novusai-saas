"""
Socket.IO 同步桥接工具 / Socket.IO Sync Bridge Utility

在 Celery Worker（同步环境）中发送 Socket.IO 消息。
Sends Socket.IO messages from Celery Worker (sync environment).
使用 socketio.RedisManager(write_only=True) 通过 Redis Pub/Sub 转发。
Uses socketio.RedisManager(write_only=True) to forward via Redis Pub/Sub.
"""

from __future__ import annotations

from typing import Any

import socketio

from app.core.config import settings
from app.core.logging import LogManager

logger = LogManager.get_logger("app")

# 延迟初始化（避免在模块导入时创建连接） / Lazy init (avoid creating connection on module import)
_sync_mgr: socketio.RedisManager | None = None


def _get_sync_manager() -> socketio.RedisManager:
    """获取同步 Redis Manager（延迟初始化） / Get sync Redis Manager (lazy init)"""
    global _sync_mgr
    if _sync_mgr is None:
        _sync_mgr = socketio.RedisManager(
            settings.REDIS_URL,
            write_only=True,
        )
    return _sync_mgr


def sio_emit_sync(
    event: str,
    data: dict[str, Any],
    room: str | None = None,
    namespace: str = "/admin",
) -> None:
    """
    同步环境下发送 Socket.IO 消息
    Send Socket.IO message from sync environment.

    用于 Celery Worker 中向前端推送通知。
    消息通过 Redis Pub/Sub 转发到 FastAPI 侧的 AsyncServer。
    Used in Celery Worker to push notifications to frontend.
    Messages are forwarded to FastAPI's AsyncServer via Redis Pub/Sub.

    Args:
        event: 事件名（如 'notification'） / Event name (e.g. 'notification')
        data: 事件数据 / Event data
        room: 目标 room（如 'user:5'、'tenant:1'、'admins'） / Target room
        namespace: Socket.IO namespace（'/admin' | '/tenant' | '/user'） / Socket.IO namespace

    Example:
        sio_emit_sync(
            "notification",
            {"type": "task.completed", "title": "Task done"},
            room="user:5",
            namespace="/admin",
        )
    """
    try:
        mgr = _get_sync_manager()
        mgr.emit(event, data, room=room, namespace=namespace)
        logger.debug(
            "SIO sync emit: event=%s room=%s namespace=%s",
            event, room, namespace,
        )
    except Exception as e:
        logger.warning("SIO sync emit failed: %s", str(e))


def notify_user_sync(
    user_type: str,
    user_id: int,
    notification_data: dict[str, Any],
) -> None:
    """
    同步环境下发送通知给指定用户 / Send notification to a specific user from sync environment

    Args:
        user_type: 用户类型 / User type (admin / tenant_admin / tenant_user)
        user_id: 用户 ID / User ID
        notification_data: 通知数据（type, category, title, body, data, priority） / Notification data
    """
    ns_map = {
        "admin": "/admin",
        "tenant_admin": "/tenant",
        "tenant_user": "/user",
    }
    namespace = ns_map.get(user_type, "/admin")
    sio_emit_sync(
        "notification",
        notification_data,
        room=f"user:{user_id}",
        namespace=namespace,
    )


def notify_admins_sync(notification_data: dict[str, Any]) -> None:
    """
    同步环境下广播通知给所有平台管理员 / Broadcast notification to all platform admins from sync environment

    Args:
        notification_data: 通知数据 / Notification data
    """
    sio_emit_sync(
        "notification",
        notification_data,
        room="admins",
        namespace="/admin",
    )


# user_type -> namespace 映射（强制下线仅发送到对应用户类型所在 namespace）
# user_type to namespace mapping (force_logout only sent to corresponding user type's namespace)
NS_MAP = {
    "admin": "/admin",
    "tenant_admin": "/tenant",
    "tenant_user": "/user",
}


async def emit_force_logout(user_id: int, user_type: str) -> None:
    """
    向指定用户所在的 Socket.IO namespace 发送强制下线事件
    Emit force_logout event to user's Socket.IO namespace.

    三个 namespace 的 user_id 是独立序列（Admin.id=5 ≠ TenantAdmin.id=5），
    必须按 user_type 仅向对应 namespace 发送，避免误踢其他端同名 ID 用户。
    Three namespaces have separate user_id sequences; emit only to the correct one.

    Args:
        user_id: 用户 ID（对应 room 中的 user_id）/ User ID
        user_type: 用户类型 admin/tenant_admin/tenant_user / User type
    """
    try:
        from app.core.socketio_server import sio
        room = f"user:{user_id}"
        payload = {"reason": "admin_force_logout"}
        ns = NS_MAP.get(user_type)
        if ns:
            await sio.emit("force_logout", payload, room=room, namespace=ns)
    except Exception:
        pass  # 静默失败，不影响主流程 / Fail silently


def notify_tenant_sync(
    tenant_id: int,
    notification_data: dict[str, Any],
    namespace: str = "/tenant",
) -> None:
    """
    同步环境下广播通知给指定企业所有在线用户 / Broadcast notification to all online users of a tenant from sync environment

    Args:
        tenant_id: 企业 ID / Tenant ID
        notification_data: 通知数据 / Notification data
        namespace: Socket.IO namespace
    """
    sio_emit_sync(
        "notification",
        notification_data,
        room=f"tenant:{tenant_id}",
        namespace=namespace,
    )


__all__ = [
    "sio_emit_sync",
    "notify_user_sync",
    "notify_admins_sync",
    "notify_tenant_sync",
    "emit_force_logout",
]
