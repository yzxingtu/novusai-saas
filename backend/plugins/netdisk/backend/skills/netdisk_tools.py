"""
NetDisk Toolkit — AI Agent 可调用的文件查询工具
安全约束：仅访问 ctx.tenant_id 下的文件，禁止跨企业
禁止使用：os / subprocess / sys / sqlite3 等被安全扫描禁止的模块
"""

from __future__ import annotations

import json


class Tools:
    """企业网盘文件查询工具包 / Netdisk file query tool package."""

    def __init__(self, ctx):
        self.ctx = ctx  # 含 tenant_id，强制企业隔离

    async def list_files(
        self,
        folder_path: str = "/",
        file_type: str = "",
    ) -> str:
        """列出指定目录下的文件和文件夹。 / 。

        :param folder_path: 目录路径（如 '/documents/2024'），默认为根目录 '/'
        :param file_type:   文件类型过滤，可选值：pdf / image / video / audio / doc，空字符串表示不过滤
        :return: JSON 格式文件列表，含名称/大小/修改时间/类型/是否已分享"""
        db = self.ctx.get_db()
        tenant_id = self.ctx.tenant_id

        parent_id = await _resolve_path(db, tenant_id, folder_path)

        from sqlalchemy import select

        from ..models.node import FileNode

        stmt = (
            select(FileNode)
            .where(
                FileNode.tenant_id == tenant_id,
                FileNode.parent_id == parent_id,
                FileNode.is_deleted.is_(False),
            )
            .order_by(FileNode.node_type, FileNode.name)
        )

        if file_type:
            mime_prefix = _file_type_to_mime(file_type)
            if mime_prefix:
                stmt = stmt.where(FileNode.mime_type.ilike(f"{mime_prefix}%"))

        result = await db.execute(stmt)
        nodes = result.scalars().all()

        items = []
        for n in nodes:
            items.append({
                "name":      n.name,
                "type":      n.node_type,
                "size":      n.size_bytes,
                "mimeType":  n.mime_type,
                "updatedAt": n.updated_at.isoformat() if n.updated_at else None,
            })

        return json.dumps({"path": folder_path, "items": items, "total": len(items)}, ensure_ascii=False)

    async def search_files(
        self,
        keyword: str,
        file_type: str = "",
        limit: int = 10,
    ) -> str:
        """在企业网盘中搜索文件（模糊匹配文件名）。 / （ ）。

        :param keyword:   搜索关键词（文件名模糊匹配）
        :param file_type: 文件类型过滤，可选值：pdf / image / video / audio / doc，空=不过滤
        :param limit:     返回结果数量上限，默认 10，最大 50
        :return: JSON 格式匹配文件列表，含文件名/完整路径/大小/修改时间"""
        db = self.ctx.get_db()
        tenant_id = self.ctx.tenant_id
        limit = min(limit, 50)

        from sqlalchemy import select

        from ..models.node import FileNode

        stmt = (
            select(FileNode)
            .where(
                FileNode.tenant_id == tenant_id,
                FileNode.is_deleted.is_(False),
                FileNode.name.ilike(f"%{keyword}%"),
            )
            .order_by(FileNode.updated_at.desc())
            .limit(limit)
        )

        if file_type:
            mime_prefix = _file_type_to_mime(file_type)
            if mime_prefix:
                stmt = stmt.where(FileNode.mime_type.ilike(f"{mime_prefix}%"))

        result = await db.execute(stmt)
        nodes = result.scalars().all()

        items = []
        for n in nodes:
            items.append({
                "name":      n.name,
                "type":      n.node_type,
                "size":      n.size_bytes,
                "mimeType":  n.mime_type,
                "updatedAt": n.updated_at.isoformat() if n.updated_at else None,
                # 注意：不返回 storage_key（敏感字段）
            })

        return json.dumps(
            {"keyword": keyword, "items": items, "total": len(items)},
            ensure_ascii=False,
        )


# ── 辅助函数（私有）──────────────────────────────────────────

async def _resolve_path(db, tenant_id: int, path: str) -> int | None:
    """将路径字符串解析为 parent_id / Parse path string to parent_id."""
    if not path or path == "/":
        return None

    from sqlalchemy import select

    from ..models.node import FileNode, NodeTypeEnum

    parts = [p for p in path.strip("/").split("/") if p]
    current_parent: int | None = None

    for part in parts:
        result = await db.execute(
            select(FileNode.id).where(
                FileNode.tenant_id == tenant_id,
                FileNode.parent_id == current_parent,
                FileNode.name == part,
                FileNode.node_type == NodeTypeEnum.FOLDER.value,
                FileNode.is_deleted.is_(False),
            )
        )
        node_id = result.scalar_one_or_none()
        if node_id is None:
            return None  # 路径不存在，返回根
        current_parent = node_id

    return current_parent


def _file_type_to_mime(file_type: str) -> str:
    """将用户友好的文件类型转换为 MIME 前缀 / Map user-friendly file type to MIME prefix."""
    _MAP = {
        "image": "image/",
        "video": "video/",
        "audio": "audio/",
        "pdf":   "application/pdf",
        "doc":   "application/vnd",
        "text":  "text/",
        "zip":   "application/zip",
    }
    return _MAP.get(file_type.lower(), "")
