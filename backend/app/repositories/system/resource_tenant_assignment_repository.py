"""
资源-租户分配 Repository
"""

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.core.logging import LogManager
from app.models.system.resource_tenant_assignment import ResourceTenantAssignment

logger = LogManager.get_logger("app")


class ResourceTenantAssignmentRepository(BaseRepository[ResourceTenantAssignment]):
    """
    资源-租户分配 Repository

    提供通用的资源→租户分配 CRUD，支持所有需要「部分租户」作用域的资源类型。
    """

    model = ResourceTenantAssignment

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    async def check_assignment(
        self,
        resource_type: str,
        resource_id: int,
        tenant_id: int,
    ) -> bool:
        """
        检查资源是否已分配给指定租户

        Args:
            resource_type: 资源类型
            resource_id: 资源 ID
            tenant_id: 租户 ID

        Returns:
            是否已分配且启用
        """
        result = await self.db.execute(
            select(ResourceTenantAssignment.id).where(
                and_(
                    ResourceTenantAssignment.resource_type == resource_type,
                    ResourceTenantAssignment.resource_id == resource_id,
                    ResourceTenantAssignment.tenant_id == tenant_id,
                    ResourceTenantAssignment.is_active.is_(True),
                    ResourceTenantAssignment.is_deleted.is_(False),
                )
            )
        )
        return result.scalar_one_or_none() is not None

    async def assign(
        self,
        resource_type: str,
        resource_id: int,
        tenant_id: int,
        config: dict | None = None,
    ) -> ResourceTenantAssignment:
        """
        分配资源给租户

        如果已存在（包括已禁用的），则重新激活；否则创建新记录。

        Args:
            resource_type: 资源类型
            resource_id: 资源 ID
            tenant_id: 租户 ID
            config: 租户级配置（可选）

        Returns:
            分配记录
        """
        result = await self.db.execute(
            select(ResourceTenantAssignment).where(
                and_(
                    ResourceTenantAssignment.resource_type == resource_type,
                    ResourceTenantAssignment.resource_id == resource_id,
                    ResourceTenantAssignment.tenant_id == tenant_id,
                    ResourceTenantAssignment.is_deleted.is_(False),
                )
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.is_active = True
            if config is not None:
                existing.config = config
            await self.db.flush()
            return existing

        assignment = ResourceTenantAssignment(
            resource_type=resource_type,
            resource_id=resource_id,
            tenant_id=tenant_id,
            is_active=True,
            config=config,
        )
        self.db.add(assignment)
        await self.db.flush()
        return assignment

    async def unassign(
        self,
        resource_type: str,
        resource_id: int,
        tenant_id: int,
    ) -> bool:
        """
        取消资源分配（物理删除）

        Returns:
            是否成功删除
        """
        result = await self.db.execute(
            delete(ResourceTenantAssignment).where(
                and_(
                    ResourceTenantAssignment.resource_type == resource_type,
                    ResourceTenantAssignment.resource_id == resource_id,
                    ResourceTenantAssignment.tenant_id == tenant_id,
                )
            )
        )
        await self.db.flush()
        return result.rowcount > 0

    async def get_assigned_tenant_ids(
        self,
        resource_type: str,
        resource_id: int,
        active_only: bool = True,
    ) -> list[int]:
        """
        获取资源已分配的租户 ID 列表

        Args:
            resource_type: 资源类型
            resource_id: 资源 ID
            active_only: 是否仅返回启用的

        Returns:
            租户 ID 列表
        """
        conditions = [
            ResourceTenantAssignment.resource_type == resource_type,
            ResourceTenantAssignment.resource_id == resource_id,
            ResourceTenantAssignment.is_deleted.is_(False),
        ]
        if active_only:
            conditions.append(ResourceTenantAssignment.is_active.is_(True))

        result = await self.db.execute(
            select(ResourceTenantAssignment.tenant_id).where(and_(*conditions))
        )
        return list(result.scalars().all())

    async def get_assigned_resource_ids(
        self,
        resource_type: str,
        tenant_id: int,
        active_only: bool = True,
    ) -> list[int]:
        """
        获取租户可访问的资源 ID 列表

        Args:
            resource_type: 资源类型
            tenant_id: 租户 ID
            active_only: 是否仅返回启用的

        Returns:
            资源 ID 列表
        """
        conditions = [
            ResourceTenantAssignment.resource_type == resource_type,
            ResourceTenantAssignment.tenant_id == tenant_id,
            ResourceTenantAssignment.is_deleted.is_(False),
        ]
        if active_only:
            conditions.append(ResourceTenantAssignment.is_active.is_(True))

        result = await self.db.execute(
            select(ResourceTenantAssignment.resource_id).where(and_(*conditions))
        )
        return list(result.scalars().all())

    async def batch_assign(
        self,
        resource_type: str,
        resource_id: int,
        tenant_ids: list[int],
    ) -> int:
        """
        批量分配资源给多个租户

        Returns:
            新增分配数
        """
        existing_ids = set(
            await self.get_assigned_tenant_ids(resource_type, resource_id, active_only=False)
        )
        count = 0
        for tid in tenant_ids:
            if tid not in existing_ids:
                await self.assign(resource_type, resource_id, tid)
                count += 1
        return count

    async def batch_unassign(
        self,
        resource_type: str,
        resource_id: int,
        tenant_ids: list[int],
    ) -> int:
        """
        批量取消分配

        Returns:
            删除数
        """
        if not tenant_ids:
            return 0

        result = await self.db.execute(
            delete(ResourceTenantAssignment).where(
                and_(
                    ResourceTenantAssignment.resource_type == resource_type,
                    ResourceTenantAssignment.resource_id == resource_id,
                    ResourceTenantAssignment.tenant_id.in_(tenant_ids),
                )
            )
        )
        await self.db.flush()
        return result.rowcount

    async def sync_assignments(
        self,
        resource_type: str,
        resource_id: int,
        tenant_ids: list[int],
    ) -> dict[str, int]:
        """
        同步分配（替换模式：添加缺失的，移除多余的）

        Returns:
            {"added": N, "removed": N}
        """
        current = set(
            await self.get_assigned_tenant_ids(resource_type, resource_id, active_only=False)
        )
        target = set(tenant_ids)

        to_add = target - current
        to_remove = current - target

        added = 0
        for tid in to_add:
            await self.assign(resource_type, resource_id, tid)
            added += 1

        removed = 0
        if to_remove:
            removed = await self.batch_unassign(resource_type, resource_id, list(to_remove))

        return {"added": added, "removed": removed}

    async def delete_all_for_resource(
        self,
        resource_type: str,
        resource_id: int,
    ) -> int:
        """
        删除资源的所有分配记录（资源被删除时调用）

        Returns:
            删除数
        """
        result = await self.db.execute(
            delete(ResourceTenantAssignment).where(
                and_(
                    ResourceTenantAssignment.resource_type == resource_type,
                    ResourceTenantAssignment.resource_id == resource_id,
                )
            )
        )
        await self.db.flush()
        return result.rowcount


def assigned_resource_ids_subquery(resource_type: str, tenant_id: int):
    """
    构建「已分配给指定租户的资源 ID」子查询

    用于租户端 Repository 的 WHERE 子句，让 assigned_tenants / admin_and_assigned
    scope 的资源对被分配的租户可见。

    用法::

        from app.repositories.system.resource_tenant_assignment_repository import assigned_resource_ids_subquery

        subq = assigned_resource_ids_subquery("skill_package", self.tenant_id)
        query = query.where(
            or_(
                Model.tenant_id == self.tenant_id,
                Model.scope == ResourceScopeEnum.ADMIN_AND_ALL.value,
                and_(
                    Model.scope.in_([
                        ResourceScopeEnum.ASSIGNED_TENANTS.value,
                        ResourceScopeEnum.ADMIN_AND_ASSIGNED.value,
                    ]),
                    Model.id.in_(subq),
                ),
            )
        )
    """
    return (
        select(ResourceTenantAssignment.resource_id)
        .where(
            and_(
                ResourceTenantAssignment.resource_type == resource_type,
                ResourceTenantAssignment.tenant_id == tenant_id,
                ResourceTenantAssignment.is_deleted.is_(False),
                ResourceTenantAssignment.is_active.is_(True),
            )
        )
    ).scalar_subquery()


__all__ = ["ResourceTenantAssignmentRepository", "assigned_resource_ids_subquery"]
