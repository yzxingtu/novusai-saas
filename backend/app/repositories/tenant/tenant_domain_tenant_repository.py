from sqlalchemy import select, asc

from app.core.base_repository import TenantRepository
from app.models.tenant.tenant_domain import TenantDomain


class TenantDomainTenantRepository(TenantRepository[TenantDomain]):
    model = TenantDomain
    
    _scope_fields: dict[str, set[str]] = {
        "tenant": {
            "id", "domain", "is_verified", "is_primary",
            "ssl_status", "created_at", "updated_at", "remark",
        },
    }
    
    async def get_by_domain(self, domain: str) -> TenantDomain | None:
        return await self.get_one_by(domain=domain)
    
    async def get_primary_domain(self, tenant_id: int) -> TenantDomain | None:
        query = select(self.model).where(
            self.model.tenant_id == self.tenant_id,
            self.model.is_primary.is_(True),
            self.model.is_deleted.is_(False),
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_tenant_domains(self, tenant_id: int) -> list[TenantDomain]:
        query = (
            select(self.model)
            .where(
                self.model.tenant_id == self.tenant_id,
                self.model.is_deleted.is_(False),
            )
            .order_by(
                self.model.is_primary.desc(),
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
        query = select(self.model.id).where(
            self.model.domain == domain,
            self.model.is_deleted.is_(False),
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
    
    async def count_tenant_domains(self, tenant_id: int) -> int:
        return await self.count(tenant_id=self.tenant_id)
    
    async def has_primary_domain(self, tenant_id: int) -> bool:
        primary = await self.get_primary_domain(self.tenant_id)
        return primary is not None
    
    async def clear_primary_flag(self, tenant_id: int) -> None:
        from sqlalchemy import update
        
        stmt = (
            update(self.model)
            .where(
                self.model.tenant_id == self.tenant_id,
                self.model.is_primary.is_(True),
                self.model.is_deleted.is_(False),
            )
            .values(is_primary=False)
        )
        await self.db.execute(stmt)


__all__ = ["TenantDomainTenantRepository"]
