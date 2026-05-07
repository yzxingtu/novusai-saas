"""中文: 生产验收探针结构测试。

EN: Structural tests for the production acceptance probe.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import production_acceptance_probe as probe


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
