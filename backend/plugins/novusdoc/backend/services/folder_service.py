"""
NovusDoc 文件夹服务

负责文件夹 CRUD 业务逻辑，从 handler 下沉复杂查询与级联操作。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now

from ..models.document import NovusdocDocument
from ..models.folder import NovusdocFolder


async def list_folders(
    db: AsyncSession,
    tenant_id: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """文件夹列表（扁平 + 树形）"""
    result = await db.execute(
        select(NovusdocFolder).where(
            NovusdocFolder.tenant_id == tenant_id,
            NovusdocFolder.is_deleted.is_(False),
        ).order_by(NovusdocFolder.sort_order, NovusdocFolder.name)
    )
    rows = result.scalars().all()

    flat = [_folder_to_dict(f) for f in rows]
    tree = _build_tree(flat)
    return flat, tree


async def create_folder(
    db: AsyncSession,
    tenant_id: int,
    *,
    name: str,
    parent_id: int | None = None,
    sort_order: int = 0,
    creator_id: int | None = None,
) -> dict[str, Any]:
    """创建文件夹"""
    folder = NovusdocFolder(
        tenant_id=tenant_id,
        name=name,
        parent_id=parent_id,
        sort_order=sort_order,
        creator_id=creator_id,
    )
    db.add(folder)
    await db.flush()
    await db.refresh(folder)
    return _folder_to_dict(folder)


async def update_folder(
    db: AsyncSession,
    tenant_id: int,
    folder_id: int,
    data: dict[str, Any],
) -> dict[str, Any] | None:
    """更新文件夹"""
    result = await db.execute(
        select(NovusdocFolder).where(
            NovusdocFolder.id == folder_id,
            NovusdocFolder.tenant_id == tenant_id,
            NovusdocFolder.is_deleted.is_(False),
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        return None

    if "name" in data:
        folder.name = data["name"].strip()
    if "parent_id" in data:
        new_parent = data["parent_id"]
        if new_parent is not None and new_parent == folder_id:
            return {"error": "folder cannot be its own parent"}
        folder.parent_id = new_parent
    if "sort_order" in data:
        folder.sort_order = data["sort_order"]
    folder.updated_at = utc_now()

    await db.flush()
    return _folder_to_dict(folder)


async def delete_folder(
    db: AsyncSession,
    tenant_id: int,
    folder_id: int,
) -> bool:
    """软删除文件夹（含级联：子文件夹和文档移至根级）"""
    result = await db.execute(
        select(NovusdocFolder).where(
            NovusdocFolder.id == folder_id,
            NovusdocFolder.tenant_id == tenant_id,
            NovusdocFolder.is_deleted.is_(False),
        )
    )
    folder = result.scalar_one_or_none()
    if not folder:
        return False

    await db.execute(
        update(NovusdocDocument)
        .where(
            NovusdocDocument.folder_id == folder_id,
            NovusdocDocument.tenant_id == tenant_id,
        )
        .values(folder_id=None, updated_at=utc_now())
    )

    await db.execute(
        update(NovusdocFolder)
        .where(
            NovusdocFolder.parent_id == folder_id,
            NovusdocFolder.tenant_id == tenant_id,
        )
        .values(parent_id=None, updated_at=utc_now())
    )

    folder.soft_delete(level="tenant")
    await db.flush()
    return True


def _folder_to_dict(folder: NovusdocFolder) -> dict[str, Any]:
    return {
        "id": folder.id,
        "name": folder.name,
        "parent_id": folder.parent_id,
        "sort_order": folder.sort_order,
        "creator_id": folder.creator_id,
        "created_at": folder.created_at.isoformat() if folder.created_at else None,
        "children": [],
    }


def _build_tree(flat: list[dict]) -> list[dict]:
    by_id: dict[int, dict] = {f["id"]: f for f in flat}
    roots: list[dict] = []
    for f in flat:
        pid = f["parent_id"]
        if pid and pid in by_id:
            by_id[pid]["children"].append(f)
        else:
            roots.append(f)
    return roots
