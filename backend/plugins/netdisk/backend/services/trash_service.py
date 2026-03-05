"""
回收站 Service
"""

from __future__ import annotations

from app.core.base_service import TenantService
from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import NotFoundException

logger = LogManager.get_logger("app")


class TrashService(TenantService):
    def __init__(self, db, tenant_id: int | None):
        # This service composes repositories on demand and does not rely on BaseService.repo.
        self.db = db
        self.tenant_id = tenant_id

    async def list_trash(self) -> list:
        from ..repositories.node_repository import NodeRepository
        repo = NodeRepository(self.db, self.tenant_id)
        return await repo.list_trash()

    async def restore(self, node_id: int) -> object:
        from sqlalchemy import select

        from app.core.base_model import utc_now
        from ..models.node import FileNode

        result = await self.db.execute(
            select(FileNode).where(
                FileNode.id == node_id,
                FileNode.tenant_id == self.tenant_id,
                FileNode.is_deleted.is_(True),
            )
        )
        node = result.scalar_one_or_none()
        if node is None:
            raise NotFoundException(message=_("plugin.netdisk.error.node_not_found"))

        node.restore()
        node.updated_at = utc_now()
        await self.db.commit()
        await self.db.refresh(node)
        return node

    async def clear_trash(self) -> int:
        """清空当前租户回收站（物理删除 + 回收存储）"""
        from sqlalchemy import delete, select

        from app.storage.manager import StorageManager
        from ..models.node import FileNode, NodeTypeEnum
        from ..repositories.quota_repository import QuotaRepository

        result = await self.db.execute(
            select(FileNode).where(
                FileNode.tenant_id == self.tenant_id,
                FileNode.is_deleted.is_(True),
                FileNode.node_type == NodeTypeEnum.FILE.value,
            )
        )
        file_nodes = result.scalars().all()

        storage = StorageManager.get_driver()
        freed_bytes = 0
        for node in file_nodes:
            if node.storage_key:
                try:
                    await storage.delete(node.storage_key)
                    freed_bytes += node.size_bytes
                except Exception as e:
                    logger.warning("netdisk: clear_trash delete storage failed key=%s: %s", node.storage_key, e)

        # 物理删除所有回收站节点
        await self.db.execute(
            delete(FileNode).where(
                FileNode.tenant_id == self.tenant_id,
                FileNode.is_deleted.is_(True),
            )
        )

        # 更新配额
        if freed_bytes > 0:
            quota_repo = QuotaRepository(self.db, self.tenant_id)
            await quota_repo.add_used(-freed_bytes)

        await self.db.commit()
        return len(file_nodes)
