"""
NovusDoc document API handlers / NovusDoc 文档 API 处理器

Data isolation via tenant_id:
- Admin side → tenant_id = PLATFORM_TENANT_ID (0)
- Tenant side → tenant_id = ctx.get_current_tenant_id()
Both sides use the exact same code path with standard integer equality.
"""

from __future__ import annotations

from ..services.document_service import PLATFORM_TENANT_ID


def _resolve_tenant_id(request, ctx) -> int:
    """
    Resolve tenant_id by endpoint side.
    - Tenant side: returns the real tenant ID from context.
    - Admin side:  returns PLATFORM_TENANT_ID (0).
    Always returns int, never None.
    """
    tid = ctx.get_current_tenant_id()
    return tid if tid is not None else PLATFORM_TENANT_ID


async def list_docs(request, db, ctx):
    tenant_id = _resolve_tenant_id(request, ctx)

    page = int(request.query_params.get("page", "1"))
    size = min(int(request.query_params.get("size", "20")), 100)
    folder_id = request.query_params.get("folder_id")
    status = request.query_params.get("status")

    from ..services.document_service import list_documents
    return await list_documents(
        db, tenant_id,
        folder_id=int(folder_id) if folder_id else None,
        status=status,
        page=page,
        size=size,
    )


async def create_doc(request, db, ctx):
    tenant_id = _resolve_tenant_id(request, ctx)

    body = await request.json()
    body["created_by"] = ctx.get_current_user_id()

    from ..services.document_service import create_document
    doc = await create_document(db, tenant_id, body)
    return {"document": doc}


async def get_doc(request, db, ctx):
    tenant_id = _resolve_tenant_id(request, ctx)

    doc_id = int(request.path_params["doc_id"])
    from ..services.document_service import get_document
    doc = await get_document(db, tenant_id, doc_id)
    if not doc:
        return {"error": "Document not found", "status_code": 404}
    return {"document": doc}


async def update_doc(request, db, ctx):
    tenant_id = _resolve_tenant_id(request, ctx)

    doc_id = int(request.path_params["doc_id"])
    body = await request.json()

    from ..services.document_service import update_document
    doc = await update_document(db, tenant_id, doc_id, body)
    if not doc:
        return {"error": "Document not found", "status_code": 404}
    return {"document": doc}


async def delete_doc(request, db, ctx):
    tenant_id = _resolve_tenant_id(request, ctx)

    doc_id = int(request.path_params["doc_id"])
    from ..services.document_service import delete_document
    ok = await delete_document(db, tenant_id, doc_id)
    if not ok:
        return {"error": "Document not found", "status_code": 404}
    return {"message": "Deleted"}
