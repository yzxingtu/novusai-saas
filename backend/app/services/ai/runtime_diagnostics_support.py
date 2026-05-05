"""
Runtime diagnostics health-check helpers.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from kombu import Connection
from redis.asyncio import Redis

from app.core.config import settings
from app.core.database import check_database_connection
from app.core.logging import get_logger
from app.core.redis import RedisManager

logger = get_logger(__name__)


class RuntimeDiagnosticsCheckSupport:
    """Build diagnostics checks without bloating the facade."""

    @staticmethod
    def build_check_item(
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

    async def check_database(self) -> dict[str, Any]:
        healthy = await check_database_connection()
        return self.build_check_item(
            "database",
            status="available" if healthy else "unavailable",
            blocking=True,
            reason=None if healthy else "database_connection_failed",
        )

    async def check_redis(self) -> dict[str, Any]:
        try:
            await RedisManager.init()
            healthy = await RedisManager.health_check()
        except Exception as exc:
            logger.warning("Runtime doctor redis check failed: {}", exc)
            healthy = False
        return self.build_check_item(
            "redis",
            status="available" if healthy else "unavailable",
            blocking=True,
            reason=None if healthy else "redis_connection_failed",
        )

    async def check_celery_broker(self) -> dict[str, Any]:
        broker_url = settings.celery_broker_url
        if not broker_url:
            return self.build_check_item(
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
                return self.build_check_item(
                    "celery_broker",
                    status="degraded",
                    blocking=False,
                    reason="unsupported_broker_scheme_check",
                    metadata={"scheme": scheme or None},
                )
        except Exception as exc:
            logger.warning("Runtime doctor celery broker check failed: {}", exc)
            healthy = False

        return self.build_check_item(
            "celery_broker",
            status="available" if healthy else "unavailable",
            blocking=True,
            reason=None if healthy else "celery_broker_connection_failed",
            metadata={"scheme": scheme or None},
        )

    def build_manifest_checks(
        self,
        manifest: dict[str, Any],
        *,
        require_agent: bool,
    ) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        summary = dict(manifest.get("summary") or {})
        provider = dict(manifest.get("provider") or {})
        model = dict(manifest.get("model") or {})
        memory_items = list(manifest.get("memory") or [])
        kb_items = list(manifest.get("knowledge_bases") or [])

        if require_agent:
            checks.append(
                self.build_check_item(
                    "provider",
                    status=str(provider.get("status") or "unavailable"),
                    blocking=True,
                    reason=provider.get("reason"),
                    metadata={"provider": provider},
                )
            )
            checks.append(
                self.build_check_item(
                    "model",
                    status=str(model.get("status") or "unavailable"),
                    blocking=True,
                    reason=model.get("reason"),
                    metadata={"model": model},
                )
            )
        elif provider.get("id") or model.get("id"):
            checks.append(
                self.build_check_item(
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
        inventory_tool_count = int(summary.get("inventory_tool_count") or 0)
        effective_tool_count = max(tool_count, inventory_tool_count)
        skill_count = int(summary.get("skill_count") or 0)
        inventory_skill_count = int(summary.get("inventory_skill_count") or 0)
        effective_skill_count = max(skill_count, inventory_skill_count)
        checks.append(
            self.build_check_item(
                "tools",
                status="available" if effective_tool_count > 0 else "degraded",
                blocking=False,
                reason=None if effective_tool_count > 0 else "no_runtime_tools_exposed",
                metadata={
                    "tool_count": tool_count,
                    "inventory_tool_count": inventory_tool_count,
                    "selection_live": bool(summary.get("selection_live")),
                },
            )
        )
        checks.append(
            self.build_check_item(
                "skills",
                status="available" if effective_skill_count > 0 else "degraded",
                blocking=False,
                reason=None
                if effective_skill_count > 0
                else "no_runtime_skills_selected",
                metadata={
                    "skill_count": skill_count,
                    "inventory_skill_count": inventory_skill_count,
                    "selection_live": bool(summary.get("selection_live")),
                },
            )
        )

        kb_available_count = len(
            [item for item in kb_items if item.get("status") == "available"]
        )
        checks.append(
            self.build_check_item(
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
            self.build_check_item(
                "memory",
                status=memory_status,
                blocking=False,
                reason=memory_reason,
            )
        )

        return checks


__all__ = ["RuntimeDiagnosticsCheckSupport"]
