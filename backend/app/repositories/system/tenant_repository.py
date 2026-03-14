"""
企业仓储 / Tenant Repository

提供企业的数据访问操作
Provides tenant data access operations.
"""

from sqlalchemy import select

from app.core.base_repository import BaseRepository
from app.models.tenant.tenant import Tenant


class TenantRepository(BaseRepository[Tenant]):
    """
    企业仓储

    提供企业特有的数据访问方法
    """

    model = Tenant

    # 不同 scope 下允许筛选的字段
    _scope_fields: dict[str, set[str]] = {
        "admin": {
            "id", "name", "code", "contact_name", "contact_phone",
            "contact_email", "is_active", "plan", "plan_id", "expires_at",
            "created_at", "updated_at",
        },
    }

    async def get_by_code(self, code: str) -> Tenant | None:
        """
        根据编码获取企业

        Args:
            code: 企业编码

        Returns:
            企业实例或 None
        """
        return await self.get_one_by(code=code)

    async def code_exists(self, code: str, exclude_id: int | None = None) -> bool:
        """
        检查编码是否已存在

        Args:
            code: 企业编码
            exclude_id: 排除的 ID

        Returns:
            是否存在
        """
        query = select(self.model.id).where(
            self.model.code == code,
            self.model.is_deleted.is_(False),
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def get_active_tenants(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Tenant]:
        """
        获取所有启用的企业

        Args:
            skip: 跳过的记录数
            limit: 返回的最大记录数

        Returns:
            企业列表
        """
        return await self.get_list(
            skip=skip,
            limit=limit,
            is_active=True,
        )

    async def count_active(self) -> int:
        """
        统计启用的企业数量

        Returns:
            企业数量
        """
        return await self.count(is_active=True)


__all__ = ["TenantRepository"]
