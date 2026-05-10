"""中文: 生产验收探针，输出可机器读取的通过/阻塞/失败门禁。

EN: Production acceptance probe that emits machine-readable pass/block/fail
gates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
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
from collections.abc import Mapping
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
AI_REAL_DIALOGUE_SMOKE_SCHEMA_VERSION = "ai-real-dialogue-smoke/v1"
AI_REAL_DIALOGUE_SMOKE_REPORT_TYPE = "ai_real_dialogue_smoke"
AI_REAL_DIALOGUE_SMOKE_EXECUTION_KIND = "real_dialogue"
AI_REAL_DIALOGUE_SMOKE_EXIT_CODES = {
    STATUS_PASSED: 0,
    STATUS_FAILED: 2,
    STATUS_BLOCKED: 3,
}
_NETWORK_BLOCK_MARKERS = (
    "ERR_PNPM_AUDIT_ENDPOINT_NOT_EXISTS",
    "CERTIFICATE_VERIFY_FAILED",
    "Connection aborted",
    "Connection reset by peer",
    "ConnectionError",
    "ECONNRESET",
    "ETIMEDOUT",
    "ENOTFOUND",
    "Failed to establish a new connection",
    "HTTP Error 502",
    "HTTP Error 503",
    "HTTP Error 504",
    "HTTPSConnectionPool",
    "Max retries exceeded",
    "Name or service not known",
    "NewConnectionError",
    "ProxyError",
    "Read timed out",
    "ReadTimeout",
    "Remote end closed connection",
    "SSLError",
    "TLSV1_ALERT",
    "UNEXPECTED_EOF",
    "Could not fetch URL",
    "ServiceUnavailable",
    "Temporary failure",
    "temporary failure",
)
_DAST_BLOCK_MARKERS = (
    *_NETWORK_BLOCK_MARKERS,
    "Connection refused",
    "Failed to access",
    "Failed to connect",
    "No route to host",
    "Target URL is not reachable",
    "TimeoutError",
    "target URL is not reachable",
    "Unable to access",
    "connection refused",
    "timed out",
)
_UNAVAILABLE_HTTP_STATUS_CODES = {502, 503, 504}
_CAPACITY_BLOCK_MARKERS = (
    *_DAST_BLOCK_MARKERS,
    "All connection attempts failed",
    "ConnectionError",
    "ConnectionRefusedError",
    "ECONNREFUSED",
    "NameResolutionError",
    "No connection could be made",
    "connection refused",
)
_CAPACITY_PLAN_DIR = Path("ops") / "production-acceptance" / "capacity"
_K6_CAPACITY_SCRIPT = _CAPACITY_PLAN_DIR / "k6_ready.js"
_LOCUST_CAPACITY_FILE = _CAPACITY_PLAN_DIR / "locust_ready.py"
_PIP_AUDIT_MAX_ATTEMPTS = 2


@dataclass(frozen=True, slots=True)
class ProbeResult:
    area: str
    name: str
    status: str
    summary: str
    details: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SmokeScenarioLedger:
    path: str
    sha256: str | None
    scenario_ids: list[str]
    required_scenario_ids: list[str]
    valid: bool
    missing_markers: list[str]
    duplicate_scenario_ids: list[str]


@dataclass(frozen=True, slots=True)
class CapacityBenchmarkMetrics:
    runner: str
    request_count: int
    failure_count: int
    error_ratio: float
    p95_ms: float
    max_ms: float | None = None
    avg_ms: float | None = None
    median_ms: float | None = None
    requests_per_second: float | None = None
    check_pass_count: int | None = None
    check_failure_count: int | None = None
    artifact_path: str | None = None
    failure_artifact_path: str | None = None


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


def _configured_env_value(name: str, *, env_file_values: dict[str, str]) -> str:
    return (os.environ.get(name) or env_file_values.get(name) or "").strip()


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


def _subprocess_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    stdout_path: Path | None = None,
    stderr_path: Path | None = None,
    timeout: float,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    process_env = None
    if env is not None:
        process_env = os.environ.copy()
        process_env.update(env)
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            env=process_env,
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
        stdout = _subprocess_text(exc.stdout)
        stderr = _subprocess_text(exc.stderr)
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
    if command.get("exit_code") == 0:
        status = STATUS_PASSED
        summary = summary_passed
    elif command.get("error") or _command_has_markers(command, block_markers):
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
        and (
            exc.code in _UNAVAILABLE_HTTP_STATUS_CODES
            or (exc.code == 404 and missing_is_blocked)
        )
    ) or isinstance(exc, urllib.error.URLError):
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


def _capacity_runner_state() -> dict[str, Any]:
    k6_path = shutil.which("k6")
    locust_binary = shutil.which("locust")
    locust_module = _module_available("locust")
    return {
        "available": bool(k6_path or locust_binary or locust_module),
        "required_any": ["k6", "locust"],
        "tools": {
            "k6": k6_path,
            "locust_binary": locust_binary,
            "locust_module": locust_module,
        },
    }


def _resolve_artifact_root(repo_root: Path, artifact_dir: Path) -> Path:
    artifact_root = artifact_dir
    if not artifact_root.is_absolute():
        artifact_root = repo_root / artifact_root
    artifact_root.mkdir(parents=True, exist_ok=True)
    return artifact_root


def _command_combined_output(command: Mapping[str, Any]) -> str:
    return "\n".join(
        str(command.get(key) or "") for key in ("stdout_tail", "stderr_tail", "error")
    )


def _command_has_markers(command: Mapping[str, Any], markers: tuple[str, ...]) -> bool:
    output = _command_combined_output(command).lower()
    return any(marker.lower() in output for marker in markers)


def _capacity_target_unavailable(text: str) -> bool:
    lowered = text.lower()
    return any(marker.lower() in lowered for marker in _CAPACITY_BLOCK_MARKERS)


def _artifact_prefix(artifact_root: Path, runner: str) -> Path:
    capacity_root = artifact_root / "capacity"
    capacity_root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    return capacity_root / f"{runner}-{stamp}-{uuid.uuid4().hex[:8]}"


def _current_repo_state(repo_root: Path) -> dict[str, Any]:
    head = _run_command(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        timeout=5,
    )
    status = _run_command(
        ["git", "status", "--porcelain"],
        cwd=repo_root,
        timeout=5,
    )
    if head.get("exit_code") != 0 or status.get("exit_code") != 0:
        return {
            "available": False,
            "head_command": head,
            "status_command": status,
        }
    commits = str(head.get("stdout_tail") or "").strip().splitlines()
    return {
        "available": bool(commits),
        "commit": commits[-1] if commits else None,
        "dirty": bool(str(status.get("stdout_tail") or "").strip()),
        "head_command": head,
        "status_command": status,
    }


def _is_unavailable_probe_error(message: str) -> bool:
    return (
        "HTTPError: HTTP Error 502" in message
        or "HTTPError: HTTP Error 503" in message
        or "HTTPError: HTTP Error 504" in message
        or "URLError" in message
        or "ConnectionRefusedError" in message
        or "TimeoutError" in message
        or "timed out" in message
    )


def _is_postgres_drill_unavailable(step: Mapping[str, Any] | None) -> bool:
    if not step:
        return False
    text = (
        str(step.get("stdout_tail") or "") + "\n" + str(step.get("stderr_tail") or "")
    ).lower()
    unavailable_markers = (
        "no such container",
        "container is not running",
        "connection refused",
        "could not connect",
        "does not exist",
        "role",
        "fatal:",
        "is the server running",
        "pg_isready:",
    )
    return any(marker in text for marker in unavailable_markers)


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
    native = _tool_map(("zap-baseline.py",))
    native_present = [name for name, path in native.items() if path]
    image = _docker_image_available(dast_image, timeout=timeout)
    passed = bool(native_present or image["available"])
    return ProbeResult(
        area="security",
        name="dast_tooling",
        status=STATUS_PASSED if passed else STATUS_BLOCKED,
        summary="OWASP ZAP tooling is available"
        if passed
        else "OWASP ZAP baseline command or local Docker image is missing",
        details={
            "native_required_any": ["zap-baseline.py"],
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
    capacity_runner = _capacity_runner_state()

    return [
        ProbeResult(
            area="capacity",
            name="capacity_benchmark_harness",
            status=(STATUS_PASSED if capacity_runner["available"] else STATUS_BLOCKED),
            summary=(
                "formal capacity benchmark runner is available"
                if capacity_runner["available"]
                else "formal capacity runner is missing"
            ),
            details={
                **capacity_runner,
                "scope": (
                    "capacity acceptance requires k6, Locust, or an approved "
                    "equivalent runner; local /ready smoke is reported separately"
                ),
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


def _parse_smoke_scenario_ledger(path: Path) -> SmokeScenarioLedger:
    if not path.exists():
        return SmokeScenarioLedger(
            path=str(path),
            sha256=None,
            scenario_ids=[],
            required_scenario_ids=[],
            valid=False,
            missing_markers=list(_SMOKE_SCENARIO_MARKERS),
            duplicate_scenario_ids=[],
        )
    text = path.read_text(encoding="utf-8", errors="replace")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    missing_markers = [
        marker for marker in _SMOKE_SCENARIO_MARKERS if marker not in text
    ]
    scenario_ids = [
        match.group(1).strip().strip("`").strip()
        for match in re.finditer(r"scenario_id\s*:\s*`?([^`\n]+)`?", text)
        if match.group(1).strip().strip("`").strip()
    ]
    duplicate_ids = sorted(
        {
            scenario_id
            for scenario_id in scenario_ids
            if scenario_ids.count(scenario_id) > 1
        }
    )
    return SmokeScenarioLedger(
        path=str(path),
        sha256=digest,
        scenario_ids=scenario_ids,
        required_scenario_ids=list(scenario_ids),
        valid=bool(scenario_ids) and not missing_markers and not duplicate_ids,
        missing_markers=missing_markers,
        duplicate_scenario_ids=duplicate_ids,
    )


def _scenario_ledger_valid(path: Path) -> bool:
    return _parse_smoke_scenario_ledger(path).valid


def _extract_smoke_report_payload(payload: Any) -> tuple[Any, str]:
    if not isinstance(payload, dict):
        return payload, "unknown"
    if payload.get("schema_version") == AI_REAL_DIALOGUE_SMOKE_SCHEMA_VERSION:
        return payload, "direct"
    data = payload.get("data")
    if isinstance(data, dict):
        result = data.get("result")
        if isinstance(result, dict):
            return result, "cli_envelope"
    return payload, "unknown"


def _report_status_text(payload: dict[str, Any]) -> str:
    return str(payload.get("overall_status") or payload.get("status") or "").lower()


def _real_dialogue_smoke_expected_exit_code(status: str) -> int | None:
    return AI_REAL_DIALOGUE_SMOKE_EXIT_CODES.get(str(status or "").lower())


def _smoke_report_status(
    path: Path | None,
    *,
    ledger: SmokeScenarioLedger | None = None,
    expected_agent_id: int | None = None,
    expected_agent_code: str | None = None,
    repo_root: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    if path is None:
        return STATUS_BLOCKED, {"path": None}
    if not path.exists():
        return STATUS_BLOCKED, {"path": str(path), "exists": False}

    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        raw_payload: Any = json.loads(text)
    except json.JSONDecodeError:
        return STATUS_BLOCKED, {
            "path": str(path),
            "format": "text",
            "validation_errors": ["report_must_be_strict_json"],
        }
    payload, payload_format = _extract_smoke_report_payload(raw_payload)
    if not isinstance(payload, dict):
        return STATUS_BLOCKED, {
            "path": str(path),
            "format": payload_format,
            "validation_errors": ["report_payload_must_be_object"],
        }

    raw_status = _report_status_text(payload)
    validation_errors: list[str] = []
    blocking_errors: list[str] = []
    failure_errors: list[str] = []

    expected_fields = {
        "schema_version": AI_REAL_DIALOGUE_SMOKE_SCHEMA_VERSION,
        "report_type": AI_REAL_DIALOGUE_SMOKE_REPORT_TYPE,
        "execution_kind": AI_REAL_DIALOGUE_SMOKE_EXECUTION_KIND,
    }
    for field_name, expected_value in expected_fields.items():
        if payload.get(field_name) != expected_value:
            validation_errors.append(f"{field_name}_invalid_or_missing")

    command = payload.get("command")
    if not isinstance(command, dict):
        blocking_errors.append("command_missing")
    else:
        expected_exit_code = _real_dialogue_smoke_expected_exit_code(raw_status)
        if expected_exit_code is None:
            blocking_errors.append("command_status_exit_contract_unknown_status")
        elif command.get("exit_code") != expected_exit_code:
            error_bucket = (
                failure_errors if raw_status == STATUS_PASSED else blocking_errors
            )
            error_bucket.append("command_exit_code_status_mismatch")
        if "real-dialogue-smoke" not in {
            str(part) for part in command.get("argv", []) if part is not None
        }:
            blocking_errors.append("command_argv_not_real_dialogue_smoke")

    provider = payload.get("provider")
    provider_evidence_passed = False
    live_provider_call_count: int | None = None
    provider_call_log_by_id: dict[str, dict[str, Any]] = {}
    provider_summary_duplicate_log_ids: list[str] = []
    if not isinstance(provider, dict):
        blocking_errors.append("provider_evidence_missing")
    else:
        mocked_llm = provider.get("mocked_llm")
        replay = provider.get("replay")
        if mocked_llm is True:
            failure_errors.append("provider_mocked_llm_forbidden")
        elif mocked_llm is not False:
            blocking_errors.append("provider_mocked_llm_flag_missing")
        if replay is True:
            failure_errors.append("provider_replay_forbidden")
        elif replay is not False:
            blocking_errors.append("provider_replay_flag_missing")

        call_count = provider.get("live_provider_call_count")
        if isinstance(call_count, bool) or not isinstance(call_count, int):
            blocking_errors.append("provider_live_call_count_invalid")
        elif call_count <= 0:
            blocking_errors.append("provider_live_call_count_missing")
        else:
            live_provider_call_count = call_count
        provider_call_logs = provider.get("call_logs")
        if not isinstance(provider_call_logs, list) or not provider_call_logs:
            blocking_errors.append("provider_call_logs_missing")
        else:
            provider_summary_log_ids: list[str] = []
            for call_log in provider_call_logs:
                if not isinstance(call_log, dict):
                    blocking_errors.append("provider_call_log_summary_must_be_object")
                    continue
                log_id = str(call_log.get("id") or "")
                if not log_id:
                    blocking_errors.append("provider_call_log_summary_id_missing")
                    continue
                provider_summary_log_ids.append(log_id)
                provider_call_log_by_id[log_id] = call_log
                if call_log.get("request_type") != "chat":
                    blocking_errors.append("provider_call_log_request_type_invalid")
                if call_log.get("call_type") != "main_chat":
                    blocking_errors.append("provider_call_log_call_type_invalid")
                if str(call_log.get("status") or "").lower() not in {
                    "success",
                    STATUS_PASSED,
                }:
                    blocking_errors.append("provider_call_log_status_not_success")
            provider_summary_duplicate_log_ids = sorted(
                {
                    log_id
                    for log_id in provider_summary_log_ids
                    if provider_summary_log_ids.count(log_id) > 1
                }
            )
            if provider_summary_duplicate_log_ids:
                blocking_errors.append("provider_call_log_summary_id_not_unique")
            if live_provider_call_count is not None and live_provider_call_count != len(
                provider_summary_log_ids
            ):
                blocking_errors.append("provider_live_call_count_mismatch")

    report_ledger = payload.get("ledger")
    if ledger is None or not ledger.valid:
        blocking_errors.append("ledger_validation_missing")
    if not isinstance(report_ledger, dict):
        blocking_errors.append("ledger_evidence_missing")
    elif ledger and ledger.valid and report_ledger.get("sha256") != ledger.sha256:
        blocking_errors.append("ledger_sha256_mismatch")

    repo_details: dict[str, Any] = {"required": repo_root is not None}
    if repo_root is not None:
        current_repo = _current_repo_state(repo_root)
        report_repo = payload.get("repo")
        repo_details.update({"current": current_repo, "report": report_repo})
        if not current_repo.get("available"):
            blocking_errors.append("repo_current_state_unavailable")
        elif current_repo.get("dirty") is True:
            blocking_errors.append("repo_current_worktree_dirty")
        if not isinstance(report_repo, dict):
            blocking_errors.append("repo_evidence_missing")
        else:
            report_commit = str(report_repo.get("commit") or "").strip()
            if not report_commit:
                blocking_errors.append("repo_commit_missing")
            elif current_repo.get("available") and report_commit != str(
                current_repo.get("commit") or ""
            ):
                blocking_errors.append("repo_commit_mismatch")
            if report_repo.get("dirty") is not False:
                blocking_errors.append("repo_report_dirty_worktree")

    scenario_results = payload.get("scenario_results")
    if not isinstance(scenario_results, list) or not scenario_results:
        blocking_errors.append("scenario_results_missing")
        scenario_results = []

    result_by_id = {
        str(item.get("scenario_id") or ""): item
        for item in scenario_results
        if isinstance(item, dict)
    }
    required_ids = ledger.required_scenario_ids if ledger and ledger.valid else []
    missing_required = [
        scenario_id for scenario_id in required_ids if scenario_id not in result_by_id
    ]
    if missing_required:
        blocking_errors.append("scenario_coverage_missing")

    failed_must_pass: list[str] = []
    blocked_must_pass: list[str] = []
    invalid_passed_results: list[str] = []
    must_pass_provider_log_ids: list[str] = []
    must_pass_provider_links: list[tuple[str, str, str]] = []
    required_id_set = set(required_ids)
    for item in scenario_results:
        if not isinstance(item, dict):
            blocking_errors.append("scenario_result_must_be_object")
            continue
        priority = str(item.get("priority") or "").lower()
        scenario_id = str(item.get("scenario_id") or "unknown")
        ledger_required = scenario_id in required_id_set
        must_pass = (
            ledger_required or bool(item.get("must_pass")) or priority == "must-pass"
        )
        item_status = str(item.get("status") or "").lower()
        if must_pass and item_status == STATUS_FAILED:
            failed_must_pass.append(scenario_id)
        elif must_pass and item_status != STATUS_PASSED:
            blocked_must_pass.append(scenario_id)
        if item_status == STATUS_PASSED and must_pass:
            checks = item.get("observable_checks")
            lacks_dialogue_ids = not item.get("conversation_id") or not item.get(
                "provider_call_log_id"
            )
            lacks_observable_checks = not isinstance(checks, dict) or not all(
                [
                    bool(checks.get("assistant_text_non_empty")),
                    bool(checks.get("provider_call_log_present")),
                    bool(checks.get("provider_call_succeeded")),
                    not bool(
                        checks.get("retired_current_page_or_online_search_exposed")
                    ),
                ]
            )
            if lacks_dialogue_ids or lacks_observable_checks:
                invalid_passed_results.append(scenario_id)
            else:
                log_id = str(item["provider_call_log_id"])
                conversation_id = str(item["conversation_id"])
                must_pass_provider_log_ids.append(log_id)
                must_pass_provider_links.append((scenario_id, log_id, conversation_id))
    if failed_must_pass:
        failure_errors.append("must_pass_scenario_failed")
    if blocked_must_pass:
        blocking_errors.append("must_pass_scenario_blocked")
    if invalid_passed_results:
        blocking_errors.append("passed_scenario_lacks_real_dialogue_evidence")
    duplicate_log_ids = sorted(
        {
            log_id
            for log_id in must_pass_provider_log_ids
            if must_pass_provider_log_ids.count(log_id) > 1
        }
    )
    if duplicate_log_ids:
        blocking_errors.append("provider_call_log_id_not_unique")
    if (
        live_provider_call_count is not None
        and must_pass_provider_log_ids
        and live_provider_call_count < len(set(must_pass_provider_log_ids))
    ):
        blocking_errors.append("provider_live_call_count_mismatch")
    missing_provider_log_summaries = sorted(
        {
            log_id
            for log_id in must_pass_provider_log_ids
            if log_id not in provider_call_log_by_id
        }
    )
    if missing_provider_log_summaries:
        blocking_errors.append("provider_call_log_summary_missing")
    provider_log_conversation_mismatches = sorted(
        {
            scenario_id
            for scenario_id, log_id, conversation_id in must_pass_provider_links
            if log_id in provider_call_log_by_id
            and str(provider_call_log_by_id[log_id].get("conversation_id") or "")
            != conversation_id
        }
    )
    if provider_log_conversation_mismatches:
        blocking_errors.append("provider_call_log_conversation_mismatch")
    provider_log_status_mismatches = sorted(
        {
            scenario_id
            for scenario_id, log_id, _conversation_id in must_pass_provider_links
            if log_id in provider_call_log_by_id
            and str(provider_call_log_by_id[log_id].get("status") or "").lower()
            not in {"success", STATUS_PASSED}
        }
    )
    if provider_log_status_mismatches:
        blocking_errors.append("provider_call_log_status_mismatch")

    agent = payload.get("agent")
    if not isinstance(agent, dict):
        blocking_errors.append("agent_evidence_missing")
    else:
        if expected_agent_id is not None:
            resolved_agent_id = agent.get("resolved_agent_id")
            try:
                resolved_agent_id_int = int(resolved_agent_id)
            except (TypeError, ValueError):
                resolved_agent_id_int = None
            if resolved_agent_id_int != expected_agent_id:
                failure_errors.append("agent_id_mismatch")
        normalized_expected_code = str(expected_agent_code or "").strip()
        if normalized_expected_code:
            report_selector = str(agent.get("selector_value") or "").strip()
            if report_selector != normalized_expected_code:
                failure_errors.append("agent_code_mismatch")

    provider_evidence_passed = live_provider_call_count is not None

    if validation_errors:
        resolved_status = STATUS_BLOCKED
    elif failure_errors or raw_status == STATUS_FAILED:
        resolved_status = STATUS_FAILED
    elif blocking_errors or raw_status == STATUS_BLOCKED:
        resolved_status = STATUS_BLOCKED
    elif raw_status == STATUS_PASSED:
        resolved_status = STATUS_PASSED
    else:
        resolved_status = STATUS_BLOCKED

    return resolved_status, {
        "path": str(path),
        "format": payload_format,
        "status": raw_status,
        "validation_errors": validation_errors,
        "blocking_errors": blocking_errors,
        "failure_errors": failure_errors,
        "failed_must_pass_scenarios": failed_must_pass,
        "blocked_must_pass_scenarios": blocked_must_pass,
        "invalid_passed_scenarios": invalid_passed_results,
        "missing_required_scenarios": missing_required,
        "duplicate_provider_call_log_ids": duplicate_log_ids,
        "duplicate_provider_summary_log_ids": provider_summary_duplicate_log_ids,
        "missing_provider_log_summaries": missing_provider_log_summaries,
        "provider_log_conversation_mismatches": provider_log_conversation_mismatches,
        "provider_log_status_mismatches": provider_log_status_mismatches,
        "provider_evidence_passed": provider_evidence_passed
        and not validation_errors
        and not failure_errors
        and not blocking_errors,
        "repo": repo_details,
        "schema_version": payload.get("schema_version"),
        "report_type": payload.get("report_type"),
        "execution_kind": payload.get("execution_kind"),
    }


def _smoke_report_passed(
    path: Path | None, *, ledger: SmokeScenarioLedger | None = None
) -> tuple[bool, dict[str, Any]]:
    status, details = _smoke_report_status(path, ledger=ledger)
    return status == STATUS_PASSED, details


def probe_ai_smoke_readiness(
    repo_root: Path,
    *,
    ai_smoke_agent_id: int | None = None,
    ai_smoke_agent_code: str | None = None,
    smoke_report_path: Path | None = None,
) -> list[ProbeResult]:
    backend_env = _read_env_file(repo_root / "backend" / ".env")
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
    expected_agent_id = ai_smoke_agent_id
    expected_agent_code = str(ai_smoke_agent_code or "").strip() or None
    selector_validation_errors: list[str] = []
    env_agent_id = _configured_env_value(
        "AI_SMOKE_AGENT_ID", env_file_values=backend_env
    )
    env_agent_code = _configured_env_value(
        "AI_SMOKE_AGENT_CODE", env_file_values=backend_env
    )
    if ai_smoke_agent_id is not None and expected_agent_code:
        selector_validation_errors.append("agent_selector_argument_ambiguous")
    elif ai_smoke_agent_id is None and expected_agent_code is None:
        if env_agent_id and env_agent_code:
            selector_validation_errors.append("agent_selector_env_ambiguous")
        if env_agent_id:
            try:
                expected_agent_id = int(env_agent_id)
            except ValueError:
                selector_validation_errors.append("ai_smoke_agent_id_invalid")
        elif env_agent_code:
            expected_agent_code = env_agent_code
    if ai_smoke_agent_id is not None:
        has_agent_selector = True
        selectors.append("--ai-smoke-agent-id")
    if expected_agent_code and ai_smoke_agent_code:
        has_agent_selector = True
        selectors.append("--ai-smoke-agent-code")
    agent_selector_passed = has_agent_selector and not selector_validation_errors

    scenario_paths = [
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
        repo_root / "ops" / "ai-smoke" / "smoke-scenarios.md",
    ]
    parsed_ledgers = [_parse_smoke_scenario_ledger(path) for path in scenario_paths]
    valid_ledgers = [ledger for ledger in parsed_ledgers if ledger.valid]
    primary_ledger = valid_ledgers[0] if valid_ledgers else None
    valid_scenarios = [ledger.path for ledger in valid_ledgers]
    smoke_report_status, smoke_report_details = _smoke_report_status(
        smoke_report_path,
        ledger=primary_ledger,
        expected_agent_id=expected_agent_id,
        expected_agent_code=expected_agent_code,
        repo_root=repo_root,
    )
    smoke_passed = smoke_report_status == STATUS_PASSED
    report_provider_evidence = bool(
        smoke_report_details.get("provider_evidence_passed")
    )
    cli_file = repo_root / "backend" / "app" / "cli_commands" / "ai_commands.py"
    cli_text = (
        cli_file.read_text(encoding="utf-8", errors="replace")
        if cli_file.exists()
        else ""
    )
    cli_available = '@ai_cmd.command("smoke")' in cli_text
    real_dialogue_cli_available = '@ai_cmd.command("real-dialogue-smoke")' in cli_text

    credential_passed = has_provider_key or (smoke_passed and report_provider_evidence)
    credential_sources = list(provider_keys)
    if smoke_passed and report_provider_evidence:
        credential_sources.append("strict_real_dialogue_smoke_report")
    return [
        ProbeResult(
            area="ai_runtime",
            name="ai_runtime_smoke_cli",
            status=STATUS_PASSED
            if cli_available and real_dialogue_cli_available
            else STATUS_BLOCKED,
            summary="AI capability and real-dialogue smoke commands are present"
            if cli_available and real_dialogue_cli_available
            else "AI smoke command coverage is incomplete",
            details={
                "path": str(cli_file),
                "capability_smoke_present": cli_available,
                "real_dialogue_smoke_present": real_dialogue_cli_available,
            },
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
                "parsed_ledgers": [asdict(ledger) for ledger in parsed_ledgers],
            },
        ),
        ProbeResult(
            area="ai_runtime",
            name="ai_provider_credentials",
            status=STATUS_PASSED if credential_passed else STATUS_BLOCKED,
            summary="AI provider credential evidence is configured or proven by real-dialogue smoke"
            if credential_passed
            else "no AI provider credential is configured in the current environment",
            details={
                "configured_variable_names": provider_keys,
                "credential_evidence_sources": credential_sources,
                "strict_smoke_report_provider_evidence": report_provider_evidence,
            },
        ),
        ProbeResult(
            area="ai_runtime",
            name="ai_smoke_agent_selector",
            status=STATUS_PASSED if agent_selector_passed else STATUS_BLOCKED,
            summary="AI smoke agent selector is configured"
            if agent_selector_passed
            else "AI smoke agent selector is invalid or ambiguous"
            if selector_validation_errors
            else "AI smoke agent selector is not configured",
            details={
                "configured_variable_names": selectors,
                "expected_agent_id": expected_agent_id,
                "expected_agent_code": expected_agent_code,
                "validation_errors": selector_validation_errors,
            },
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
                    "python -m app.cli ai real-dialogue-smoke --agent-id <id> --raw-json "
                    "> <archived smoke report>"
                ),
            },
        ),
    ]


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _coerce_int(value: Any) -> int | None:
    number = _coerce_float(value)
    if number is None:
        return None
    return int(round(number))


def _mapping_value(mapping: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in {None, ""}:
            return mapping[key]
    return None


def _parse_k6_summary_json(path: Path) -> CapacityBenchmarkMetrics:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"k6 summary is not readable JSON: {exc}") from exc

    metrics = payload.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError("k6 summary does not contain a metrics object")

    def values_for(name: str) -> Mapping[str, Any]:
        metric = metrics.get(name)
        if not isinstance(metric, Mapping):
            return {}
        values = metric.get("values")
        return values if isinstance(values, Mapping) else {}

    http_reqs = values_for("http_reqs")
    failures = values_for("http_req_failed")
    durations = values_for("http_req_duration")
    checks = values_for("checks")

    request_count = _coerce_int(http_reqs.get("count"))
    p95_ms = _coerce_float(durations.get("p(95)"))
    error_ratio = _coerce_float(failures.get("rate"))
    if request_count is None or request_count < 0:
        raise ValueError("k6 summary is missing http_reqs.values.count")
    if p95_ms is None:
        raise ValueError("k6 summary is missing http_req_duration.values.p(95)")
    if error_ratio is None:
        raise ValueError("k6 summary is missing http_req_failed.values.rate")

    failure_count = _coerce_int(failures.get("fails"))
    if failure_count is None:
        failure_count = int(round(request_count * error_ratio))
    return CapacityBenchmarkMetrics(
        runner="k6",
        request_count=request_count,
        failure_count=failure_count,
        error_ratio=error_ratio,
        p95_ms=p95_ms,
        max_ms=_coerce_float(durations.get("max")),
        avg_ms=_coerce_float(durations.get("avg")),
        median_ms=_coerce_float(durations.get("med")),
        requests_per_second=_coerce_float(http_reqs.get("rate")),
        check_pass_count=_coerce_int(checks.get("passes")),
        check_failure_count=_coerce_int(checks.get("fails")),
        artifact_path=str(path),
    )


def _parse_locust_stats_csv(
    stats_path: Path, *, failures_path: Path | None = None
) -> CapacityBenchmarkMetrics:
    try:
        with stats_path.open(newline="", encoding="utf-8-sig") as file:
            rows = list(csv.DictReader(file))
    except OSError as exc:
        raise ValueError(f"Locust stats CSV is not readable: {exc}") from exc
    if not rows:
        raise ValueError("Locust stats CSV is empty")

    aggregate_row = next(
        (row for row in rows if str(row.get("Name", "")).strip() == "Aggregated"),
        None,
    )
    ready_row = next(
        (
            row
            for row in rows
            if str(row.get("Name", "")).strip().rstrip("/") in {"", "ready", "/ready"}
        ),
        None,
    )
    row = aggregate_row or ready_row or rows[-1]

    request_count = _coerce_int(
        _mapping_value(row, ("Request Count", "# requests", "Requests"))
    )
    failure_count = _coerce_int(
        _mapping_value(row, ("Failure Count", "# failures", "Failures"))
    )
    p95_ms = _coerce_float(_mapping_value(row, ("95%", "95")))
    if request_count is None or request_count < 0:
        raise ValueError("Locust stats CSV is missing Request Count")
    if failure_count is None or failure_count < 0:
        raise ValueError("Locust stats CSV is missing Failure Count")
    if p95_ms is None:
        raise ValueError("Locust stats CSV is missing 95% latency")

    return CapacityBenchmarkMetrics(
        runner="locust",
        request_count=request_count,
        failure_count=failure_count,
        error_ratio=(failure_count / request_count) if request_count else 1.0,
        p95_ms=p95_ms,
        max_ms=_coerce_float(_mapping_value(row, ("Max Response Time", "Max"))),
        avg_ms=_coerce_float(_mapping_value(row, ("Average Response Time", "Average"))),
        median_ms=_coerce_float(
            _mapping_value(row, ("Median Response Time", "Median"))
        ),
        requests_per_second=_coerce_float(_mapping_value(row, ("Requests/s",))),
        artifact_path=str(stats_path),
        failure_artifact_path=str(failures_path) if failures_path else None,
    )


def _capacity_result_from_metrics(
    *,
    metrics: CapacityBenchmarkMetrics,
    command_result: Mapping[str, Any],
    api_base_url: str,
    requested: int,
    concurrency: int,
    p95_budget_ms: float,
    error_budget_ratio: float,
) -> ProbeResult:
    threshold_failures: list[str] = []
    if metrics.request_count < requested:
        threshold_failures.append("request_count_below_requested")
    if metrics.error_ratio > error_budget_ratio:
        threshold_failures.append("error_ratio_above_budget")
    if metrics.p95_ms > p95_budget_ms:
        threshold_failures.append("p95_above_budget")
    if metrics.check_failure_count not in {None, 0}:
        threshold_failures.append("runner_check_failures")
    if command_result.get("exit_code") != 0:
        threshold_failures.append("runner_exit_code_nonzero")

    details = {
        "url": f"{_normalize_base_url(api_base_url)}/ready",
        "runner": metrics.runner,
        "requests": requested,
        "concurrency": concurrency,
        "p95_budget_ms": p95_budget_ms,
        "error_budget_ratio": error_budget_ratio,
        "metrics": asdict(metrics),
        "threshold_failures": threshold_failures,
        "command_result": dict(command_result),
        "scope": (
            "formal capacity benchmark using a checked-in k6/Locust plan; "
            "local Python /ready smoke is reported separately"
        ),
    }
    return ProbeResult(
        area="capacity",
        name="capacity_acceptance_benchmark",
        status=STATUS_FAILED if threshold_failures else STATUS_PASSED,
        summary="capacity benchmark breached acceptance thresholds"
        if threshold_failures
        else "capacity benchmark passed",
        details=details,
    )


def _capacity_blocked_result(
    *,
    summary: str,
    runner: Mapping[str, Any],
    requests: int,
    concurrency: int,
    details: dict[str, Any] | None = None,
) -> ProbeResult:
    payload = {
        "requests": requests,
        "concurrency": concurrency,
        "runner": dict(runner),
        "scope": (
            "real capacity acceptance requires k6 or Locust benchmark evidence; "
            "the Python readiness smoke is not accepted as capacity"
        ),
    }
    if details:
        payload.update(details)
    return ProbeResult(
        area="capacity",
        name="capacity_acceptance_benchmark",
        status=STATUS_BLOCKED,
        summary=summary,
        details=payload,
    )


def _run_k6_capacity_benchmark(
    api_base_url: str,
    *,
    k6_path: str,
    repo_root: Path,
    artifact_root: Path,
    concurrency: int,
    requests: int,
    timeout: float,
    p95_budget_ms: float,
    error_budget_ratio: float,
) -> ProbeResult:
    script_path = repo_root / _K6_CAPACITY_SCRIPT
    runner = _capacity_runner_state()
    if not script_path.exists():
        return _capacity_blocked_result(
            summary="k6 capacity plan file is missing",
            runner=runner,
            requests=requests,
            concurrency=concurrency,
            details={"plan_path": str(script_path)},
        )

    prefix = _artifact_prefix(artifact_root, "k6")
    summary_path = prefix.with_name(f"{prefix.name}-summary.json")
    stdout_path = prefix.with_name(f"{prefix.name}-stdout.txt")
    stderr_path = prefix.with_name(f"{prefix.name}-stderr.txt")
    command = [
        k6_path,
        "run",
        "--vus",
        str(concurrency),
        "--iterations",
        str(requests),
        "--summary-export",
        str(summary_path),
        str(script_path),
    ]
    command_result = _run_command(
        command,
        cwd=repo_root,
        env={
            "API_BASE_URL": _normalize_base_url(api_base_url),
            "CAPACITY_TARGET_PATH": "/ready",
            "K6_NO_CLOUD": "1",
        },
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout=timeout,
    )
    output = _command_combined_output(command_result)
    if command_result.get("exit_code") != 0 and _capacity_target_unavailable(output):
        return _capacity_blocked_result(
            summary="capacity benchmark target is unavailable",
            runner=runner,
            requests=requests,
            concurrency=concurrency,
            details={"command_result": command_result, "artifact": str(summary_path)},
        )
    if not summary_path.exists():
        return _capacity_blocked_result(
            summary="k6 capacity benchmark did not produce a summary artifact",
            runner=runner,
            requests=requests,
            concurrency=concurrency,
            details={"command_result": command_result, "artifact": str(summary_path)},
        )
    try:
        metrics = _parse_k6_summary_json(summary_path)
    except ValueError as exc:
        return _capacity_blocked_result(
            summary="k6 capacity benchmark summary is not parseable",
            runner=runner,
            requests=requests,
            concurrency=concurrency,
            details={
                "command_result": command_result,
                "artifact": str(summary_path),
                "parse_error": str(exc),
            },
        )
    return _capacity_result_from_metrics(
        metrics=metrics,
        command_result=command_result,
        api_base_url=api_base_url,
        requested=requests,
        concurrency=concurrency,
        p95_budget_ms=p95_budget_ms,
        error_budget_ratio=error_budget_ratio,
    )


def _run_locust_capacity_benchmark(
    api_base_url: str,
    *,
    locust_command: list[str],
    repo_root: Path,
    artifact_root: Path,
    concurrency: int,
    requests: int,
    timeout: float,
    p95_budget_ms: float,
    error_budget_ratio: float,
) -> ProbeResult:
    locust_file = repo_root / _LOCUST_CAPACITY_FILE
    runner = _capacity_runner_state()
    if not locust_file.exists():
        return _capacity_blocked_result(
            summary="Locust capacity plan file is missing",
            runner=runner,
            requests=requests,
            concurrency=concurrency,
            details={"plan_path": str(locust_file)},
        )

    prefix = _artifact_prefix(artifact_root, "locust")
    stdout_path = prefix.with_name(f"{prefix.name}-stdout.txt")
    stderr_path = prefix.with_name(f"{prefix.name}-stderr.txt")
    stats_path = prefix.with_name(f"{prefix.name}_stats.csv")
    failures_path = prefix.with_name(f"{prefix.name}_failures.csv")
    target_duration = max(
        5, (requests + max(1, concurrency) - 1) // max(1, concurrency)
    )
    max_duration = max(1, int(timeout) - 1)
    run_time_seconds = max(1, min(target_duration, max_duration))
    command = [
        *locust_command,
        "-f",
        str(locust_file),
        "--headless",
        "-u",
        str(concurrency),
        "-r",
        str(concurrency),
        "--host",
        _normalize_base_url(api_base_url),
        "--run-time",
        f"{run_time_seconds}s",
        "--csv",
        str(prefix),
        "--only-summary",
    ]
    command_result = _run_command(
        command,
        cwd=repo_root,
        env={
            "CAPACITY_REQUESTS": str(requests),
            "CAPACITY_TARGET_PATH": "/ready",
        },
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout=timeout,
    )
    output = _command_combined_output(command_result)
    failure_text = ""
    if failures_path.exists():
        failure_text = failures_path.read_text(encoding="utf-8", errors="replace")
    if command_result.get("exit_code") != 0 and _capacity_target_unavailable(
        output + "\n" + failure_text
    ):
        return _capacity_blocked_result(
            summary="capacity benchmark target is unavailable",
            runner=runner,
            requests=requests,
            concurrency=concurrency,
            details={"command_result": command_result, "artifact": str(stats_path)},
        )
    if not stats_path.exists():
        return _capacity_blocked_result(
            summary="Locust capacity benchmark did not produce a stats artifact",
            runner=runner,
            requests=requests,
            concurrency=concurrency,
            details={"command_result": command_result, "artifact": str(stats_path)},
        )
    try:
        metrics = _parse_locust_stats_csv(stats_path, failures_path=failures_path)
    except ValueError as exc:
        return _capacity_blocked_result(
            summary="Locust capacity benchmark stats are not parseable",
            runner=runner,
            requests=requests,
            concurrency=concurrency,
            details={
                "command_result": command_result,
                "artifact": str(stats_path),
                "parse_error": str(exc),
            },
        )
    if (
        metrics.request_count > 0
        and metrics.failure_count >= metrics.request_count
        and _capacity_target_unavailable(failure_text)
    ):
        return _capacity_blocked_result(
            summary="capacity benchmark target is unavailable",
            runner=runner,
            requests=requests,
            concurrency=concurrency,
            details={
                "command_result": command_result,
                "metrics": asdict(metrics),
                "artifact": str(stats_path),
                "failure_artifact": str(failures_path),
            },
        )
    return _capacity_result_from_metrics(
        metrics=metrics,
        command_result=command_result,
        api_base_url=api_base_url,
        requested=requests,
        concurrency=concurrency,
        p95_budget_ms=p95_budget_ms,
        error_budget_ratio=error_budget_ratio,
    )


def run_capacity_benchmark(
    api_base_url: str,
    *,
    concurrency: int,
    requests: int,
    timeout: float,
    p95_budget_ms: float,
    error_budget_ratio: float,
    repo_root: Path | None = None,
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
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

    runner = _capacity_runner_state()
    if not runner["available"]:
        return _capacity_blocked_result(
            summary="capacity acceptance is blocked because k6/Locust is missing",
            runner=runner,
            requests=requests,
            concurrency=concurrency,
            details={"run_with": "uv sync --extra dev or install k6"},
        )

    resolved_repo_root = repo_root or Path(__file__).resolve().parents[2]
    artifact_root = _resolve_artifact_root(resolved_repo_root, artifact_dir)
    tools = runner["tools"]
    locust_binary = tools.get("locust_binary")
    if locust_binary or tools.get("locust_module"):
        locust_command = (
            [locust_binary] if locust_binary else [sys.executable, "-m", "locust"]
        )
        return _run_locust_capacity_benchmark(
            api_base_url,
            locust_command=locust_command,
            repo_root=resolved_repo_root,
            artifact_root=artifact_root,
            concurrency=concurrency,
            requests=requests,
            timeout=timeout,
            p95_budget_ms=p95_budget_ms,
            error_budget_ratio=error_budget_ratio,
        )

    k6_path = tools.get("k6")
    if k6_path:
        return _run_k6_capacity_benchmark(
            api_base_url,
            k6_path=k6_path,
            repo_root=resolved_repo_root,
            artifact_root=artifact_root,
            concurrency=concurrency,
            requests=requests,
            timeout=timeout,
            p95_budget_ms=p95_budget_ms,
            error_budget_ratio=error_budget_ratio,
        )

    return _capacity_blocked_result(
        summary="capacity acceptance has no runnable k6/Locust command",
        runner=runner,
        requests=requests,
        concurrency=concurrency,
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
    unavailable_only = (
        requests == len(errors)
        and bool(errors)
        and all(_is_unavailable_probe_error(error) for error in errors)
    )
    return ProbeResult(
        area="capacity",
        name="local_ready_load_smoke",
        status=STATUS_PASSED
        if not errors
        else STATUS_BLOCKED
        if unavailable_only
        else STATUS_FAILED,
        summary="local /ready load smoke passed"
        if not errors
        else "local /ready load smoke is blocked because the target is unavailable"
        if unavailable_only
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
    unavailable = _is_postgres_drill_unavailable(failed_step)
    if cleanup_failed and _is_postgres_drill_unavailable(cleanup_failed):
        unavailable = True

    return ProbeResult(
        area="backup_restore",
        name="postgres_backup_restore_drill",
        status=STATUS_PASSED
        if passed
        else STATUS_BLOCKED
        if unavailable
        else STATUS_FAILED,
        summary="PostgreSQL backup/restore disposable drill passed"
        if passed
        else "PostgreSQL backup/restore disposable drill is blocked because the target is unavailable"
        if unavailable
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
            "unavailable": unavailable,
            "steps": steps,
            "cleanup_steps": cleanup_steps,
        },
    )


def _pip_audit_vulnerability_count(artifact: Path) -> int | None:
    if not artifact.exists():
        return None
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    dependencies = payload.get("dependencies")
    if not isinstance(dependencies, list):
        return None
    count = 0
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            continue
        vulns = dependency.get("vulns")
        if isinstance(vulns, list):
            count += len(vulns)
    return count


def _run_pip_audit_scan(
    *, backend_dir: Path, artifact_root: Path, timeout: float
) -> ProbeResult:
    artifact_root.mkdir(parents=True, exist_ok=True)
    canonical_artifact = artifact_root / "pip-audit.json"
    if canonical_artifact.exists():
        canonical_artifact.unlink()

    attempts: list[dict[str, Any]] = []
    last_artifact: Path | None = None
    final_command: dict[str, Any] | None = None
    for attempt_number in range(1, _PIP_AUDIT_MAX_ATTEMPTS + 1):
        attempt_artifact = artifact_root / f"pip-audit-attempt-{attempt_number}.json"
        if attempt_artifact.exists():
            attempt_artifact.unlink()
        stdout_path = artifact_root / f"pip-audit-attempt-{attempt_number}.stdout.log"
        stderr_path = artifact_root / f"pip-audit-attempt-{attempt_number}.stderr.log"
        command = _run_command(
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
                str(attempt_artifact),
            ],
            cwd=backend_dir,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout=timeout,
        )
        final_command = command
        vulnerability_count = _pip_audit_vulnerability_count(attempt_artifact)
        blocked = bool(
            command.get("error")
            or command.get("timed_out")
            or _command_has_markers(command, _NETWORK_BLOCK_MARKERS)
        )
        attempt_details = {
            "attempt": attempt_number,
            "artifact": str(attempt_artifact),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "exit_code": command.get("exit_code"),
            "blocked": blocked,
            "vulnerability_count": vulnerability_count,
        }
        attempts.append(attempt_details)
        if attempt_artifact.exists():
            last_artifact = attempt_artifact
            shutil.copyfile(attempt_artifact, canonical_artifact)
        if command.get("exit_code") == 0:
            return ProbeResult(
                area="security",
                name="python_dependency_audit_scan",
                status=STATUS_PASSED,
                summary="pip-audit passed",
                details={
                    "artifact": str(canonical_artifact),
                    "attempts": attempts,
                    "command_result": command,
                    "retry_count": attempt_number - 1,
                },
            )
        if not blocked:
            return ProbeResult(
                area="security",
                name="python_dependency_audit_scan",
                status=STATUS_FAILED,
                summary="pip-audit found vulnerabilities"
                if vulnerability_count
                else "pip-audit failed",
                details={
                    "artifact": str(canonical_artifact),
                    "attempts": attempts,
                    "command_result": command,
                    "retry_count": attempt_number - 1,
                    "vulnerability_count": vulnerability_count,
                },
            )

    if last_artifact and not canonical_artifact.exists():
        shutil.copyfile(last_artifact, canonical_artifact)
    return ProbeResult(
        area="security",
        name="python_dependency_audit_scan",
        status=STATUS_BLOCKED,
        summary="pip-audit could not reach audit data after retry",
        details={
            "artifact": str(canonical_artifact),
            "attempts": attempts,
            "command_result": final_command or {},
            "retry_count": max(0, len(attempts) - 1),
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
        results.append(
            _run_pip_audit_scan(
                backend_dir=backend_dir,
                artifact_root=artifact_root,
                timeout=timeout,
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

    pnpm_cmd = shutil.which("pnpm") or "pnpm"
    frontend_audit_specs = [
        (
            "frontend_dependency_audit_scan",
            artifact_root / "pnpm-audit-all.json",
            [
                pnpm_cmd,
                "audit",
                "--audit-level",
                "high",
                "--registry",
                "https://registry.npmjs.org",
                "--json",
            ],
        ),
        (
            "frontend_production_dependency_audit_scan",
            artifact_root / "pnpm-audit-prod.json",
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
        ),
    ]
    for name, pnpm_artifact, command in frontend_audit_specs:
        pnpm = _run_command(
            command,
            cwd=frontend_dir,
            stdout_path=pnpm_artifact,
            timeout=timeout,
        )
        results.append(
            _command_probe_result(
                area="security",
                name=name,
                command=pnpm,
                summary_passed=f"{name} passed",
                summary_failed=f"{name} found high/critical vulnerabilities",
                summary_blocked=f"{name} registry or command is unavailable",
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
        block_markers=_DAST_BLOCK_MARKERS,
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
    if status_result.status == STATUS_PASSED and fail_new is None:
        return ProbeResult(
            area=status_result.area,
            name=status_result.name,
            status=STATUS_BLOCKED,
            summary="OWASP ZAP baseline did not report a parseable FAIL-NEW count",
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
            repo_root=repo_root,
            artifact_dir=artifact_dir,
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


def _resolve_cli_path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def main() -> int:
    args = _parse_args()
    repo_root = _resolve_cli_path(args.repo_root)
    report = build_report(
        api_base_url=args.api_base_url,
        frontend_base_url=args.frontend_base_url,
        load_smoke_concurrency=max(1, args.load_smoke_concurrency),
        load_smoke_requests=max(0, args.load_smoke_requests),
        capacity_concurrency=max(1, args.capacity_concurrency),
        capacity_requests=max(0, args.capacity_requests),
        capacity_p95_budget_ms=max(1.0, args.capacity_p95_budget_ms),
        capacity_error_budget_ratio=max(0.0, args.capacity_error_budget_ratio),
        repo_root=repo_root,
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
        ai_smoke_report=(
            _resolve_cli_path(args.ai_smoke_report) if args.ai_smoke_report else None
        ),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["overall_status"] == STATUS_FAILED:
        return 2
    if report["overall_status"] == STATUS_BLOCKED and not args.allow_blocked:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
