"""
Socket.IO Namespace 模块

注册所有 Socket.IO namespace 到 AsyncServer 实例。
"""

import socketio

from app.core.logging import LogManager

logger = LogManager.get_logger("app")


def register_namespaces(sio: socketio.AsyncServer) -> None:
    """
    注册所有 Socket.IO namespace

    Args:
        sio: AsyncServer 实例
    """
    from app.sio.admin_ns import AdminNamespace
    from app.sio.collaboration_ns import CollaborationNamespace
    from app.sio.tenant_ns import TenantNamespace
    from app.sio.user_ns import UserNamespace

    sio.register_namespace(AdminNamespace("/admin"))
    sio.register_namespace(TenantNamespace("/tenant"))
    sio.register_namespace(UserNamespace("/user"))
    sio.register_namespace(CollaborationNamespace("/collaboration"))

    logger.info(
        "Socket.IO namespaces registered: /admin, /tenant, /user, /collaboration",
    )


__all__ = ["register_namespaces"]
