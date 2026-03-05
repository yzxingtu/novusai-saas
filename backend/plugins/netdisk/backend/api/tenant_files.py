"""
租户端文件/文件夹操作 API

Handler 签名：(request, db, ctx)
- db   = PluginDbProxy（仅允许 px_netdisk_* 表）
- ctx  = PluginContext，通过 ctx.get_current_tenant_id() 获取 tenant_id
- 返回 dict 自动包装为 success(data=...)
"""

from __future__ import annotations

from app.core.i18n import _
from ._schemas import node_schema as _node_schema

# ── 文件节点 ──────────────────────────────────────────────────────────────

async def list_nodes(request, db, ctx):
    parent_id_str = request.query_params.get("parent_id")
    parent_id = int(parent_id_str) if parent_id_str else None
    from ..services.file_service import FileService
    svc = FileService(db, ctx.get_current_tenant_id())
    nodes = await svc.list_dir(parent_id)
    return {"items": [_node_schema(n) for n in nodes], "total": len(nodes)}


async def get_node(request, db, ctx):
    node_id = int(request.path_params["node_id"])
    from ..services.file_service import FileService
    svc = FileService(db, ctx.get_current_tenant_id())
    result = await svc.get_node(node_id)
    return {
        "node": _node_schema(result["node"]),
        "breadcrumbs": [_node_schema(n) for n in result["breadcrumbs"]],
    }


async def create_folder(request, db, ctx):
    body = await request.json()
    from ..services.file_service import FileService
    svc = FileService(db, ctx.get_current_tenant_id())
    folder = await svc.create_folder(
        parent_id=body.get("parent_id"),
        name=body["name"],
    )
    return {"node": _node_schema(folder)}


async def rename_node(request, db, ctx):
    node_id = int(request.path_params["node_id"])
    body = await request.json()
    from ..services.file_service import FileService
    svc = FileService(db, ctx.get_current_tenant_id())
    node = await svc.rename(node_id, body["name"])
    return {"node": _node_schema(node)}


async def move_node(request, db, ctx):
    node_id = int(request.path_params["node_id"])
    body = await request.json()
    from ..services.file_service import FileService
    svc = FileService(db, ctx.get_current_tenant_id())
    node = await svc.move(node_id, body.get("new_parent_id"))
    return {"node": _node_schema(node)}


async def copy_node(request, db, ctx):
    node_id = int(request.path_params["node_id"])
    body = await request.json()
    from ..services.file_service import FileService
    svc = FileService(db, ctx.get_current_tenant_id())
    node = await svc.copy(node_id, body.get("new_parent_id"))
    return {"node": _node_schema(node)}


async def delete_node(request, db, ctx):
    node_id = int(request.path_params["node_id"])
    permanent = request.query_params.get("permanent", "false").lower() == "true"
    from ..services.file_service import FileService
    svc = FileService(db, ctx.get_current_tenant_id())
    await svc.delete(node_id, permanent=permanent)
    return {"deleted": True}


async def batch_op(request, db, ctx):
    body = await request.json()
    action   = body.get("action")
    node_ids = body.get("node_ids", [])
    from ..services.file_service import FileService
    svc = FileService(db, ctx.get_current_tenant_id())
    from app.exceptions import ValidationException
    if action == "delete":
        count = await svc.batch_delete(node_ids, permanent=body.get("permanent", False))
    elif action == "move":
        count = await svc.batch_move(node_ids, body.get("new_parent_id"))
    elif action == "copy":
        count = 0
        for nid in node_ids:
            try:
                await svc.copy(nid, body.get("new_parent_id"))
                count += 1
            except Exception:
                pass
    else:
        raise ValidationException(
            message=_("plugin.netdisk.error.unknown_batch_action"),
        )
    return {"count": count}


async def search_files(request, db, ctx):
    q         = request.query_params.get("q", "")
    node_type = request.query_params.get("node_type")
    limit     = int(request.query_params.get("limit", "50"))
    limit     = min(limit, 100)
    from ..services.file_service import FileService
    svc   = FileService(db, ctx.get_current_tenant_id())
    nodes = await svc.search(q, node_type=node_type or None, limit=limit)
    return {"items": [_node_schema(n) for n in nodes], "total": len(nodes)}


# ── 回收站 ──────────────────────────────────────────────────────────────────

async def list_trash(request, db, ctx):
    from ..services.trash_service import TrashService
    svc   = TrashService(db, ctx.get_current_tenant_id())
    nodes = await svc.list_trash()
    return {"items": [_node_schema(n) for n in nodes], "total": len(nodes)}


async def restore_node(request, db, ctx):
    node_id = int(request.path_params["node_id"])
    from ..services.trash_service import TrashService
    svc  = TrashService(db, ctx.get_current_tenant_id())
    node = await svc.restore(node_id)
    return {"node": _node_schema(node)}


async def clear_trash(request, db, ctx):
    from ..services.trash_service import TrashService
    svc   = TrashService(db, ctx.get_current_tenant_id())
    count = await svc.clear_trash()
    return {"cleared": count}

