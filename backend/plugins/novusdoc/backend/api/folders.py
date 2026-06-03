"""NovusDoc folder API handlers / NovusDoc 文件夹 API 处理器"""

from __future__ import annotations

from .documents import _resolve_tenant_id


async def list_folders(request, db, ctx):
    tenant_id = _resolve_tenant_id(request, ctx)

    from ..services.folder_service import list_folders as _list

    folders = await _list(db, tenant_id)
    return {"items": folders, "total": len(folders)}


async def create_folder(request, db, ctx):
    tenant_id = _resolve_tenant_id(request, ctx)

    body = await request.json()
    from ..services.folder_service import create_folder as _create

    folder = await _create(db, tenant_id, body)
    return {"folder": folder}


async def update_folder(request, db, ctx):
    tenant_id = _resolve_tenant_id(request, ctx)

    folder_id = int(request.path_params["folder_id"])
    body = await request.json()

    from ..services.folder_service import update_folder as _update

    folder = await _update(db, tenant_id, folder_id, body)
    if not folder:
        return {"error": "Folder not found", "status_code": 404}
    return {"folder": folder}


async def delete_folder(request, db, ctx):
    tenant_id = _resolve_tenant_id(request, ctx)

    folder_id = int(request.path_params["folder_id"])
    from ..services.folder_service import delete_folder as _delete

    ok = await _delete(db, tenant_id, folder_id)
    if not ok:
        return {"error": "Folder not found", "status_code": 404}
    return {"message": "Deleted"}
