"""
附件仓储

提供附件数据访问能力（租户隔离）
"""

from sqlalchemy import func, select

from app.core.base_repository import TenantRepository
from app.models.tenant.attachment import Attachment


class AttachmentRepository(TenantRepository[Attachment]):
    """
    附件仓储
    """

    model = Attachment

    _scope_fields = {
        "tenant": {
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
            "business_type",
            "created_at",
            "updated_at",
        },
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

    async def get_by_hash(
        self, file_hash: str, driver: str | None = None
    ) -> Attachment | None:
        """
        根据哈希获取附件

        Args:
            file_hash: 文件哈希
            driver: 存储驱动名称，传入时仅匹配同驱动的记录（防止驱动切换后误命中）
        """
        query = select(self.model).where(
            self.model.tenant_id == self.tenant_id,
            self.model.hash == file_hash,
            self.model.is_deleted.is_(False),
        )
        if driver is not None:
            query = query.where(self.model.driver == driver)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_path(self, path: str) -> Attachment | None:
        """
        根据存储路径获取附件
        """
        result = await self.db.execute(
            select(self.model).where(
                self.model.tenant_id == self.tenant_id,
                self.model.path == path,
                self.model.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def sum_size(self) -> int:
        """
        统计租户附件总占用大小
        """
        result = await self.db.execute(
            select(func.coalesce(func.sum(self.model.size), 0)).where(
                self.model.tenant_id == self.tenant_id,
                self.model.is_deleted.is_(False),
            )
        )
        return int(result.scalar() or 0)


__all__ = ["AttachmentRepository"]
