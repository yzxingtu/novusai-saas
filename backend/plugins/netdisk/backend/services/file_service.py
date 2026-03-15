"""
文件/文件夹操作 Service
"""

from __future__ import annotations

from app.core.base_service import TenantService
from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException, NotFoundException

logger = LogManager.get_logger("app")


class FileService(TenantService):
    def __init__(self, db, tenant_id: int | None):
        # This service composes repositories on demand and does not rely on BaseService.repo.
        self.db = db
        self.tenant_id = tenant_id

    # ── 私有辅助 ──────────────────────────────────────────────

    def _get_repos(self):
        from ..repositories.node_repository import NodeRepository
        from ..repositories.quota_repository import QuotaRepository
        node_repo  = NodeRepository(self.db, self.tenant_id)
        quota_repo = QuotaRepository(self.db, self.tenant_id)
        return node_repo, quota_repo

    async def _get_node_or_404(self, node_id: int):
        from ..repositories.node_repository import NodeRepository
        repo = NodeRepository(self.db, self.tenant_id)
        node = await repo.get(node_id)
        if node is None or node.tenant_id != self.tenant_id:
            raise NotFoundException(message=_("plugin.netdisk.error.node_not_found"))
        return node

    async def _check_name_conflict(
        self,
        node_repo,
        parent_id: int | None,
        name: str,
        node_type: str,
        exclude_id: int | None = None,
    ) -> None:
        if await node_repo.name_exists(parent_id, name, node_type, exclude_id=exclude_id):
            raise BusinessException(message=_("plugin.netdisk.error.name_exists"))

    # ── 目录操作 ──────────────────────────────────────────────

    async def list_dir(self, parent_id: int | None) -> list:
        node_repo, _ = self._get_repos()
        return await node_repo.list_dir(parent_id)

    async def get_node(self, node_id: int) -> dict:
        """获取节点详情（含路径面包屑） / Get node detail (with path breadcrumb)."""
        node_repo, _ = self._get_repos()
        node = await self._get_node_or_404(node_id)
        breadcrumbs = await node_repo.get_ancestors(node_id)
        return {"node": node, "breadcrumbs": breadcrumbs}

    async def create_folder(self, parent_id: int | None, name: str) -> object:
        from app.core.base_model import utc_now
        from ..models.node import FileNode, NodeTypeEnum

        node_repo, _ = self._get_repos()
        if parent_id is not None:
            await self._get_node_or_404(parent_id)

        await self._check_name_conflict(node_repo, parent_id, name, NodeTypeEnum.FOLDER.value)

        folder = FileNode(
            tenant_id=self.tenant_id,
            parent_id=parent_id,
            name=name,
            node_type=NodeTypeEnum.FOLDER.value,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self.db.add(folder)
        await self.db.commit()
        await self.db.refresh(folder)
        return folder

    async def rename(self, node_id: int, new_name: str) -> object:
        from app.core.base_model import utc_now

        node_repo, _ = self._get_repos()
        node = await self._get_node_or_404(node_id)
        await self._check_name_conflict(
            node_repo, node.parent_id, new_name, node.node_type, exclude_id=node_id
        )
        node.name = new_name
        node.updated_at = utc_now()
        await self.db.commit()
        await self.db.refresh(node)
        return node

    async def move(self, node_id: int, new_parent_id: int | None) -> object:
        """移动节点（含循环检测） / Move node (with cycle check)."""
        from app.core.base_model import utc_now

        node_repo, _ = self._get_repos()
        node = await self._get_node_or_404(node_id)

        if new_parent_id is not None:
            ancestors = await node_repo.get_ancestors(new_parent_id)
            ancestor_ids = {n.id for n in ancestors} | {new_parent_id}
            if node_id in ancestor_ids:
                raise BusinessException(message=_("plugin.netdisk.error.move_to_child"))
            await self._get_node_or_404(new_parent_id)

        await self._check_name_conflict(
            node_repo, new_parent_id, node.name, node.node_type, exclude_id=node_id
        )

        node.parent_id = new_parent_id
        node.updated_at = utc_now()
        await self.db.commit()
        await self.db.refresh(node)
        return node

    async def copy(self, node_id: int, new_parent_id: int | None) -> object:
        """深拷贝节点（先检查配额） / Deep copy node (quota check first)."""
        from ..repositories.quota_repository import QuotaRepository

        node = await self._get_node_or_404(node_id)

        # 检查配额（仅 file 占空间）
        if node.is_file:
            quota_repo = QuotaRepository(self.db, self.tenant_id)
            quota = await quota_repo.get_or_create()
            if not quota.check_capacity(node.size_bytes):
                raise BusinessException(
                    message=_("plugin.netdisk.error.quota_exceeded").format(free=f"{quota.free_bytes / 1024**3:.2f}"),
                    status_code=429,
                )

        new_node = await self._deep_copy(node, new_parent_id)
        await self.db.commit()
        return new_node

    async def _deep_copy(self, node, new_parent_id: int | None):
        from app.core.base_model import utc_now
        from app.storage.manager import StorageManager
        from ..models.node import FileNode

        new_node = FileNode(
            tenant_id=self.tenant_id,
            parent_id=new_parent_id,
            name=node.name,
            node_type=node.node_type,
            size_bytes=node.size_bytes,
            mime_type=node.mime_type,
            created_at=utc_now(),
            updated_at=utc_now(),
        )

        if node.is_file and node.storage_key:
            # 在 StorageService 层复制实际文件
            storage = StorageManager.get_driver()
            new_key = f"netdisk/{self.tenant_id}/copy_{node.id}_{node.name}"
            try:
                data = await storage.get(node.storage_key)
                await storage.put(new_key, data, mime_type=node.mime_type)
                new_node.storage_key = new_key
            except Exception as e:
                logger.error("netdisk: copy storage file failed: %s", e)
                raise BusinessException(message=_("plugin.netdisk.error.copy_failed"))

        self.db.add(new_node)
        await self.db.flush()

        # 递归拷贝子节点（仅文件夹）
        if node.is_folder:
            from ..repositories.node_repository import NodeRepository
            node_repo = NodeRepository(self.db, self.tenant_id)
            children = await node_repo.list_dir(node.id)
            for child in children:
                await self._deep_copy(child, new_node.id)

        return new_node

    # ── 删除操作 ──────────────────────────────────────────────

    async def delete(self, node_id: int, permanent: bool = False) -> None:
        """删除节点：permanent=False 移入回收站，True 永久删除 / Delete node: False=trash, True=permanent."""
        node = await self._get_node_or_404(node_id)

        if permanent:
            await self._before_permanent_delete(node)
            await self.db.delete(node)
        else:
            node.soft_delete()

        await self.db.commit()

    async def _before_permanent_delete(self, node) -> None:
        """永久删除前清理 storage 文件 + 更新配额 / Before permanent delete: clear storage + update quota."""
        from app.storage.manager import StorageManager
        from ..repositories.quota_repository import QuotaRepository

        if node.is_file and node.storage_key:
            try:
                storage = StorageManager.get_driver()
                await storage.delete(node.storage_key)
            except Exception as e:
                logger.warning("netdisk: delete storage file failed key=%s: %s", node.storage_key, e)

            quota_repo = QuotaRepository(self.db, self.tenant_id)
            await quota_repo.add_used(-node.size_bytes)

    async def batch_delete(self, node_ids: list[int], permanent: bool = False) -> int:
        count = 0
        for node_id in node_ids:
            try:
                await self.delete(node_id, permanent=permanent)
                count += 1
            except Exception as e:
                logger.warning("netdisk: batch delete node %d failed: %s", node_id, e)
        return count

    async def batch_move(self, node_ids: list[int], new_parent_id: int | None) -> int:
        count = 0
        for node_id in node_ids:
            try:
                await self.move(node_id, new_parent_id)
                count += 1
            except Exception as e:
                logger.warning("netdisk: batch move node %d failed: %s", node_id, e)
        return count

    # ── 搜索 ──────────────────────────────────────────────────

    async def search(
        self,
        keyword: str,
        node_type: str | None = None,
        limit: int = 50,
    ) -> list:
        from ..repositories.node_repository import NodeRepository
        repo = NodeRepository(self.db, self.tenant_id)
        return await repo.search(keyword, node_type=node_type, limit=min(limit, 100))
