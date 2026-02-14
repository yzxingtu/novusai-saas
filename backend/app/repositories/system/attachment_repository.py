"""
平台端附件仓储

提供跨租户的附件数据访问能力（平台管理员专用）
"""

from typing import Any

from sqlalchemy import select, func

from app.core.base_repository import BaseRepository
from app.models.tenant.attachment import Attachment


class AdminAttachmentRepository(BaseRepository[Attachment]):
    """
    平台端附件仓储
    
    提供跨租户的附件数据访问方法
    """
    
    model = Attachment
    
    # 不同 scope 下允许筛选的字段
    _scope_fields: dict[str, set[str]] = {
        "admin": {
            "id",
            "tenant_id",
            "name",
            "original_name",
            "path",
            "hash",
            "mime_type",
            "extension",
            "visibility",
            "status",
            "driver",
            "source",
            "uploader_id",
            "business_type",
            "business_id",
            "created_at",
            "updated_at",
        },
    }

    async def get_by_hash(self, file_hash: str, tenant_id: int | None = None) -> Attachment | None:
        """
        根据哈希获取附件
        
        Args:
            file_hash: 文件哈希
            tenant_id: 可选的租户 ID
        
        Returns:
            附件实例或 None
        """
        query = select(self.model).where(
            self.model.hash == file_hash,
            self.model.is_deleted.is_(False),
        )
        if tenant_id is not None:
            query = query.where(self.model.tenant_id == tenant_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def sum_size(self, tenant_id: int | None = None) -> int:
        """
        统计附件总占用大小
        
        Args:
            tenant_id: 可选的租户 ID，不传则统计所有租户
        
        Returns:
            总大小（字节）
        """
        query = select(func.coalesce(func.sum(self.model.size), 0)).where(
            self.model.is_deleted.is_(False),
        )
        if tenant_id is not None:
            query = query.where(self.model.tenant_id == tenant_id)
        result = await self.db.execute(query)
        return int(result.scalar() or 0)

    async def get_storage_stats(self, tenant_id: int | None = None) -> dict[str, Any]:
        """
        获取存储统计
        
        Args:
            tenant_id: 可选的租户 ID
        
        Returns:
            存储统计信息
        """
        total_size = await self.sum_size(tenant_id)
        total_count = await self.count(tenant_id=tenant_id) if tenant_id else await self.count()
        return {
            "total_size": total_size,
            "total_count": total_count,
        }

    async def get_storage_stats_by_tenant(self) -> list[dict[str, Any]]:
        """
        获取按租户分组的存储统计
        
        Returns:
            各租户存储统计列表
        """
        query = (
            select(
                self.model.tenant_id,
                func.count(self.model.id).label("count"),
                func.coalesce(func.sum(self.model.size), 0).label("total_size"),
            )
            .where(self.model.is_deleted.is_(False))
            .group_by(self.model.tenant_id)
            .order_by(func.sum(self.model.size).desc())
        )
        result = await self.db.execute(query)
        rows = result.all()
        return [
            {
                "tenant_id": row.tenant_id,
                "count": row.count,
                "total_size": int(row.total_size),
            }
            for row in rows
        ]


__all__ = ["AdminAttachmentRepository"]
