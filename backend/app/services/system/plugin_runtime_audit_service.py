"""
Plugin runtime lifecycle audit service / 插件运行态生命周期审计服务。

Read-only snapshot audit only. / 仅提供只读快照审计。
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.system.plugin import Plugin
from app.models.system.resource_tenant_assignment import ResourceTenantAssignment
from app.plugins._extension_registrar import get_failed_extensions
from app.plugins.health import PluginHealthMonitor
from app.plugins.runtime_gate import evaluate_plugin_runtime_gate
from app.schemas.ai.plugin_runtime_audit import (
    ExtensionLifecycleAuditReport,
    ExtensionLifecycleAuditStageResult,
    ExtensionLifecycleExposedCapability,
    ExtensionLifecycleRecentFailure,
)
from app.services.system.plugin_service import PluginService

logger = get_logger(__name__)


class PluginRuntimeAuditService:
    """Assemble read-only plugin lifecycle audit snapshots."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._plugin_service = PluginService(db)
        self._health_monitor = PluginHealthMonitor(db)

    async def build_plugin_audit_report(
        self,
        *,
        plugin: Plugin,
        tenant_id: int | None = None,
    ) -> ExtensionLifecycleAuditReport:
        dependency_status = await self._plugin_service.get_dependency_status(plugin)
        recovery_state = self._plugin_service.get_recovery_state(
            plugin,
            dependency_status=dependency_status,
        )
        health_status = await self._health_monitor.get_health_status(plugin.name)
        gate = await evaluate_plugin_runtime_gate(
            self.db,
            plugin.name,
            tenant_id=tenant_id,
            require_enabled=False,
            enforce_scope=tenant_id is not None,
        )
        assignment_summary = await self._build_assignment_summary(plugin.id)

        stage_results = self._build_stage_results(
            plugin=plugin,
            dependency_status=dependency_status,
            recovery_state=recovery_state,
            health_status=health_status,
            gate_result=gate,
        )
        recent_failures = self._build_recent_failures(
            plugin=plugin,
            health_status=health_status,
            dependency_status=dependency_status,
            registrar_failures=get_failed_extensions(plugin.name),
        )
        exposed_capabilities = self._build_exposed_capabilities(
            plugin=plugin,
            gate_reason=gate.reason_code,
            dependency_status=dependency_status,
            health_status=health_status,
            assignment_summary=assignment_summary,
        )
        recovery_actions = self._build_recovery_actions(recovery_state)
        degraded_reason = self._resolve_degraded_reason(
            stage_results=stage_results,
            fallback_reason=recovery_state.get("reason"),
        )

        return ExtensionLifecycleAuditReport(
            runtime_kind="plugin",
            target={
                "plugin_id": plugin.id,
                "plugin_name": plugin.name,
                "display_name": plugin.display_name,
                "version": plugin.version,
                "scope": plugin.scope,
                "status": plugin.status,
                "enabled_at": plugin.enabled_at,
                "tenant_scope": assignment_summary,
                "gate": {
                    "allowed": gate.allowed,
                    "reason_code": gate.reason_code,
                    "plugin_scope": gate.plugin_scope,
                    "plugin_status": gate.plugin_status,
                    "license_status": gate.license_status,
                },
                "extensions_summary": self._build_extensions_summary(plugin.manifest),
            },
            stage_results=stage_results,
            degraded_reason=degraded_reason,
            recovery_actions=recovery_actions,
            exposed_capabilities=exposed_capabilities,
            recent_failures=recent_failures,
        )

    async def list_plugin_audit_reports(
        self,
        *,
        plugin_name: str | None = None,
        plugin_id: int | None = None,
        tenant_id: int | None = None,
        limit: int = 50,
    ) -> list[ExtensionLifecycleAuditReport]:
        stmt: Select[tuple[Plugin]] = select(Plugin).where(Plugin.is_deleted.is_(False))
        if plugin_id is not None:
            stmt = stmt.where(Plugin.id == int(plugin_id))
        if plugin_name:
            stmt = stmt.where(Plugin.name == plugin_name.strip())
        stmt = stmt.order_by(Plugin.id.desc()).limit(max(1, min(int(limit), 200)))
        rows = await self.db.execute(stmt)
        plugins = list(rows.scalars().all())
        return [
            await self.build_plugin_audit_report(plugin=plugin, tenant_id=tenant_id)
            for plugin in plugins
        ]

    async def _build_assignment_summary(self, plugin_id: int) -> dict[str, Any]:
        stmt = select(
            func.count(ResourceTenantAssignment.id).label("total"),
            func.count(
                ResourceTenantAssignment.id
            ).filter(ResourceTenantAssignment.is_active.is_(True)).label("active"),
        ).where(
            ResourceTenantAssignment.resource_type == "plugin",
            ResourceTenantAssignment.resource_id == plugin_id,
            ResourceTenantAssignment.is_deleted.is_(False),
        )
        row = (await self.db.execute(stmt)).one()
        total = int(row.total or 0)
        active = int(row.active or 0)
        return {"total_assignments": total, "active_assignments": active}

    @staticmethod
    def _build_extensions_summary(manifest: Any) -> dict[str, Any]:
        if not isinstance(manifest, Mapping):
            return {"declared": False}
        extensions = manifest.get("extensions")
        if not isinstance(extensions, Mapping):
            return {"declared": False}
        counts: dict[str, int] = {}
        for key, value in extensions.items():
            counts[str(key)] = len(value) if isinstance(value, list) else 0
        return {
            "declared": True,
            "types": counts,
            "total": sum(counts.values()),
            "mcp": {
                "runtime_status": "not_implemented",
                "enabled": False,
                "transport": None,
                "server_ref": None,
                "declared_tools": 0,
                "declared_resources": 0,
                "declared_prompts": 0,
            },
        }

    @staticmethod
    def _stage_status(ok: bool, *, degraded: bool = False) -> str:
        if ok:
            return "degraded" if degraded else "available"
        return "unavailable"

    def _build_stage_results(
        self,
        *,
        plugin: Plugin,
        dependency_status: Mapping[str, Any],
        recovery_state: Mapping[str, Any],
        health_status: Mapping[str, Any],
        gate_result: Any,
    ) -> list[ExtensionLifecycleAuditStageResult]:
        manifest = plugin.manifest if isinstance(plugin.manifest, dict) else {}
        extensions = manifest.get("extensions") if isinstance(manifest, dict) else None
        dependencies_ready = dependency_status.get("overall") == "installed"
        needs_attention = bool(recovery_state.get("needs_attention"))
        error_count = int(health_status.get("error_count") or 0)
        threshold = int(health_status.get("auto_disable_threshold") or 10)

        return [
            ExtensionLifecycleAuditStageResult(
                stage="discovery",
                status="available",
                reason=None,
                metadata={"plugin_name": plugin.name, "plugin_id": plugin.id},
            ),
            ExtensionLifecycleAuditStageResult(
                stage="manifest_validation",
                status=self._stage_status(
                    isinstance(manifest, dict) and bool(manifest),
                    degraded=not bool(extensions),
                ),
                reason=None if bool(extensions) else "extensions_block_missing_or_empty",
                metadata={"manifest_keys": sorted(manifest.keys())},
            ),
            ExtensionLifecycleAuditStageResult(
                stage="registration",
                status=self._stage_status(
                    plugin.status in {"enabled", "installed"},
                    degraded=plugin.status == "error",
                ),
                reason=(
                    None
                    if plugin.status in {"enabled", "installed"}
                    else f"plugin_status_{plugin.status}"
                ),
                metadata={"plugin_status": plugin.status},
            ),
            ExtensionLifecycleAuditStageResult(
                stage="enable_gate",
                status=self._stage_status(gate_result.allowed, degraded=not gate_result.allowed),
                reason=None if gate_result.allowed else gate_result.reason_code,
                metadata={
                    "gate_reason_code": gate_result.reason_code,
                    "license_status": gate_result.license_status,
                },
            ),
            ExtensionLifecycleAuditStageResult(
                stage="runtime_health",
                status=self._stage_status(
                    plugin.status != "error" and error_count == 0,
                    degraded=error_count > 0 and plugin.status != "error",
                ),
                reason=(
                    "runtime_error_state"
                    if plugin.status == "error"
                    else ("consecutive_errors_detected" if error_count > 0 else None)
                ),
                metadata={
                    "error_count": error_count,
                    "auto_disable_threshold": threshold,
                    "error_message": health_status.get("error_message"),
                },
            ),
            ExtensionLifecycleAuditStageResult(
                stage="degraded_mode",
                status="degraded" if needs_attention else "available",
                reason=(str(recovery_state.get("reason") or "") or None),
                metadata=dict(recovery_state),
            ),
            ExtensionLifecycleAuditStageResult(
                stage="recovery",
                status=(
                    "degraded"
                    if needs_attention and bool(recovery_state.get("primary_action"))
                    else ("available" if dependencies_ready else "degraded")
                ),
                reason=(
                    "recovery_action_recommended"
                    if recovery_state.get("primary_action")
                    else (None if dependencies_ready else "dependencies_missing")
                ),
                metadata={
                    "primary_action": recovery_state.get("primary_action"),
                    "secondary_actions": list(
                        recovery_state.get("secondary_actions") or []
                    ),
                },
            ),
            ExtensionLifecycleAuditStageResult(
                stage="disable_cleanup",
                status="available",
                reason=None,
                metadata={
                    "plugin_status": plugin.status,
                    "supports_force_cleanup": True,
                },
            ),
        ]

    def _build_recent_failures(
        self,
        *,
        plugin: Plugin,
        health_status: Mapping[str, Any],
        dependency_status: Mapping[str, Any],
        registrar_failures: list[dict[str, str]],
    ) -> list[ExtensionLifecycleRecentFailure]:
        items: list[ExtensionLifecycleRecentFailure] = []
        error_message = str(health_status.get("error_message") or "").strip()
        if error_message:
            items.append(
                ExtensionLifecycleRecentFailure(
                    source="runtime_health",
                    code="plugin_error_message",
                    message=error_message,
                    occurred_at=plugin.updated_at,
                )
            )

        if dependency_status.get("overall") != "installed":
            missing_python = (
                dependency_status.get("python", {}).get("missing", [])
                if isinstance(dependency_status.get("python"), dict)
                else []
            )
            missing_plugins = (
                dependency_status.get("plugins", {}).get("missing", [])
                if isinstance(dependency_status.get("plugins"), dict)
                else []
            )
            if missing_python:
                items.append(
                    ExtensionLifecycleRecentFailure(
                        source="dependency",
                        code="missing_python_dependencies",
                        message="; ".join(str(x) for x in missing_python[:5]),
                        occurred_at=plugin.updated_at,
                        metadata={"missing_count": len(missing_python)},
                    )
                )
            if missing_plugins:
                items.append(
                    ExtensionLifecycleRecentFailure(
                        source="dependency",
                        code="missing_plugin_dependencies",
                        message="; ".join(str(x) for x in missing_plugins[:5]),
                        occurred_at=plugin.updated_at,
                        metadata={"missing_count": len(missing_plugins)},
                    )
                )

        for failed in registrar_failures[:10]:
            items.append(
                ExtensionLifecycleRecentFailure(
                    source="registrar",
                    code=f"extension_load_failed:{failed.get('type') or 'unknown'}",
                    message=str(failed.get("entry_point") or ""),
                    occurred_at=plugin.updated_at,
                    metadata={"extension_type": failed.get("type")},
                )
            )
        return items

    def _build_exposed_capabilities(
        self,
        *,
        plugin: Plugin,
        gate_reason: str,
        dependency_status: Mapping[str, Any],
        health_status: Mapping[str, Any],
        assignment_summary: Mapping[str, Any],
    ) -> list[ExtensionLifecycleExposedCapability]:
        manifest = plugin.manifest if isinstance(plugin.manifest, dict) else {}
        extensions = manifest.get("extensions") if isinstance(manifest, dict) else {}
        extension_items: list[ExtensionLifecycleExposedCapability] = []

        for cap in plugin.granted_capabilities or []:
            name = str(cap or "").strip()
            if not name:
                continue
            extension_items.append(
                ExtensionLifecycleExposedCapability(
                    name=name,
                    kind="granted_capability",
                    status="available"
                    if gate_reason == "allowed"
                    else "degraded",
                    reason=None if gate_reason == "allowed" else gate_reason,
                    source="plugin.granted_capabilities",
                )
            )

        if isinstance(extensions, Mapping):
            for key, raw in extensions.items():
                count = len(raw) if isinstance(raw, list) else 0
                extension_items.append(
                    ExtensionLifecycleExposedCapability(
                        name=f"extensions.{key}",
                        kind="plugin_extension",
                        status="available" if count > 0 else "degraded",
                        reason=None if count > 0 else "extension_empty",
                        metadata={"declared_count": count},
                        source="plugin.manifest.extensions",
                    )
                )

        extension_items.append(
            ExtensionLifecycleExposedCapability(
                name="dependency_chain",
                kind="runtime_dependency",
                status=(
                    "available"
                    if dependency_status.get("overall") == "installed"
                    else "degraded"
                ),
                reason=(
                    None
                    if dependency_status.get("overall") == "installed"
                    else "dependencies_missing"
                ),
                metadata=dict(dependency_status),
                source="dependency_status",
            )
        )
        extension_items.append(
            ExtensionLifecycleExposedCapability(
                name="runtime_health",
                kind="health_probe",
                status=(
                    "available"
                    if int(health_status.get("error_count") or 0) == 0
                    else "degraded"
                ),
                reason=(
                    None
                    if int(health_status.get("error_count") or 0) == 0
                    else "error_count_above_zero"
                ),
                metadata=dict(health_status),
                source="plugin_health_monitor",
            )
        )
        extension_items.append(
            ExtensionLifecycleExposedCapability(
                name="tenant_assignment",
                kind="scope_assignment",
                status="available",
                reason=None,
                metadata=dict(assignment_summary),
                source="resource_tenant_assignments",
            )
        )
        extension_items.append(
            ExtensionLifecycleExposedCapability(
                name="extensions.mcp",
                kind="mcp_declared",
                status="not_implemented",
                reason="mcp_runtime_not_implemented",
                metadata={
                    "runtime_status": "not_implemented",
                    "declared_tools": 0,
                    "declared_resources": 0,
                    "declared_prompts": 0,
                },
                source="manifest_projection",
            )
        )
        return extension_items

    @staticmethod
    def _build_recovery_actions(recovery_state: Mapping[str, Any]) -> list[str]:
        actions: list[str] = []
        primary = str(recovery_state.get("primary_action") or "").strip()
        if primary:
            actions.append(primary)
        for action in recovery_state.get("secondary_actions") or []:
            text = str(action or "").strip()
            if text and text not in actions:
                actions.append(text)
        return actions

    @staticmethod
    def _resolve_degraded_reason(
        *,
        stage_results: list[ExtensionLifecycleAuditStageResult],
        fallback_reason: Any,
    ) -> str | None:
        for stage in stage_results:
            if stage.status in {"degraded", "unavailable"}:
                if stage.reason:
                    return stage.reason
                return f"{stage.stage}_degraded"
        fallback = str(fallback_reason or "").strip()
        return fallback or None


__all__ = ["PluginRuntimeAuditService"]
