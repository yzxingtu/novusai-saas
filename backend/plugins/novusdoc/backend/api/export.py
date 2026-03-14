"""NovusDoc export API handler / NovusDoc 导出 API 处理器"""

from __future__ import annotations

from starlette.responses import Response

from .documents import _resolve_tenant_id


async def export_doc(request, db, ctx):
    tenant_id = _resolve_tenant_id(request, ctx)

    doc_id = int(request.path_params["doc_id"])
    fmt = request.query_params.get("format", "html")

    from ..services.document_service import get_document
    doc = await get_document(db, tenant_id, doc_id)
    if not doc:
        return {"error": "Document not found", "status_code": 404}

    title = doc["title"]

    if fmt in ("markdown", "md"):
        text = doc.get("content_text", "")
        return Response(
            content=text,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{title}.md"'},
        )

    html = doc.get("content_html") or f"<h1>{title}</h1><p>{doc.get('content_text', '')}</p>"
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{title}.html"'},
    )
