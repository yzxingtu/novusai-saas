"""
插件 Repository
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.base_repository import BaseRepository
from app.enums.plugin import PluginStatusEnum
from app.models.system.plugin import Plugin
from app.models.system.resource_tenant_assignment import ResourceTenantAssignment


class PluginRepository(BaseRepository[Plugin]):
    """插件数据访问"""

    model = Plugin

    async def get_by_name(self, name: str) -> Plugin | None:
        """根据唯一标识查询插件"""
        result = await self.db.execute(
            select(Plugin).where(
                Plugin.name == name,
                Plugin.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def list_enabled(self) -> list[Plugin]:
        """查询所有已启用的插件"""
        result = await self.db.execute(
            select(Plugin).where(
                Plugin.status == PluginStatusEnum.ENABLED.value,
                Plugin.is_deleted.is_(False),
            ).order_by(Plugin.name)
        )
        return list(result.scalars().all())

    async def get_with_versions(self, plugin_id: int) -> Plugin | None:
        """查询插件并加载版本历史"""
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
        """查询插件的租户分配列表"""
        result = await self.db.execute(
            select(ResourceTenantAssignment).where(
                ResourceTenantAssignment.resource_type == "plugin",
                ResourceTenantAssignment.resource_id == plugin_id,
            )
        )
        return list(result.scalars().all())

    async def get_all_except(self, exclude_name: str) -> list[Plugin]:
        """查询除指定插件外的所有插件（引用计数用）"""
        result = await self.db.execute(
            select(Plugin).where(
                Plugin.name != exclude_name,
                Plugin.is_deleted.is_(False),
            )
        )
        return list(result.scalars().all())
