"""中文: Prometheus metrics 端点和中间件结构测试。

EN: Structural tests for the Prometheus metrics endpoint and middleware.

Test type: structural
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import app.main as app_main
from app.main import create_application
from app.middleware.access_control import EXEMPT_PATH_PREFIXES, AccessControlMiddleware
from app.middleware.audit_log import should_log_request
from app.middleware.maintenance import _EXEMPT_PREFIXES
from app.middleware.prometheus_metrics import (
    PrometheusMetricsMiddleware,
    metrics_response,
    set_component_health,
)


def _unwrap_routes_app(app):
    current = app
    for _ in range(10):
        if hasattr(current, "routes"):
            return current
        current = getattr(current, "other_asgi_app", getattr(current, "app", None))
        if current is None:
            break
    raise AssertionError("FastAPI routes app not found")


def _build_metrics_app(*, raise_server_exceptions: bool = True) -> TestClient:
    app = FastAPI()
    app.add_middleware(PrometheusMetricsMiddleware)

    @app.get("/metrics")
    async def metrics():
        return metrics_response()

    @app.get("/ok")
    async def ok():
        return {"ok": True}

    @app.get("/items/{item_id}")
    async def item(item_id: int):
        return {"item_id": item_id}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("simulated failure")

    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


def test_metrics_route_is_registered_on_application() -> None:
    app = _unwrap_routes_app(create_application())

    routes = {
        getattr(route, "path", ""): getattr(route, "methods", set())
        for route in app.routes
    }

    assert "/metrics" in routes
    assert "GET" in routes["/metrics"]


def test_metrics_endpoint_returns_prometheus_text_exposition() -> None:
    with _build_metrics_app() as client:
        client.get("/ok")
        response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "# HELP novusai_app_info" in body
    assert "# TYPE novusai_app_info gauge" in body
    assert "novusai_app_info" in body
    assert "# HELP novusai_http_requests_total" in body
    assert "# TYPE novusai_http_requests_total counter" in body
    assert (
        'novusai_http_requests_total{method="GET",route="/ok",status_code="200"}'
        in body
    )
    assert "# HELP novusai_http_request_duration_seconds" in body
    assert "# TYPE novusai_http_request_duration_seconds histogram" in body
    assert any(
        line.startswith("novusai_http_request_duration_seconds_bucket")
        and 'route="/ok"' in line
        and 'status_code="200"' in line
        for line in body.splitlines()
    )
    assert "novusai_http_request_duration_seconds_count" in body
    assert "novusai_http_request_duration_seconds_sum" in body
    assert "# HELP novusai_http_requests_in_progress" in body
    assert "# TYPE novusai_http_requests_in_progress gauge" in body
    assert 'novusai_http_requests_in_progress{method="GET",route="/ok"} 0.0' in body


def test_metrics_endpoint_exports_component_health_samples() -> None:
    set_component_health("test_database", True)

    with _build_metrics_app() as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert "# HELP novusai_component_health" in response.text
    assert "# TYPE novusai_component_health gauge" in response.text
    assert 'novusai_component_health{component="test_database"} 1.0' in response.text


def test_metrics_use_route_templates_instead_of_raw_dynamic_paths() -> None:
    with _build_metrics_app() as client:
        response = client.get("/items/123")
        metrics = client.get("/metrics").text

    assert response.status_code == 200
    assert (
        'novusai_http_requests_total{method="GET",route="/items/{item_id}",'
        'status_code="200"}' in metrics
    )
    assert 'route="/items/123"' not in metrics


def test_metrics_record_500_and_clear_in_progress_gauge() -> None:
    with _build_metrics_app(raise_server_exceptions=False) as client:
        response = client.get("/boom")
        metrics = client.get("/metrics").text

    assert response.status_code == 500
    assert (
        'novusai_http_requests_total{method="GET",route="/boom",status_code="500"}'
        in metrics
    )
    assert (
        'novusai_http_requests_in_progress{method="GET",route="/boom"} 0.0' in metrics
    )
    assert (
        'novusai_http_requests_in_progress{method="GET",route="/boom"} 1.0'
        not in metrics
    )


def test_metrics_self_scrape_is_not_recorded_as_http_business_metric() -> None:
    with _build_metrics_app() as client:
        client.get("/metrics")
        metrics = client.get("/metrics").text

    assert 'route="/metrics"' not in metrics


def test_metrics_path_is_infra_exempt_and_not_audited() -> None:
    async def noop_app(scope, receive, send):
        return None

    access_control = AccessControlMiddleware(noop_app)

    assert "/metrics" in EXEMPT_PATH_PREFIXES
    assert "/metrics" in _EXEMPT_PREFIXES
    assert access_control._is_exempt_path("/metrics") is True
    assert access_control._is_exempt_path("/metrics-admin") is False
    assert should_log_request("/metrics", "GET") is False
    assert should_log_request("/metrics-admin", "GET") is True


@pytest.mark.asyncio
async def test_metrics_component_health_refresh_is_ttl_cached(monkeypatch) -> None:
    calls = {"database": 0, "redis": 0}

    async def fake_database_check() -> bool:
        calls["database"] += 1
        set_component_health("database", True)
        return True

    async def fake_redis_check() -> bool:
        calls["redis"] += 1
        return True

    from app.core.redis import RedisManager

    monkeypatch.setattr(app_main, "_check_database_component", fake_database_check)
    monkeypatch.setattr(
        RedisManager,
        "health_check",
        staticmethod(fake_redis_check),
    )
    monkeypatch.setattr(
        app_main,
        "_METRICS_COMPONENT_HEALTH_REFRESH_TTL_SECONDS",
        3600.0,
    )
    monkeypatch.setattr(app_main, "_metrics_component_health_last_refresh", 0.0)
    monkeypatch.setattr(app_main, "_metrics_component_health_lock", None)

    await app_main._refresh_metrics_component_health()
    await app_main._refresh_metrics_component_health()

    assert calls == {"database": 1, "redis": 1}
