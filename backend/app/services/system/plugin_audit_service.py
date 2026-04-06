"""
Plugin audit compatibility wrapper / 插件审计兼容包装服务。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import NotFoundException
from app.services.system.plugin_runtime_audit_service import PluginRuntimeAuditService
from app.services.system.plugin_service import PluginService


class PluginAuditService:
    """Compatibility surface expected by admin controllers."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._plugin_service = PluginService(db)
        self._runtime_service = PluginRuntimeAuditService(db)

    async def build_audit_report(
        self,
        *,
        scope: str = "admin",
        plugin_id: int | None = None,
        tenant_id: int | None = None,
        plugin: str | None = None,
    ) -> dict[str, Any]:
        del scope
        if plugin_id is None and not str(plugin or "").strip():
            reports = await self._runtime_service.list_plugin_audit_reports(
                tenant_id=tenant_id,
            )
            return {
                "items": [report.model_dump() for report in reports],
                "total": len(reports),
            }

        target = None
        if plugin_id is not None:
            target = await self._plugin_service.get_by_id(int(plugin_id))
        elif plugin:
            reports = await self._runtime_service.list_plugin_audit_reports(
                plugin_name=str(plugin).strip(),
                tenant_id=tenant_id,
                limit=1,
            )
            if reports:
                return reports[0].model_dump()

        if target is None:
            raise NotFoundException(message="Plugin not found")

        report = await self._runtime_service.build_plugin_audit_report(
            plugin=target,
            tenant_id=tenant_id,
        )
        return report.model_dump()


__all__ = ["PluginAuditService"]
