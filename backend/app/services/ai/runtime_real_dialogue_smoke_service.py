"""中文: AI 真对话 smoke 执行服务。

EN: AI real-dialogue smoke execution service.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.constants import DEFAULT_MEMORY_SCENE, MEMORY_CHANNEL_SYSTEM
from app.configs.service import PLATFORM_TENANT_ID
from app.core.base_model import utc_now
from app.core.logging import get_logger
from app.enums.ai import CallStatusEnum, CallTypeEnum, RequestTypeEnum
from app.exceptions import AppException
from app.models.ai.call_log import AICallLog
from app.schemas.ai.invalid_ai_runtime_input import is_invalid_ai_runtime_reference
from app.services.ai.agent_chat_service import AgentChatService
from app.services.ai.runtime_diagnostics_support import RuntimeDiagnosticsCheckSupport
from app.services.ai.runtime_inventory_service import RuntimeInventoryService
from app.services.ai.runtime_root_cause_projector import RuntimeRootCauseProjector

AI_REAL_DIALOGUE_SMOKE_SCHEMA_VERSION = "ai-real-dialogue-smoke/v1"
AI_REAL_DIALOGUE_SMOKE_REPORT_TYPE = "ai_real_dialogue_smoke"
AI_REAL_DIALOGUE_SMOKE_EXECUTION_KIND = "real_dialogue"

_STATUS_PASSED = "passed"
_STATUS_FAILED = "failed"
_STATUS_BLOCKED = "blocked"
_LEDGER_MARKERS = (
    "scenario_id",
    "user_input",
    "required_capabilities",
    "expected_observable_outcome",
)
_BLOCKED_ERROR_MARKERS = (
    "api key",
    "api_key",
    "credential",
    "not configured",
    "no available",
    "not found",
    "agent.error.not_found",
    "密钥",
    "未配置",
    "没有配置",
    "不存在",
)
_RETIRED_CAPABILITY_MARKERS = (
    "current_page",
    "page_session",
    "page_context",
    "page_data",
    "pageop_",
    "fetch_url",
    "hosted_web_search",
    "native_web_search",
    "online_search",
    "response.web_search_call",
    "search_provider",
    "web_research",
    "web_search",
    "web_search_options",
    "web_search_runtime",
)
_FABRICATED_SOURCE_MARKERS = (
    "http://",
    "https://",
    "据路透",
    "据彭博",
    "据新华社",
    "据央视",
    "source:",
    "citation",
    "[1]",
)
_RETIRED_CAPABILITY_FREE_TEXT_KEYS = frozenset(
    {
        "assistant_text",
        "content",
        "detail",
        "error_message",
        "message",
        "output_text",
        "reason",
        "source_text",
        "summary",
        "text",
        "user_input",
    }
)

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RealDialogueSmokeScenario:
    """中文: 从 smoke ledger 解析出的单个真对话场景。

    EN: One real-dialogue scenario parsed from the smoke ledger.
    """

    scenario_id: str
    user_input: str
    must_pass: bool = True


@dataclass(frozen=True, slots=True)
class RealDialogueSmokeLedger:
    """中文: smoke ledger 的可验证摘要。

    EN: Verifiable summary of the smoke ledger.
    """

    path: str | None
    sha256: str | None
    scenario_ids: list[str]
    scenarios: list[RealDialogueSmokeScenario]
    valid: bool
    missing_markers: list[str]
    duplicate_scenario_ids: list[str]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_backtick_or_value(line: str, key: str) -> str:
    match = re.search(rf"{re.escape(key)}\s*:\s*`([^`]+)`", line)
    if match:
        return match.group(1).strip()
    match = re.search(rf"{re.escape(key)}\s*:\s*(.+)$", line)
    if not match:
        return ""
    return match.group(1).strip().strip("`").strip()


def _parse_smoke_ledger(path: Path | None) -> RealDialogueSmokeLedger:
    if path is None or not path.exists():
        return RealDialogueSmokeLedger(
            path=str(path) if path is not None else None,
            sha256=None,
            scenario_ids=[],
            scenarios=[],
            valid=False,
            missing_markers=list(_LEDGER_MARKERS),
            duplicate_scenario_ids=[],
        )

    text = path.read_text(encoding="utf-8", errors="replace")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    missing_markers = [marker for marker in _LEDGER_MARKERS if marker not in text]
    scenarios: list[RealDialogueSmokeScenario] = []
    current: dict[str, Any] | None = None
    for line in text.splitlines():
        if "scenario_id" in line:
            if current is not None and current.get("scenario_id"):
                scenarios.append(
                    RealDialogueSmokeScenario(
                        scenario_id=str(current.get("scenario_id") or "").strip(),
                        user_input=str(current.get("user_input") or "").strip(),
                        must_pass=bool(current.get("must_pass", True)),
                    )
                )
            current = {
                "scenario_id": _extract_backtick_or_value(line, "scenario_id"),
                "user_input": "",
                "must_pass": True,
            }
            continue
        if current is None:
            continue
        if "user_input" in line:
            current["user_input"] = _extract_backtick_or_value(line, "user_input")
        elif "priority" in line:
            priority = _extract_backtick_or_value(line, "priority").lower()
            current["must_pass"] = priority in {"", "must-pass", "p0", "p1", "high"}
        elif "must_pass" in line:
            value = _extract_backtick_or_value(line, "must_pass").lower()
            current["must_pass"] = value not in {"false", "0", "no"}
    if current is not None and current.get("scenario_id"):
        scenarios.append(
            RealDialogueSmokeScenario(
                scenario_id=str(current.get("scenario_id") or "").strip(),
                user_input=str(current.get("user_input") or "").strip(),
                must_pass=bool(current.get("must_pass", True)),
            )
        )

    scenario_ids = [scenario.scenario_id for scenario in scenarios]
    duplicate_ids = sorted(
        {
            scenario_id
            for scenario_id in scenario_ids
            if scenario_ids.count(scenario_id) > 1
        }
    )
    scenarios_with_missing_prompt = [
        scenario.scenario_id for scenario in scenarios if not scenario.user_input
    ]
    valid = (
        not missing_markers
        and bool(scenarios)
        and not duplicate_ids
        and not scenarios_with_missing_prompt
    )
    if scenarios_with_missing_prompt:
        missing_markers = [*missing_markers, "scenario_user_input"]
    return RealDialogueSmokeLedger(
        path=str(path),
        sha256=digest,
        scenario_ids=scenario_ids,
        scenarios=scenarios,
        valid=valid,
        missing_markers=missing_markers,
        duplicate_scenario_ids=duplicate_ids,
    )


def _git_metadata(repo_root: Path | None) -> dict[str, Any]:
    if repo_root is None:
        return {"commit": None, "dirty": None}
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            check=False,
            timeout=3,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            check=False,
            timeout=3,
        )
        return {
            "commit": commit.stdout.strip() if commit.returncode == 0 else None,
            "dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
        }
    except Exception:
        return {"commit": None, "dirty": None}


def _status_from_error(exc: Exception) -> str:
    text = str(exc).lower()
    if any(marker in text for marker in _BLOCKED_ERROR_MARKERS):
        return _STATUS_BLOCKED
    if isinstance(exc, AppException) and exc.status_code in {401, 403, 404}:
        return _STATUS_BLOCKED
    return _STATUS_FAILED


def _contains_retired_capability(value: Any, *, field_name: str | None = None) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key or "")
            if _contains_retired_capability(key_text):
                return True
            if key_text in _RETIRED_CAPABILITY_FREE_TEXT_KEYS:
                continue
            if _contains_retired_capability(nested, field_name=key_text):
                return True
        return False
    if isinstance(value, list | tuple | set):
        return any(
            _contains_retired_capability(item, field_name=field_name) for item in value
        )
    text = str(value or "").strip()
    if not text:
        return False
    if field_name in _RETIRED_CAPABILITY_FREE_TEXT_KEYS:
        return False
    lowered = text.lower()
    return is_invalid_ai_runtime_reference(text) or any(
        marker in lowered for marker in _RETIRED_CAPABILITY_MARKERS
    )


def _contains_fabricated_live_source(value: Any) -> bool:
    text = str(value or "").lower()
    return any(marker.lower() in text for marker in _FABRICATED_SOURCE_MARKERS)


def _sentence_count(value: str) -> int:
    parts = [part for part in re.split(r"[。！？.!?]+", value) if part.strip()]
    return len(parts)


def _scenario_requires_capability_smoke(scenario_id: str) -> bool:
    return "runtime-capability-smoke" in scenario_id


def _scenario_requires_short_enterprise_answer(scenario_id: str) -> bool:
    return "short-answer-real-turn" in scenario_id


def _scenario_requires_tool_policy_guard(scenario_id: str) -> bool:
    return "tool-policy-guard" in scenario_id


def _blocking_checks_passed(checks: list[dict[str, Any]]) -> bool:
    return all(
        str(check.get("status") or "") == "available"
        for check in checks
        if bool(check.get("blocking"))
    )


def _resolve_overall_status(scenario_results: list[dict[str, Any]]) -> str:
    must_pass = [item for item in scenario_results if bool(item.get("must_pass"))]
    if any(item.get("status") == _STATUS_FAILED for item in must_pass):
        return _STATUS_FAILED
    if any(item.get("status") == _STATUS_BLOCKED for item in must_pass):
        return _STATUS_BLOCKED
    if scenario_results and all(
        item.get("status") == _STATUS_PASSED for item in scenario_results
    ):
        return _STATUS_PASSED
    if any(item.get("status") == _STATUS_FAILED for item in scenario_results):
        return _STATUS_FAILED
    return _STATUS_BLOCKED


def _summarize_results(scenario_results: list[dict[str, Any]]) -> dict[str, int]:
    must_pass = [item for item in scenario_results if bool(item.get("must_pass"))]
    return {
        "total": len(scenario_results),
        "passed": sum(
            1 for item in scenario_results if item.get("status") == _STATUS_PASSED
        ),
        "failed": sum(
            1 for item in scenario_results if item.get("status") == _STATUS_FAILED
        ),
        "blocked": sum(
            1 for item in scenario_results if item.get("status") == _STATUS_BLOCKED
        ),
        "must_pass_total": len(must_pass),
        "must_pass_passed": sum(
            1 for item in must_pass if item.get("status") == _STATUS_PASSED
        ),
    }


class RuntimeRealDialogueSmokeService:
    """中文: 运行真实 AgentChatService 对话并生成生产验收报告。

    EN: Runs real AgentChatService turns and produces production acceptance reports.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run(
        self,
        *,
        tenant_id: int | None,
        agent_id: int | None,
        agent_code: str | None,
        ledger_path: str | None,
        scenario_ids: list[str] | None,
        message: str | None,
        user_id: int | None,
        user_role: str,
        user_role_id: int | None,
        repo_root: str | None = None,
    ) -> dict[str, Any]:
        resolved_tenant_id = PLATFORM_TENANT_ID if tenant_id is None else int(tenant_id)
        repo_path = Path(repo_root) if repo_root else None
        ledger = _parse_smoke_ledger(Path(ledger_path) if ledger_path else None)
        scenarios = self._select_scenarios(
            ledger=ledger,
            scenario_ids=list(scenario_ids or []),
            message=message,
        )

        report: dict[str, Any] = {
            "schema_version": AI_REAL_DIALOGUE_SMOKE_SCHEMA_VERSION,
            "report_type": AI_REAL_DIALOGUE_SMOKE_REPORT_TYPE,
            "execution_kind": AI_REAL_DIALOGUE_SMOKE_EXECUTION_KIND,
            "overall_status": _STATUS_BLOCKED,
            "generated_at": _now_iso(),
            "command": {
                "argv": ["python", "-m", "app.cli", "ai", "real-dialogue-smoke"],
                "exit_code": 0,
            },
            "repo": _git_metadata(repo_path),
            "ledger": {
                "path": ledger.path,
                "sha256": ledger.sha256,
                "scenario_ids": ledger.scenario_ids,
                "valid": ledger.valid,
                "missing_markers": ledger.missing_markers,
                "duplicate_scenario_ids": ledger.duplicate_scenario_ids,
            },
            "agent": {
                "selector_type": "id" if agent_id is not None else "code",
                "selector_value": str(
                    agent_id if agent_id is not None else agent_code or ""
                ),
                "resolved_agent_id": None,
                "resolved_agent_name": None,
                "tenant_id": resolved_tenant_id,
            },
            "provider": {
                "credential_source": None,
                "live_provider_call_count": 0,
                "call_logs": [],
                "mocked_llm": False,
                "replay": False,
            },
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "blocked": 0,
                "must_pass_total": 0,
                "must_pass_passed": 0,
            },
            "scenario_results": [],
        }

        if not scenarios:
            report["scenario_results"] = [
                {
                    "scenario_id": "scenario_selection",
                    "must_pass": True,
                    "status": _STATUS_BLOCKED,
                    "error_message": "No runnable smoke scenarios were selected.",
                }
            ]
            report["summary"] = _summarize_results(report["scenario_results"])
            return report

        try:
            agent = await RuntimeInventoryService(self.db)._resolve_agent(
                tenant_id=resolved_tenant_id,
                agent_id=agent_id,
                agent_code=agent_code,
            )
            if agent is None:
                raise ValueError("agent selector is required")
            resolved_agent_id = int(agent.id)
            report["agent"].update(
                {
                    "resolved_agent_id": resolved_agent_id,
                    "resolved_agent_name": getattr(agent, "name", None),
                    "resolved_agent_code": getattr(agent, "feature_code", None),
                }
            )
        except Exception as exc:
            report["scenario_results"] = [
                {
                    "scenario_id": scenario.scenario_id,
                    "must_pass": scenario.must_pass,
                    "status": _status_from_error(exc),
                    "error_message": str(exc),
                }
                for scenario in scenarios
            ]
            report["overall_status"] = _resolve_overall_status(
                report["scenario_results"]
            )
            report["summary"] = _summarize_results(report["scenario_results"])
            return report

        scenario_results: list[dict[str, Any]] = []
        for scenario in scenarios:
            scenario_results.append(
                await self._run_scenario(
                    tenant_id=resolved_tenant_id,
                    agent_id=resolved_agent_id,
                    scenario=scenario,
                    user_id=user_id,
                    user_role=user_role,
                    user_role_id=user_role_id,
                )
            )

        report["scenario_results"] = scenario_results
        report["overall_status"] = _resolve_overall_status(scenario_results)
        report["summary"] = _summarize_results(scenario_results)
        provider_calls = [
            item for item in scenario_results if item.get("provider_call_log_id")
        ]
        provider_call_logs = [
            {
                "id": item.get("provider_call_log_id"),
                "conversation_id": item.get("conversation_id"),
                "status": item.get("provider_call_status"),
                "provider_name": item.get("provider_name"),
                "model_name": item.get("model_name"),
                "request_type": item.get("request_type"),
                "call_type": item.get("call_type"),
            }
            for item in provider_calls
        ]
        report["provider"]["live_provider_call_count"] = len(provider_calls)
        first_provider = next(
            (
                item
                for item in scenario_results
                if item.get("provider_name") or item.get("model_name")
            ),
            {},
        )
        report["provider"].update(
            {
                "credential_source": "runtime_provider_config"
                if provider_calls
                else None,
                "call_logs": provider_call_logs,
                "provider_name": first_provider.get("provider_name"),
                "model": first_provider.get("model_name"),
            }
        )
        return report

    @staticmethod
    def _select_scenarios(
        *,
        ledger: RealDialogueSmokeLedger,
        scenario_ids: list[str],
        message: str | None,
    ) -> list[RealDialogueSmokeScenario]:
        if message and str(message).strip():
            return [
                RealDialogueSmokeScenario(
                    scenario_id="CLI-CUSTOM-real-dialogue-smoke",
                    user_input=str(message).strip(),
                    must_pass=True,
                )
            ]
        scenarios = list(ledger.scenarios)
        selected_ids = {item.strip() for item in scenario_ids if item.strip()}
        if selected_ids:
            scenarios = [
                scenario
                for scenario in scenarios
                if scenario.scenario_id in selected_ids
            ]
        return scenarios

    async def _run_scenario(
        self,
        *,
        tenant_id: int,
        agent_id: int,
        scenario: RealDialogueSmokeScenario,
        user_id: int | None,
        user_role: str,
        user_role_id: int | None,
    ) -> dict[str, Any]:
        started_at = utc_now()
        try:
            capability_smoke = await self._run_capability_smoke(
                tenant_id=tenant_id,
                agent_id=agent_id,
                enabled=_scenario_requires_capability_smoke(scenario.scenario_id),
            )
            service = AgentChatService(self.db, tenant_id)
            response = await service.chat(
                agent_id=agent_id,
                message=scenario.user_input,
                conversation_id=None,
                variables={
                    "smoke_scenario_id": scenario.scenario_id,
                    "smoke_execution_kind": AI_REAL_DIALOGUE_SMOKE_EXECUTION_KIND,
                },
                user_id=user_id,
                user_role=user_role,
                user_role_id=user_role_id,
                permissions=set(),
                memory_scene=DEFAULT_MEMORY_SCENE,
                memory_channel=MEMORY_CHANNEL_SYSTEM,
                memory_source="real_dialogue_smoke",
                interaction_mode="trusted_auto",
            )
            call_log = await self._latest_call_log(
                conversation_id=response.conversation_id,
                agent_id=agent_id,
                created_after=started_at,
            )
            assistant_text = str(response.message or "").strip()
            provider_status = str(getattr(call_log, "status", "") or "")
            selected_tools = list(
                (response.context_diagnostics or {}).get("selected_tool_names") or []
            )
            selected_skills = list(
                (response.context_diagnostics or {}).get("selected_skill_names") or []
            )
            retired_probe_values = {
                "selected_tool_names": selected_tools,
                "selected_skill_names": selected_skills,
                "context_diagnostics": response.context_diagnostics,
                "last_run_summary": response.last_run_summary,
                "capability_smoke": capability_smoke,
            }
            retired_capability_exposed = _contains_retired_capability(
                retired_probe_values
            )
            scripted_checks = self._build_scripted_checks(
                scenario=scenario,
                assistant_text=assistant_text,
                selected_tools=selected_tools,
                selected_skills=selected_skills,
                capability_smoke=capability_smoke,
            )
            observable_checks = {
                "assistant_text_non_empty": bool(assistant_text),
                "provider_call_log_present": call_log is not None,
                "provider_call_succeeded": provider_status
                in {"", CallStatusEnum.SUCCESS.value},
                "retired_current_page_or_online_search_exposed": retired_capability_exposed,
                **scripted_checks,
            }
            passed = (
                observable_checks["assistant_text_non_empty"]
                and observable_checks["provider_call_log_present"]
                and observable_checks["provider_call_succeeded"]
                and not observable_checks[
                    "retired_current_page_or_online_search_exposed"
                ]
                and all(scripted_checks.values())
            )
            return {
                "scenario_id": scenario.scenario_id,
                "must_pass": scenario.must_pass,
                "status": _STATUS_PASSED if passed else _STATUS_FAILED,
                "conversation_id": response.conversation_id,
                "assistant_text_non_empty": bool(assistant_text),
                "assistant_text_sample": assistant_text[:500],
                "provider_call_log_id": getattr(call_log, "id", None),
                "provider_call_status": provider_status or None,
                "provider_name": getattr(call_log, "provider_name_snapshot", None),
                "model_name": getattr(call_log, "model_name_snapshot", None),
                "request_type": getattr(call_log, "request_type", None),
                "call_type": getattr(call_log, "call_type", None),
                "total_tokens": response.total_tokens,
                "duration_ms": response.duration_ms,
                "observable_checks": observable_checks,
                "retired_capability_probe_values": retired_probe_values
                if retired_capability_exposed
                else {},
                "capability_smoke": capability_smoke,
                "context_diagnostics": response.context_diagnostics,
                "last_run_summary": response.last_run_summary,
            }
        except Exception as exc:
            logger.warning(
                "AI real-dialogue smoke scenario failed: scenario={} err={}",
                scenario.scenario_id,
                str(exc),
            )
            return {
                "scenario_id": scenario.scenario_id,
                "must_pass": scenario.must_pass,
                "status": _status_from_error(exc),
                "error_message": str(exc),
                "error_type": type(exc).__name__,
            }

    async def _run_capability_smoke(
        self,
        *,
        tenant_id: int,
        agent_id: int,
        enabled: bool,
    ) -> dict[str, Any] | None:
        if not enabled:
            return None
        manifest = await RuntimeInventoryService(self.db).get_manifest(
            scope="real_dialogue_smoke",
            tenant_id=tenant_id,
            agent_id=agent_id,
            agent_code=None,
        )
        support = RuntimeDiagnosticsCheckSupport()
        checks = [
            support.build_check_item(
                "agent_resolution",
                status="available",
                blocking=True,
                reason=None,
                metadata={"agent_name": manifest.get("summary", {}).get("agent_name")},
            )
        ]
        checks.extend(support.build_manifest_checks(manifest, require_agent=True))
        status = RuntimeRootCauseProjector.resolve_overall_status(checks)
        return {
            "overall_status": status,
            "passed": _blocking_checks_passed(checks),
            "checks": checks,
        }

    @staticmethod
    def _build_scripted_checks(
        *,
        scenario: RealDialogueSmokeScenario,
        assistant_text: str,
        selected_tools: list[Any],
        selected_skills: list[Any],
        capability_smoke: dict[str, Any] | None,
    ) -> dict[str, bool]:
        scenario_id = scenario.scenario_id
        checks: dict[str, bool] = {}
        if _scenario_requires_capability_smoke(scenario_id):
            checks["capability_smoke_green_or_passed"] = bool(
                capability_smoke and capability_smoke.get("passed")
            )
        if _scenario_requires_short_enterprise_answer(scenario_id):
            checks["answer_concise"] = 0 < _sentence_count(assistant_text) <= 4
            checks["answer_enterprise_saas_relevant"] = any(
                marker in assistant_text
                for marker in ("企业", "SaaS", "saas", "NovusAI", "能力")
            )
        if _scenario_requires_tool_policy_guard(scenario_id):
            exposed_values = [assistant_text, *selected_tools, *selected_skills]
            checks["no_fabricated_live_source"] = not any(
                _contains_fabricated_live_source(value) for value in exposed_values
            )
        return checks

    async def _latest_call_log(
        self,
        *,
        conversation_id: int,
        agent_id: int,
        created_after: datetime,
    ) -> AICallLog | None:
        result = await self.db.execute(
            select(AICallLog)
            .where(
                AICallLog.conversation_id == conversation_id,
                AICallLog.agent_id == agent_id,
                AICallLog.created_at >= created_after,
                AICallLog.request_type == RequestTypeEnum.CHAT.value,
                AICallLog.call_type == CallTypeEnum.MAIN_CHAT.value,
                AICallLog.is_deleted.is_(False),
            )
            .order_by(AICallLog.created_at.desc(), AICallLog.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


__all__ = [
    "AI_REAL_DIALOGUE_SMOKE_EXECUTION_KIND",
    "AI_REAL_DIALOGUE_SMOKE_REPORT_TYPE",
    "AI_REAL_DIALOGUE_SMOKE_SCHEMA_VERSION",
    "RuntimeRealDialogueSmokeService",
]
