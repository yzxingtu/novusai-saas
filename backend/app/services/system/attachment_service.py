"""
平台端附件服务

提供跨租户的附件管理能力（平台管理员专用）
"""

from typing import Any

from app.core.base_service import GlobalService
from app.core.i18n import _
from app.exceptions import NotFoundException
from app.models.tenant.attachment import Attachment
from app.repositories.system.attachment_repository import AdminAttachmentRepository


class AdminAttachmentService(GlobalService[Attachment, AdminAttachmentRepository]):
    """
    平台端附件服务
    
    提供跨租户的附件管理能力
    """
    
    model = Attachment
    repository_class = AdminAttachmentRepository

    async def soft_delete(self, attachment_id: int) -> bool:
        """
        软删除附件
        
        Args:
            attachment_id: 附件 ID
        
        Returns:
            是否删除成功
        """
        attachment = await self.repo.get_by_id(attachment_id)
        if not attachment:
            raise NotFoundException(message=_("error.common.not_found"))
        return await self.repo.delete(attachment_id, soft=True)

    async def get_storage_stats(self, tenant_id: int | None = None) -> dict[str, Any]:
        """
        获取存储统计
        
        Args:
            tenant_id: 可选的租户 ID，不传则统计所有租户
        
        Returns:
            存储统计信息
        """
        return await self.repo.get_storage_stats(tenant_id)

    async def get_storage_stats_by_tenant(self) -> list[dict[str, Any]]:
        """
        获取按租户分组的存储统计
        
        Returns:
            各租户存储统计列表
        """
        return await self.repo.get_storage_stats_by_tenant()


__all__ = ["AdminAttachmentService"]
