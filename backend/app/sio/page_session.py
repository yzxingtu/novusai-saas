"""
Page Session Room Management
页面会话房间管理

Handles frontend page_session_join / page_session_leave events,
joining/leaving client sid to/from page_session:{id} rooms.
处理前端 page_session_join / page_session_leave 事件，
将客户端 sid 加入/离开 page_session:{id} 房间。

Backend dispatches page_operation_invoke events to specified page_session_id rooms
via invoke_page_operation(), frontend executes and returns results via page_operation_result.
后端通过 invoke_page_operation() 向指定 page_session_id 房间
下发 page_operation_invoke 事件，前端执行后通过 page_operation_result 回传结果。
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import socketio

from app.core.logging import LogManager

logger = LogManager.get_logger("app")

# invoke_id → Future mapping, for awaiting frontend result callback / invoke_id → Future 映射，用于等待前端回传结果
_pending_invocations: dict[str, asyncio.Future[dict[str, Any]]] = {}

# Default operation timeout (seconds) / 默认操作超时（秒）
PAGE_OPERATION_TIMEOUT = 30


class PageSessionMixin:
    """
    Mixin: Adds page_session room management to AsyncNamespace subclasses.
    Mixin：为 AsyncNamespace 子类添加 page_session 房间管理能力。

    Subclasses only need to mix in this Mixin to automatically handle
    page_session_join / page_session_leave / page_operation_result events.
    子类只需在类定义中混入此 Mixin 即可自动处理
    page_session_join / page_session_leave / page_operation_result 事件。
    """

    async def on_page_session_join(
        self: socketio.AsyncNamespace,  # type: ignore[override]
        sid: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Frontend requests to join page_session room / 前端请求加入 page_session 房间"""
        if not data or not data.get("page_session_id"):
            return
        page_session_id = str(data["page_session_id"])[:64]
        room = f"page_session:{page_session_id}"
        await self.enter_room(sid, room)
        logger.debug(
            "SIO %s sid=%s joined room %s",
            self.namespace, sid, room,
        )

    async def on_page_session_leave(
        self: socketio.AsyncNamespace,  # type: ignore[override]
        sid: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Frontend requests to leave page_session room / 前端请求离开 page_session 房间"""
        if not data or not data.get("page_session_id"):
            return
        page_session_id = str(data["page_session_id"])[:64]
        room = f"page_session:{page_session_id}"
        await self.leave_room(sid, room)
        logger.debug(
            "SIO %s sid=%s left room %s",
            self.namespace, sid, room,
        )

    async def on_page_operation_result(
        self: socketio.AsyncNamespace,  # type: ignore[override]
        sid: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Frontend returns operation execution result / 前端回传操作执行结果"""
        _ = sid
        if not data or not data.get("invoke_id"):
            return
        invoke_id = data["invoke_id"]
        future = _pending_invocations.get(invoke_id)
        if future and not future.done():
            future.set_result(data)
            logger.debug(
                "SIO %s page_operation:result received invoke_id=%s success=%s",
                self.namespace, invoke_id, data.get("success"),
            )


async def invoke_page_operation(
    page_session_id: str,
    page_key: str,
    operation_name: str,
    params: dict[str, Any] | None = None,
    requires_confirmation: bool = False,
    timeout: float = PAGE_OPERATION_TIMEOUT,
    namespace: str | None = None,
) -> dict[str, Any]:
    """
    Dispatch page operation to specified page_session_id and await result.
    向指定 page_session_id 下发页面操作并等待结果。

    Sends page_operation:invoke event to page_session:{id} room via Socket.IO,
    waits for frontend to return execution result via page_operation:result.
    通过 Socket.IO 向 page_session:{id} 房间发送 page_operation:invoke 事件，
    等待前端通过 page_operation:result 回传执行结果。

    Args:
        page_session_id: Frontend page session ID / 前端页面会话 ID
        page_key: Page identifier (pageContextKey) / 页面标识（pageContextKey）
        operation_name: Operation name / 操作名称
        params: Operation params / 操作参数
        requires_confirmation: Whether user confirmation is needed / 是否需要用户确认
        timeout: Timeout (seconds), default 30s / 超时时间（秒），默认 30s
        namespace: Socket.IO namespace, None broadcasts to all namespaces / Socket.IO namespace，None 时向所有 namespace 广播

    Returns:
        Operation result dict (with invoke_id, success, message, data, error_type) /
        操作结果 dict（含 invoke_id, success, message, data, error_type）

    Raises:
        asyncio.TimeoutError: Operation timed out (frontend didn't return result in time) /
            操作超时（前端未在限定时间内回传结果）
    """
    from app.core.socketio_server import get_sio

    sio = get_sio()
    invoke_id = str(uuid.uuid4())
    room = f"page_session:{page_session_id}"

    # Create Future to await callback / 创建 Future 等待回传
    loop = asyncio.get_running_loop()
    future: asyncio.Future[dict[str, Any]] = loop.create_future()
    _pending_invocations[invoke_id] = future

    # Construct invoke event data / 构造 invoke 事件数据
    invoke_data = {
        "invoke_id": invoke_id,
        "page_key": page_key,
        "operation_name": operation_name,
        "params": params or {},
        "requires_confirmation": requires_confirmation,
    }

    try:
        # Send to specified namespace or all namespaces / 发送到指定 namespace 或所有 namespace
        namespaces = [namespace] if namespace else ["/admin", "/tenant"]
        for ns in namespaces:
            await sio.emit(
                "page_operation_invoke",
                invoke_data,
                room=room,
                namespace=ns,
            )

        logger.debug(
            "page_operation:invoke sent invoke_id=%s page_key=%s op=%s room=%s",
            invoke_id, page_key, operation_name, room,
        )

        # Wait for frontend result callback / 等待前端回传结果
        result = await asyncio.wait_for(future, timeout=timeout)
        return result

    except asyncio.TimeoutError:
        logger.warning(
            "page_operation:invoke timed out invoke_id=%s page_key=%s op=%s timeout=%ss",
            invoke_id, page_key, operation_name, timeout,
        )
        return {
            "invoke_id": invoke_id,
            "success": False,
            "message": f"Operation '{operation_name}' timed out after {timeout}s",
            "error_type": "timeout",
        }

    except Exception as e:
        logger.error(
            "page_operation:invoke failed invoke_id=%s error=%s",
            invoke_id, e,
        )
        return {
            "invoke_id": invoke_id,
            "success": False,
            "message": f"Operation '{operation_name}' failed: {e!s}",
            "error_type": "internal_error",
        }

    finally:
        _pending_invocations.pop(invoke_id, None)
