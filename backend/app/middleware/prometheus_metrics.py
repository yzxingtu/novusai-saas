"""中文: Prometheus 指标导出与 HTTP 请求采集。

EN: Prometheus metric export and HTTP request instrumentation.
"""

from __future__ import annotations

import time
from collections.abc import Iterable

from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
)
from starlette.routing import Match
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings

_HTTP_DURATION_BUCKETS = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)

APP_INFO = Info(
    "novusai_app",
    "NovusAI application build and runtime information.",
)
HTTP_REQUESTS_TOTAL = Counter(
    "novusai_http_requests_total",
    "Total HTTP requests handled by the NovusAI backend.",
    ("method", "route", "status_code"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "novusai_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "route", "status_code"),
    buckets=_HTTP_DURATION_BUCKETS,
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "novusai_http_requests_in_progress",
    "HTTP requests currently being handled by the NovusAI backend.",
    ("method", "route"),
)
COMPONENT_HEALTH = Gauge(
    "novusai_component_health",
    "Component health from lightweight health/readiness probes: 1 healthy, 0 unhealthy.",
    ("component",),
)

APP_INFO.info(
    {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "env": settings.APP_ENV,
    }
)


def set_component_health(component: str, healthy: bool) -> None:
    """中文: 记录组件健康状态，供告警规则消费。

    EN: Records component health for alert rules.
    """
    COMPONENT_HEALTH.labels(component=component).set(1 if healthy else 0)


def metrics_response() -> Response:
    """中文: 返回 Prometheus text exposition 响应。

    EN: Returns a Prometheus text exposition response.
    """
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def _iter_routes(scope: Scope) -> Iterable[object]:
    app = scope.get("app")
    return getattr(app, "routes", []) if app is not None else []


def _route_template(scope: Scope) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return str(path)

    for candidate in _iter_routes(scope):
        try:
            match, _child_scope = candidate.matches(scope)
        except Exception:
            continue
        if match == Match.FULL:
            candidate_path = getattr(candidate, "path", None)
            if candidate_path:
                return str(candidate_path)

    return "__unmatched__"


class PrometheusMetricsMiddleware:
    """中文: 纯 ASGI HTTP 指标中间件，避免 BaseHTTPMiddleware 取消级联。

    EN: Pure ASGI HTTP metrics middleware, avoiding BaseHTTPMiddleware
    cancellation cascades.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        if path == "/metrics":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method") or "GET").upper()
        route = _route_template(scope)
        status_code = 500
        started_at = time.perf_counter()
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, route=route).inc()

        async def wrapped_send(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message.get("status") or 500)
            await send(message)

        try:
            await self.app(scope, receive, wrapped_send)
        finally:
            elapsed = time.perf_counter() - started_at
            status_label = str(status_code)
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                route=route,
                status_code=status_label,
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                route=route,
                status_code=status_label,
            ).observe(elapsed)
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method, route=route).dec()


__all__ = [
    "PrometheusMetricsMiddleware",
    "metrics_response",
    "set_component_health",
]
