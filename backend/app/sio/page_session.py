"""
Page Session Room Management
页面会话房间管理

Handles frontend page_session_join / page_session_leave events,
joining/leaving client sid to/from page_session:{id} rooms.
处理前端 page_session_join / page_session_leave 事件，
将客户端 sid 加入/离开 page_session:{id} 房间。

Backend dispatches runtime events to specified page_session_id rooms via helpers
such as invoke_ui_action() and request_ui_snapshot().
Frontend executes and returns results via the corresponding *_result events.
后端通过 invoke_ui_action()、request_ui_snapshot() 等辅助方法向指定
page_session_id 房间下发运行时事件，前端执行后通过对应 *_result 回传结果。

Live page-session transport is keyed by explicit page_session_id only.
The connector boundary no longer tracks or recovers sessions by page_key.
运行时页面会话传输只使用显式 page_session_id。
连接器边界不再按 page_key 追踪或恢复会话。
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import Any

import socketio

from app.core.i18n import _
from app.core.logging import LogManager
from app.core.response import (
    build_error_event,
    build_error_payload,
    build_exception_debug,
)
from app.middleware.trace import (
    extract_optional_trace_id,
    normalize_trace_id,
    trace_id_var,
)

logger = LogManager.get_logger("app")

# invoke_id → Future mapping, for awaiting frontend result callback / invoke_id → Future 映射，用于等待前端回传结果
_pending_invocations: dict[str, asyncio.Future[dict[str, Any]]] = {}

# Default operation timeout (seconds) / 默认操作超时（秒）
# 60s to align with frontend CONFIRM_TIMEOUT_MS / 与前端确认超时 60s 对齐
PAGE_OPERATION_TIMEOUT = 60


def _extract_trace_id(payload: dict[str, Any] | None = None) -> str | None:
    """Extract a safe trace id from Socket.IO payload / 从 Socket.IO 载荷提取安全 trace id。"""
    if not isinstance(payload, dict):
        return None
    return extract_optional_trace_id(payload.get("trace_id"))


def _socket_event_error_payload(
    *,
    code: int | str,
    message: str,
    debug: Any = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Socket.IO event error payload / 构建 Socket.IO 事件错误载荷。"""
    return build_error_event(
        code=code,
        message=message,
        trace_id=trace_id_var.get() or None,
        debug=debug,
        extra=extra,
    )


