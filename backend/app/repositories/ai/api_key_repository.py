"""
AI API Key Repository

处理 AI API Key 数据访问
"""

from datetime import datetime
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.models.ai import ProviderApiKey


class ProviderApiKeyRepository(BaseRepository[ProviderApiKey]):
    """
    AI API Key Repository
    
    提供 AI API Key 的数据访问操作
    """
    
    model = ProviderApiKey
    
    async def get_available_key(
        self,
        provider_id: int,
        tenant_id: int | None = None
    ) -> ProviderApiKey | None:
        """
        获取可用的 API Key
        
        优先使用租户自己的 Key，否则回退到平台 Key
        
        Args:
            provider_id: 供应商 ID
            tenant_id: 租户 ID
            
        Returns:
            ProviderApiKey 对象或 None
        """
        # 先查找租户级 Key
        if tenant_id:
            stmt = select(ProviderApiKey).where(
                ProviderApiKey.provider_id == provider_id,
                ProviderApiKey.tenant_id == tenant_id,
                ProviderApiKey.is_active == True,
                ProviderApiKey.is_deleted == False
            ).order_by(
                ProviderApiKey.created_at.desc()
            )
            result = await self.db.execute(stmt)
            key = result.scalar_one_or_none()
            
            if key:
                return key
        
        # 回退到平台级 Key
        stmt = select(ProviderApiKey).where(
            ProviderApiKey.provider_id == provider_id,
            ProviderApiKey.tenant_id == None,
            ProviderApiKey.is_active == True,
            ProviderApiKey.is_deleted == False
        ).order_by(
            ProviderApiKey.created_at.desc()
        )
        
        result = await self.db.execute(stmt)
        key = result.scalar_one_or_none()
        
        # 检查 Key 是否可用
        if key and key.is_available():
            return key
        
        return None
    
    async def get_available_keys_with_load_balancing(
        self,
        provider_id: int,
        tenant_id: int | None = None
    ) -> list[ProviderApiKey]:
        """
        获取所有可用的 API Key（用于负载均衡）
        
        Args:
            provider_id: 供应商 ID
            tenant_id: 租户 ID
            
        Returns:
            ProviderApiKey 列表（按使用次数升序，实现负载均衡）
        """
        conditions = [
            ProviderApiKey.provider_id == provider_id,
            ProviderApiKey.is_active == True,
            ProviderApiKey.is_deleted == False,
        ]
        
        if tenant_id:
            # 优先使用租户级 Key
            conditions.append(ProviderApiKey.tenant_id == tenant_id)
        else:
            # 平台级调用，只使用平台级 Key
            conditions.append(ProviderApiKey.tenant_id == None)
        
        stmt = select(ProviderApiKey).where(
            and_(*conditions)
        ).order_by(
            ProviderApiKey.usage_count.asc(),  # 使用次数少的优先（负载均衡）
            ProviderApiKey.created_at.desc()
        )
        
        result = await self.db.execute(stmt)
        keys = list(result.scalars().all())
        
        # 过滤出真正可用的 Key
        return [key for key in keys if key.is_available()]
    
    async def get_keys_by_provider(
        self,
        provider_id: int,
        tenant_id: int | None = None,
        include_deleted: bool = False
    ) -> list[ProviderApiKey]:
        """
        获取供应商的所有 API Key
        
        Args:
            provider_id: 供应商 ID
            tenant_id: 租户 ID（None 表示获取所有 Key）
            include_deleted: 是否包含已删除的记录
            
        Returns:
            ProviderApiKey 列表
        """
        conditions = [
            ProviderApiKey.provider_id == provider_id
        ]
        
        if not include_deleted:
            conditions.append(ProviderApiKey.is_deleted == False)
        
        if tenant_id is not None:
            conditions.append(ProviderApiKey.tenant_id == tenant_id)
        
        stmt = select(ProviderApiKey).where(
            and_(*conditions)
        ).order_by(
            ProviderApiKey.created_at.desc()
        )
        
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def get_next_available_key(
        self,
        provider_id: int,
        exclude_key_id: int,
        tenant_id: int | None = None,
    ) -> ProviderApiKey | None:
        """
        获取下一个可用 Key（排除当前 Key，用于重试轮换）
        
        Args:
            provider_id: 供应商 ID
            exclude_key_id: 排除的 Key ID
            tenant_id: 租户 ID
            
        Returns:
            ProviderApiKey 对象或 None
        """
        if tenant_id:
            stmt = select(ProviderApiKey).where(
                ProviderApiKey.provider_id == provider_id,
                ProviderApiKey.id != exclude_key_id,
                ProviderApiKey.is_active == True,
                ProviderApiKey.is_deleted == False,
                (
                    (ProviderApiKey.tenant_id == tenant_id)
                    | (ProviderApiKey.tenant_id == None)
                ),
            ).order_by(ProviderApiKey.created_at.desc())
        else:
            stmt = select(ProviderApiKey).where(
                ProviderApiKey.provider_id == provider_id,
                ProviderApiKey.id != exclude_key_id,
                ProviderApiKey.tenant_id == None,
                ProviderApiKey.is_active == True,
                ProviderApiKey.is_deleted == False,
            ).order_by(ProviderApiKey.created_at.desc())

        result = await self.db.execute(stmt)
        next_key = result.scalar_one_or_none()

        if next_key and next_key.is_available():
            return next_key

        return None

    async def update_usage_count(
        self,
        key_id: int,
        increment: int = 1
    ) -> None:
        """
        更新 API Key 使用次数
        
        Args:
            key_id: API Key ID
            increment: 增量
        """
        key = await self.get_by_id(key_id)
        if key:
            key.usage_count += increment
            key.last_used_at = datetime.utcnow()
            await self.db.commit()


__all__ = [
    "ProviderApiKeyRepository",
]
