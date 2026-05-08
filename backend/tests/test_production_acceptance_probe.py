"""中文: 生产验收探针结构测试。

EN: Structural tests for the production acceptance probe.

Test type: structural
"""

from __future__ import annotations

import json
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


def _ready_health_request_json(url: str, *, timeout: float):
    del timeout
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


def _status_ok(_url: str, *, timeout: float):
    del timeout
    return {"status_code": 200, "elapsed_ms": 1}


def _metrics_ok(_url: str, *, timeout: float, limit: int = 512 * 1024):
    del timeout, limit
    return {
        "status_code": 200,
        "elapsed_ms": 1,
        "content_type": "text/plain",
        "body": "",
    }


def _zap_image_missing(_image: str, *, timeout: float):
    del timeout
    return {"available": False, "docker": "docker", "check": {"exit_code": 1}}


def _zap_image_available(_image: str, *, timeout: float):
    del timeout
    return {"available": True, "docker": "docker", "check": {"exit_code": 0}}


def _zap_pass_command(*args, **kwargs):
    del args, kwargs
    return {
        "exit_code": 0,
        "stdout_tail": "FAIL-NEW: 0\tWARN-NEW: 1",
        "stderr_tail": "",
    }


def _command_pass(*args, **kwargs):
    del args, kwargs
    return {"exit_code": 0, "stdout_tail": "", "stderr_tail": ""}


def test_request_helpers_reject_non_http_urls() -> None:
    with pytest.raises(ValueError, match="http or https"):
        probe._request_status("file:///etc/passwd", timeout=1)


def test_command_probe_result_blocks_on_registry_endpoint_failure() -> None:
    result = probe._command_probe_result(
        area="security",
        name="frontend_dependency_audit_scan",
        command={
            "exit_code": 1,
            "stderr_tail": "ERR_PNPM_AUDIT_ENDPOINT_NOT_EXISTS",
        },
        summary_passed="passed",
        summary_failed="failed",
        summary_blocked="blocked",
        block_markers=probe._NETWORK_BLOCK_MARKERS,
    )

    assert result.status == probe.STATUS_BLOCKED
    assert result.summary == "blocked"


def test_http_error_result_blocks_when_local_target_is_unavailable() -> None:
    result = probe._http_error_result(
        area="readiness",
        name="api_ready",
        url="http://localhost:8000/ready",
        exc=urllib.error.HTTPError(
            "http://localhost:8000/ready",
            502,
            "Bad Gateway",
            {},
            None,
        ),
    )

    assert result.status == probe.STATUS_BLOCKED
    assert result.details["url"] == "http://localhost:8000/ready"


def test_probe_api_passes_metrics_when_prometheus_exposition_is_valid(
    monkeypatch,
) -> None:
    def fake_request_text(url: str, *, timeout: float, limit: int = 512 * 1024):
        del timeout
        assert url == "http://localhost:8000/metrics"
        assert limit == 512 * 1024
        return {
            "status_code": 200,
            "elapsed_ms": 1,
            "content_type": "text/plain; version=0.0.4; charset=utf-8",
            "body": _valid_metrics_body(),
        }

    monkeypatch.setattr(probe, "_request_json", _ready_health_request_json)
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
    def fake_request_text(url: str, *, timeout: float, limit: int = 512 * 1024):
        del timeout, limit
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    monkeypatch.setattr(probe, "_request_json", _ready_health_request_json)
    monkeypatch.setattr(probe, "_request_text", fake_request_text)

    results = {
        result.name: result
        for result in probe.probe_api("http://localhost:8000", timeout=1)
    }

    metrics = results["prometheus_metrics_endpoint"]
    assert metrics.status == probe.STATUS_BLOCKED
    assert metrics.details["url"] == "http://localhost:8000/metrics"


def test_probe_api_fails_metrics_when_content_type_is_not_text(monkeypatch) -> None:
    def fake_request_text(url: str, *, timeout: float, limit: int = 512 * 1024):
        del url, timeout, limit
        return {
            "status_code": 200,
            "elapsed_ms": 1,
            "content_type": "application/json",
            "body": _valid_metrics_body(),
        }

    monkeypatch.setattr(probe, "_request_json", _ready_health_request_json)
    monkeypatch.setattr(probe, "_request_text", fake_request_text)

    results = {
        result.name: result
        for result in probe.probe_api("http://localhost:8000", timeout=1)
    }

    metrics = results["prometheus_metrics_endpoint"]
    assert metrics.status == probe.STATUS_FAILED
    assert metrics.details["missing_markers"] == []


