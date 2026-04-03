"""
插件托管智能体同步服务 / Plugin-managed agent sync service

让带有 source_plugin 的平台智能体在作用域与企业分配上始终跟随来源插件。
Keep source_plugin-backed platform agents aligned with their source plugin
scope and tenant assignments.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select

from app.core.i18n import _
from app.core.logging import get_logger
from app.enums.common import ResourceScopeEnum
from app.enums.plugin import PluginStatusEnum
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent import Agent
from app.models.system.plugin import Plugin
from app.repositories.system.plugin_repository import PluginRepository
from app.repositories.system.resource_tenant_assignment_repository import (
    ResourceTenantAssignmentRepository,
)

logger = get_logger(__name__)

_EXPLICIT_ASSIGNMENT_SCOPES = {
    ResourceScopeEnum.SELECTED_TENANTS.value,
    ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
}
_NO_ASSIGNMENT_SCOPES = {
    ResourceScopeEnum.ADMIN_ONLY.value,
    ResourceScopeEnum.GLOBAL_SHARED.value,
    ResourceScopeEnum.ALL_TENANTS.value,
}


@dataclass(slots=True, frozen=True)
class SourcePluginInfo:
    id: int
    name: str
    display_name: str
    enabled: bool
    scope: str


class PluginManagedAgentSyncService:
    """同步插件托管智能体与来源插件的分发规则 / Sync plugin-managed agents."""

    def __init__(self, db) -> None:
        self.db = db
        self._plugin_repo = PluginRepository(db)
        self._assignment_repo = ResourceTenantAssignmentRepository(db)

    async def get_source_plugin_map(
        self,
        plugin_names: Iterable[str],
    ) -> dict[str, SourcePluginInfo]:
        normalized = sorted(
            {
                str(name).strip()
                for name in plugin_names
                if name is not None and str(name).strip()
            }
        )
        if not normalized:
            return {}

        result = await self.db.execute(
            select(
                Plugin.id,
                Plugin.name,
                Plugin.display_name,
                Plugin.scope,
                Plugin.status,
            ).where(
                Plugin.name.in_(normalized),
                Plugin.is_deleted.is_(False),
            )
        )

        return {
            row.name: SourcePluginInfo(
                id=row.id,
                name=row.name,
                display_name=row.display_name,
                enabled=row.status == PluginStatusEnum.ENABLED.value,
                scope=row.scope,
            )
            for row in result.all()
        }

    async def sync_from_agent_update(
        self,
        agent: Agent,
        tenant_ids: list[int] | None,
    ) -> list[int]:
        """按智能体页提交的 tenant_ids 同步插件与智能体分配 / Sync from agent-side edits."""
        plugin = await self._require_source_plugin(agent.source_plugin)
        if tenant_ids is None:
            target_tenant_ids = await self._get_assigned_tenant_ids("plugin", plugin.id)
        else:
            target_tenant_ids = self._normalize_tenant_ids(plugin.scope, tenant_ids)
            await self._assignment_repo.sync_assignments(
                "plugin",
                plugin.id,
                target_tenant_ids,
            )

        await self._apply_agent_distribution(
            agent,
            target_scope=plugin.scope,
            tenant_ids=target_tenant_ids,
        )
        return target_tenant_ids

    async def sync_agents_for_plugin(self, plugin_id: int) -> int:
        """插件分配变化后，镜像同步所有来源智能体 / Mirror plugin assignment changes back to agents."""
        plugin = await self._plugin_repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(message=_("plugin.error.not_found"))

        target_tenant_ids = await self._get_assigned_tenant_ids("plugin", plugin.id)
        result = await self.db.execute(
            select(Agent).where(
                Agent.source_plugin == plugin.name,
                Agent.is_deleted.is_(False),
            )
        )
        agents = list(result.scalars().all())
        for agent in agents:
            await self._apply_agent_distribution(
                agent,
                target_scope=plugin.scope,
                tenant_ids=target_tenant_ids,
            )
        return len(agents)

    async def get_effective_agent_assignment_ids(self, agent: Agent) -> list[int]:
        """获取插件托管智能体的最终企业分配 / Get effective tenant assignments for an agent."""
        if not getattr(agent, "source_plugin", None):
            return await self._get_assigned_tenant_ids("agent", agent.id)

        plugin = await self._get_source_plugin(agent.source_plugin)
        if not plugin:
            return await self._get_assigned_tenant_ids("agent", agent.id)
        return await self._get_assigned_tenant_ids("plugin", plugin.id)

    async def _apply_agent_distribution(
        self,
        agent: Agent,
        *,
        target_scope: str,
        tenant_ids: list[int],
    ) -> None:
        normalized_tenant_ids = self._normalize_tenant_ids(target_scope, tenant_ids)
        if agent.scope != target_scope:
            agent.scope = target_scope
            logger.info(
                "Aligned plugin-managed agent scope with source plugin: agent_id={} source_plugin={} scope={}",
                agent.id,
                agent.source_plugin,
                target_scope,
            )
        await self._assignment_repo.sync_assignments(
            "agent",
            agent.id,
            normalized_tenant_ids,
        )

    async def _get_source_plugin(self, plugin_name: str | None) -> Plugin | None:
        normalized = str(plugin_name or "").strip()
        if not normalized:
            return None
        return await self._plugin_repo.get_by_name(normalized)

    async def _require_source_plugin(self, plugin_name: str | None) -> Plugin:
        plugin = await self._get_source_plugin(plugin_name)
        if not plugin:
            raise NotFoundException(message=_("plugin.error.not_found"))
        return plugin

    async def _get_assigned_tenant_ids(
        self,
        resource_type: str,
        resource_id: int,
    ) -> list[int]:
        tenant_ids = await self._assignment_repo.get_assigned_tenant_ids(
            resource_type,
            resource_id,
        )
        return sorted({int(tenant_id) for tenant_id in tenant_ids})

    @staticmethod
    def _normalize_tenant_ids(scope: str | None, tenant_ids: list[int] | None) -> list[int]:
        scope_value = str(scope or "").strip()
        normalized_ids = sorted(
            {
                int(tenant_id)
                for tenant_id in (tenant_ids or [])
                if isinstance(tenant_id, int) and tenant_id > 0
            }
        )

        if scope_value in _EXPLICIT_ASSIGNMENT_SCOPES:
            return normalized_ids
        if normalized_ids:
            raise BusinessException(
                message=_("plugin.error.scope_disallows_tenant_assignment").format(
                    scope=scope_value or "-",
                )
            )
        if scope_value in _NO_ASSIGNMENT_SCOPES or not scope_value:
            return []
        return normalized_ids


__all__ = ["PluginManagedAgentSyncService", "SourcePluginInfo"]
