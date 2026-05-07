"""中文: 生产验收探针，输出可机器读取的通过/阻塞/失败门禁。

EN: Production acceptance probe that emits machine-readable pass/block/fail
gates.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_BLOCKED = "blocked"

DEFAULT_POSTGRES_CONTAINER = "novusai-postgres-dev"
DEFAULT_POSTGRES_DB = "novusai_saas"
DEFAULT_POSTGRES_USER = "postgres"
DEFAULT_DAST_IMAGE = "zaproxy/zap-stable:latest"
DEFAULT_ARTIFACT_DIR = Path("ops") / "acceptance-artifacts"

_POSTGRES_TOOLS = ("pg_dump", "pg_restore", "psql")
_SMOKE_SCENARIO_MARKERS = (
    "scenario_id",
    "user_input",
    "required_capabilities",
    "expected_observable_outcome",
)
_NETWORK_BLOCK_MARKERS = (
    "ERR_PNPM_AUDIT_ENDPOINT_NOT_EXISTS",
    "ECONNRESET",
    "ETIMEDOUT",
    "ENOTFOUND",
    "HTTPSConnectionPool",
    "Max retries exceeded",
    "SSLError",
    "UNEXPECTED_EOF",
    "Could not fetch URL",
    "ServiceUnavailable",
    "temporary failure",
)


@dataclass(frozen=True, slots=True)
class ProbeResult:
    area: str
    name: str
    status: str
    summary: str
    details: dict[str, Any]


def _normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def _validate_probe_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("probe URL must use http or https")


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        values[key.strip()] = raw_value.strip().strip('"').strip("'")
    return values


def _has_env_value(
    names: tuple[str, ...],
    *,
    env_file_values: dict[str, str],
) -> tuple[bool, list[str]]:
    configured = [
        name
        for name in names
        if (os.environ.get(name) or env_file_values.get(name) or "").strip()
    ]
    return bool(configured), configured


def _request_json(url: str, *, timeout: float) -> dict[str, Any]:
    _validate_probe_url(url)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    started_at = time.perf_counter()
    # 中文: _validate_probe_url 已限制 http/https；Bandit 不能跨函数识别这个守卫。
    # EN: _validate_probe_url restricts http/https; Bandit cannot infer that guard.
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        body = response.read(64 * 1024).decode("utf-8", errors="replace")
        try:
            payload: Any = json.loads(body) if body else None
        except json.JSONDecodeError:
            payload = {"raw": body[:500]}
        return {
            "status_code": response.status,
            "elapsed_ms": elapsed_ms,
            "payload": payload,
        }


def _request_status(url: str, *, timeout: float) -> dict[str, Any]:
    _validate_probe_url(url)
    request = urllib.request.Request(url, headers={"Accept": "*/*"})
    started_at = time.perf_counter()
    # 中文: _validate_probe_url 已限制 http/https；Bandit 不能跨函数识别这个守卫。
    # EN: _validate_probe_url restricts http/https; Bandit cannot infer that guard.
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        return {"status_code": response.status, "elapsed_ms": elapsed_ms}


def _request_text(
    url: str, *, timeout: float, limit: int = 512 * 1024
) -> dict[str, Any]:
    _validate_probe_url(url)
    request = urllib.request.Request(url, headers={"Accept": "*/*"})
    started_at = time.perf_counter()
    # 中文: _validate_probe_url 已限制 http/https；Bandit 不能跨函数识别这个守卫。
    # EN: _validate_probe_url restricts http/https; Bandit cannot infer that guard.
    with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        body = response.read(limit).decode("utf-8", errors="replace")
        return {
            "status_code": response.status,
            "elapsed_ms": elapsed_ms,
            "content_type": response.headers.get("Content-Type", ""),
            "body": body,
        }


def _tail_text(value: str | None, limit: int = 4000) -> str:
    if not value:
        return ""
    return value[-limit:]


def _run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    stdout_path: Path | None = None,
    stderr_path: Path | None = None,
    timeout: float,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return {
            "command": args,
            "cwd": str(cwd) if cwd else None,
            "exit_code": None,
            "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
            "error": f"{type(exc).__name__}: {exc}",
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        return {
            "command": args,
            "cwd": str(cwd) if cwd else None,
            "exit_code": None,
            "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
            "timed_out": True,
            "timeout_seconds": timeout,
            "stdout_tail": _tail_text(stdout),
            "stderr_tail": _tail_text(stderr),
        }

    if stdout_path is not None:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text(completed.stdout, encoding="utf-8")
    if stderr_path is not None:
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.write_text(completed.stderr, encoding="utf-8")

    return {
        "command": args,
        "cwd": str(cwd) if cwd else None,
        "exit_code": completed.returncode,
        "elapsed_ms": round((time.perf_counter() - started_at) * 1000, 2),
        "stdout_tail": _tail_text(completed.stdout),
        "stderr_tail": _tail_text(completed.stderr),
        "stdout_path": str(stdout_path) if stdout_path else None,
        "stderr_path": str(stderr_path) if stderr_path else None,
    }


def _command_probe_result(
    *,
    area: str,
    name: str,
    command: dict[str, Any],
    summary_passed: str,
    summary_failed: str,
    summary_blocked: str,
    block_markers: tuple[str, ...] = (),
    extra_details: dict[str, Any] | None = None,
) -> ProbeResult:
    combined_output = (
        str(command.get("stdout_tail") or "")
        + "\n"
        + str(command.get("stderr_tail") or "")
        + "\n"
        + str(command.get("error") or "")
    )
    if command.get("exit_code") == 0:
        status = STATUS_PASSED
        summary = summary_passed
    elif command.get("error") or any(
        marker in combined_output for marker in block_markers
    ):
        status = STATUS_BLOCKED
        summary = summary_blocked
    else:
        status = STATUS_FAILED
        summary = summary_failed

    details = {"command_result": command}
    if extra_details:
        details.update(extra_details)
    return ProbeResult(
        area=area,
        name=name,
        status=status,
        summary=summary,
        details=details,
    )


def _http_error_result(
    *,
    area: str,
    name: str,
    url: str,
    exc: Exception,
    missing_is_blocked: bool = False,
) -> ProbeResult:
    status = STATUS_FAILED
    if (
        isinstance(exc, urllib.error.HTTPError)
        and exc.code == 404
        and missing_is_blocked
    ):
        status = STATUS_BLOCKED
    return ProbeResult(
        area=area,
        name=name,
        status=status,
        summary=f"{url} probe failed: {type(exc).__name__}",
        details={"url": url, "error": str(exc)},
    )


def _tool_map(tool_names: tuple[str, ...]) -> dict[str, str | None]:
    return {name: shutil.which(name) for name in tool_names}


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _docker_image_available(image: str, *, timeout: float) -> dict[str, Any]:
    docker = shutil.which("docker")
    if not docker:
        return {"available": False, "docker": None, "check": None}
    check = _run_command(
        [docker, "image", "inspect", image, "--format", "{{.Id}}"],
        timeout=timeout,
    )
    return {
        "available": check.get("exit_code") == 0,
        "docker": docker,
        "check": check,
    }


def _safe_pg_identifier(value: str, *, label: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{label} is required")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", cleaned):
        raise ValueError(f"{label} must be a safe PostgreSQL identifier")
    return cleaned


def _docker_visible_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return url
    host = "host.docker.internal"
    netloc = host if parsed.port is None else f"{host}:{parsed.port}"
    return urllib.parse.urlunparse(
        (
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def probe_api(api_base_url: str, *, timeout: float) -> list[ProbeResult]:
    base = _normalize_base_url(api_base_url)
    results: list[ProbeResult] = []

    ready_url = f"{base}/ready"
    try:
        ready = _request_json(ready_url, timeout=timeout)
        payload = ready.get("payload")
        data = payload.get("data") if isinstance(payload, dict) else {}
        passed = ready["status_code"] == 200 and data.get("ready") is True
        results.append(
            ProbeResult(
                area="readiness",
                name="api_ready",
                status=STATUS_PASSED if passed else STATUS_FAILED,
                summary="/ready returned ready=true"
                if passed
                else "/ready did not return ready=true",
                details={"url": ready_url, **ready},
            )
        )
    except Exception as exc:
        results.append(
            _http_error_result(
                area="readiness",
                name="api_ready",
                url=ready_url,
                exc=exc,
            )
        )

    health_url = f"{base}/health"
    try:
        health = _request_json(health_url, timeout=timeout)
        payload = health.get("payload")
        data = payload.get("data") if isinstance(payload, dict) else {}
        health_status = data.get("status")
        passed = health["status_code"] == 200 and health_status == "healthy"
        results.append(
            ProbeResult(
                area="monitoring",
                name="api_health",
                status=STATUS_PASSED if passed else STATUS_FAILED,
                summary="/health returned healthy"
                if passed
                else f"/health returned {health_status or 'unknown'}",
                details={"url": health_url, **health},
            )
        )
    except Exception as exc:
        results.append(
            _http_error_result(
                area="monitoring",
                name="api_health",
                url=health_url,
                exc=exc,
            )
        )

    metrics_url = f"{base}/metrics"
    try:
        metrics = _request_text(metrics_url, timeout=timeout)
        body = str(metrics.pop("body", ""))
        content_type = str(metrics.get("content_type", "")).lower()
        required_markers = (
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
        )
        missing_markers = [marker for marker in required_markers if marker not in body]
        passed = (
            metrics["status_code"] == 200
            and "text/plain" in content_type
            and not missing_markers
        )
        results.append(
            ProbeResult(
                area="monitoring",
                name="prometheus_metrics_endpoint",
                status=STATUS_PASSED if passed else STATUS_FAILED,
                summary="/metrics returned Prometheus exposition"
                if passed
                else "/metrics did not return the expected Prometheus exposition",
                details={
                    "url": metrics_url,
                    **metrics,
                    "missing_markers": missing_markers,
                    "body_sample": body[:500],
                },
            )
        )
    except Exception as exc:
        results.append(
            _http_error_result(
                area="monitoring",
                name="prometheus_metrics_endpoint",
                url=metrics_url,
                exc=exc,
                missing_is_blocked=True,
            )
        )
    return results


def probe_frontend(frontend_base_url: str | None, *, timeout: float) -> ProbeResult:
    if not frontend_base_url:
        return ProbeResult(
            area="readiness",
            name="frontend_root",
            status=STATUS_BLOCKED,
            summary="frontend base URL not provided",
            details={},
        )
    url = _normalize_base_url(frontend_base_url)
    try:
        result = _request_status(url, timeout=timeout)
        passed = 200 <= result["status_code"] < 400
        return ProbeResult(
            area="readiness",
            name="frontend_root",
            status=STATUS_PASSED if passed else STATUS_FAILED,
            summary="frontend root is reachable"
            if passed
            else "frontend root returned a non-success status",
            details={"url": url, **result},
        )
    except Exception as exc:
        return _http_error_result(
            area="readiness",
            name="frontend_root",
            url=url,
            exc=exc,
        )


def _postgres_tooling_result(*, postgres_container: str, timeout: float) -> ProbeResult:
    host_tools = _tool_map(_POSTGRES_TOOLS)
    host_present = [name for name, path in host_tools.items() if path]
    if len(host_present) == len(_POSTGRES_TOOLS):
        return ProbeResult(
            area="backup_restore",
            name="postgres_backup_restore_tooling",
            status=STATUS_PASSED,
            summary="PostgreSQL backup/restore tooling is available on the host",
            details={
                "mode": "host",
                "required": list(_POSTGRES_TOOLS),
                "present": host_present,
                "missing": [],
            },
        )

    docker = shutil.which("docker")
    if not docker:
        return ProbeResult(
            area="backup_restore",
            name="postgres_backup_restore_tooling",
            status=STATUS_BLOCKED,
            summary="pg_dump, pg_restore, psql, and Docker fallback are missing",
            details={
                "mode": "missing",
                "required": list(_POSTGRES_TOOLS),
                "host_present": host_present,
                "host_missing": [
                    name for name in _POSTGRES_TOOLS if not host_tools[name]
                ],
            },
        )

    docker_checks: dict[str, Any] = {}
    present: list[str] = []
    for tool in _POSTGRES_TOOLS:
        result = _run_command(
            [docker, "exec", postgres_container, tool, "--version"],
            timeout=timeout,
        )
        docker_checks[tool] = result
        if result.get("exit_code") == 0:
            present.append(tool)

    passed = len(present) == len(_POSTGRES_TOOLS)
    return ProbeResult(
        area="backup_restore",
        name="postgres_backup_restore_tooling",
        status=STATUS_PASSED if passed else STATUS_BLOCKED,
        summary="PostgreSQL backup/restore tooling is available inside Docker"
        if passed
        else "PostgreSQL tools are not available on host or in the dev container",
        details={
            "mode": "docker",
            "container": postgres_container,
            "required": list(_POSTGRES_TOOLS),
            "present": present,
            "missing": [name for name in _POSTGRES_TOOLS if name not in present],
            "host_present": host_present,
            "docker_checks": docker_checks,
        },
    )


def _dast_tooling_result(*, dast_image: str, timeout: float) -> ProbeResult:
    native = _tool_map(("zap-baseline.py", "zap-cli"))
    native_present = [name for name, path in native.items() if path]
    image = _docker_image_available(dast_image, timeout=timeout)
    passed = bool(native_present or image["available"])
    return ProbeResult(
        area="security",
        name="dast_tooling",
        status=STATUS_PASSED if passed else STATUS_BLOCKED,
        summary="OWASP ZAP tooling is available"
        if passed
        else "OWASP ZAP command or local Docker image is missing",
        details={
            "native_required_any": ["zap-baseline.py", "zap-cli"],
            "native_present": native_present,
            "docker_image": dast_image,
            "docker_image_available": image["available"],
            "docker": image["docker"],
            "image_check": image["check"],
        },
    )


def probe_external_tooling(
    *,
    postgres_container: str = DEFAULT_POSTGRES_CONTAINER,
    dast_image: str = DEFAULT_DAST_IMAGE,
    timeout: float = 5.0,
) -> list[ProbeResult]:
    pip_audit_present = _module_available("pip_audit") or bool(
        shutil.which("pip-audit")
    )
    bandit_present = _module_available("bandit") or bool(shutil.which("bandit"))
    pnpm_present = bool(shutil.which("pnpm"))
    k6_present = bool(shutil.which("k6"))
    locust_present = bool(shutil.which("locust")) or _module_available("locust")

    return [
        ProbeResult(
            area="capacity",
            name="capacity_benchmark_harness",
            status=STATUS_PASSED,
            summary="built-in HTTP capacity benchmark harness is available",
            details={
                "mode": "python-stdlib",
                "external_tools": {
                    "k6": k6_present,
                    "locust": locust_present,
                },
            },
        ),
        _postgres_tooling_result(
            postgres_container=postgres_container,
            timeout=timeout,
        ),
        ProbeResult(
            area="security",
            name="python_dependency_audit_tooling",
            status=STATUS_PASSED if pip_audit_present else STATUS_BLOCKED,
            summary="pip-audit is available"
            if pip_audit_present
            else "pip-audit is missing",
            details={
                "module": _module_available("pip_audit"),
                "binary": shutil.which("pip-audit"),
            },
        ),
        ProbeResult(
            area="security",
            name="python_sast_tooling",
            status=STATUS_PASSED if bandit_present else STATUS_BLOCKED,
            summary="bandit is available" if bandit_present else "bandit is missing",
            details={
                "module": _module_available("bandit"),
                "binary": shutil.which("bandit"),
            },
        ),
        ProbeResult(
            area="security",
            name="frontend_dependency_audit_tooling",
            status=STATUS_PASSED if pnpm_present else STATUS_BLOCKED,
            summary="pnpm audit tooling is available"
            if pnpm_present
            else "pnpm is missing",
            details={"binary": shutil.which("pnpm")},
        ),
        _dast_tooling_result(dast_image=dast_image, timeout=timeout),
    ]


def _scenario_ledger_valid(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return all(marker in text for marker in _SMOKE_SCENARIO_MARKERS)


def _smoke_report_status(path: Path | None) -> tuple[str, dict[str, Any]]:
    if path is None:
        return STATUS_BLOCKED, {"path": None}
    if not path.exists():
        return STATUS_BLOCKED, {"path": str(path), "exists": False}

    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        raw_status = str(payload.get("overall_status") or payload.get("status") or "")
        status = raw_status.lower()
        scenario_results = payload.get("scenario_results")
        failed_must_pass: list[str] = []
        if isinstance(scenario_results, list):
            for item in scenario_results:
                if not isinstance(item, dict):
                    continue
                priority = str(item.get("priority") or "").lower()
                must_pass = bool(item.get("must_pass")) or priority == "must-pass"
                item_status = str(item.get("status") or "").lower()
                if must_pass and item_status != STATUS_PASSED:
                    failed_must_pass.append(str(item.get("scenario_id") or "unknown"))
        if failed_must_pass:
            resolved_status = STATUS_FAILED
        elif status in {STATUS_PASSED, STATUS_FAILED, STATUS_BLOCKED}:
            resolved_status = status
        else:
            resolved_status = STATUS_BLOCKED
        return resolved_status, {
            "path": str(path),
            "format": "json",
            "status": raw_status,
            "failed_must_pass_scenarios": failed_must_pass,
        }
    lowered = text.lower()
    if "overall_status: passed" in lowered or "status: passed" in lowered:
        return STATUS_PASSED, {"path": str(path), "format": "text"}
    if "overall_status: failed" in lowered or "status: failed" in lowered:
        return STATUS_FAILED, {"path": str(path), "format": "text"}
    return STATUS_BLOCKED, {"path": str(path), "format": "text"}


def _smoke_report_passed(path: Path | None) -> tuple[bool, dict[str, Any]]:
    status, details = _smoke_report_status(path)
    return status == STATUS_PASSED, details


def probe_ai_smoke_readiness(
    repo_root: Path,
    *,
    ai_smoke_agent_id: int | None = None,
    ai_smoke_agent_code: str | None = None,
    smoke_report_path: Path | None = None,
) -> list[ProbeResult]:
    backend_env = _read_env_file(repo_root / "backend" / ".env")
    smoke_report_status, smoke_report_details = _smoke_report_status(smoke_report_path)
    smoke_passed = smoke_report_status == STATUS_PASSED
    has_provider_key, provider_keys = _has_env_value(
        (
            "OPENAI_API_KEY",
            "AZURE_OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "DASHSCOPE_API_KEY",
            "DEEPSEEK_API_KEY",
        ),
        env_file_values=backend_env,
    )
    has_agent_selector, selectors = _has_env_value(
        ("AI_SMOKE_AGENT_ID", "AI_SMOKE_AGENT_CODE"),
        env_file_values=backend_env,
    )
    if ai_smoke_agent_id is not None:
        has_agent_selector = True
        selectors.append("--ai-smoke-agent-id")
    if ai_smoke_agent_code:
        has_agent_selector = True
        selectors.append("--ai-smoke-agent-code")

    scenario_paths = [
        repo_root / "ops" / "ai-smoke" / "smoke-scenarios.md",
        repo_root
        / ".trellis"
        / "tasks"
        / "04-23-codex-llm-first-dialogue-replan"
        / "smoke-scenarios.md",
        repo_root
        / ".trellis"
        / "tasks"
        / "04-29-ai-dialogue-governance-reset"
        / "smoke-scenarios.md",
    ]
    valid_scenarios = [
        str(path) for path in scenario_paths if _scenario_ledger_valid(path)
    ]
    cli_file = repo_root / "backend" / "app" / "cli_commands" / "ai_commands.py"
    cli_text = (
        cli_file.read_text(encoding="utf-8", errors="replace")
        if cli_file.exists()
        else ""
    )
    cli_available = '@ai_cmd.command("smoke")' in cli_text

    credential_passed = has_provider_key or smoke_passed
    return [
        ProbeResult(
            area="ai_runtime",
            name="ai_runtime_smoke_cli",
            status=STATUS_PASSED if cli_available else STATUS_BLOCKED,
            summary="novusai ai smoke command is present"
            if cli_available
            else "novusai ai smoke command is missing",
            details={"path": str(cli_file)},
        ),
        ProbeResult(
            area="ai_runtime",
            name="ai_real_dialogue_smoke_scenarios",
            status=STATUS_PASSED if valid_scenarios else STATUS_BLOCKED,
            summary="AI smoke scenario ledger is present"
            if valid_scenarios
            else "AI smoke scenario ledger is missing required markers",
            details={
                "valid_paths": valid_scenarios,
                "expected_paths": [str(path) for path in scenario_paths],
                "required_markers": list(_SMOKE_SCENARIO_MARKERS),
            },
        ),
        ProbeResult(
            area="ai_runtime",
            name="ai_provider_credentials",
            status=STATUS_PASSED if credential_passed else STATUS_BLOCKED,
            summary="AI provider credential evidence is configured"
            if credential_passed
            else "no AI provider credential or passed smoke report is configured",
            details={
                "configured_variable_names": provider_keys,
                "passed_smoke_report_counts_as_credential_evidence": smoke_passed,
            },
        ),
        ProbeResult(
            area="ai_runtime",
            name="ai_smoke_agent_selector",
            status=STATUS_PASSED if has_agent_selector else STATUS_BLOCKED,
            summary="AI smoke agent selector is configured"
            if has_agent_selector
            else "AI smoke agent selector is not configured",
            details={"configured_variable_names": selectors},
        ),
        ProbeResult(
            area="ai_runtime",
            name="ai_real_dialogue_smoke_execution",
            status=smoke_report_status,
            summary="real-dialogue smoke report is archived and marked passed"
            if smoke_passed
            else "real-dialogue smoke report is archived and marked failed"
            if smoke_report_status == STATUS_FAILED
            else "real-dialogue smoke report is not archived as passed",
            details={
                "report": smoke_report_details,
                "run_command": (
                    "python -m app.cli ai smoke --agent-id <id> --json "
                    "> <archived smoke report>"
                ),
            },
        ),
    ]


def run_capacity_benchmark(
    api_base_url: str,
    *,
    concurrency: int,
    requests: int,
    timeout: float,
    p95_budget_ms: float,
    error_budget_ratio: float,
) -> ProbeResult:
    if requests <= 0:
        return ProbeResult(
            area="capacity",
            name="capacity_acceptance_benchmark",
            status=STATUS_BLOCKED,
            summary="capacity benchmark was not requested",
            details={
                "requests": requests,
                "concurrency": concurrency,
                "run_with": "--capacity-requests",
            },
        )

    base = _normalize_base_url(api_base_url)
    targets = [f"{base}/", f"{base}/ready", f"{base}/health", f"{base}/metrics"]
    latencies: list[float] = []
    errors: list[str] = []

    def hit_target(target_url: str) -> None:
        started_at = time.perf_counter()
        try:
            if target_url.endswith("/metrics"):
                result = _request_text(target_url, timeout=timeout)
            elif target_url.endswith("/health") or target_url.endswith("/ready"):
                result = _request_json(target_url, timeout=timeout)
            else:
                result = _request_status(target_url, timeout=timeout)
            if not 200 <= result["status_code"] < 400:
                errors.append(f"{target_url}:status={result['status_code']}")
        except Exception as exc:
            errors.append(f"{target_url}:{type(exc).__name__}: {exc}")
        finally:
            latencies.append(round((time.perf_counter() - started_at) * 1000, 2))

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        futures = [
            executor.submit(hit_target, targets[index % len(targets)])
            for index in range(requests)
        ]
        for future in as_completed(futures):
            future.result()
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    sorted_latencies = sorted(latencies)
    p95_index = max(
        0, min(len(sorted_latencies) - 1, int(len(sorted_latencies) * 0.95))
    )
    success_count = requests - len(errors)
    error_ratio = (len(errors) / requests) if requests else 1.0
    p95_ms = sorted_latencies[p95_index] if sorted_latencies else None
    passed = error_ratio <= error_budget_ratio and (
        p95_ms is not None and p95_ms <= p95_budget_ms
    )
    return ProbeResult(
        area="capacity",
        name="capacity_acceptance_benchmark",
        status=STATUS_PASSED if passed else STATUS_FAILED,
        summary="capacity benchmark passed"
        if passed
        else "capacity benchmark exceeded latency or error budgets",
        details={
            "targets": targets,
            "requests": requests,
            "concurrency": concurrency,
            "elapsed_ms": elapsed_ms,
            "success_count": success_count,
            "error_count": len(errors),
            "error_ratio": round(error_ratio, 4),
            "p95_ms": p95_ms,
            "p95_budget_ms": p95_budget_ms,
            "error_budget_ratio": error_budget_ratio,
            "errors": errors[:10],
            "scope": (
                "local benchmark across public app, readiness, health, and "
                "metrics endpoints; production signoff still needs target-env SLOs"
            ),
        },
    )


def run_load_smoke(
    api_base_url: str,
    *,
    concurrency: int,
    requests: int,
    timeout: float,
) -> ProbeResult:
    if requests <= 0:
        return ProbeResult(
            area="capacity",
            name="local_ready_load_smoke",
            status=STATUS_BLOCKED,
            summary="local ready endpoint load smoke was not requested",
            details={"requests": requests, "concurrency": concurrency},
        )

    ready_url = f"{_normalize_base_url(api_base_url)}/ready"
    latencies: list[float] = []
    errors: list[str] = []

    def hit_ready() -> None:
        started_at = time.perf_counter()
        try:
            result = _request_json(ready_url, timeout=timeout)
            if result["status_code"] != 200:
                errors.append(f"status={result['status_code']}")
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            latencies.append(round((time.perf_counter() - started_at) * 1000, 2))

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as executor:
        futures = [executor.submit(hit_ready) for _ in range(requests)]
        for future in as_completed(futures):
            future.result()
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    sorted_latencies = sorted(latencies)
    p95_index = max(
        0, min(len(sorted_latencies) - 1, int(len(sorted_latencies) * 0.95))
    )
    details = {
        "url": ready_url,
        "requests": requests,
        "concurrency": concurrency,
        "elapsed_ms": elapsed_ms,
        "success_count": requests - len(errors),
        "error_count": len(errors),
        "p95_ms": sorted_latencies[p95_index] if sorted_latencies else None,
        "max_ms": sorted_latencies[-1] if sorted_latencies else None,
        "errors": errors[:10],
        "scope": "local readiness smoke only, not a capacity benchmark",
    }
    return ProbeResult(
        area="capacity",
        name="local_ready_load_smoke",
        status=STATUS_PASSED if not errors else STATUS_FAILED,
        summary="local /ready load smoke passed"
        if not errors
        else "local /ready load smoke had errors",
        details=details,
    )


def run_postgres_backup_restore_drill(
    *,
    requested: bool,
    postgres_container: str,
    source_db: str,
    postgres_user: str,
    restore_db_prefix: str,
    timeout: float,
) -> ProbeResult:
    if not requested:
        return ProbeResult(
            area="backup_restore",
            name="postgres_backup_restore_drill",
            status=STATUS_BLOCKED,
            summary="PostgreSQL backup/restore drill was not requested",
            details={
                "container": postgres_container,
                "source_db": source_db,
                "run_with": "--run-backup-restore-drill",
            },
        )

    docker = shutil.which("docker")
    if not docker:
        return ProbeResult(
            area="backup_restore",
            name="postgres_backup_restore_drill",
            status=STATUS_BLOCKED,
            summary="Docker is missing for the disposable PostgreSQL drill",
            details={"container": postgres_container, "source_db": source_db},
        )

    try:
        safe_source_db = _safe_pg_identifier(source_db, label="source_db")
        safe_user = _safe_pg_identifier(postgres_user, label="postgres_user")
        safe_prefix = _safe_pg_identifier(restore_db_prefix, label="restore_db_prefix")
    except ValueError as exc:
        return ProbeResult(
            area="backup_restore",
            name="postgres_backup_restore_drill",
            status=STATUS_FAILED,
            summary="PostgreSQL drill arguments are not safe identifiers",
            details={"error": str(exc)},
        )

    restore_db = f"{safe_prefix}_{uuid.uuid4().hex[:12]}"
    dump_path = f"/var/lib/postgresql/data/{restore_db}.dump"
    steps: list[dict[str, Any]] = []
    cleanup_steps: list[dict[str, Any]] = []

    def docker_exec(*args: str) -> dict[str, Any]:
        return _run_command(
            [docker, "exec", postgres_container, *args],
            timeout=timeout,
        )

    planned_steps = [
        (
            "pg_isready_source",
            ("pg_isready", "-U", safe_user, "-d", safe_source_db),
        ),
        (
            "pg_dump_custom",
            (
                "pg_dump",
                "-U",
                safe_user,
                "-d",
                safe_source_db,
                "-Fc",
                "--no-owner",
                "--no-acl",
                "-f",
                dump_path,
            ),
        ),
        (
            "create_restore_db",
            (
                "psql",
                "-U",
                safe_user,
                "-d",
                "postgres",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                (
                    f"CREATE DATABASE {restore_db} TEMPLATE template0 "
                    "ENCODING 'UTF8' LC_COLLATE 'C' LC_CTYPE 'C';"
                ),
            ),
        ),
        (
            "pg_restore_custom",
            (
                "pg_restore",
                "-U",
                safe_user,
                "-d",
                restore_db,
                "--exit-on-error",
                "--single-transaction",
                "--no-owner",
                "--no-acl",
                dump_path,
            ),
        ),
        (
            "verify_source_alembic",
            (
                "psql",
                "-U",
                safe_user,
                "-d",
                safe_source_db,
                "-At",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                "SELECT string_agg(version_num, ',' ORDER BY version_num) "
                "FROM alembic_version;",
            ),
        ),
        (
            "verify_restore_alembic",
            (
                "psql",
                "-U",
                safe_user,
                "-d",
                restore_db,
                "-At",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                "SELECT string_agg(version_num, ',' ORDER BY version_num) "
                "FROM alembic_version;",
            ),
        ),
        (
            "verify_restored_public_tables",
            (
                "psql",
                "-U",
                safe_user,
                "-d",
                restore_db,
                "-At",
                "-v",
                "ON_ERROR_STOP=1",
                "-c",
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'public';",
            ),
        ),
    ]

    try:
        for step_name, step_args in planned_steps:
            result = docker_exec(*step_args)
            steps.append({"step": step_name, **result})
            if result.get("exit_code") != 0:
                break
    finally:
        cleanup_steps.append(
            {
                "step": "drop_restore_db",
                **docker_exec(
                    "psql",
                    "-U",
                    safe_user,
                    "-d",
                    "postgres",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-c",
                    f"DROP DATABASE IF EXISTS {restore_db} WITH (FORCE);",
                ),
            }
        )
        cleanup_steps.append(
            {"step": "remove_dump", **docker_exec("rm", "-f", dump_path)}
        )

    failed_step = next((step for step in steps if step.get("exit_code") != 0), None)
    cleanup_failed = next(
        (step for step in cleanup_steps if step.get("exit_code") != 0), None
    )
    step_map = {str(step.get("step")): step for step in steps}
    source_head = str(
        step_map.get("verify_source_alembic", {}).get("stdout_tail", "")
    ).strip()
    restore_head = str(
        step_map.get("verify_restore_alembic", {}).get("stdout_tail", "")
    ).strip()
    table_count_raw = str(
        step_map.get("verify_restored_public_tables", {}).get("stdout_tail", "")
    ).strip()
    try:
        restored_table_count = int(table_count_raw)
    except ValueError:
        restored_table_count = None
    validation_failed = failed_step is None and (
        not source_head or source_head != restore_head or not restored_table_count
    )
    passed = failed_step is None and cleanup_failed is None and not validation_failed

    return ProbeResult(
        area="backup_restore",
        name="postgres_backup_restore_drill",
        status=STATUS_PASSED if passed else STATUS_FAILED,
        summary="PostgreSQL backup/restore disposable drill passed"
        if passed
        else "PostgreSQL backup/restore disposable drill failed",
        details={
            "container": postgres_container,
            "source_db": safe_source_db,
            "restore_db": restore_db,
            "dump_path": dump_path,
            "source_alembic": source_head,
            "restore_alembic": restore_head,
            "restored_table_count": restored_table_count,
            "validation_failed": validation_failed,
            "failed_step": failed_step.get("step") if failed_step else None,
            "cleanup_failed_step": cleanup_failed.get("step")
            if cleanup_failed
            else None,
            "steps": steps,
            "cleanup_steps": cleanup_steps,
        },
    )


def run_security_scans(
    *, repo_root: Path, artifact_dir: Path, timeout: float
) -> list[ProbeResult]:
    results: list[ProbeResult] = []
    backend_dir = repo_root / "backend"
    frontend_dir = repo_root / "frontend"
    artifact_root = artifact_dir
    if not artifact_root.is_absolute():
        artifact_root = repo_root / artifact_root
    artifact_root.mkdir(parents=True, exist_ok=True)

    if _module_available("pip_audit"):
        pip_audit_artifact = artifact_root / "pip-audit.json"
        pip_audit = _run_command(
            [
                sys.executable,
                "-m",
                "pip_audit",
                "--local",
                "--skip-editable",
                "--progress-spinner",
                "off",
                "--format",
                "json",
                "--output",
                str(pip_audit_artifact),
            ],
            cwd=backend_dir,
            timeout=timeout,
        )
        results.append(
            _command_probe_result(
                area="security",
                name="python_dependency_audit_scan",
                command=pip_audit,
                summary_passed="pip-audit passed",
                summary_failed="pip-audit found vulnerabilities",
                summary_blocked="pip-audit could not reach audit data",
                block_markers=_NETWORK_BLOCK_MARKERS,
                extra_details={"artifact": str(pip_audit_artifact)},
            )
        )
    else:
        results.append(
            ProbeResult(
                area="security",
                name="python_dependency_audit_scan",
                status=STATUS_BLOCKED,
                summary="pip-audit module is missing",
                details={},
            )
        )

    if _module_available("bandit"):
        bandit_artifact = artifact_root / "bandit.json"
        bandit = _run_command(
            [
                sys.executable,
                "-m",
                "bandit",
                "-r",
                "app",
                "scripts",
                "-x",
                ".venv,migrations,plugins/.backups,tests",
                "-ll",
                "-f",
                "json",
                "-o",
                str(bandit_artifact),
            ],
            cwd=backend_dir,
            timeout=timeout,
        )
        results.append(
            _command_probe_result(
                area="security",
                name="python_sast_scan",
                command=bandit,
                summary_passed="bandit passed",
                summary_failed="bandit found medium/high issues",
                summary_blocked="bandit command could not run",
                extra_details={"artifact": str(bandit_artifact)},
            )
        )
    else:
        results.append(
            ProbeResult(
                area="security",
                name="python_sast_scan",
                status=STATUS_BLOCKED,
                summary="bandit module is missing",
                details={},
            )
        )

    pnpm_artifact = artifact_root / "pnpm-audit-prod.json"
    pnpm_cmd = shutil.which("pnpm") or "pnpm"
    pnpm = _run_command(
        [
            pnpm_cmd,
            "audit",
            "--prod",
            "--audit-level",
            "high",
            "--registry",
            "https://registry.npmjs.org",
            "--json",
        ],
        cwd=frontend_dir,
        stdout_path=pnpm_artifact,
        timeout=timeout,
    )
    results.append(
        _command_probe_result(
            area="security",
            name="frontend_dependency_audit_scan",
            command=pnpm,
            summary_passed="pnpm audit passed",
            summary_failed="pnpm audit found high/critical vulnerabilities",
            summary_blocked="pnpm audit registry or command is unavailable",
            block_markers=_NETWORK_BLOCK_MARKERS,
            extra_details={"artifact": str(pnpm_artifact)},
        )
    )
    return results


def run_dast_baseline(
    *,
    target_url: str,
    repo_root: Path,
    artifact_dir: Path,
    dast_image: str,
    allow_pull: bool,
    timeout: float,
) -> ProbeResult:
    artifact_root = artifact_dir
    if not artifact_root.is_absolute():
        artifact_root = repo_root / artifact_root
    artifact_root.mkdir(parents=True, exist_ok=True)

    native = shutil.which("zap-baseline.py")
    if native:
        command = [
            native,
            "-t",
            target_url,
            "-I",
            "-m",
            "1",
            "-J",
            "zap-backend-baseline.json",
            "-r",
            "zap-backend-baseline.html",
        ]
        result = _run_command(command, cwd=artifact_root, timeout=timeout)
    else:
        image = _docker_image_available(dast_image, timeout=timeout)
        docker = image["docker"]
        if not docker:
            return ProbeResult(
                area="security",
                name="dast_baseline_scan",
                status=STATUS_BLOCKED,
                summary="Docker is missing for OWASP ZAP baseline",
                details={"target_url": target_url, "image": dast_image},
            )
        if not image["available"]:
            if not allow_pull:
                return ProbeResult(
                    area="security",
                    name="dast_baseline_scan",
                    status=STATUS_BLOCKED,
                    summary="OWASP ZAP Docker image is not local",
                    details={
                        "target_url": target_url,
                        "image": dast_image,
                        "run_with": "--allow-dast-pull",
                        "image_check": image["check"],
                    },
                )
            pull = _run_command([docker, "pull", dast_image], timeout=timeout)
            if pull.get("exit_code") != 0:
                return ProbeResult(
                    area="security",
                    name="dast_baseline_scan",
                    status=STATUS_BLOCKED,
                    summary="OWASP ZAP Docker image could not be pulled",
                    details={
                        "target_url": target_url,
                        "image": dast_image,
                        "pull": pull,
                    },
                )
        command = [
            docker,
            "run",
            "--rm",
            "--pull=never",
            "--add-host",
            "host.docker.internal:host-gateway",
            "-v",
            f"{artifact_root.resolve()}:/zap/wrk",
            dast_image,
            "zap-baseline.py",
            "-t",
            _docker_visible_url(target_url),
            "-I",
            "-m",
            "1",
            "-J",
            "zap-backend-baseline.json",
            "-r",
            "zap-backend-baseline.html",
        ]
        result = _run_command(command, timeout=timeout)

    output = (
        str(result.get("stdout_tail") or "")
        + "\n"
        + str(result.get("stderr_tail") or "")
    )
    fail_match = re.search(r"FAIL-NEW:\s*(\d+)", output)
    fail_new = int(fail_match.group(1)) if fail_match else None
    status_result = _command_probe_result(
        area="security",
        name="dast_baseline_scan",
        command=result,
        summary_passed="OWASP ZAP baseline passed",
        summary_failed="OWASP ZAP baseline reported failures",
        summary_blocked="OWASP ZAP baseline could not start",
        extra_details={
            "target_url": target_url,
            "docker_target_url": _docker_visible_url(target_url),
            "artifact_dir": str(artifact_root),
            "report_files": [
                str(artifact_root / "zap-backend-baseline.json"),
                str(artifact_root / "zap-backend-baseline.html"),
            ],
            "fail_new": fail_new,
        },
    )
    if status_result.status == STATUS_PASSED and fail_new not in {0, None}:
        return ProbeResult(
            area=status_result.area,
            name=status_result.name,
            status=STATUS_FAILED,
            summary="OWASP ZAP baseline reported FAIL alerts",
            details=status_result.details,
        )
    return status_result


def build_report(
    *,
    api_base_url: str,
    frontend_base_url: str | None,
    load_smoke_concurrency: int,
    load_smoke_requests: int,
    capacity_concurrency: int,
    capacity_requests: int,
    capacity_p95_budget_ms: float,
    capacity_error_budget_ratio: float,
    repo_root: Path,
    timeout: float,
    postgres_container: str,
    postgres_db: str,
    postgres_user: str,
    postgres_restore_prefix: str,
    run_backup_restore_drill: bool,
    run_security_scans_enabled: bool,
    run_dast_baseline_scan: bool,
    dast_target_url: str | None,
    dast_image: str,
    allow_dast_pull: bool,
    artifact_dir: Path,
    ai_smoke_agent_id: int | None,
    ai_smoke_agent_code: str | None,
    ai_smoke_report: Path | None,
) -> dict[str, Any]:
    results: list[ProbeResult] = []
    results.extend(probe_api(api_base_url, timeout=timeout))
    results.append(probe_frontend(frontend_base_url, timeout=timeout))
    results.extend(
        probe_external_tooling(
            postgres_container=postgres_container,
            dast_image=dast_image,
            timeout=timeout,
        )
    )
    results.extend(
        probe_ai_smoke_readiness(
            repo_root,
            ai_smoke_agent_id=ai_smoke_agent_id,
            ai_smoke_agent_code=ai_smoke_agent_code,
            smoke_report_path=ai_smoke_report,
        )
    )
    results.append(
        run_load_smoke(
            api_base_url,
            concurrency=load_smoke_concurrency,
            requests=load_smoke_requests,
            timeout=timeout,
        )
    )
    results.append(
        run_capacity_benchmark(
            api_base_url,
            concurrency=capacity_concurrency,
            requests=capacity_requests,
            timeout=timeout,
            p95_budget_ms=capacity_p95_budget_ms,
            error_budget_ratio=capacity_error_budget_ratio,
        )
    )
    results.append(
        run_postgres_backup_restore_drill(
            requested=run_backup_restore_drill,
            postgres_container=postgres_container,
            source_db=postgres_db,
            postgres_user=postgres_user,
            restore_db_prefix=postgres_restore_prefix,
            timeout=timeout * 24,
        )
    )
    if run_security_scans_enabled:
        results.extend(
            run_security_scans(
                repo_root=repo_root,
                artifact_dir=artifact_dir,
                timeout=timeout * 24,
            )
        )
    else:
        results.append(
            ProbeResult(
                area="security",
                name="security_scan_execution",
                status=STATUS_BLOCKED,
                summary="security scans were not requested",
                details={"run_with": "--run-security-scans"},
            )
        )
    if run_dast_baseline_scan:
        results.append(
            run_dast_baseline(
                target_url=dast_target_url or api_base_url,
                repo_root=repo_root,
                artifact_dir=artifact_dir,
                dast_image=dast_image,
                allow_pull=allow_dast_pull,
                timeout=timeout * 120,
            )
        )
    else:
        results.append(
            ProbeResult(
                area="security",
                name="dast_baseline_scan",
                status=STATUS_BLOCKED,
                summary="OWASP ZAP baseline was not requested",
                details={"run_with": "--run-dast-baseline"},
            )
        )

    summary = {
        STATUS_PASSED: sum(1 for result in results if result.status == STATUS_PASSED),
        STATUS_BLOCKED: sum(1 for result in results if result.status == STATUS_BLOCKED),
        STATUS_FAILED: sum(1 for result in results if result.status == STATUS_FAILED),
    }
    return {
        "overall_status": STATUS_FAILED
        if summary[STATUS_FAILED]
        else STATUS_BLOCKED
        if summary[STATUS_BLOCKED]
        else STATUS_PASSED,
        "summary": summary,
        "results": [asdict(result) for result in results],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Production acceptance probe: readiness, monitoring, capacity, "
            "backup/restore, security, DAST, and AI smoke evidence."
        )
    )
    parser.add_argument("--api-base-url", default="http://localhost:8000")
    parser.add_argument("--frontend-base-url", default="http://localhost:5666")
    parser.add_argument("--load-smoke-requests", type=int, default=0)
    parser.add_argument("--load-smoke-concurrency", type=int, default=8)
    parser.add_argument("--capacity-requests", type=int, default=0)
    parser.add_argument("--capacity-concurrency", type=int, default=16)
    parser.add_argument("--capacity-p95-budget-ms", type=float, default=1000.0)
    parser.add_argument("--capacity-error-budget-ratio", type=float, default=0.0)
    parser.add_argument("--postgres-container", default=DEFAULT_POSTGRES_CONTAINER)
    parser.add_argument("--postgres-db", default=DEFAULT_POSTGRES_DB)
    parser.add_argument("--postgres-user", default=DEFAULT_POSTGRES_USER)
    parser.add_argument("--postgres-restore-prefix", default="novusai_restore_drill")
    parser.add_argument("--run-backup-restore-drill", action="store_true")
    parser.add_argument("--run-security-scans", action="store_true")
    parser.add_argument("--run-dast-baseline", action="store_true")
    parser.add_argument("--dast-target-url", default=None)
    parser.add_argument("--dast-image", default=DEFAULT_DAST_IMAGE)
    parser.add_argument("--allow-dast-pull", action="store_true")
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--ai-smoke-agent-id", type=int, default=None)
    parser.add_argument("--ai-smoke-agent-code", default=None)
    parser.add_argument("--ai-smoke-report", default=None)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Exit 0 when only blocked gates remain.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="Repository root for acceptance artifact and AI smoke checks.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = build_report(
        api_base_url=args.api_base_url,
        frontend_base_url=args.frontend_base_url,
        load_smoke_concurrency=max(1, args.load_smoke_concurrency),
        load_smoke_requests=max(0, args.load_smoke_requests),
        capacity_concurrency=max(1, args.capacity_concurrency),
        capacity_requests=max(0, args.capacity_requests),
        capacity_p95_budget_ms=max(1.0, args.capacity_p95_budget_ms),
        capacity_error_budget_ratio=max(0.0, args.capacity_error_budget_ratio),
        repo_root=Path(args.repo_root),
        timeout=max(0.5, args.timeout),
        postgres_container=args.postgres_container,
        postgres_db=args.postgres_db,
        postgres_user=args.postgres_user,
        postgres_restore_prefix=args.postgres_restore_prefix,
        run_backup_restore_drill=args.run_backup_restore_drill,
        run_security_scans_enabled=args.run_security_scans,
        run_dast_baseline_scan=args.run_dast_baseline,
        dast_target_url=args.dast_target_url,
        dast_image=args.dast_image,
        allow_dast_pull=args.allow_dast_pull,
        artifact_dir=Path(args.artifact_dir),
        ai_smoke_agent_id=args.ai_smoke_agent_id,
        ai_smoke_agent_code=args.ai_smoke_agent_code,
        ai_smoke_report=Path(args.ai_smoke_report) if args.ai_smoke_report else None,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["overall_status"] == STATUS_FAILED:
        return 2
    if report["overall_status"] == STATUS_BLOCKED and not args.allow_blocked:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