def _page_operation_error_result(
    *,
    invoke_id: str,
    error_type: str,
    message: str,
    code: int | str,
    debug: Any = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build page operation failure result / 构建页面操作失败结果。"""
    payload = build_error_payload(
        message=message,
        code=code,
        trace_id=trace_id_var.get() or None,
        debug=debug,
        extra=extra,
    )
    return {
        "invoke_id": invoke_id,
        "success": False,
        "error_type": error_type,
        **payload,
    }


def _runtime_request_error_result(
    *,
    request_id: str,
    error_type: str,
    message: str,
    code: int | str,
    debug: Any = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build generic runtime request failure result / 构建通用 runtime 请求失败结果。"""
    payload = build_error_payload(
        message=message,
        code=code,
        trace_id=trace_id_var.get() or None,
        debug=debug,
        extra=extra,
    )
    return {
        "request_id": request_id,
        "success": False,
        "error_type": error_type,
        **payload,
    }


def _handle_socket_event_failure(
    *,
    namespace: str | None,
    event: str,
    sid: str,
    exc: Exception,
) -> dict[str, Any]:
    logger.error(
        "SIO {} event failed: event={} sid={} error={}",
        namespace,
        event,
        sid,
        exc,
        exc_info=True,
    )
    return _socket_event_error_payload(
        code="SOCKET_EVENT_ERROR",
        message=_("common.server_error"),
        debug=build_exception_debug(exc),
        extra={"event": event},
    )


def _user_role_to_scope(user_role: str) -> str:
    """Map ExecutionContext.user_role to Socket.IO namespace / 将 user_role 映射到 Socket.IO namespace"""
    if user_role == "platform_admin":
        return "/admin"
    if user_role == "tenant_admin":
        return "/tenant"
    if user_role == "tenant_user":
        return "/user"
    return "/tenant"  # default / 缺省走企业端命名空间


def get_active_session_id(
    user_id: int | None, page_key: str, user_role: str = "tenant_admin"
) -> str | None:
    """
    Live page-session recovery no longer falls back from page_key.
    运行时页面会话恢复不再从 page_key 回退。

    The connector boundary must use explicit page_session_id. This helper now
    returns None so page_key cannot re-enter the live path.
    连接器边界必须显式携带 page_session_id；该辅助函数现在固定返回 None，
    防止 page_key 重新进入 live path。
    """
    _ = (user_id, page_key, user_role)
    return None


class PageSessionMixin:
    """
    Mixin: Adds page_session room management to AsyncNamespace subclasses.
    Mixin：为 AsyncNamespace 子类添加 page_session 房间管理能力。

    Subclasses only need to mix in this Mixin to automatically handle
    page_session_join / page_session_leave /
    ui_action_result / ui_snapshot_result / ui_read_*_result events.
    子类只需在类定义中混入此 Mixin 即可自动处理
    page_session_join / page_session_leave /
    ui_action_result / ui_snapshot_result / ui_read_*_result 事件。
    """

    async def trigger_event(
        self: socketio.AsyncNamespace,  # type: ignore[override] / 忽略与基类签名差异
        event: str,
        *args: Any,
    ) -> Any:
        """Bind trace context for generic Socket.IO events / 为通用 Socket.IO 事件绑定 trace 上下文。"""
        if event in ("connect", "disconnect"):
            return await super().trigger_event(event, *args)

        if event not in {
            "ui_action_result",
            "ui_snapshot_result",
            "ui_read_region_result",
            "ui_read_table_result",
            "ui_list_interactables_result",
            "page_session_join",
            "page_session_leave",
        }:
            sid = str(args[0]) if args else ""
            payload = args[1] if len(args) > 1 and isinstance(args[1], dict) else None
            try:
                if sid:
                    await self.bind_socket_trace(sid, payload)
                return await super().trigger_event(event, *args)
            except Exception as exc:
                return _handle_socket_event_failure(
                    namespace=self.namespace,
                    event=event,
                    sid=sid,
                    exc=exc,
                )
            finally:
                trace_id_var.set("")

        return await super().trigger_event(event, *args)

    async def get_socket_session_with_fallback(
        self: socketio.AsyncNamespace,  # type: ignore[override] / 忽略与基类签名差异
        sid: str,
    ) -> dict[str, Any] | None:
        """Get Socket.IO session with backup fallback / 获取 Socket.IO session，失败时回退备份。"""
        with contextlib.suppress(Exception):
            session = await self.get_session(sid)
            if isinstance(session, dict):
                return session

        sid_sessions = getattr(self, "_sid_sessions", None)
        if isinstance(sid_sessions, dict):
            fallback = sid_sessions.get(sid)
            if isinstance(fallback, dict):
                return fallback
        return None

    async def bind_socket_trace(
        self: socketio.AsyncNamespace,  # type: ignore[override] / 忽略与基类签名差异
        sid: str,
        payload: dict[str, Any] | None = None,
        default_trace_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Bind current Socket.IO event to trace context / 将当前 Socket.IO 事件绑定到 trace 上下文。"""
        session = await self.get_socket_session_with_fallback(sid)
        trace_id = normalize_trace_id(
            _extract_trace_id(payload)
            or (session or {}).get("trace_id")
            or default_trace_id
        )
        trace_id_var.set(trace_id)

        updated_session = session
        if session is not None and session.get("trace_id") != trace_id:
            updated_session = {**session, "trace_id": trace_id}
            with contextlib.suppress(Exception):
                await self.save_session(sid, updated_session)
            sid_sessions = getattr(self, "_sid_sessions", None)
            if isinstance(sid_sessions, dict):
                sid_sessions[sid] = updated_session

        return updated_session

    async def on_page_session_join(
        self: socketio.AsyncNamespace,  # type: ignore[override] / 忽略与基类签名差异
        sid: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Frontend requests to join page_session room / 前端请求加入 page_session 房间"""
        try:
            await self.bind_socket_trace(sid, data)
            if not data or not data.get("page_session_id"):
                return
            page_session_id = str(data["page_session_id"])[:64]
            room = f"page_session:{page_session_id}"
            await self.enter_room(sid, room)
            page_key = (data.get("page_key") or "").strip()[:128]

            logger.debug(
                "SIO {} sid={} joined room {}",
                self.namespace,
                sid,
                room,
            )
            await self.emit(
                "page_session_joined",
                {
                    "page_session_id": page_session_id,
                    "page_key": page_key,
                    "trace_id": trace_id_var.get() or None,
                },
                to=sid,
            )
            return None
        except Exception as exc:
            return _handle_socket_event_failure(
                namespace=self.namespace,
                event="page_session_join",
                sid=sid,
                exc=exc,
            )
        finally:
            trace_id_var.set("")

    async def on_page_session_leave(
        self: socketio.AsyncNamespace,  # type: ignore[override] / 忽略与基类签名差异
        sid: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Frontend requests to leave page_session room / 前端请求离开 page_session 房间"""
        try:
            await self.bind_socket_trace(sid, data)
            if not data or not data.get("page_session_id"):
                return
            page_session_id = str(data["page_session_id"])[:64]
            room = f"page_session:{page_session_id}"
            await self.leave_room(sid, room)

            logger.debug(
                "SIO {} sid={} left room {}",
                self.namespace,
                sid,
                room,
            )
            return None
        except Exception as exc:
            return _handle_socket_event_failure(
                namespace=self.namespace,
                event="page_session_leave",
                sid=sid,
                exc=exc,
            )
        finally:
            trace_id_var.set("")

    def cleanup_page_sessions_for_disconnect(
        self: socketio.AsyncNamespace,  # type: ignore[override] / 忽略与基类签名差异
        sid: str,
    ) -> None:
        """No-op disconnect hook; live session ownership is room-based only."""
        _ = sid
        return None

    async def _handle_pending_result_event(
        self: socketio.AsyncNamespace,
        sid: str,
        data: dict[str, Any] | None,
        *,
        event_name: str,
        id_field: str,
        error_code: str,
    ) -> dict[str, Any] | None:
        request_id = ""
        try:
            await self.bind_socket_trace(sid, data)
            if not data or not data.get(id_field):
                return None
            request_id = str(data[id_field])
            future = _pending_invocations.get(request_id)
            if future and not future.done():
                result_payload = dict(data)
                if not result_payload.get("trace_id"):
                    result_payload["trace_id"] = normalize_trace_id(
                        trace_id_var.get() or request_id,
                        default=request_id,
                    )
                future.set_result(result_payload)
                logger.debug(
                    "SIO {} {} received {}={} success={}",
                    self.namespace,
                    event_name,
                    id_field,
                    request_id,
                    data.get("success"),
                )
            return None
        except Exception as exc:
            future = _pending_invocations.get(request_id) if request_id else None
            if future and not future.done():
                with contextlib.suppress(Exception):
                    error_result = (
                        _page_operation_error_result(
                            invoke_id=request_id,
                            error_type="internal_error",
                            message=_("common.server_error"),
                            code=error_code,
                            debug=build_exception_debug(exc),
                            extra={"event": event_name},
                        )
                        if id_field == "invoke_id"
                        else _runtime_request_error_result(
                            request_id=request_id,
                            error_type="internal_error",
                            message=_("common.server_error"),
                            code=error_code,
                            debug=build_exception_debug(exc),
                            extra={"event": event_name},
                        )
                    )
                    future.set_result(error_result)
            return _handle_socket_event_failure(
                namespace=self.namespace,
                event=event_name,
                sid=sid,
                exc=exc,
            )
        finally:
            trace_id_var.set("")

    async def on_ui_action_result(
        self: socketio.AsyncNamespace,
        sid: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return await self._handle_pending_result_event(
            sid,
            data,
            event_name="ui_action_result",
            id_field="invoke_id",
            error_code="UI_ACTION_RESULT_ERROR",
        )

    async def on_ui_snapshot_result(
        self: socketio.AsyncNamespace,
        sid: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return await self._handle_pending_result_event(
            sid,
            data,
            event_name="ui_snapshot_result",
            id_field="request_id",
            error_code="UI_SNAPSHOT_RESULT_ERROR",
        )

    async def on_ui_read_region_result(
        self: socketio.AsyncNamespace,
        sid: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return await self._handle_pending_result_event(
            sid,
            data,
            event_name="ui_read_region_result",
            id_field="request_id",
            error_code="UI_READ_REGION_RESULT_ERROR",
        )

    async def on_ui_read_table_result(
        self: socketio.AsyncNamespace,
        sid: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return await self._handle_pending_result_event(
            sid,
            data,
            event_name="ui_read_table_result",
            id_field="request_id",
            error_code="UI_READ_TABLE_RESULT_ERROR",
        )

    async def on_ui_list_interactables_result(
        self: socketio.AsyncNamespace,
        sid: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        return await self._handle_pending_result_event(
            sid,
            data,
            event_name="ui_list_interactables_result",
            id_field="request_id",
            error_code="UI_LIST_INTERACTABLES_RESULT_ERROR",
        )


async def _dispatch_page_session_request(
    *,
    event_name: str,
    payload: dict[str, Any],
    page_session_id: str,
    request_id: str,
    timeout: float,
    namespace: str | None = None,
) -> dict[str, Any]:
    from app.core.socketio_server import get_sio

    sio = get_sio()
    room = f"page_session:{page_session_id}"
    loop = asyncio.get_running_loop()
    future: asyncio.Future[dict[str, Any]] = loop.create_future()
    _pending_invocations[request_id] = future

    try:
        namespaces = [namespace] if namespace else ["/admin", "/tenant", "/user"]
        for ns in namespaces:
            await sio.emit(
                event_name,
                payload,
                room=room,
                namespace=ns,
            )
        logger.debug(
            "{} sent request_id={} room={}",
            event_name,
            request_id,
            room,
        )
        return await asyncio.wait_for(future, timeout=timeout)
    finally:
        _pending_invocations.pop(request_id, None)


async def invoke_ui_action(
    *,
    page_session_id: str,
    action_type: str,
    payload: dict[str, Any] | None = None,
    timeout: float = PAGE_OPERATION_TIMEOUT,
    namespace: str | None = None,
    tool_call_id: str | None = None,
) -> dict[str, Any]:
    invoke_id = str(uuid.uuid4())
    action_payload = dict(payload or {})
    action_payload.pop("page_key", None)
    request_payload: dict[str, Any] = {
        "invoke_id": invoke_id,
        "trace_id": normalize_trace_id(
            trace_id_var.get() or invoke_id, default=invoke_id
        ),
        "action_type": action_type,
        **action_payload,
    }
    if tool_call_id:
        request_payload["tool_call_id"] = tool_call_id

    try:
        return await _dispatch_page_session_request(
            event_name="ui_action_invoke",
            payload=request_payload,
            page_session_id=page_session_id,
            request_id=invoke_id,
            timeout=timeout,
            namespace=namespace,
        )
    except asyncio.TimeoutError:
        return _page_operation_error_result(
            invoke_id=invoke_id,
            error_type="timeout",
            message=_(
                "page_operation.error.timeout", op=action_type, timeout=int(timeout)
            ),
            code="UI_ACTION_TIMEOUT",
        )
    except Exception as exc:
        return _page_operation_error_result(
            invoke_id=invoke_id,
            error_type="internal_error",
            message=_(
                "page_operation.error.internal_failed",
                op=action_type,
                error=_("common.server_error"),
            ),
            code="UI_ACTION_INTERNAL_ERROR",
            debug=build_exception_debug(exc),
        )


async def request_ui_snapshot(
    *,
    page_session_id: str,
    mode: str = "compact",
    surface_id: str | None = None,
    timeout: float = PAGE_OPERATION_TIMEOUT,
    namespace: str | None = None,
) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "request_id": request_id,
        "trace_id": normalize_trace_id(
            trace_id_var.get() or request_id, default=request_id
        ),
        "mode": mode,
    }
    if surface_id:
        payload["surface_id"] = surface_id

    try:
        return await _dispatch_page_session_request(
            event_name="ui_snapshot_request",
            payload=payload,
            page_session_id=page_session_id,
            request_id=request_id,
            timeout=timeout,
            namespace=namespace,
        )
    except asyncio.TimeoutError:
        return _runtime_request_error_result(
            request_id=request_id,
            error_type="timeout",
            message=_("tool.ui.snapshot.request_timeout"),
            code="UI_SNAPSHOT_TIMEOUT",
        )
    except Exception as exc:
        return _runtime_request_error_result(
            request_id=request_id,
            error_type="internal_error",
            message=_("tool.ui.snapshot.request_failed"),
            code="UI_SNAPSHOT_INTERNAL_ERROR",
            debug=build_exception_debug(exc),
        )


async def request_ui_read_region(
    *,
    page_session_id: str,
    region_locator: str,
    timeout: float = PAGE_OPERATION_TIMEOUT,
    namespace: str | None = None,
) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    payload = {
        "request_id": request_id,
        "trace_id": normalize_trace_id(
            trace_id_var.get() or request_id, default=request_id
        ),
        "region_locator": region_locator,
    }
    try:
        return await _dispatch_page_session_request(
            event_name="ui_read_region_request",
            payload=payload,
            page_session_id=page_session_id,
            request_id=request_id,
            timeout=timeout,
            namespace=namespace,
        )
    except asyncio.TimeoutError:
        return _runtime_request_error_result(
            request_id=request_id,
            error_type="timeout",
            message=_("tool.ui.read.region_timeout"),
            code="UI_READ_REGION_TIMEOUT",
        )
    except Exception as exc:
        return _runtime_request_error_result(
            request_id=request_id,
            error_type="internal_error",
            message=_("tool.ui.read.region_request_failed"),
            code="UI_READ_REGION_INTERNAL_ERROR",
            debug=build_exception_debug(exc),
        )


async def request_ui_read_table(
    *,
    page_session_id: str,
    table_locator: str,
    page: int = 1,
    page_size: int = 20,
    filters: dict[str, Any] | None = None,
    timeout: float = PAGE_OPERATION_TIMEOUT,
    namespace: str | None = None,
) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "request_id": request_id,
        "trace_id": normalize_trace_id(
            trace_id_var.get() or request_id, default=request_id
        ),
        "table_locator": table_locator,
        "page": page,
        "page_size": page_size,
    }
    if filters:
        payload["filters"] = filters
    try:
        return await _dispatch_page_session_request(
            event_name="ui_read_table_request",
            payload=payload,
            page_session_id=page_session_id,
            request_id=request_id,
            timeout=timeout,
            namespace=namespace,
        )
    except asyncio.TimeoutError:
        return _runtime_request_error_result(
            request_id=request_id,
            error_type="timeout",
            message=_("tool.ui.read.table_timeout"),
            code="UI_READ_TABLE_TIMEOUT",
        )
    except Exception as exc:
        return _runtime_request_error_result(
            request_id=request_id,
            error_type="internal_error",
            message=_("tool.ui.read.table_request_failed"),
            code="UI_READ_TABLE_INTERNAL_ERROR",
            debug=build_exception_debug(exc),
        )


async def request_ui_list_interactables(
    *,
    page_session_id: str,
    surface_id: str | None = None,
    timeout: float = PAGE_OPERATION_TIMEOUT,
    namespace: str | None = None,
) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "request_id": request_id,
        "trace_id": normalize_trace_id(
            trace_id_var.get() or request_id, default=request_id
        ),
    }
    if surface_id:
        payload["surface_id"] = surface_id
    try:
        return await _dispatch_page_session_request(
            event_name="ui_list_interactables_request",
            payload=payload,
            page_session_id=page_session_id,
            request_id=request_id,
            timeout=timeout,
            namespace=namespace,
        )
    except asyncio.TimeoutError:
        return _runtime_request_error_result(
            request_id=request_id,
            error_type="timeout",
            message=_("tool.ui.read.interactables_timeout"),
            code="UI_LIST_INTERACTABLES_TIMEOUT",
        )
    except Exception as exc:
        return _runtime_request_error_result(
            request_id=request_id,
            error_type="internal_error",
            message=_("tool.ui.read.interactables_request_failed"),
            code="UI_LIST_INTERACTABLES_INTERNAL_ERROR",
            debug=build_exception_debug(exc),
        )
