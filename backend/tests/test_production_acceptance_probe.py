"""中文: 生产验收探针结构测试。

EN: Structural tests for the production acceptance probe.

Test type: structural
"""

from __future__ import annotations

import urllib.error
from pathlib import Path

import pytest

from scripts import production_acceptance_probe as probe


def _valid_metrics_body() -> str:
    return (
        "# HELP novusai_app_info Application info\n"
        "# TYPE novusai_app_info gauge\n"
        "novusai_app_info 1\n"
        "# HELP novusai_http_requests_total HTTP requests\n"
        "# TYPE novusai_http_requests_total counter\n"
        "novusai_http_requests_total 1\n"
        "# HELP novusai_http_request_duration_seconds HTTP duration\n"
        "# TYPE novusai_http_request_duration_seconds histogram\n"
        'novusai_http_request_duration_seconds_bucket{le="+Inf"} 1\n'
        "# HELP novusai_http_requests_in_progress In-progress HTTP requests\n"
        "# TYPE novusai_http_requests_in_progress gauge\n"
        "novusai_http_requests_in_progress 0\n"
        "# HELP novusai_component_health Component health\n"
        "# TYPE novusai_component_health gauge\n"
        'novusai_component_health{component="database"} 1\n'
    )


def test_request_helpers_reject_non_http_urls() -> None:
    with pytest.raises(ValueError, match="http or https"):
        probe._request_status("file:///etc/passwd", timeout=1)


def test_tool_result_blocks_when_required_tool_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(probe.shutil, "which", lambda _name: None)

    result = probe._tool_result(
        area="backup_restore",
        name="postgres_backup_restore_tooling",
        tools=("pg_dump", "pg_restore", "psql"),
        require_all=True,
        summary_ready="ready",
        summary_missing="missing",
    )

    assert result.status == probe.STATUS_BLOCKED
    assert result.details["missing"] == ["pg_dump", "pg_restore", "psql"]


def test_probe_api_passes_metrics_when_prometheus_exposition_is_valid(
    monkeypatch,
) -> None:
    def fake_request_json(url: str, *, timeout: float):
        if url.endswith("/ready"):
            return {
                "status_code": 200,
                "elapsed_ms": 1,
                "payload": {"data": {"ready": True}},
            }
        if url.endswith("/health"):
            return {
                "status_code": 200,
                "elapsed_ms": 1,
                "payload": {"data": {"status": "healthy"}},
            }
        raise AssertionError(f"unexpected JSON probe URL: {url}")

    def fake_request_text(url: str, *, timeout: float, limit: int = 512 * 1024):
        assert url == "http://localhost:8000/metrics"
        assert limit == 512 * 1024
        return {
            "status_code": 200,
            "elapsed_ms": 1,
            "content_type": "text/plain; version=0.0.4; charset=utf-8",
            "body": _valid_metrics_body(),
        }

    monkeypatch.setattr(probe, "_request_json", fake_request_json)
    monkeypatch.setattr(probe, "_request_text", fake_request_text)

    results = {
        result.name: result
        for result in probe.probe_api("http://localhost:8000", timeout=1)
    }

    assert results["api_ready"].status == probe.STATUS_PASSED
    assert results["api_health"].status == probe.STATUS_PASSED
    assert results["prometheus_metrics_endpoint"].status == probe.STATUS_PASSED
    assert results["prometheus_metrics_endpoint"].details["missing_markers"] == []


