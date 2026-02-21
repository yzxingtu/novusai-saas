"""
插件租户分配仓储

提供插件租户分配记录的数据访问操作
"""

from sqlalchemy import delete, select

from app.core.base_repository import BaseRepository
from app.models.system.plugin_tenant_assignment import PluginTenantAssignment


class PluginTenantAssignmentRepository(BaseRepository[PluginTenantAssignment]):
    """
    插件租户分配仓储
    """

    model = PluginTenantAssignment

    _scope_fields = {
        "admin": {
            "id", "plugin_id", "tenant_id", "assigned_by", "assigned_at", "created_at",
        },
    }

    async def get_by_plugin_and_tenant(
        self, plugin_id: int, tenant_id: int
    ) -> PluginTenantAssignment | None:
        """根据插件 ID 和租户 ID 获取分配记录"""
        return await self.get_one_by(plugin_id=plugin_id, tenant_id=tenant_id)

    async def get_by_plugin(
        self, plugin_id: int
    ) -> list[PluginTenantAssignment]:
        """获取插件的所有租户分配记录"""
        return await self.get_list(limit=10000, plugin_id=plugin_id)

    async def get_by_tenant(
        self, tenant_id: int
    ) -> list[PluginTenantAssignment]:
        """获取租户被分配的所有插件记录"""
        return await self.get_list(limit=10000, tenant_id=tenant_id)

    async def get_assigned_tenant_ids(
        self, plugin_id: int
    ) -> list[int]:
        """获取插件已分配的租户 ID 列表"""
        stmt = select(self.model.tenant_id).where(
            self.model.plugin_id == plugin_id,
            self.model.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    async def is_assigned(
        self, plugin_id: int, tenant_id: int
    ) -> bool:
        """检查插件是否已分配给指定租户"""
        record = await self.get_by_plugin_and_tenant(plugin_id, tenant_id)
        return record is not None

    async def bulk_assign(
        self,
        plugin_id: int,
        tenant_ids: list[int],
        assigned_by: int | None = None,
    ) -> list[PluginTenantAssignment]:
        """批量分配插件给多个租户（跳过已分配的）"""
        created: list[PluginTenantAssignment] = []
        for tid in tenant_ids:
            existing = await self.get_by_plugin_and_tenant(plugin_id, tid)
            if existing:
                continue
            record = await self.create({
                "plugin_id": plugin_id,
                "tenant_id": tid,
                "assigned_by": assigned_by,
            })
            created.append(record)
        if created:
            await self.db.flush()
        return created

    async def bulk_unassign(
        self, plugin_id: int, tenant_ids: list[int]
    ) -> int:
        """批量取消分配（物理删除）"""
        stmt = delete(self.model).where(
            self.model.plugin_id == plugin_id,
            self.model.tenant_id.in_(tenant_ids),
        )
        result = await self.db.execute(stmt)
        return result.rowcount
