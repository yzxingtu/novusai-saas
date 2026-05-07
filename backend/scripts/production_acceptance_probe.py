"""中文: 生产验收探针，输出可机器读取的通过/阻塞/失败门禁。

EN: Production acceptance probe that emits machine-readable pass/block/fail
gates.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_BLOCKED = "blocked"


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
        value = raw_value.strip().strip('"').strip("'")
        values[key.strip()] = value
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
        return {
            "status_code": response.status,
            "elapsed_ms": elapsed_ms,
        }


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
        details={
            "url": url,
            "error": str(exc),
        },
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
                area="readiness", name="api_ready", url=ready_url, exc=exc
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
        metrics = _request_status(metrics_url, timeout=timeout)
        results.append(
            ProbeResult(
                area="monitoring",
                name="prometheus_metrics_endpoint",
                status=STATUS_PASSED,
                summary="/metrics endpoint is reachable",
                details={"url": metrics_url, **metrics},
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


def _tool_map(tool_names: tuple[str, ...]) -> dict[str, str | None]:
    return {name: shutil.which(name) for name in tool_names}


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _tool_result(
    *,
    area: str,
    name: str,
    tools: tuple[str, ...],
    require_all: bool,
    summary_ready: str,
    summary_missing: str,
) -> ProbeResult:
    resolved = _tool_map(tools)
    present = [name for name, path in resolved.items() if path]
    passed = len(present) == len(tools) if require_all else bool(present)
    return ProbeResult(
        area=area,
        name=name,
        status=STATUS_PASSED if passed else STATUS_BLOCKED,
        summary=summary_ready if passed else summary_missing,
        details={
            "required": list(tools),
            "present": present,
            "missing": [name for name in tools if not resolved[name]],
        },
    )


def probe_external_tooling() -> list[ProbeResult]:
    results = [
        _tool_result(
            area="capacity",
            name="load_capacity_tooling",
            tools=("k6", "locust"),
            require_all=False,
            summary_ready="load/capacity tool is available",
            summary_missing="no k6 or locust binary found for real load/capacity test",
        ),
        _tool_result(
            area="backup_restore",
            name="postgres_backup_restore_tooling",
            tools=("pg_dump", "pg_restore", "psql"),
            require_all=True,
            summary_ready="PostgreSQL backup/restore tooling is available",
            summary_missing="pg_dump, pg_restore, or psql is missing",
        ),
        _tool_result(
            area="security",
            name="python_dependency_audit_tooling",
            tools=("pip-audit",),
            require_all=True,
            summary_ready="pip-audit is available",
            summary_missing="pip-audit is missing",
        ),
        _tool_result(
            area="security",
            name="python_sast_tooling",
            tools=("bandit", "semgrep"),
            require_all=False,
            summary_ready="Python SAST tooling is available",
            summary_missing="bandit or semgrep is missing",
        ),
        _tool_result(
            area="security",
            name="dast_tooling",
            tools=("zap-cli", "zap-baseline.py"),
            require_all=False,
            summary_ready="DAST tooling is available",
            summary_missing="OWASP ZAP command is missing",
        ),
        _tool_result(
            area="security",
            name="frontend_dependency_audit_tooling",
            tools=("pnpm",),
            require_all=True,
            summary_ready="pnpm audit tooling is available",
            summary_missing="pnpm is missing",
        ),
    ]
    if _module_available("pip_audit"):
        results[2] = ProbeResult(
            area="security",
            name="python_dependency_audit_tooling",
            status=STATUS_PASSED,
            summary="pip-audit module is available",
            details={
                "required": ["pip-audit"],
                "present": ["pip_audit"],
                "missing": [],
            },
        )
    if _module_available("bandit"):
        results[3] = ProbeResult(
            area="security",
            name="python_sast_tooling",
            status=STATUS_PASSED,
            summary="bandit module is available",
            details={
                "required": ["bandit", "semgrep"],
                "present": ["bandit"],
                "missing": ["semgrep"],
            },
        )
    return results


def probe_ai_smoke_readiness(repo_root: Path) -> list[ProbeResult]:
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
    ]
    existing_scenarios = [str(path) for path in scenario_paths if path.exists()]
    cli_file = repo_root / "backend" / "app" / "cli_commands" / "ai_commands.py"
    cli_available = cli_file.exists()

    results = [
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
            status=STATUS_PASSED if existing_scenarios else STATUS_BLOCKED,
            summary="AI smoke scenario ledger is present"
            if existing_scenarios
            else "AI smoke scenario ledger is not present in this workspace",
            details={"expected_paths": [str(path) for path in scenario_paths]},
        ),
        ProbeResult(
            area="ai_runtime",
            name="ai_provider_credentials",
            status=STATUS_PASSED if has_provider_key else STATUS_BLOCKED,
            summary="AI provider credential variable is configured"
            if has_provider_key
            else "no AI provider credential variable is configured",
            details={"configured_variable_names": provider_keys},
        ),
        ProbeResult(
            area="ai_runtime",
            name="ai_smoke_agent_selector",
            status=STATUS_PASSED if has_agent_selector else STATUS_BLOCKED,
            summary="AI smoke agent selector is configured"
            if has_agent_selector
            else "AI_SMOKE_AGENT_ID or AI_SMOKE_AGENT_CODE is not configured",
            details={"configured_variable_names": selectors},
        ),
    ]
    results.append(
        ProbeResult(
            area="ai_runtime",
            name="ai_real_dialogue_smoke_execution",
            status=STATUS_BLOCKED,
            summary=(
                "real-dialogue smoke is not executed by this probe; run "
                "`novusai ai smoke --agent-id/--agent-code` against a real provider "
                "and archive the report"
            ),
            details={
                "requires": [
                    "real provider credentials",
                    "agent selector",
                    "smoke scenario ledger",
                    "archived smoke report",
                ]
            },
        )
    )
    return results


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


def build_report(
    *,
    api_base_url: str,
    frontend_base_url: str | None,
    load_smoke_concurrency: int,
    load_smoke_requests: int,
    repo_root: Path,
    timeout: float,
) -> dict[str, Any]:
    results: list[ProbeResult] = []
    results.extend(probe_api(api_base_url, timeout=timeout))
    results.append(probe_frontend(frontend_base_url, timeout=timeout))
    results.extend(probe_external_tooling())
    results.extend(probe_ai_smoke_readiness(repo_root))
    results.append(
        run_load_smoke(
            api_base_url,
            concurrency=load_smoke_concurrency,
            requests=load_smoke_requests,
            timeout=timeout,
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
            "Production acceptance probe: readiness, tooling, local load smoke, "
            "and AI smoke prerequisites."
        )
    )
    parser.add_argument("--api-base-url", default="http://localhost:8000")
    parser.add_argument("--frontend-base-url", default="http://localhost:5666")
    parser.add_argument("--load-smoke-requests", type=int, default=0)
    parser.add_argument("--load-smoke-concurrency", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument(
        "--allow-blocked",
        action="store_true",
        help="Exit 0 when only blocked gates remain.",
    )
    parser.add_argument(
        "--repo-root",
        default=str(Path(__file__).resolve().parents[2]),
        help="Repository root for AI smoke prerequisite checks.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = build_report(
        api_base_url=args.api_base_url,
        frontend_base_url=args.frontend_base_url,
        load_smoke_concurrency=max(1, args.load_smoke_concurrency),
        load_smoke_requests=max(0, args.load_smoke_requests),
        repo_root=Path(args.repo_root),
        timeout=max(0.5, args.timeout),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["overall_status"] == STATUS_FAILED:
        return 2
    if report["overall_status"] == STATUS_BLOCKED and not args.allow_blocked:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
