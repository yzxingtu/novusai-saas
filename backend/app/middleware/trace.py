"""
Trace ID Middleware / 请求追踪中间件

Generates or propagates X-Trace-ID for request correlation across logs and downstream services.
生成或传播 X-Trace-ID，用于在日志和下游服务中关联请求。

Uses pure ASGI instead of BaseHTTPMiddleware to avoid CancelledError cascade on Ctrl+C shutdown.
使用纯 ASGI 实现，避免 Ctrl+C 关闭时 BaseHTTPMiddleware 导致的任务取消级联错误。
"""

import uuid

from contextvars import ContextVar
from starlette.datastructures import State
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# ContextVar for async context propagation / 用于异步上下文传播的 ContextVar
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


class TraceIdMiddleware:
    """
    Trace ID middleware (pure ASGI implementation).
    追踪 ID 中间件（纯 ASGI 实现）

    - Reads X-Trace-ID from request header (from frontend), or generates new UUID
    - Sets trace_id into scope.state and ContextVar
    - Adds X-Trace-ID to response headers
    - 读取请求头 X-Trace-ID（来自前端），或生成新的 UUID
    - 将 trace_id 写入 scope.state 和 ContextVar
    - 将 X-Trace-ID 添加到响应头
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Read or generate trace_id / 读取或生成 trace_id
        headers = dict(scope.get("headers", []))
        raw_tid = headers.get(b"x-trace-id", b"")
        try:
            tid = raw_tid.decode("utf-8").strip() if raw_tid else ""
        except UnicodeDecodeError:
            tid = ""
        tid = tid or str(uuid.uuid4())
        trace_id_var.set(tid)

        # Ensure scope has state (for AuditLogMiddleware etc.) / 确保 scope 有 state
        # TestClient uses dict, TenantMiddleware uses dict; wrap in State for attribute-style access
        raw = scope.get("state")
        if raw is None:
            raw = {}
        if not isinstance(raw, State):
            scope["state"] = State(raw)
        scope["state"].trace_id = tid

        # Wrap send to add X-Trace-ID to response headers / 包装 send 以添加 X-Trace-ID
        async def wrapped_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers_list = list(message.get("headers", []))
                headers_list.append((b"x-trace-id", tid.encode("utf-8")))
                message = {**message, "headers": headers_list}
            await send(message)

        await self.app(scope, receive, wrapped_send)
