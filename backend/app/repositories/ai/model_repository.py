"""
AI 模型 Repository

处理 AI 模型数据访问
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.models.ai import AIModel


class AIModelRepository(BaseRepository[AIModel]):
    """
    AI 模型 Repository
    
    提供 AI 模型的数据访问操作
    """
    
    model = AIModel
    
    async def get_by_code(
        self,
        code: str,
        include_deleted: bool = False
    ) -> AIModel | None:
        """
        根据代码获取模型
        
        Args:
            code: 模型代码
            include_deleted: 是否包含已删除的记录
            
        Returns:
            AIModel 对象或 None
        """
        stmt = select(AIModel).where(
            AIModel.code == code
        )
        
        if not include_deleted:
            stmt = stmt.where(AIModel.is_deleted.is_(False))
        
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_by_provider(
        self,
        provider_id: int,
        include_deleted: bool = False
    ) -> list[AIModel]:
        """
        获取供应商的所有模型
        
        Args:
            provider_id: 供应商 ID
            include_deleted: 是否包含已删除的记录
            
        Returns:
            AIModel 列表
        """
        stmt = select(AIModel).where(
            AIModel.provider_id == provider_id
        )
        
        if not include_deleted:
            stmt = stmt.where(AIModel.is_deleted.is_(False))
        
        stmt = stmt.order_by(AIModel.created_at.desc())
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_active_models_by_provider(
        self,
        provider_id: int
    ) -> list[AIModel]:
        """
        获取供应商的启用模型
        
        Args:
            provider_id: 供应商 ID
            
        Returns:
            AIModel 列表
        """
        stmt = select(AIModel).where(
            AIModel.provider_id == provider_id,
            AIModel.is_active.is_(True),
            AIModel.is_deleted.is_(False)
        ).order_by(
            AIModel.created_at.desc()
        )
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    

    async def code_exists(
        self,
        code: str,
        exclude_id: int | None = None
    ) -> bool:
        """
        检查模型代码是否存在
        
        Args:
            code: 模型代码
            exclude_id: 排除的 ID（用于更新时排除自己）
            
        Returns:
            是否存在
        """
        from sqlalchemy import func
        
        stmt = select(func.count(AIModel.id)).where(
            AIModel.code == code,
            AIModel.is_deleted.is_(False)
        )
        
        if exclude_id is not None:
            stmt = stmt.where(AIModel.id != exclude_id)
        
        result = await self.db.execute(stmt)
        count = result.scalar() or 0
        return count > 0
    async def get_active_with_provider(
        self, model_id: int
    ) -> AIModel | None:
        """
        获取启用的模型（预加载 provider 关系）

        Args:
            model_id: 模型 ID

        Returns:
            AIModel 对象或 None
        """
        from sqlalchemy.orm import selectinload

        stmt = select(AIModel).where(
            AIModel.id == model_id,
            AIModel.is_active.is_(True),
            AIModel.is_deleted.is_(False),
        ).options(selectinload(AIModel.provider))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_by_name_and_provider(
        self, name: str, provider_id: int
    ) -> AIModel | None:
        """
        根据名称和供应商获取启用的模型

        Args:
            name: 模型名称
            provider_id: 供应商 ID

        Returns:
            AIModel 对象或 None
        """
        stmt = select(AIModel).where(
            AIModel.provider_id == provider_id,
            AIModel.name == name,
            AIModel.is_active.is_(True),
            AIModel.is_deleted.is_(False),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()




__all__ = [
    "AIModelRepository",
]
