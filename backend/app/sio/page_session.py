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

Active session tracking: (scope, user_id, page_key) -> {page_session_id -> last_seen}.
Fallback recovery only works when there is exactly one active session for the page;
ambiguous multi-tab sessions return None to avoid cross-tab misrouting.
活跃会话追踪：(scope, user_id, page_key) -> {page_session_id -> last_seen}。
只有页面唯一活跃会话时才允许 fallback 恢复；多标签页歧义场景返回 None，避免串页误操作。
"""

from __future__ import annotations

import asyncio
import contextlib
import time
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

# (scope, user_id, page_key) -> {page_session_id: last_seen_monotonic} / 复合键 → 会话 ID → 最后活跃单调时间戳
# scope: "/admin" | "/tenant" | "/user" (Socket.IO namespace) / 作用域：管理端/企业端/用户端（Socket.IO 命名空间）
_active_sessions: dict[tuple[str, int, str], dict[str, float]] = {}

# (scope, sid) -> {(active_key, page_session_id)}, for precise cleanup on leave/disconnect / 连接维度索引，便于离开/断开时精确清理
_sid_active_sessions: dict[tuple[str, str], set[tuple[tuple[str, int, str], str]]] = {}

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


def get_active_session_id(user_id: int | None, page_key: str, user_role: str = "tenant_admin") -> str | None:
    """
    Get the active page_session_id for (user_id, page_key) from active session tracking.
    Fallback is intentionally conservative: only returns a session when there is
    exactly one active candidate for the page; otherwise returns None.
    从活跃会话映射中获取 (user_id, page_key) 对应的活跃 page_session_id。
    该 fallback 是保守策略：只有页面唯一活跃候选会话时才返回，否则返回 None。

    Args:
        user_id: Current user ID / 当前用户 ID
        page_key: Page identifier (pageContextKey) / 页面标识
        user_role: User role (platform_admin / tenant_admin / tenant_user) / 用户角色

    Returns:
        Active page_session_id or None / 活跃 page_session_id 或 None
    """
    if not user_id or not page_key:
        return None
    scope = _user_role_to_scope(user_role)
    key = (scope, user_id, page_key)
    session_map = _active_sessions.get(key)
    if not session_map:
        return None
    if len(session_map) == 1:
        return next(iter(session_map))
    logger.info(
        "Ambiguous active page sessions: scope={} user_id={} page_key={} count={} sessions={}",
        scope,
        user_id,
        page_key,
        len(session_map),
        list(session_map.keys()),
    )
    return None


def _remove_active_session_entry(
    active_key: tuple[str, int, str],
    page_session_id: str,
) -> None:
    session_map = _active_sessions.get(active_key)
    if not session_map:
        return
    session_map.pop(page_session_id, None)
    if not session_map:
        _active_sessions.pop(active_key, None)


def _track_sid_active_session(
    scope: str,
    sid: str,
    active_key: tuple[str, int, str],
    page_session_id: str,
) -> None:
    sid_key = (scope, sid)
    tracked_pairs = _sid_active_sessions.setdefault(sid_key, set())

    stale_pairs = {
        pair for pair in tracked_pairs
        if pair[0] == active_key and pair[1] != page_session_id
    }
    for stale_active_key, stale_session_id in stale_pairs:
        _remove_active_session_entry(stale_active_key, stale_session_id)
        tracked_pairs.discard((stale_active_key, stale_session_id))

    tracked_pairs.add((active_key, page_session_id))


def _remove_sid_active_sessions(
    scope: str,
    sid: str,
    page_session_id: str | None = None,
) -> None:
    sid_key = (scope, sid)
    tracked_pairs = _sid_active_sessions.get(sid_key)
    if not tracked_pairs:
        return

    pairs_to_remove = {
        pair for pair in tracked_pairs
        if page_session_id is None or pair[1] == page_session_id
    }
    for active_key, tracked_session_id in pairs_to_remove:
        _remove_active_session_entry(active_key, tracked_session_id)
        tracked_pairs.discard((active_key, tracked_session_id))

    if not tracked_pairs:
        _sid_active_sessions.pop(sid_key, None)


class PageSessionMixin:
    """
    Mixin: Adds page_session room management to AsyncNamespace subclasses.
    Mixin：为 AsyncNamespace 子类添加 page_session 房间管理能力。

    Subclasses only need to mix in this Mixin to automatically handle
    page_session_join / page_session_leave / page_operation_result events.
    子类只需在类定义中混入此 Mixin 即可自动处理
    page_session_join / page_session_leave / page_operation_result 事件。
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
            "page_operation_result",
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
            session = await self.bind_socket_trace(sid, data)
            if not data or not data.get("page_session_id"):
                return
            page_session_id = str(data["page_session_id"])[:64]
            room = f"page_session:{page_session_id}"
            await self.enter_room(sid, room)

            # Track active session for executor to recover stale session after reconnect / 追踪活跃会话供执行器在重连后恢复过期会话
            page_key = (data.get("page_key") or "").strip()[:128]
            if page_key:
                try:
                    user_id = session.get("user_id") if session else None
                    if user_id is not None:
                        scope = self.namespace or "/tenant"
                        key = (scope, int(user_id), page_key)
                        session_map = _active_sessions.setdefault(key, {})
                        session_map[page_session_id] = time.monotonic()
                        _track_sid_active_session(scope, sid, key, page_session_id)
                        logger.debug(
                            "SIO {} active_session stored scope={} user_id={} page_key={} session={} active_count={}",
                            self.namespace, scope, user_id, page_key, page_session_id, len(session_map),
                        )
                except Exception as e:
                    logger.debug("SIO {} get_session for active_session failed: {}", self.namespace, e)

            logger.debug(
                "SIO {} sid={} joined room {}",
                self.namespace, sid, room,
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

            # Remove from active session tracking for this socket only / 仅从此 socket 的活跃会话索引中移除
            scope = self.namespace or "/tenant"
            _remove_sid_active_sessions(scope, sid, page_session_id)

            logger.debug(
                "SIO {} sid={} left room {}",
                self.namespace, sid, room,
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
        """Clean page_session tracking for a disconnected socket / 清理断线 socket 的 page_session 追踪。"""
        scope = self.namespace or "/tenant"
        _remove_sid_active_sessions(scope, sid)

    async def on_page_operation_result(
        self: socketio.AsyncNamespace,  # type: ignore[override] / 忽略与基类签名差异
        sid: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Frontend returns operation execution result / 前端回传操作执行结果"""
        _sid = sid  # noqa: F841
        invoke_id = ""
        try:
            await self.bind_socket_trace(sid, data)
            if not data or not data.get("invoke_id"):
                return
            invoke_id = str(data["invoke_id"])
            future = _pending_invocations.get(invoke_id)
            if future and not future.done():
                result_payload = dict(data)
                if not result_payload.get("trace_id"):
                    result_payload["trace_id"] = normalize_trace_id(
                        trace_id_var.get() or invoke_id,
                        default=invoke_id,
                    )
                future.set_result(result_payload)
                logger.debug(
                    "SIO {} page_operation:result received invoke_id={} success={}",
                    self.namespace, invoke_id, data.get("success"),
                )
            return None
        except Exception as exc:
            future = _pending_invocations.get(invoke_id) if invoke_id else None
            if future and not future.done():
                with contextlib.suppress(Exception):
                    future.set_result(
                        _page_operation_error_result(
                            invoke_id=invoke_id,
                            error_type="internal_error",
                            message=_("common.server_error"),
                            code="PAGE_OPERATION_RESULT_ERROR",
                            debug=build_exception_debug(exc),
                            extra={"event": "page_operation_result"},
                        )
                    )
            return _handle_socket_event_failure(
                namespace=self.namespace,
                event="page_operation_result",
                sid=sid,
                exc=exc,
            )
        finally:
            trace_id_var.set("")


async def invoke_page_operation(
    page_session_id: str,
    page_key: str,
    operation_name: str,
    params: dict[str, Any] | None = None,
    requires_confirmation: bool = False,
    auto_approved: bool = False,
    tool_call_id: str | None = None,
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
        auto_approved: Whether backend trust policy already approved the operation / 是否已由后端信任策略自动批准
        tool_call_id: Tool call ID for frontend to associate confirmation card with message / 工具调用 ID，供前端将确认卡片关联到对应消息
        timeout: Timeout (seconds), default 60s / 超时时间（秒），默认 60s
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
    invoke_data: dict[str, Any] = {
        "invoke_id": invoke_id,
        "trace_id": normalize_trace_id(trace_id_var.get() or invoke_id, default=invoke_id),
        "page_key": page_key,
        "operation_name": operation_name,
        "params": params or {},
        "requires_confirmation": requires_confirmation,
        "auto_approved": auto_approved,
    }
    if tool_call_id:
        invoke_data["tool_call_id"] = tool_call_id

    try:
        # Send to specified namespace or all namespaces / 发送到指定 namespace 或所有 namespace
        namespaces = [namespace] if namespace else ["/admin", "/tenant", "/user"]
        for ns in namespaces:
            await sio.emit(
                "page_operation_invoke",
                invoke_data,
                room=room,
                namespace=ns,
            )

        logger.debug(
            "page_operation:invoke sent invoke_id={} page_key={} op={} room={}",
            invoke_id, page_key, operation_name, room,
        )

        # Wait for frontend result callback / 等待前端回传结果
        result = await asyncio.wait_for(future, timeout=timeout)
        return result

    except asyncio.TimeoutError:
        logger.warning(
            "page_operation:invoke timed out invoke_id={} page_key={} op={} timeout={}s",
            invoke_id, page_key, operation_name, timeout,
        )
        return _page_operation_error_result(
            invoke_id=invoke_id,
            error_type="timeout",
            message=_("page_operation.error.timeout", op=operation_name, timeout=int(timeout)),
            code="PAGE_OPERATION_TIMEOUT",
        )

    except Exception as e:
        logger.error(
            "page_operation:invoke failed invoke_id={} error={}",
            invoke_id, e,
        )
        return _page_operation_error_result(
            invoke_id=invoke_id,
            error_type="internal_error",
            message=_(
                "page_operation.error.internal_failed",
                op=operation_name,
                error=_("common.server_error"),
            ),
            code="PAGE_OPERATION_INTERNAL_ERROR",
            debug=build_exception_debug(e),
        )

    finally:
        _pending_invocations.pop(invoke_id, None)
