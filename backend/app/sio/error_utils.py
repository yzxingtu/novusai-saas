"""
Socket.IO error helpers / Socket.IO 错误辅助函数
"""

from __future__ import annotations

from typing import Any

from socketio.exceptions import ConnectionRefusedError as SocketConnectionRefusedError

from app.core.i18n import _
from app.core.response import (
    build_exception_debug,
    build_socket_connect_error,
)

_SOCKET_REASON_CODE_MAP: dict[str, int | str] = {
    "account_not_found": 4040,
    "authentication_failed": 4010,
    "connection_failed": 5000,
    "max_connections_exceeded": 4290,
    "rate_limited": 4290,
    "token_expired": 4011,
    "token_required": 4010,
    "websocket_disabled": 5030,
}

_SOCKET_REASON_MESSAGE_MAP: dict[str, str] = {
    "account_not_found": _("common.not_found"),
    "authentication_failed": _("common.unauthorized"),
    "connection_failed": _("common.server_error"),
    "max_connections_exceeded": _("rate_limited"),
    "rate_limited": _("rate_limited"),
    "token_expired": _("token_expired"),
    "token_required": _("common.unauthorized"),
    "websocket_disabled": _("common.server_error"),
}


def socket_connect_refusal(
    reason: str,
    *,
    exc: BaseException | None = None,
    extra: dict[str, Any] | None = None,
) -> SocketConnectionRefusedError:
    """Create ConnectionRefusedError with structured payload / 创建带结构化载荷的 ConnectionRefusedError。"""
    return build_socket_connect_error(
        reason,
        code=_SOCKET_REASON_CODE_MAP.get(reason, 5000),
        message=_SOCKET_REASON_MESSAGE_MAP.get(reason, _("common.server_error")),
        debug=build_exception_debug(exc) if exc is not None else None,
        extra=extra,
    )


__all__ = ["socket_connect_refusal"]
