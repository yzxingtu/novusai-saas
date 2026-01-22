"""
租户套餐仓储

提供套餐的数据访问操作（平台级，非租户隔离）
"""

from sqlalchemy import select, asc
from sqlalchemy.orm import selectinload

from app.core.base_repository import BaseRepository
from app.models.tenant.tenant_plan import TenantPlan


class TenantPlanRepository(BaseRepository[TenantPlan]):
    """
    租户套餐仓储
    
    提供套餐特有的数据访问方法
    注意：套餐是平台级数据，不做租户隔离
    """
    
    model = TenantPlan
    
    async def get_by_code(self, code: str) -> TenantPlan | None:
        """
        根据代码获取套餐
        
        Args:
            code: 套餐代码
        
        Returns:
            套餐实例或 None
        """
        return await self.get_one_by(code=code)
    
    async def code_exists(
        self,
        code: str,
        exclude_id: int | None = None,
    ) -> bool:
        """
        检查套餐代码是否已存在
        
        Args:
            code: 套餐代码
            exclude_id: 排除的 ID（用于更新时排除自身）
        
        Returns:
            是否存在
        """
        query = select(self.model.id).where(
            self.model.code == code,
            self.model.is_deleted == False,
        )
        if exclude_id:
            query = query.where(self.model.id != exclude_id)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
    
    async def get_with_permissions(self, plan_id: int) -> TenantPlan | None:
        """
        获取套餐及其关联权限
        
        Args:
            plan_id: 套餐 ID
        
        Returns:
            套餐实例（含权限）或 None
        """
        query = (
            select(self.model)
            .options(selectinload(self.model.permissions))
            .where(
                self.model.id == plan_id,
                self.model.is_deleted == False,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_active_plans(self) -> list[TenantPlan]:
        """
        获取所有启用的套餐
        
        Returns:
            启用的套餐列表，按 sort_order 排序
        """
        query = (
            select(self.model)
            .where(
                self.model.is_active == True,
                self.model.is_deleted == False,
            )
            .order_by(asc(self.model.sort_order), asc(self.model.id))
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def get_with_tenants(self, plan_id: int) -> TenantPlan | None:
        """
        获取套餐及其关联租户
        
        Args:
            plan_id: 套餐 ID
        
        Returns:
            套餐实例（含租户）或 None
        """
        query = (
            select(self.model)
            .options(selectinload(self.model.tenants))
            .where(
                self.model.id == plan_id,
                self.model.is_deleted == False,
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_all_with_permissions(self) -> list[TenantPlan]:
        """
        获取所有套餐及其权限
        
        Returns:
            套餐列表（含权限）
        """
        query = (
            select(self.model)
            .options(selectinload(self.model.permissions))
            .where(self.model.is_deleted == False)
            .order_by(asc(self.model.sort_order), asc(self.model.id))
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())


__all__ = ["TenantPlanRepository"]