def test_probe_api_blocks_metrics_when_endpoint_is_missing(monkeypatch) -> None:
    def fake_request_json(url: str, *, timeout: float):
        if url.endswith("/ready"):
            return {
                "status_code": 200,
                "elapsed_ms": 1,
                "payload": {"data": {"ready": True}},
            }
        return {
            "status_code": 200,
            "elapsed_ms": 1,
            "payload": {"data": {"status": "healthy"}},
        }

    def fake_request_text(url: str, *, timeout: float, limit: int = 512 * 1024):
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    monkeypatch.setattr(probe, "_request_json", fake_request_json)
    monkeypatch.setattr(probe, "_request_text", fake_request_text)

    results = {
        result.name: result
        for result in probe.probe_api("http://localhost:8000", timeout=1)
    }

    metrics = results["prometheus_metrics_endpoint"]
    assert metrics.status == probe.STATUS_BLOCKED
    assert metrics.details["url"] == "http://localhost:8000/metrics"


def test_probe_api_fails_metrics_when_exposition_is_invalid(monkeypatch) -> None:
    def fake_request_json(url: str, *, timeout: float):
        if url.endswith("/ready"):
            return {
                "status_code": 200,
                "elapsed_ms": 1,
                "payload": {"data": {"ready": True}},
            }
        return {
            "status_code": 200,
            "elapsed_ms": 1,
            "payload": {"data": {"status": "healthy"}},
        }

    def fake_request_text(url: str, *, timeout: float, limit: int = 512 * 1024):
        return {
            "status_code": 200,
            "elapsed_ms": 1,
            "content_type": "application/json",
            "body": '{"code":0,"data":{}}',
        }

    monkeypatch.setattr(probe, "_request_json", fake_request_json)
    monkeypatch.setattr(probe, "_request_text", fake_request_text)

    results = {
        result.name: result
        for result in probe.probe_api("http://localhost:8000", timeout=1)
    }

    metrics = results["prometheus_metrics_endpoint"]
    assert metrics.status == probe.STATUS_FAILED
    assert metrics.details["missing_markers"] == [
        "# HELP novusai_app_info",
        "# TYPE novusai_app_info",
        "novusai_app_info",
        "# HELP novusai_http_requests_total",
        "# TYPE novusai_http_requests_total",
        "novusai_http_requests_total",
        "# HELP novusai_http_request_duration_seconds",
        "# TYPE novusai_http_request_duration_seconds",
        "novusai_http_request_duration_seconds_bucket",
        "# HELP novusai_http_requests_in_progress",
        "# TYPE novusai_http_requests_in_progress",
        "novusai_http_requests_in_progress",
        "# HELP novusai_component_health",
        "# TYPE novusai_component_health",
        "novusai_component_health",
    ]


def test_probe_api_fails_metrics_when_content_type_is_not_text(monkeypatch) -> None:
    def fake_request_json(url: str, *, timeout: float):
        if url.endswith("/ready"):
            return {
                "status_code": 200,
                "elapsed_ms": 1,
                "payload": {"data": {"ready": True}},
            }
        return {
            "status_code": 200,
            "elapsed_ms": 1,
            "payload": {"data": {"status": "healthy"}},
        }

    def fake_request_text(url: str, *, timeout: float, limit: int = 512 * 1024):
        return {
            "status_code": 200,
            "elapsed_ms": 1,
            "content_type": "application/json",
            "body": _valid_metrics_body(),
        }

    monkeypatch.setattr(probe, "_request_json", fake_request_json)
    monkeypatch.setattr(probe, "_request_text", fake_request_text)

    results = {
        result.name: result
        for result in probe.probe_api("http://localhost:8000", timeout=1)
    }

    metrics = results["prometheus_metrics_endpoint"]
    assert metrics.status == probe.STATUS_FAILED
    assert metrics.details["missing_markers"] == []


