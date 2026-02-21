"""
Socket.IO 同步桥接工具

在 Celery Worker（同步环境）中发送 Socket.IO 消息。
使用 socketio.RedisManager(write_only=True) 通过 Redis Pub/Sub 转发。
"""

from __future__ import annotations

from typing import Any

import socketio

from app.core.config import settings
from app.core.logging import LogManager

logger = LogManager.get_logger("app")

# 延迟初始化（避免在模块导入时创建连接）
_sync_mgr: socketio.RedisManager | None = None


def _get_sync_manager() -> socketio.RedisManager:
    """获取同步 Redis Manager（延迟初始化）"""
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

    用于 Celery Worker 中向前端推送通知。
    消息通过 Redis Pub/Sub 转发到 FastAPI 侧的 AsyncServer。

    Args:
        event: 事件名（如 'notification'）
        data: 事件数据
        room: 目标 room（如 'user:5'、'tenant:1'、'admins'）
        namespace: Socket.IO namespace（'/admin' | '/tenant' | '/user'）

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
    同步环境下发送通知给指定用户

    Args:
        user_type: 用户类型 (admin / tenant_admin / tenant_user)
        user_id: 用户 ID
        notification_data: 通知数据（type, category, title, body, data, priority）
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
    同步环境下广播通知给所有平台管理员

    Args:
        notification_data: 通知数据
    """
    sio_emit_sync(
        "notification",
        notification_data,
        room="admins",
        namespace="/admin",
    )


def notify_tenant_sync(
    tenant_id: int,
    notification_data: dict[str, Any],
    namespace: str = "/tenant",
) -> None:
    """
    同步环境下广播通知给指定租户所有在线用户

    Args:
        tenant_id: 租户 ID
        notification_data: 通知数据
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
]
