"""
NovusDoc 文件夹 API handlers

分层规范：handler 仅负责参数解析与响应封装，业务逻辑委托给 folder_service。
"""

from __future__ import annotations

from app.core.logging import get_logger

from ..services import folder_service

logger = get_logger("plugin.novusdoc.api")


def _safe_int(val, name: str = "id") -> tuple[int | None, dict | None]:
    if val is None:
        return None, {"error": f"{name} required", "code": 4001}
    try:
        return int(val), None
    except (ValueError, TypeError):
        return None, {"error": f"invalid {name}", "code": 4001}


async def list_folders(request, db, ctx):
    """GET /folders — 文件夹列表（树形）"""
    tenant_id = ctx.get_current_tenant_id()
    if not tenant_id:
        return {"error": "tenant_id required", "code": 4010}

    flat, tree = await folder_service.list_folders(db, tenant_id)
    return {"items": flat, "tree": tree, "total": len(flat)}


async def create_folder(request, db, ctx):
    """POST /folders — 创建文件夹"""
    tenant_id = ctx.get_current_tenant_id()
    if not tenant_id:
        return {"error": "tenant_id required", "code": 4010}

    body = await request.json()
    name = body.get("name", "").strip()
    if not name:
        return {"error": "name is required", "code": 4001}

    result = await folder_service.create_folder(
        db, tenant_id,
        name=name,
        parent_id=body.get("parent_id"),
        sort_order=body.get("sort_order", 0),
        creator_id=ctx.get_current_user_id(),
    )
    await db.commit()
    return result


async def update_folder(request, db, ctx):
    """PUT /folders/{id} — 更新文件夹"""
    tenant_id = ctx.get_current_tenant_id()
    if not tenant_id:
        return {"error": "tenant_id required", "code": 4010}

    folder_id, err = _safe_int(request.path_params.get("id"), "folder id")
    if err:
        return err

    body = await request.json()
    result = await folder_service.update_folder(db, tenant_id, folder_id, body)
    if result is None:
        return {"error": "folder not found", "code": 4040, "status_code": 404}
    if isinstance(result, dict) and "error" in result:
        return {"error": result["error"], "code": 4220}

    await db.commit()
    return result


async def delete_folder(request, db, ctx):
    """DELETE /folders/{id} — 软删除文件夹"""
    tenant_id = ctx.get_current_tenant_id()
    if not tenant_id:
        return {"error": "tenant_id required", "code": 4010}

    folder_id, err = _safe_int(request.path_params.get("id"), "folder id")
    if err:
        return err

    deleted = await folder_service.delete_folder(db, tenant_id, folder_id)
    if not deleted:
        return {"error": "folder not found", "code": 4040, "status_code": 404}

    await db.commit()
    return {"message": "deleted"}
