"""
AI 供应商 Repository

处理 AI 供应商数据访问
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.core.i18n import _
from app.models.ai import AIProvider


class AIProviderRepository(BaseRepository[AIProvider]):
    """
    AI 供应商 Repository
    
    提供 AI 供应商的数据访问操作
    """
    
    model = AIProvider
    
    async def get_by_code(
        self,
        code: str,
        include_deleted: bool = False
    ) -> AIProvider | None:
        """
        根据代码获取供应商
        
        Args:
            code: 供应商代码
            include_deleted: 是否包含已删除的记录
            
        Returns:
            AIProvider 对象或 None
        """
        stmt = select(AIProvider).where(
            AIProvider.code == code
        )
        
        if not include_deleted:
            stmt = stmt.where(AIProvider.is_deleted == False)
        
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_active_providers(
        self,
        limit: int | None = None
    ) -> list[AIProvider]:
        """
        获取启用的供应商列表
        
        Args:
            limit: 限制返回数量
            
        Returns:
            AIProvider 列表
        """
        stmt = select(AIProvider).where(
            AIProvider.is_active == True,
            AIProvider.is_deleted == False
        ).order_by(
            AIProvider.sort_order.asc(),
            AIProvider.created_at.desc()
        )
        
        if limit:
            stmt = stmt.limit(limit)
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def code_exists(
        self,
        code: str,
        exclude_id: int | None = None
    ) -> bool:
        """
        检查代码是否已存在
        
        Args:
            code: 供应商代码
            exclude_id: 排除的 ID（用于更新时检查）
            
        Returns:
            是否存在
        """
        stmt = select(AIProvider.id).where(
            AIProvider.code == code,
            AIProvider.is_deleted == False
        )
        
        if exclude_id:
            stmt = stmt.where(AIProvider.id != exclude_id)
        
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None


__all__ = [
    "AIProviderRepository",
]
