"""
租户用户角色仓储

提供租户用户角色的数据访问操作（租户隔离），扁平结构无层级
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.core.base_repository import TenantRepository
from app.models.auth.tenant_user_role import TenantUserRole


class TenantUserRoleRepository(TenantRepository[TenantUserRole]):
    """
    租户用户角色仓储

    提供租户用户角色特有的数据访问方法，自动过滤租户 ID
    """

    model = TenantUserRole

    async def get_by_code(self, code: str) -> TenantUserRole | None:
        """
        根据代码获取角色（租户内）

        Args:
            code: 角色代码

        Returns:
            角色实例或 None
        """
        return await self.get_one_by(code=code, tenant_id=self.tenant_id)

    async def code_exists(
        self,
        code: str,
        exclude_id: int | None = None,
    ) -> bool:
        """
        检查角色代码是否已存在（租户内唯一）

        Args:
            code: 角色代码
            exclude_id: 排除的 ID

        Returns:
            是否存在
        """
        query = select(self.model.id).where(
            self.model.tenant_id == self.tenant_id,
            self.model.code == code,
            self.model.is_deleted.is_(False),
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def name_exists(
        self,
        name: str,
        exclude_id: int | None = None,
    ) -> bool:
        """
        检查角色名称是否已存在（租户内唯一）

        Args:
            name: 角色名称
            exclude_id: 排除的 ID

        Returns:
            是否存在
        """
        query = select(self.model.id).where(
            self.model.tenant_id == self.tenant_id,
            self.model.name == name,
            self.model.is_deleted.is_(False),
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def count_users(self, role_id: int) -> int:
        """
        统计角色下的用户数量

        Args:
            role_id: 角色 ID

        Returns:
            用户数量
        """
        from app.models.tenant.tenant_user import TenantUser

        query = select(func.count(TenantUser.id)).where(
            TenantUser.tenant_id == self.tenant_id,
            TenantUser.role_id == role_id,
            TenantUser.is_deleted.is_(False),
        )

        result = await self.db.execute(query)
        return result.scalar() or 0


__all__ = ["TenantUserRoleRepository"]
