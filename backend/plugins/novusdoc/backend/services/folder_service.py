"""NovusDoc folder service / NovusDoc 文件夹服务"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def list_folders(
    db: AsyncSession, tenant_id: int,
) -> list[dict[str, Any]]:
    from ..models.folder import NovusdocFolder

    result = await db.execute(
        select(NovusdocFolder).where(
            NovusdocFolder.tenant_id == tenant_id,
            NovusdocFolder.is_deleted.is_(False),
        ).order_by(NovusdocFolder.sort_order, NovusdocFolder.name)
    )
    folders = result.scalars().all()
    return [
        {
            "id": f.id,
            "name": f.name,
            "parent_id": f.parent_id,
            "sort_order": f.sort_order,
        }
        for f in folders
    ]


async def create_folder(
    db: AsyncSession, tenant_id: int, data: dict[str, Any],
) -> dict[str, Any]:
    from ..models.folder import NovusdocFolder

    folder = NovusdocFolder(
        tenant_id=tenant_id,
        name=data["name"],
        parent_id=data.get("parent_id"),
        sort_order=data.get("sort_order", 0),
    )
    db.add(folder)
    await db.flush()
    await db.refresh(folder)
    return {"id": folder.id, "name": folder.name, "parent_id": folder.parent_id}


async def update_folder(
    db: AsyncSession, tenant_id: int, folder_id: int, data: dict[str, Any],
) -> dict[str, Any] | None:
    from ..models.folder import NovusdocFolder

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
        folder.name = data["name"]
    if "parent_id" in data:
        folder.parent_id = data["parent_id"]
    if "sort_order" in data:
        folder.sort_order = data["sort_order"]

    await db.flush()
    return {"id": folder.id, "name": folder.name, "parent_id": folder.parent_id}


async def delete_folder(
    db: AsyncSession, tenant_id: int, folder_id: int,
) -> bool:
    from ..models.folder import NovusdocFolder

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

    folder.is_deleted = True
    await db.flush()
    return True
