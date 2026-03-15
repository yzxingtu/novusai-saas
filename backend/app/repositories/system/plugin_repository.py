"""
插件 Repository / Plugin Repository

提供插件及企业分配的数据访问。
Provides plugin and tenant assignment data access.
"""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.base_repository import BaseRepository
from app.enums.plugin import PluginStatusEnum
from app.models.system.plugin import Plugin
from app.models.system.resource_tenant_assignment import ResourceTenantAssignment


class PluginRepository(BaseRepository[Plugin]):
    """插件数据访问 / Plugin data access repository."""

    model = Plugin

    async def get_by_name(self, name: str) -> Plugin | None:
        """根据唯一标识查询插件 / Get plugin by unique name."""
        result = await self.db.execute(
            select(Plugin).where(
                Plugin.name == name,
                Plugin.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def list_enabled(self) -> list[Plugin]:
        """查询所有已启用的插件 / List all enabled plugins."""
        result = await self.db.execute(
            select(Plugin).where(
                Plugin.status == PluginStatusEnum.ENABLED.value,
                Plugin.is_deleted.is_(False),
            ).order_by(Plugin.name)
        )
        return list(result.scalars().all())

    async def get_with_versions(self, plugin_id: int) -> Plugin | None:
        """查询插件并加载版本历史 / Get plugin with version history."""
        result = await self.db.execute(
            select(Plugin)
            .options(selectinload(Plugin.versions))
            .where(
                Plugin.id == plugin_id,
                Plugin.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def get_tenant_assignments(
        self, plugin_id: int
    ) -> list[ResourceTenantAssignment]:
        """查询插件的企业分配列表（仅返回未软删除的分配） / Get plugin tenant assignments (excl. soft-deleted)."""
        result = await self.db.execute(
            select(ResourceTenantAssignment).where(
                ResourceTenantAssignment.resource_type == "plugin",
                ResourceTenantAssignment.resource_id == plugin_id,
                ResourceTenantAssignment.is_deleted.is_(False),
            )
        )
        return list(result.scalars().all())

    async def get_all_except(self, exclude_name: str) -> list[Plugin]:
        """查询除指定插件外的所有插件（引用计数用） / Get all plugins except one (for ref count)."""
        result = await self.db.execute(
            select(Plugin).where(
                Plugin.name != exclude_name,
                Plugin.is_deleted.is_(False),
            )
        )
        return list(result.scalars().all())
