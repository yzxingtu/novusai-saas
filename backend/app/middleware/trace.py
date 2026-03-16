"""
Trace ID Middleware / 请求追踪中间件

Generates or propagates X-Trace-ID for request correlation across logs and downstream services.
生成或传播 X-Trace-ID，用于在日志和下游服务中关联请求。
"""

import uuid

from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# ContextVar for async context propagation / 用于异步上下文传播的 ContextVar
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


class TraceIdMiddleware(BaseHTTPMiddleware):
    """
    Trace ID middleware / 追踪 ID 中间件

    - Reads X-Trace-ID from request header (from frontend), or generates new UUID
    - Sets trace_id into request.state and ContextVar
    - Adds X-Trace-ID to response headers
    - 读取请求头 X-Trace-ID（来自前端），或生成新的 UUID
    - 将 trace_id 写入 request.state 和 ContextVar
    - 将 X-Trace-ID 添加到响应头
    """

    async def dispatch(self, request: Request, call_next):
        tid = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
        trace_id_var.set(tid)
        request.state.trace_id = tid
        response = await call_next(request)
        response.headers["X-Trace-ID"] = tid
        return response
