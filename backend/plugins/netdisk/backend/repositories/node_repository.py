"""
文件节点 Repository — 文件树 CRUD + 路径解析
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.core.base_repository import TenantRepository

if TYPE_CHECKING:
    from ..models.node import FileNode


class NodeRepository(TenantRepository["FileNode"]):

    async def list_dir(
        self,
        parent_id: int | None,
        include_deleted: bool = False,
    ) -> list[FileNode]:
        """列出指定目录内容"""
        from ..models.node import FileNode
        stmt = (
            select(FileNode)
            .where(
                FileNode.tenant_id == self.tenant_id,
                FileNode.parent_id == parent_id,
            )
        )
        if not include_deleted:
            stmt = stmt.where(FileNode.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_ancestors(self, node_id: int) -> list[FileNode]:
        """递归获取所有祖先节点（用于防循环检测 + 面包屑）"""
        from ..models.node import FileNode
        ancestors: list[FileNode] = []
        visited: set[int] = set()
        current_id: int | None = node_id

        while current_id is not None:
            if current_id in visited:
                break
            visited.add(current_id)
            result = await self.db.execute(
                select(FileNode).where(
                    FileNode.id == current_id,
                    FileNode.tenant_id == self.tenant_id,
                )
            )
            node = result.scalar_one_or_none()
            if node is None:
                break
            ancestors.append(node)
            current_id = node.parent_id

        ancestors.reverse()
        return ancestors

    async def get_path(self, node_id: int) -> list[FileNode]:
        """返回从根到该节点的完整路径（面包屑）"""
        return await self.get_ancestors(node_id)

    async def count_folder_children(self, folder_id: int) -> int:
        """统计文件夹子节点数（不含已删除）"""
        from ..models.node import FileNode
        result = await self.db.execute(
            select(func.count(FileNode.id)).where(
                FileNode.parent_id == folder_id,
                FileNode.tenant_id == self.tenant_id,
                FileNode.is_deleted.is_(False),
            )
        )
        return result.scalar_one() or 0

    async def name_exists(
        self,
        parent_id: int | None,
        name: str,
        node_type: str,
        exclude_id: int | None = None,
    ) -> bool:
        """检查目标目录下同名同类型节点是否存在"""
        from ..models.node import FileNode
        stmt = select(FileNode.id).where(
            FileNode.tenant_id == self.tenant_id,
            FileNode.parent_id == parent_id,
            FileNode.name == name,
            FileNode.node_type == node_type,
            FileNode.is_deleted.is_(False),
        )
        if exclude_id is not None:
            stmt = stmt.where(FileNode.id != exclude_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_trash(self) -> list[FileNode]:
        """回收站列表（仅当前企业顶层删除节点）"""
        from ..models.node import FileNode
        result = await self.db.execute(
            select(FileNode)
            .where(
                FileNode.tenant_id == self.tenant_id,
                FileNode.is_deleted.is_(True),
            )
            .order_by(FileNode.deleted_at.desc())
        )
        return list(result.scalars().all())

    async def search(
        self,
        keyword: str,
        node_type: str | None = None,
        limit: int = 50,
    ) -> list[FileNode]:
        """文件名模糊搜索"""
        from ..models.node import FileNode
        stmt = (
            select(FileNode)
            .where(
                FileNode.tenant_id == self.tenant_id,
                FileNode.is_deleted.is_(False),
                FileNode.name.ilike(f"%{keyword}%"),
            )
        )
        if node_type:
            stmt = stmt.where(FileNode.node_type == node_type)
        stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def sum_folder_size(self) -> int:
        """统计企业全部文件总大小（用于配额重算）"""
        from ..models.node import FileNode, NodeTypeEnum
        result = await self.db.execute(
            select(func.coalesce(func.sum(FileNode.size_bytes), 0)).where(
                FileNode.tenant_id == self.tenant_id,
                FileNode.is_deleted.is_(False),
                FileNode.node_type == NodeTypeEnum.FILE.value,
            )
        )
        return result.scalar_one() or 0