def test_probe_api_fails_metrics_when_required_family_is_missing(monkeypatch) -> None:
    def fake_request_text(url: str, *, timeout: float, limit: int = 512 * 1024):
        del url, timeout, limit
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

    monkeypatch.setattr(probe, "_request_json", _ready_health_request_json)
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


def test_ai_smoke_readiness_requires_ledger_selector_and_report(
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
    (cli_dir / "ai_commands.py").write_text(
        '@ai_cmd.command("smoke")\ndef ai_smoke():\n    pass\n'
        '@ai_cmd.command("real-dialogue-smoke")\ndef ai_real_dialogue_smoke():\n    pass\n',
        encoding="utf-8",
    )

    results = {
        result.name: result for result in probe.probe_ai_smoke_readiness(tmp_path)
    }

    assert results["ai_runtime_smoke_cli"].status == probe.STATUS_PASSED
    assert results["ai_real_dialogue_smoke_scenarios"].status == probe.STATUS_BLOCKED
    assert results["ai_provider_credentials"].status == probe.STATUS_BLOCKED
    assert results["ai_smoke_agent_selector"].status == probe.STATUS_BLOCKED
    assert results["ai_real_dialogue_smoke_execution"].status == probe.STATUS_BLOCKED


def _write_smoke_ledger(path: Path) -> str:
    path.parent.mkdir(parents=True)
    content = (
        "scenario_id: S1\n"
        "user_input: ping\n"
        "required_capabilities: provider\n"
        "expected_observable_outcome: answer\n"
    )
    path.write_text(content, encoding="utf-8")
    import hashlib

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _strict_ai_smoke_report_payload(
    ledger_hash: str,
    *,
    provider: dict | None = None,
    scenario_results: list[dict] | None = None,
    overall_status: str = "passed",
) -> dict:
    return {
        "schema_version": "ai-real-dialogue-smoke/v1",
        "report_type": "ai_real_dialogue_smoke",
        "execution_kind": "real_dialogue",
        "overall_status": overall_status,
        "command": {
            "argv": ["python", "-m", "app.cli", "ai", "real-dialogue-smoke"],
            "exit_code": 0,
        },
        "ledger": {"sha256": ledger_hash, "scenario_ids": ["S1"]},
        "agent": {
            "selector_type": "id",
            "selector_value": "59",
            "resolved_agent_id": 59,
        },
        "provider": provider
        if provider is not None
        else {
            "live_provider_call_count": 1,
            "mocked_llm": False,
            "replay": False,
            "call_logs": [
                {
                    "id": 202,
                    "conversation_id": 101,
                    "status": "success",
                    "provider_name": "test-provider",
                    "model_name": "test-model",
                    "request_type": "chat",
                    "call_type": "main_chat",
                }
            ],
        },
        "scenario_results": scenario_results
        if scenario_results is not None
        else [
            {
                "scenario_id": "S1",
                "must_pass": True,
                "status": "passed",
                "conversation_id": 101,
                "provider_call_log_id": 202,
                "observable_checks": {
                    "assistant_text_non_empty": True,
                    "provider_call_log_present": True,
                    "provider_call_succeeded": True,
                    "retired_current_page_or_online_search_exposed": False,
                },
            }
        ],
    }


def test_ai_smoke_minimal_passed_json_is_not_execution_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cli_dir = tmp_path / "backend" / "app" / "cli_commands"
    cli_dir.mkdir(parents=True)
    (cli_dir / "ai_commands.py").write_text(
        '@ai_cmd.command("smoke")\ndef ai_smoke():\n    pass\n'
        '@ai_cmd.command("real-dialogue-smoke")\ndef ai_real_dialogue_smoke():\n    pass\n',
        encoding="utf-8",
    )
    ledger = tmp_path / "ops" / "ai-smoke" / "smoke-scenarios.md"
    _write_smoke_ledger(ledger)
    report = tmp_path / "smoke-report.json"
    report.write_text('{"overall_status":"passed"}', encoding="utf-8")

    results = {
        result.name: result
        for result in probe.probe_ai_smoke_readiness(
            tmp_path,
            ai_smoke_agent_id=59,
            smoke_report_path=report,
        )
    }

    assert results["ai_real_dialogue_smoke_scenarios"].status == probe.STATUS_PASSED
    assert results["ai_provider_credentials"].status == probe.STATUS_BLOCKED
    assert results["ai_smoke_agent_selector"].status == probe.STATUS_PASSED
    assert results["ai_real_dialogue_smoke_execution"].status == probe.STATUS_BLOCKED
    assert (
        "schema_version_invalid_or_missing"
        in results["ai_real_dialogue_smoke_execution"].details["report"][
            "validation_errors"
        ]
    )


def test_ai_smoke_strict_report_can_satisfy_execution_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cli_dir = tmp_path / "backend" / "app" / "cli_commands"
    cli_dir.mkdir(parents=True)
    (cli_dir / "ai_commands.py").write_text(
        '@ai_cmd.command("smoke")\ndef ai_smoke():\n    pass\n'
        '@ai_cmd.command("real-dialogue-smoke")\ndef ai_real_dialogue_smoke():\n    pass\n',
        encoding="utf-8",
    )
    ledger = tmp_path / "ops" / "ai-smoke" / "smoke-scenarios.md"
    ledger_hash = _write_smoke_ledger(ledger)
    report = tmp_path / "smoke-report.json"
    report.write_text(
        json.dumps(_strict_ai_smoke_report_payload(ledger_hash)),
        encoding="utf-8",
    )

    results = {
        result.name: result
        for result in probe.probe_ai_smoke_readiness(
            tmp_path,
            ai_smoke_agent_id=59,
            smoke_report_path=report,
        )
    }

    assert results["ai_real_dialogue_smoke_scenarios"].status == probe.STATUS_PASSED
    assert results["ai_provider_credentials"].status == probe.STATUS_BLOCKED
    assert results["ai_provider_credentials"].details[
        "strict_smoke_report_provider_evidence"
    ]
    assert results["ai_smoke_agent_selector"].status == probe.STATUS_PASSED
    assert results["ai_real_dialogue_smoke_execution"].status == probe.STATUS_PASSED


def test_ai_smoke_markdown_passed_report_is_blocked(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cli_dir = tmp_path / "backend" / "app" / "cli_commands"
    cli_dir.mkdir(parents=True)
    (cli_dir / "ai_commands.py").write_text(
        '@ai_cmd.command("smoke")\ndef ai_smoke():\n    pass\n'
        '@ai_cmd.command("real-dialogue-smoke")\ndef ai_real_dialogue_smoke():\n    pass\n',
        encoding="utf-8",
    )
    _write_smoke_ledger(tmp_path / "ops" / "ai-smoke" / "smoke-scenarios.md")
    report = tmp_path / "smoke-report.md"
    report.write_text("overall_status: passed\n", encoding="utf-8")

    results = {
        result.name: result
        for result in probe.probe_ai_smoke_readiness(
            tmp_path,
            ai_smoke_agent_id=59,
            smoke_report_path=report,
        )
    }

    assert results["ai_real_dialogue_smoke_execution"].status == probe.STATUS_BLOCKED
    assert (
        "report_must_be_strict_json"
        in results["ai_real_dialogue_smoke_execution"].details["report"][
            "validation_errors"
        ]
    )


def test_ai_smoke_report_requires_ledger_authoritative_provider_log_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cli_dir = tmp_path / "backend" / "app" / "cli_commands"
    cli_dir.mkdir(parents=True)
    (cli_dir / "ai_commands.py").write_text(
        '@ai_cmd.command("smoke")\ndef ai_smoke():\n    pass\n'
        '@ai_cmd.command("real-dialogue-smoke")\ndef ai_real_dialogue_smoke():\n    pass\n',
        encoding="utf-8",
    )
    ledger_hash = _write_smoke_ledger(
        tmp_path / "ops" / "ai-smoke" / "smoke-scenarios.md"
    )
    report = tmp_path / "smoke-report.json"
    report.write_text(
        json.dumps(
            _strict_ai_smoke_report_payload(
                ledger_hash,
                scenario_results=[{"scenario_id": "S1", "status": "passed"}],
            )
        ),
        encoding="utf-8",
    )

    results = {
        result.name: result
        for result in probe.probe_ai_smoke_readiness(
            tmp_path,
            ai_smoke_agent_id=59,
            smoke_report_path=report,
        )
    }

    report_details = results["ai_real_dialogue_smoke_execution"].details["report"]
    assert results["ai_real_dialogue_smoke_execution"].status == probe.STATUS_BLOCKED
    assert (
        "passed_scenario_lacks_real_dialogue_evidence"
        in report_details["blocking_errors"]
    )
    assert report_details["invalid_passed_scenarios"] == ["S1"]


@pytest.mark.parametrize(
    ("provider_patch", "expected_error"),
    [
        ({"mocked_llm": True}, "provider_mocked_llm_forbidden"),
        ({"replay": True}, "provider_replay_forbidden"),
        ({"mocked_llm": None}, "provider_mocked_llm_flag_missing"),
        ({"live_provider_call_count": "1"}, "provider_live_call_count_invalid"),
    ],
)
def test_ai_smoke_report_rejects_mock_replay_or_weak_provider_evidence(
    tmp_path: Path,
    monkeypatch,
    provider_patch: dict,
    expected_error: str,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cli_dir = tmp_path / "backend" / "app" / "cli_commands"
    cli_dir.mkdir(parents=True)
    (cli_dir / "ai_commands.py").write_text(
        '@ai_cmd.command("smoke")\ndef ai_smoke():\n    pass\n'
        '@ai_cmd.command("real-dialogue-smoke")\ndef ai_real_dialogue_smoke():\n    pass\n',
        encoding="utf-8",
    )
    ledger_hash = _write_smoke_ledger(
        tmp_path / "ops" / "ai-smoke" / "smoke-scenarios.md"
    )
    provider = _strict_ai_smoke_report_payload(ledger_hash)["provider"]
    provider.update(provider_patch)
    report = tmp_path / "smoke-report.json"
    report.write_text(
        json.dumps(_strict_ai_smoke_report_payload(ledger_hash, provider=provider)),
        encoding="utf-8",
    )

    results = {
        result.name: result
        for result in probe.probe_ai_smoke_readiness(
            tmp_path,
            ai_smoke_agent_id=59,
            smoke_report_path=report,
        )
    }

    report_details = results["ai_real_dialogue_smoke_execution"].details["report"]
    assert results["ai_real_dialogue_smoke_execution"].status in {
        probe.STATUS_BLOCKED,
        probe.STATUS_FAILED,
    }
    assert expected_error in (
        report_details["blocking_errors"] + report_details["failure_errors"]
    )


def test_capacity_benchmark_blocks_when_not_requested() -> None:
    result = probe.run_capacity_benchmark(
        "http://localhost:8000",
        concurrency=4,
        requests=0,
        timeout=1,
        p95_budget_ms=1000,
        error_budget_ratio=0,
    )

    assert result.status == probe.STATUS_BLOCKED
    assert result.details["run_with"] == "--capacity-requests"


def test_local_load_smoke_blocks_when_target_is_unavailable(monkeypatch) -> None:
    def raise_bad_gateway(url: str, *, timeout: float):
        del timeout
        raise urllib.error.HTTPError(url, 502, "Bad Gateway", {}, None)

    monkeypatch.setattr(probe, "_request_json", raise_bad_gateway)

    result = probe.run_load_smoke(
        "http://localhost:8000",
        concurrency=2,
        requests=4,
        timeout=1,
    )

    assert result.status == probe.STATUS_BLOCKED
    assert result.details["success_count"] == 0
    assert result.details["error_count"] == 4


def test_capacity_benchmark_passes_when_thresholds_are_met(monkeypatch) -> None:
    monkeypatch.setattr(probe, "_request_status", _status_ok)
    monkeypatch.setattr(probe, "_request_json", _ready_health_request_json)
    monkeypatch.setattr(probe, "_request_text", _metrics_ok)

    result = probe.run_capacity_benchmark(
        "http://localhost:8000",
        concurrency=2,
        requests=8,
        timeout=1,
        p95_budget_ms=5000,
        error_budget_ratio=0,
    )

    assert result.status == probe.STATUS_PASSED
    assert result.details["success_count"] == 8


def test_postgres_restore_drill_is_blocked_until_explicitly_requested() -> None:
    result = probe.run_postgres_backup_restore_drill(
        requested=False,
        postgres_container="novusai-postgres-dev",
        source_db="novusai_saas",
        postgres_user="postgres",
        restore_db_prefix="novusai_restore_drill",
        timeout=1,
    )

    assert result.status == probe.STATUS_BLOCKED
    assert result.details["run_with"] == "--run-backup-restore-drill"


def test_postgres_restore_drill_rejects_unsafe_identifiers() -> None:
    result = probe.run_postgres_backup_restore_drill(
        requested=True,
        postgres_container="novusai-postgres-dev",
        source_db="novusai_saas; DROP DATABASE postgres",
        postgres_user="postgres",
        restore_db_prefix="novusai_restore_drill",
        timeout=1,
    )

    assert result.status == probe.STATUS_FAILED
    assert "safe PostgreSQL identifier" in result.details["error"]


def test_dast_baseline_blocks_when_zap_image_is_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        probe.shutil, "which", lambda name: "docker" if name == "docker" else None
    )
    monkeypatch.setattr(probe, "_docker_image_available", _zap_image_missing)

    result = probe.run_dast_baseline(
        target_url="http://localhost:8000",
        repo_root=tmp_path,
        artifact_dir=Path("artifacts"),
        dast_image="zaproxy/zap-stable:latest",
        allow_pull=False,
        timeout=1,
    )

    assert result.status == probe.STATUS_BLOCKED
    assert result.details["run_with"] == "--allow-dast-pull"


def test_dast_baseline_passes_when_zap_reports_no_failures(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(
        probe.shutil, "which", lambda name: "docker" if name == "docker" else None
    )
    monkeypatch.setattr(probe, "_docker_image_available", _zap_image_available)
    monkeypatch.setattr(probe, "_run_command", _zap_pass_command)

    result = probe.run_dast_baseline(
        target_url="http://localhost:8000",
        repo_root=tmp_path,
        artifact_dir=Path("artifacts"),
        dast_image="zaproxy/zap-stable:latest",
        allow_pull=False,
        timeout=1,
    )

    assert result.status == probe.STATUS_PASSED
    assert result.details["fail_new"] == 0
    assert result.details["docker_target_url"] == "http://host.docker.internal:8000"


def test_security_scan_execution_passes_when_commands_pass(monkeypatch, tmp_path: Path):
    (tmp_path / "backend").mkdir()
    (tmp_path / "frontend").mkdir()
    monkeypatch.setattr(probe, "_module_available", lambda _name: True)
    monkeypatch.setattr(probe, "_run_command", _command_pass)

    results = {
        result.name: result
        for result in probe.run_security_scans(
            repo_root=tmp_path,
            artifact_dir=Path("artifacts"),
            timeout=1,
        )
    }

    assert results["python_dependency_audit_scan"].status == probe.STATUS_PASSED
    assert results["python_sast_scan"].status == probe.STATUS_PASSED
    assert results["frontend_dependency_audit_scan"].status == probe.STATUS_PASSED


def test_build_report_stays_blocked_when_optional_gates_are_not_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        probe,
        "probe_api",
        lambda _api_base_url, *, timeout: [
            probe.ProbeResult(
                area="readiness",
                name="api_ready",
                status=probe.STATUS_PASSED,
                summary="ready",
                details={"timeout": timeout},
            )
        ],
    )
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
    monkeypatch.setattr(probe, "probe_external_tooling", lambda **_kwargs: [])
    monkeypatch.setattr(probe, "probe_ai_smoke_readiness", lambda *_args, **_kwargs: [])
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
    monkeypatch.setattr(
        probe,
        "run_capacity_benchmark",
        lambda *_args, **_kwargs: probe.ProbeResult(
            area="capacity",
            name="capacity_acceptance_benchmark",
            status=probe.STATUS_BLOCKED,
            summary="blocked",
            details={},
        ),
    )

    report = probe.build_report(
        api_base_url="http://localhost:8000",
        frontend_base_url="http://localhost:5666",
        load_smoke_concurrency=2,
        load_smoke_requests=4,
        capacity_concurrency=2,
        capacity_requests=0,
        capacity_p95_budget_ms=1000,
        capacity_error_budget_ratio=0,
        repo_root=tmp_path,
        timeout=1,
        postgres_container="novusai-postgres-dev",
        postgres_db="novusai_saas",
        postgres_user="postgres",
        postgres_restore_prefix="novusai_restore_drill",
        run_backup_restore_drill=False,
        run_security_scans_enabled=False,
        run_dast_baseline_scan=False,
        dast_target_url=None,
        dast_image="zaproxy/zap-stable:latest",
        allow_dast_pull=False,
        artifact_dir=Path("artifacts"),
        ai_smoke_agent_id=None,
        ai_smoke_agent_code=None,
        ai_smoke_report=None,
    )

    assert report["overall_status"] == probe.STATUS_BLOCKED
    assert report["summary"][probe.STATUS_BLOCKED] == 4
