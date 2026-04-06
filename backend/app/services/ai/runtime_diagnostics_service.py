"""
Unified AI runtime diagnostics service / 统一 AI runtime 诊断服务。
"""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse

from kombu import Connection
from redis.asyncio import Redis
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.core.config import settings
from app.core.database import check_database_connection
from app.core.logging import get_logger
from app.core.redis import RedisManager
from app.enums.ai import CallStatusEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.call_log import AICallLog
from app.services.ai.monitoring_service import MonitoringService
from app.services.ai.runtime_inventory_service import RuntimeInventoryService
from app.services.ai.skill_registry_service import SkillRegistryService

logger = get_logger(__name__)

_BUDGET_TERMINATION_REASONS = {
    "budget_exit",
    "elapsed_budget_exceeded",
    "completion_budget_exceeded",
    "tool_round_budget_exceeded",
    "retry_budget_exhausted",
    "prompt_budget_exceeded",
    "tool_result_budget_exceeded",
    "candidate_tool_budget_exceeded",
}


class RuntimeDiagnosticsService:
    """Provide runtime doctor, smoke, root-cause, and starter-pack actions."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.inventory = RuntimeInventoryService(db)

    async def get_capabilities(
        self,
        *,
        scope: Any = "runtime",
        tenant_id: int | None = None,
        agent_id: int | None = None,
        agent_code: str | None = None,
    ) -> dict[str, Any]:
        return await self.inventory.get_manifest(
            scope=scope,
            tenant_id=tenant_id,
            agent_id=agent_id,
            agent_code=agent_code,
        )

    async def run_doctor(
        self,
        *,
        scope: Any = "runtime",
        tenant_id: int | None = None,
        agent_id: int | None = None,
        agent_code: str | None = None,
    ) -> dict[str, Any]:
        manifest = await self.get_capabilities(
            scope=scope,
            tenant_id=tenant_id,
            agent_id=agent_id,
            agent_code=agent_code,
        )
        checks: list[dict[str, Any]] = [
            await self._check_database(),
            await self._check_redis(),
            await self._check_celery_broker(),
        ]
        checks.extend(
            self._build_manifest_checks(
                manifest,
                require_agent=False,
                require_page_context=False,
            )
        )
        recent_failures = await self._aggregate_recent_failures(tenant_id=tenant_id)
        recommended_actions = self._build_recommended_actions(
            checks=checks,
            manifest=manifest,
            recent_failures=recent_failures,
        )
        return {
            "overall_status": self._resolve_overall_status(checks),
            "checks": checks,
            "recent_failures": recent_failures,
            "capability_manifest_summary": dict(manifest.get("summary") or {}),
            "recommended_actions": recommended_actions,
        }

    async def run_smoke(
        self,
        *,
        scope: Any = "runtime",
        tenant_id: int | None = None,
        agent_id: int | None = None,
        agent_code: str | None = None,
    ) -> dict[str, Any]:
        if agent_id is None and not str(agent_code or "").strip():
            checks = [
                self._check_item(
                    "agent_resolution",
                    status="unavailable",
                    blocking=True,
                    reason="agent_id_or_agent_code_required",
                )
            ]
            return {
                "overall_status": "red",
                "checks": checks,
                "runtime_capability_manifest": None,
                "recommended_actions": [
                    "Provide --agent-id or --agent-code before running runtime smoke."
                ],
            }

        manifest = await self.get_capabilities(
            scope=scope,
            tenant_id=tenant_id,
            agent_id=agent_id,
            agent_code=agent_code,
        )
        checks = [
            self._check_item(
                "agent_resolution",
                status="available",
                blocking=True,
                reason=None,
                metadata={"agent_name": manifest.get("summary", {}).get("agent_name")},
            )
        ]
        checks.extend(
            self._build_manifest_checks(
                manifest,
                require_agent=True,
                require_page_context=False,
            )
        )
        recommended_actions = self._build_recommended_actions(
            checks=checks,
            manifest=manifest,
            recent_failures=[],
        )
        return {
            "overall_status": self._resolve_overall_status(checks),
            "checks": checks,
            "runtime_capability_manifest": manifest,
            "recommended_actions": recommended_actions,
        }

    async def build_root_cause(
        self,
        *,
        scope: Any = "runtime",
        trace_id: str | None = None,
        call_log_id: int | None = None,
        conversation_id: int | None = None,
        turn: int | None = None,
    ) -> dict[str, Any]:
        del scope
        call_log = await self._resolve_call_log(
            trace_id=trace_id,
            call_log_id=call_log_id,
            conversation_id=conversation_id,
            turn=turn,
        )
        diagnostics = MonitoringService._extract_call_trace_diagnostics(
            call_log.request_metadata
        )
        failure_layer, cause_code, summary, first_fix, confidence = (
            self._classify_root_cause(call_log, diagnostics)
        )
        recovered_via_retry = bool(
            diagnostics.get("recovered_via_retry")
            or any(
                bool(event.get("recovered"))
                for event in (diagnostics.get("retry_events") or [])
                if isinstance(event, dict)
            )
        )
        return {
            "status": "success"
            if failure_layer is None and call_log.status == CallStatusEnum.SUCCESS.value
            else "failed",
            "failure_layer": failure_layer,
            "cause_code": cause_code,
            "summary": summary,
            "evidence": self._build_root_cause_evidence(call_log, diagnostics),
            "first_fix": first_fix,
            "confidence": confidence,
            "recovered_via_retry": recovered_via_retry,
            "related_ids": {
                "call_log_id": call_log.id,
                "trace_id": call_log.trace_id,
                "conversation_id": call_log.conversation_id,
                "agent_id": call_log.agent_id,
                "provider_id": call_log.provider_id,
                "model_id": call_log.model_id,
                "turn": turn,
            },
        }

    async def run_root_cause(
        self,
        *,
        trace_id: str | None = None,
        call_log_id: int | None = None,
        conversation_id: int | None = None,
        turn: int | None = None,
    ) -> dict[str, Any]:
        return await self.build_root_cause(
            trace_id=trace_id,
            call_log_id=call_log_id,
            conversation_id=conversation_id,
            turn=turn,
        )

    async def sync_official_starter_pack(
        self,
        *,
        pack_keys: list[str] | None = None,
        install_missing: bool = True,
        upgrade_existing: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        return await SkillRegistryService(self.db).sync_official_starter_packs(
            pack_keys=pack_keys,
            install_missing=install_missing,
            upgrade_existing=upgrade_existing,
            dry_run=dry_run,
        )

    @staticmethod
    def _check_item(
        name: str,
        *,
        status: str,
        blocking: bool = False,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "status": status,
            "blocking": blocking,
            "reason": reason,
            "metadata": dict(metadata or {}),
        }

    async def _check_database(self) -> dict[str, Any]:
        healthy = await check_database_connection()
        return self._check_item(
            "database",
            status="available" if healthy else "unavailable",
            blocking=True,
            reason=None if healthy else "database_connection_failed",
        )

    async def _check_redis(self) -> dict[str, Any]:
        try:
            await RedisManager.init()
            healthy = await RedisManager.health_check()
        except Exception as exc:
            logger.warning("Runtime doctor redis check failed: {}", exc)
            healthy = False
        return self._check_item(
            "redis",
            status="available" if healthy else "unavailable",
            blocking=True,
            reason=None if healthy else "redis_connection_failed",
        )

    async def _check_celery_broker(self) -> dict[str, Any]:
        broker_url = settings.celery_broker_url
        if not broker_url:
            return self._check_item(
                "celery_broker",
                status="unavailable",
                blocking=True,
                reason="celery_broker_url_missing",
            )

        parsed = urlparse(broker_url)
        scheme = str(parsed.scheme or "").lower()
        try:
            if scheme.startswith("redis"):
                client = Redis.from_url(
                    broker_url,
                    decode_responses=True,
                    socket_connect_timeout=3,
                    socket_timeout=3,
                )
                try:
                    healthy = bool(await client.ping())
                finally:
                    await client.aclose()
            elif scheme in {"amqp", "amqps", "pyamqp"}:
                with Connection(broker_url, connect_timeout=3) as connection:
                    connection.ensure_connection(max_retries=1)
                healthy = True
            else:
                return self._check_item(
                    "celery_broker",
                    status="degraded",
                    blocking=False,
                    reason="unsupported_broker_scheme_check",
                    metadata={"scheme": scheme or None},
                )
        except Exception as exc:
            logger.warning("Runtime doctor celery broker check failed: {}", exc)
            healthy = False

        return self._check_item(
            "celery_broker",
            status="available" if healthy else "unavailable",
            blocking=True,
            reason=None if healthy else "celery_broker_connection_failed",
            metadata={"scheme": scheme or None},
        )

    def _build_manifest_checks(
        self,
        manifest: dict[str, Any],
        *,
        require_agent: bool,
        require_page_context: bool,
    ) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        summary = dict(manifest.get("summary") or {})
        provider = dict(manifest.get("provider") or {})
        model = dict(manifest.get("model") or {})
        web_research_items = list(manifest.get("web_research") or [])
        page_context_items = list(manifest.get("page_context") or [])
        memory_items = list(manifest.get("memory") or [])
        kb_items = list(manifest.get("knowledge_bases") or [])

        if require_agent:
            checks.append(
                self._check_item(
                    "provider",
                    status=str(provider.get("status") or "unavailable"),
                    blocking=True,
                    reason=provider.get("reason"),
                    metadata={"provider": provider},
                )
            )
            checks.append(
                self._check_item(
                    "model",
                    status=str(model.get("status") or "unavailable"),
                    blocking=True,
                    reason=model.get("reason"),
                    metadata={"model": model},
                )
            )
        elif provider.get("id") or model.get("id"):
            checks.append(
                self._check_item(
                    "provider_model_resolution",
                    status="available"
                    if provider.get("status") == "available"
                    and model.get("status") == "available"
                    else "degraded",
                    blocking=False,
                    reason=None
                    if provider.get("status") == "available"
                    and model.get("status") == "available"
                    else "provider_or_model_degraded",
                    metadata={"provider": provider, "model": model},
                )
            )

        tool_count = int(summary.get("tool_count") or 0)
        skill_count = int(summary.get("skill_count") or 0)
        checks.append(
            self._check_item(
                "tools",
                status="available" if tool_count > 0 else "degraded",
                blocking=False,
                reason=None if tool_count > 0 else "no_runtime_tools_exposed",
                metadata={"tool_count": tool_count},
            )
        )
        checks.append(
            self._check_item(
                "skills",
                status="available" if skill_count > 0 else "degraded",
                blocking=False,
                reason=None if skill_count > 0 else "no_runtime_skills_selected",
                metadata={"skill_count": skill_count},
            )
        )

        web_research = next(
            (
                item
                for item in web_research_items
                if str(item.get("name") or "").strip() == "web_research"
            ),
            {},
        )
        research_status = str(web_research.get("status") or "unavailable")
        research_metadata = dict(web_research.get("metadata") or {})
        has_one_of_pair = bool(research_metadata.get("has_web_search")) ^ bool(
            research_metadata.get("has_fetch_url")
        )
        checks.append(
            self._check_item(
                "web_research_contract",
                status=research_status,
                blocking=has_one_of_pair,
                reason=web_research.get("reason"),
                metadata=research_metadata,
            )
        )

        kb_available_count = len(
            [item for item in kb_items if item.get("status") == "available"]
        )
        checks.append(
            self._check_item(
                "knowledge_base",
                status="available" if kb_available_count > 0 else "degraded",
                blocking=False,
                reason=None
                if kb_available_count > 0
                else "no_effective_knowledge_base_binding",
                metadata={"knowledge_base_count": kb_available_count},
            )
        )

        memory_status = next(
            (
                str(item.get("status") or "unavailable")
                for item in memory_items
                if str(item.get("name") or "").strip() == "memory"
            ),
            "unavailable",
        )
        memory_reason = next(
            (
                item.get("reason")
                for item in memory_items
                if str(item.get("name") or "").strip() == "memory"
            ),
            None,
        )
        checks.append(
            self._check_item(
                "memory",
                status=memory_status,
                blocking=False,
                reason=memory_reason,
            )
        )

        page_status = next(
            (
                str(item.get("status") or "unavailable")
                for item in page_context_items
                if str(item.get("name") or "").strip()
            ),
            "unavailable",
        )
        page_reason = next(
            (
                item.get("reason")
                for item in page_context_items
                if str(item.get("name") or "").strip()
            ),
            None,
        )
        checks.append(
            self._check_item(
                "page_context",
                status=page_status,
                blocking=require_page_context,
                reason=page_reason,
            )
        )
        return checks

    async def _aggregate_recent_failures(
        self,
        *,
        tenant_id: int | None,
    ) -> list[dict[str, Any]]:
        since = utc_now() - timedelta(hours=24)
        stmt: Select[tuple[AICallLog]] = (
            select(AICallLog)
            .where(
                AICallLog.is_deleted.is_(False),
                AICallLog.created_at >= since,
            )
            .order_by(AICallLog.created_at.desc(), AICallLog.id.desc())
            .limit(500)
        )
        if tenant_id is not None:
            stmt = stmt.where(AICallLog.tenant_id == tenant_id)

        result = await self.db.execute(stmt)
        logs = list(result.scalars().all())

        failure_counter: Counter[tuple[str | None, ...]] = Counter()
        collected = 0
        for log in logs:
            diagnostics = MonitoringService._extract_call_trace_diagnostics(
                log.request_metadata
            )
            if not self._is_failed_call(log, diagnostics):
                continue
            selected_tools = diagnostics.get("selected_tool_names") or []
            key = (
                diagnostics.get("failure_kind"),
                getattr(log, "provider_name_snapshot", None),
                getattr(log, "model_name_snapshot", None),
                getattr(log, "agent_name_snapshot", None),
                selected_tools[0] if selected_tools else None,
                diagnostics.get("contract_breach_type"),
            )
            failure_counter[key] += 1
            collected += 1
            if collected >= 50:
                break

        return [
            {
                "failure_kind": failure_kind,
                "provider": provider_name,
                "model": model_name,
                "agent": agent_name,
                "tool": tool_name,
                "contract_breach_type": contract,
                "count": count,
            }
            for (
                failure_kind,
                provider_name,
                model_name,
                agent_name,
                tool_name,
                contract,
            ), count in failure_counter.most_common()
        ]

    @staticmethod
    def _is_failed_call(log: AICallLog, diagnostics: dict[str, Any]) -> bool:
        if str(log.status or "") != CallStatusEnum.SUCCESS.value:
            return True
        if str(diagnostics.get("turn_outcome") or "") in {
            "failed",
            "partial",
            "tool_round_failed",
        }:
            return True
        if str(diagnostics.get("failure_kind") or "").strip() not in {"", "none"}:
            return True
        return False

    async def _resolve_call_log(
        self,
        *,
        trace_id: str | None,
        call_log_id: int | None,
        conversation_id: int | None,
        turn: int | None,
    ) -> AICallLog:
        if call_log_id is not None:
            result = await self.db.execute(
                select(AICallLog).where(
                    AICallLog.id == call_log_id,
                    AICallLog.is_deleted.is_(False),
                )
            )
            call_log = result.scalar_one_or_none()
            if call_log is None:
                raise NotFoundException(message="AI call log not found")
            return call_log

        if trace_id:
            result = await self.db.execute(
                select(AICallLog)
                .where(
                    AICallLog.trace_id == trace_id,
                    AICallLog.is_deleted.is_(False),
                )
                .order_by(AICallLog.created_at.desc(), AICallLog.id.desc())
                .limit(1)
            )
            call_log = result.scalar_one_or_none()
            if call_log is None:
                raise NotFoundException(message="AI call log not found")
            return call_log

        if conversation_id is not None and turn is not None:
            result = await self.db.execute(
                select(AICallLog)
                .where(
                    AICallLog.conversation_id == conversation_id,
                    AICallLog.is_deleted.is_(False),
                )
                .order_by(AICallLog.created_at.asc(), AICallLog.id.asc())
            )
            logs = list(result.scalars().all())
            if turn <= 0 or turn > len(logs):
                raise NotFoundException(message="AI call log not found")
            return logs[turn - 1]

        raise BusinessException(
            message="trace_id, call_log_id, or conversation_id+turn is required"
        )

    def _classify_root_cause(
        self,
        call_log: AICallLog,
        diagnostics: dict[str, Any],
    ) -> tuple[str | None, str | None, str, str | None, float | None]:
        error_message = str(call_log.error_message or "").strip()
        failure_kind = str(diagnostics.get("failure_kind") or "").strip()
        contract_breach_type = str(
            diagnostics.get("contract_breach_type") or ""
        ).strip()
        termination_reason = str(
            diagnostics.get("termination_reason") or ""
        ).strip()
        budget_exit_reason = str(
            diagnostics.get("budget_exit_reason") or ""
        ).strip()
        provider_events = list(diagnostics.get("provider_events") or [])
        retry_events = list(diagnostics.get("retry_events") or [])
        selected_tools = list(diagnostics.get("selected_tool_names") or [])
        unfinished_intents = list(diagnostics.get("unfinished_intents") or [])

        if (
            str(call_log.status or "") == CallStatusEnum.SUCCESS.value
            and not failure_kind
            and not contract_breach_type
            and termination_reason not in _BUDGET_TERMINATION_REASONS
        ):
            return (
                None,
                None,
                "The call completed successfully and no blocking failure signal was found.",
                None,
                0.98,
            )

        if contract_breach_type:
            lower_contract = contract_breach_type.lower()
            if "research" in lower_contract or "unfinished_intent" in lower_contract:
                return (
                    "research_contract",
                    contract_breach_type,
                    "The turn failed because the web-research contract was not fully satisfied.",
                    "Inspect the agent's web_search/fetch_url tool pair and the unfinished-intent retry rules for this trace.",
                    0.92,
                )
            return (
                "stream_output_contract",
                contract_breach_type,
                "The turn failed because the stream/output contract was breached.",
                "Start with the stream handler and final output contract reconciliation for this trace.",
                0.9,
            )

        if unfinished_intents:
            return (
                "research_contract",
                failure_kind or "unfinished_intents",
                "The turn exited with unfinished intents that never reached the required completion signal.",
                "Check intent retry / fetch_url completion criteria before changing downstream formatting.",
                0.86,
            )

        lower_error = error_message.lower()
        if provider_events or any(
            token in lower_error
            for token in ("provider", "upstream", "timeout", "rate limit", "api key")
        ):
            return (
                "provider_gateway",
                failure_kind or "provider_gateway_error",
                "The failure came from the provider gateway or upstream model interaction.",
                "Inspect provider events, model routing, and upstream credentials for this trace first.",
                0.84,
            )

        if selected_tools or "tool" in failure_kind or "tool" in lower_error:
            return (
                "tool_execution",
                failure_kind or "tool_execution_failed",
                "A runtime tool call failed or the tool loop did not converge.",
                "Start with the selected tool payloads and execution logs for the affected turn.",
                0.82,
            )

        if any(
            token in lower_error for token in ("skill", "grant", "resolver", "toolkit")
        ):
            return (
                "skill_resolution",
                failure_kind or "skill_resolution_failed",
                "The turn failed before execution because runtime skills/tools could not be resolved cleanly.",
                "Check agent skill grants and runtime skill resolution for this agent.",
                0.78,
            )

        if any(
            token in lower_error
            for token in ("context", "knowledge base", "memory", "page_context")
        ):
            return (
                "context_assembly",
                failure_kind or "context_assembly_failed",
                "The turn failed while assembling runtime context.",
                "Inspect context assembly diagnostics, including KB, memory, and page-context inputs.",
                0.76,
            )

        if termination_reason in _BUDGET_TERMINATION_REASONS or budget_exit_reason:
            return (
                "post_processing",
                budget_exit_reason or termination_reason or "budget_exit",
                "The turn exhausted a runtime budget or exited during finalization.",
                "Tune runtime budgets or remove the stop-loss path that terminated this turn.",
                0.8,
            )

        if retry_events:
            return (
                "post_processing",
                failure_kind or "retry_exhausted",
                "The turn could not recover after runtime retries.",
                "Inspect retry chain diagnostics before changing model prompts or frontend rendering.",
                0.74,
            )

        return (
            "post_processing",
            failure_kind or "unknown_failure",
            "The turn failed after execution, but no narrower failure layer matched.",
            "Start from turn diagnostics and provider/tool evidence on this call log.",
            0.6,
        )

    @staticmethod
    def _build_root_cause_evidence(
        call_log: AICallLog,
        diagnostics: dict[str, Any],
    ) -> list[dict[str, Any]]:
        evidence: list[dict[str, Any]] = []

        def append(label: str, value: Any) -> None:
            if value in (None, "", [], {}, ()):
                return
            evidence.append({"label": label, "value": value})

        append("call_status", call_log.status)
        append("error_message", call_log.error_message)
        append("turn_outcome", diagnostics.get("turn_outcome"))
        append("termination_reason", diagnostics.get("termination_reason"))
        append("failure_kind", diagnostics.get("failure_kind"))
        append("contract_breach_type", diagnostics.get("contract_breach_type"))
        append("budget_exit_reason", diagnostics.get("budget_exit_reason"))
        append("selected_tool_names", diagnostics.get("selected_tool_names"))
        append("selected_skill_names", diagnostics.get("selected_skill_names"))
        append("unfinished_intents", diagnostics.get("unfinished_intents"))
        append("retry_events", diagnostics.get("retry_events"))
        append("provider_events", diagnostics.get("provider_events"))
        append("fallback_history", diagnostics.get("fallback_history"))
        return evidence

    @staticmethod
    def _resolve_overall_status(checks: list[dict[str, Any]]) -> str:
        if any(
            bool(check.get("blocking")) and str(check.get("status")) == "unavailable"
            for check in checks
        ):
            return "red"
        if any(str(check.get("status")) != "available" for check in checks):
            return "yellow"
        return "green"

    @staticmethod
    def _build_recommended_actions(
        *,
        checks: list[dict[str, Any]],
        manifest: dict[str, Any],
        recent_failures: list[dict[str, Any]],
    ) -> list[str]:
        actions: list[str] = []
        for check in checks:
            status = str(check.get("status") or "")
            reason = str(check.get("reason") or "").strip()
            name = str(check.get("name") or "").strip()
            if status == "unavailable":
                actions.append(f"Restore `{name}` before relying on runtime diagnostics.")
            elif status == "degraded" and reason:
                actions.append(f"Investigate `{name}` degradation: {reason}.")

        for item in manifest.get("disabled_capabilities") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            reason = str(item.get("reason") or "").strip()
            if name and reason:
                actions.append(f"Capability `{name}` is degraded: {reason}.")

        if recent_failures:
            failure_kind = str(recent_failures[0].get("failure_kind") or "unknown")
            actions.append(
                f"Start with the most frequent recent failure kind: `{failure_kind}`."
            )

        deduped: list[str] = []
        for action in actions:
            if action not in deduped:
                deduped.append(action)
        return deduped[:8]


AIRuntimeDiagnosticsService = RuntimeDiagnosticsService


__all__ = [
    "AIRuntimeDiagnosticsService",
    "RuntimeDiagnosticsService",
]