def test_probe_api_fails_metrics_when_required_family_is_missing(monkeypatch) -> None:
    def fake_request_json(url: str, *, timeout: float):
        if url.endswith("/ready"):
            return {
                "status_code": 200,
                "elapsed_ms": 1,
                "payload": {"data": {"ready": True}},
            }
        return {
            "status_code": 200,
            "elapsed_ms": 1,
            "payload": {"data": {"status": "healthy"}},
        }

    def fake_request_text(url: str, *, timeout: float, limit: int = 512 * 1024):
        return {
            "status_code": 200,
            "elapsed_ms": 1,
            "content_type": "text/plain; version=0.0.4; charset=utf-8",
            "body": _valid_metrics_body().replace(
                "# HELP novusai_component_health Component health\n"
                "# TYPE novusai_component_health gauge\n"
                'novusai_component_health{component="database"} 1\n',
                "",
            ),
        }

    monkeypatch.setattr(probe, "_request_json", fake_request_json)
    monkeypatch.setattr(probe, "_request_text", fake_request_text)

    results = {
        result.name: result
        for result in probe.probe_api("http://localhost:8000", timeout=1)
    }

    metrics = results["prometheus_metrics_endpoint"]
    assert metrics.status == probe.STATUS_FAILED
    assert metrics.details["missing_markers"] == [
        "# HELP novusai_component_health",
        "# TYPE novusai_component_health",
        "novusai_component_health",
    ]


def test_ai_smoke_readiness_reports_missing_scenarios_and_agent_selector(
    tmp_path: Path,
    monkeypatch,
) -> None:
    for key in (
        "OPENAI_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "DASHSCOPE_API_KEY",
        "DEEPSEEK_API_KEY",
        "AI_SMOKE_AGENT_ID",
        "AI_SMOKE_AGENT_CODE",
    ):
        monkeypatch.delenv(key, raising=False)
    cli_dir = tmp_path / "backend" / "app" / "cli_commands"
    cli_dir.mkdir(parents=True)
    (cli_dir / "ai_commands.py").write_text("pass\n", encoding="utf-8")

    results = {
        result.name: result for result in probe.probe_ai_smoke_readiness(tmp_path)
    }

    assert results["ai_runtime_smoke_cli"].status == probe.STATUS_PASSED
    assert results["ai_real_dialogue_smoke_scenarios"].status == probe.STATUS_BLOCKED
    assert results["ai_smoke_agent_selector"].status == probe.STATUS_BLOCKED
    assert results["ai_real_dialogue_smoke_execution"].status == probe.STATUS_BLOCKED


def test_build_report_marks_blocked_when_optional_production_gates_are_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_probe_api(_api_base_url: str, *, timeout: float):
        return [
            probe.ProbeResult(
                area="readiness",
                name="api_ready",
                status=probe.STATUS_PASSED,
                summary="ready",
                details={"timeout": timeout},
            )
        ]

    monkeypatch.setattr(probe, "probe_api", fake_probe_api)
    monkeypatch.setattr(
        probe,
        "probe_frontend",
        lambda _url, *, timeout: probe.ProbeResult(
            area="readiness",
            name="frontend_root",
            status=probe.STATUS_PASSED,
            summary="ready",
            details={"timeout": timeout},
        ),
    )
    monkeypatch.setattr(
        probe,
        "probe_external_tooling",
        lambda: [
            probe.ProbeResult(
                area="security",
                name="dast_tooling",
                status=probe.STATUS_BLOCKED,
                summary="missing",
                details={},
            )
        ],
    )
    monkeypatch.setattr(probe, "probe_ai_smoke_readiness", lambda _repo_root: [])
    monkeypatch.setattr(
        probe,
        "run_load_smoke",
        lambda *_args, **_kwargs: probe.ProbeResult(
            area="capacity",
            name="local_ready_load_smoke",
            status=probe.STATUS_PASSED,
            summary="passed",
            details={},
        ),
    )

    report = probe.build_report(
        api_base_url="http://localhost:8000",
        frontend_base_url="http://localhost:5666",
        load_smoke_concurrency=2,
        load_smoke_requests=4,
        repo_root=tmp_path,
        timeout=1,
    )

    assert report["overall_status"] == probe.STATUS_BLOCKED
    assert report["summary"] == {
        probe.STATUS_BLOCKED: 1,
        probe.STATUS_FAILED: 0,
        probe.STATUS_PASSED: 3,
    }
