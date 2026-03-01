"""
NovusDoc 全文搜索 API handler

分层规范：handler 仅负责参数解析与响应封装，搜索逻辑委托给 search_service。
"""

from __future__ import annotations

from ..services import search_service
from .utils import resolve_tenant_id


async def search_docs(request, db, ctx):
    """GET /search — 全文搜索文档"""
    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}

    q = request.query_params.get("q", "").strip()
    if not q:
        return {"items": [], "total": 0}

    try:
        page = max(1, int(request.query_params.get("page[number]", "1")))
        size = max(1, min(100, int(request.query_params.get("page[size]", "20"))))
    except (ValueError, TypeError):
        page, size = 1, 20

    items, total = await search_service.search_documents(
        db, tenant_id, query=q, page=page, size=size,
    )

    return {"items": items, "total": total, "page": page, "size": size}
