"""
企业域名仓储 / Tenant Domain Repository

提供企业域名的数据访问操作（平台级，非企业隔离）
Provides tenant domain data access (platform-level, no tenant isolation).
"""

from sqlalchemy import asc, select

from app.core.base_repository import BaseRepository
from app.models.tenant.tenant_domain import TenantDomain


class TenantDomainRepository(BaseRepository[TenantDomain]):
    """
    企业域名仓储 / Tenant domain repository.

    提供域名特有的数据访问方法
    注意：域名管理是平台级操作，不做企业隔离
    """

    model = TenantDomain

    # 按 scope 限制可过滤字段
    _scope_fields: dict[str, set[str]] = {
        "admin": {
            "id", "tenant_id", "domain", "is_verified",
            "is_primary", "ssl_status", "created_at", "updated_at",
        },
        "tenant": {
            "id", "domain", "is_verified", "is_primary",
            "ssl_status", "created_at", "updated_at", "remark",
        },
    }

    async def get_by_domain(self, domain: str) -> TenantDomain | None:
        """
        根据域名获取记录 / Get record by domain.

        Args:
            domain: 域名

        Returns:
            域名实例或 None
        """
        return await self.get_one_by(domain=domain)

    async def get_primary_domain(self, tenant_id: int) -> TenantDomain | None:
        """
        获取企业的主域名 / Get tenant primary domain.

        Args:
            tenant_id: 企业 ID

        Returns:
            主域名实例或 None
        """
        query = select(self.model).where(
            self.model.tenant_id == tenant_id,
            self.model.is_primary.is_(True),
            self.model.is_deleted.is_(False),
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_tenant_domains(self, tenant_id: int) -> list[TenantDomain]:
        """
        获取企业所有域名 / Get all domains for tenant.

        Args:
            tenant_id: 企业 ID

        Returns:
            域名列表，主域名排在前面
        """
        query = (
            select(self.model)
            .where(
                self.model.tenant_id == tenant_id,
                self.model.is_deleted.is_(False),
            )
            .order_by(
                self.model.is_primary.desc(),  # 主域名排在前面
                asc(self.model.created_at),
            )
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def domain_exists(
        self,
        domain: str,
        exclude_id: int | None = None,
    ) -> bool:
        """
        检查域名是否已存在 / Check if domain already exists.

        Args:
            domain: 域名
            exclude_id: 排除的 ID（用于更新时排除自身）

        Returns:
            是否存在
        """
        query = select(self.model.id).where(
            self.model.domain == domain,
            self.model.is_deleted.is_(False),
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)

        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def count_tenant_domains(self, tenant_id: int) -> int:
        """
        统计企业域名数量 / Count tenant domains.

        Args:
            tenant_id: 企业 ID

        Returns:
            域名数量
        """
        return await self.count(tenant_id=tenant_id)

    async def has_primary_domain(self, tenant_id: int) -> bool:
        """
        检查企业是否已有主域名 / Check if tenant has primary domain.

        Args:
            tenant_id: 企业 ID

        Returns:
            是否有主域名
        """
        primary = await self.get_primary_domain(tenant_id)
        return primary is not None

    async def clear_primary_flag(self, tenant_id: int) -> None:
        """
        清除企业现有的主域名标记 / Clear tenant primary domain flag.

        在设置新的主域名之前调用，确保只有一个主域名

        Args:
            tenant_id: 企业 ID
        """
        from sqlalchemy import update

        stmt = (
            update(self.model)
            .where(
                self.model.tenant_id == tenant_id,
                self.model.is_primary.is_(True),
                self.model.is_deleted.is_(False),
            )
            .values(is_primary=False)
        )
        await self.db.execute(stmt)


__all__ = ["TenantDomainRepository"]
