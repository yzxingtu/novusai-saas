"""
NovusDoc AI 功能 API handlers

所有 AI handler 通过 ai_service.stream_ai_feature() 统一调用，
返回 plugin_sse_response() 封装的 SSE 流式响应。

handler 签名：(request, db, ctx) — ctx 为 PluginContext
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.plugins.sse import plugin_sse_response

from ..services.ai_service import stream_ai_feature
from .utils import resolve_tenant_id

logger = get_logger("plugin.novusdoc.ai")


async def _get_doc_title(db, ctx, doc_id_str: str) -> str:
    """Helper: get document title for AI context."""
    if not doc_id_str:
        return ""
    try:
        from ..services.document_service import get_document
        tenant_id = resolve_tenant_id(ctx)
        if tenant_id is None:
            return ""
        doc = await get_document(db, tenant_id, int(doc_id_str))
        return doc.get("title", "") if doc else ""
    except Exception:
        return ""


async def _ai_handler(request, db, ctx, feature: str):
    """Generic AI handler: parse body → stream_ai_feature → SSE response."""
    tenant_id = resolve_tenant_id(ctx)
    if tenant_id is None:
        return {"error": "tenant_id required", "code": 4010, "status_code": 401}

    doc_id_str = request.path_params.get("doc_id", "")
    doc_title = await _get_doc_title(db, ctx, doc_id_str)

    try:
        body = await request.json()
    except Exception:
        body = {}

    generator = stream_ai_feature(ctx, feature, body, doc_title=doc_title)

    return plugin_sse_response(
        generator,
        plugin_name="novusdoc",
    )


async def ai_continue(request, db, ctx):
    """POST /docs/{doc_id}/ai/continue — AI 续写"""
    return await _ai_handler(request, db, ctx, "continue")


async def ai_optimize(request, db, ctx):
    """POST /docs/{doc_id}/ai/optimize — AI 优化"""
    return await _ai_handler(request, db, ctx, "optimize")


async def ai_proofread(request, db, ctx):
    """POST /docs/{doc_id}/ai/proofread — AI 校对"""
    return await _ai_handler(request, db, ctx, "proofread")


async def ai_translate(request, db, ctx):
    """POST /docs/{doc_id}/ai/translate — AI 翻译"""
    return await _ai_handler(request, db, ctx, "translate")


async def ai_summarize(request, db, ctx):
    """POST /docs/{doc_id}/ai/summarize — AI 摘要"""
    return await _ai_handler(request, db, ctx, "summarize")


async def ai_expand(request, db, ctx):
    """POST /docs/{doc_id}/ai/expand — AI 扩写"""
    return await _ai_handler(request, db, ctx, "expand")


async def ai_rewrite(request, db, ctx):
    """POST /docs/{doc_id}/ai/rewrite — AI 改写"""
    return await _ai_handler(request, db, ctx, "rewrite")


async def ai_image(request, db, ctx):
    """POST /docs/{doc_id}/ai/image — AI 配图"""
    return await _ai_handler(request, db, ctx, "image")


async def ai_custom(request, db, ctx):
    """POST /docs/{doc_id}/ai/custom — AI 自定义 Prompt"""
    return await _ai_handler(request, db, ctx, "custom")


async def ai_sidebar_chat(request, db, ctx):
    """POST /docs/{doc_id}/ai/chat — AI 侧边对话"""
    return await _ai_handler(request, db, ctx, "chat")
