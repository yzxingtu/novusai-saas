"""
Unified AI runtime diagnostics service / 统一 AI runtime 诊断服务。
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from kombu import Connection
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import check_database_connection
from app.core.logging import get_logger
from app.core.redis import RedisManager
from app.enums.ai import CallStatusEnum
from app.exceptions import NotFoundException
from app.models.ai.call_log import AICallLog
from app.services.ai.monitoring_read_model_projector import (
    MonitoringReadModelProjector,
)
from app.services.ai.runtime_diagnostics_query_service import (
    RuntimeDiagnosticsQueryService,
)
from app.services.ai.runtime_inventory_service import RuntimeInventoryService
from app.services.ai.runtime_root_cause_projector import RuntimeRootCauseProjector
from app.services.ai.skill_registry_service import SkillRegistryService

logger = get_logger(__name__)


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
        conversation_turn = None
        call_log: AICallLog | None = None

        if conversation_id is not None and turn is not None:
            conversation_turn = await self._resolve_conversation_turn(
                conversation_id=conversation_id,
                turn=turn,
            )
            if call_log_id is not None or trace_id:
                call_log = await self._resolve_call_log(
                    trace_id=trace_id,
                    call_log_id=call_log_id,
                    conversation_id=None,
                    turn=None,
                )
            else:
                call_log = await self._resolve_related_call_log_for_conversation_turn(
                    conversation_id=conversation_id,
                    turn=turn,
                )
        else:
            call_log = await self._resolve_call_log(
                trace_id=trace_id,
                call_log_id=call_log_id,
                conversation_id=conversation_id,
                turn=turn,
            )

        if call_log is None and conversation_turn is None:
            raise NotFoundException(message="AI call log not found")

        call_log_diagnostics = (
            MonitoringReadModelProjector.extract_call_trace_diagnostics(
                call_log.request_metadata
            )
            if call_log is not None
            else {}
        )
        conversation_diagnostics = (
            dict(conversation_turn.get("diagnostics") or {})
            if isinstance(conversation_turn, dict)
            else {}
        )
        diagnostics = self._merge_root_cause_diagnostics(
            conversation_diagnostics=conversation_diagnostics,
            call_log_diagnostics=call_log_diagnostics,
        )
        failure_layer, cause_code, summary, first_fix, confidence = (
            self._classify_root_cause(
                call_log=call_log,
                diagnostics=diagnostics,
                conversation_turn=conversation_turn,
            )
        )
        recovered_via_retry = bool(
            diagnostics.get("recovered_via_retry")
            or any(
                bool(event.get("recovered"))
                for event in (diagnostics.get("retry_events") or [])
                if isinstance(event, dict)
            )
        )
        status = self._resolve_root_cause_status(
            call_log=call_log,
            diagnostics=diagnostics,
            conversation_turn=conversation_turn,
        )
        return {
            "status": status,
            "failure_layer": failure_layer,
            "cause_code": cause_code,
            "summary": summary,
            "evidence": self._build_root_cause_evidence(
                call_log,
                diagnostics,
                conversation_turn=conversation_turn,
            ),
            "first_fix": first_fix,
            "confidence": confidence,
            "recovered_via_retry": recovered_via_retry,
            "related_ids": {
                "call_log_id": call_log.id if call_log is not None else None,
                "trace_id": call_log.trace_id if call_log is not None else None,
                "conversation_id": (
                    conversation_id
                    or (call_log.conversation_id if call_log is not None else None)
                ),
                "conversation_message_id": (
                    conversation_turn.get("message_id")
                    if isinstance(conversation_turn, dict)
                    else None
                ),
                "agent_id": call_log.agent_id if call_log is not None else None,
                "provider_id": call_log.provider_id if call_log is not None else None,
                "model_id": call_log.model_id if call_log is not None else None,
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
        return await RuntimeDiagnosticsQueryService(self).aggregate_recent_failures(
            tenant_id=tenant_id
        )

    @staticmethod
    def _is_failed_call(log: AICallLog, diagnostics: dict[str, Any]) -> bool:
        if str(diagnostics.get("conversation_outcome") or "") in {
            "failed",
            "partial",
        }:
            return True
        if str(log.status or "") != CallStatusEnum.SUCCESS.value:
            return True
        if str(diagnostics.get("turn_outcome") or "") in {
            "failed",
            "partial",
            "tool_round_failed",
        }:
            return True
        return str(diagnostics.get("failure_kind") or "").strip() not in {"", "none"}

    @classmethod
    def _merge_root_cause_diagnostics(
        cls,
        *,
        conversation_diagnostics: dict[str, Any],
        call_log_diagnostics: dict[str, Any],
    ) -> dict[str, Any]:
        return RuntimeRootCauseProjector.merge_root_cause_diagnostics(
            conversation_diagnostics=conversation_diagnostics,
            call_log_diagnostics=call_log_diagnostics,
        )

    async def _resolve_conversation_turn(
        self,
        *,
        conversation_id: int,
        turn: int,
    ) -> dict[str, Any]:
        return await RuntimeDiagnosticsQueryService(self).resolve_conversation_turn(
            conversation_id=conversation_id,
            turn=turn,
        )

    async def _resolve_related_call_log_for_conversation_turn(
        self,
        *,
        conversation_id: int,
        turn: int,
    ) -> AICallLog | None:
        return await RuntimeDiagnosticsQueryService(
            self
        ).resolve_related_call_log_for_conversation_turn(
            conversation_id=conversation_id,
            turn=turn,
        )

    async def _resolve_call_log(
        self,
        *,
        trace_id: str | None,
        call_log_id: int | None,
        conversation_id: int | None,
        turn: int | None,
    ) -> AICallLog:
        return await RuntimeDiagnosticsQueryService(self).resolve_call_log(
            trace_id=trace_id,
            call_log_id=call_log_id,
            conversation_id=conversation_id,
            turn=turn,
        )

    @staticmethod
    def _resolve_root_cause_status(
        *,
        call_log: AICallLog | None,
        diagnostics: dict[str, Any],
        conversation_turn: dict[str, Any] | None,
    ) -> str:
        return RuntimeRootCauseProjector.resolve_root_cause_status(
            call_log=call_log,
            diagnostics=diagnostics,
            conversation_turn=conversation_turn,
        )

    def _classify_root_cause(
        self,
        *,
        call_log: AICallLog | None,
        diagnostics: dict[str, Any],
        conversation_turn: dict[str, Any] | None,
    ) -> tuple[str | None, str | None, str, str | None, float | None]:
        return RuntimeRootCauseProjector.classify_root_cause(
            call_log=call_log,
            diagnostics=diagnostics,
            conversation_turn=conversation_turn,
        )

    @staticmethod
    def _build_root_cause_evidence(
        call_log: AICallLog | None,
        diagnostics: dict[str, Any],
        *,
        conversation_turn: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        return RuntimeRootCauseProjector.build_root_cause_evidence(
            call_log,
            diagnostics,
            conversation_turn=conversation_turn,
        )

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
