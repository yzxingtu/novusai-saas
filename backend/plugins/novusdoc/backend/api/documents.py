"""
NovusDoc 文档 API handlers

路径由 plugin.yaml tenant_routes / admin_routes 声明，通过 api_dispatcher 分发。
handler 签名：(request, db, ctx) — ctx 为 PluginContext（可选）

admin_routes 使用 tenant_id=0 作为平台级文档命名空间。
"""

from __future__ import annotations

from app.core.logging import get_logger

from ..enums import DocStatus
from .utils import resolve_tenant_id

logger = get_logger("plugin.novusdoc.api")


async def list_docs(request, db, ctx):
    """GET /docs — 文档列表"""
    from ..services.document_service import list_documents

    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}

    params = request.query_params
    folder_id_str = params.get("filter[folder_id][eq]") or params.get("folder_id")
    status = params.get("filter[status][eq]") or params.get("status")
    is_starred_str = params.get("filter[is_starred][eq]")
    search = params.get("filter[search]") or params.get("filter[title][ilike]") or params.get("q")
    sort = params.get("sort", "-updated_at")
    try:
        page = int(params.get("page[number]", "1"))
    except (ValueError, TypeError):
        page = 1
    try:
        size = int(params.get("page[size]", "20"))
    except (ValueError, TypeError):
        size = 20

    try:
        folder_id = int(folder_id_str) if folder_id_str else None
    except (ValueError, TypeError):
        folder_id = None
    is_starred = None
    if is_starred_str is not None:
        is_starred = is_starred_str.lower() in ("true", "1")

    items, total = await list_documents(
        db, tenant_id,
        folder_id=folder_id,
        status=status,
        is_starred=is_starred,
        search=search,
        sort=sort,
        page=page,
        size=size,
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "size": size,
    }


async def create_doc(request, db, ctx):
    """POST /docs — 创建文档"""
    from ..services.document_service import create_document

    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}

    body = await request.json()
    doc = await create_document(
        db, tenant_id,
        title=body.get("title", ""),
        content=body.get("content"),
        folder_id=body.get("folder_id"),
        status=body.get("status", DocStatus.DRAFT.value),
        creator_id=ctx.get_current_user_id(),
        creator_type=ctx.get_current_user_role(),
    )

    await ctx.emit_event("document_created", {
        "doc_id": doc["id"],
        "title": doc["title"],
        "tenant_id": tenant_id,
    })

    await db.commit()
    return doc


async def get_doc(request, db, ctx):
    """GET /docs/{doc_id} — 文档详情"""
    from ..services.document_service import get_document

    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}

    doc_id_str = request.path_params.get("doc_id")
    if not doc_id_str:
        return {"error": "doc_id required", "code": 4001}

    try:
        doc_id = int(doc_id_str)
    except (ValueError, TypeError):
        return {"error": "invalid doc_id", "code": 4001}

    doc = await get_document(db, tenant_id, doc_id)
    if not doc:
        return {"error": "document not found", "code": 4040, "status_code": 404}

    return doc


async def update_doc(request, db, ctx):
    """PUT /docs/{doc_id} — 更新文档"""
    from ..services.document_service import update_document

    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}

    doc_id_str = request.path_params.get("doc_id")
    if not doc_id_str:
        return {"error": "doc_id required", "code": 4001}

    try:
        doc_id = int(doc_id_str)
    except (ValueError, TypeError):
        return {"error": "invalid doc_id", "code": 4001}

    body = await request.json()
    doc = await update_document(
        db, tenant_id, doc_id, body,
        editor_id=ctx.get_current_user_id(),
    )

    if not doc:
        return {"error": "document not found", "code": 4040, "status_code": 404}

    await ctx.emit_event("document_saved", {
        "doc_id": doc["id"],
        "title": doc["title"],
        "tenant_id": tenant_id,
    })

    await db.commit()
    return doc


async def delete_doc(request, db, ctx):
    """DELETE /docs/{doc_id} — 软删除文档"""
    from ..services.document_service import delete_document

    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}

    doc_id_str = request.path_params.get("doc_id")
    if not doc_id_str:
        return {"error": "doc_id required", "code": 4001}

    try:
        doc_id = int(doc_id_str)
    except (ValueError, TypeError):
        return {"error": "invalid doc_id", "code": 4001}

    deleted = await delete_document(db, tenant_id, doc_id)
    if not deleted:
        return {"error": "document not found", "code": 4040, "status_code": 404}

    await ctx.emit_event("document_deleted", {
        "doc_id": doc_id,
        "tenant_id": tenant_id,
    })

    await db.commit()
    return {"message": "deleted"}
