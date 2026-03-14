"""
Tenant AI writing endpoint / 企业端 AI 写作端点

POST /api/tenant/ai/writing/{feature}
Provides SSE streaming AI writing capabilities for rich text editors.
/ 为富文本编辑器提供 SSE 流式 AI 写作能力。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.deps import ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.sse import SSEFormatter, create_sse_response
from app.rbac.decorators import auth_only
from app.services.ai.writing_service import VALID_FEATURES, stream_writing_feature

router = APIRouter(prefix="/ai/writing", tags=[_("menu.tags.ai_writing")])


class AIWritingRequest(BaseModel):
    """AI writing request body / AI 写作请求体"""
    selected_text: str = Field(default="", max_length=10000)
    before_text: str = Field(default="", max_length=5000)
    after_text: str = Field(default="", max_length=2000)
    context_title: str = Field(default="", max_length=200)
    instruction: str = Field(default="", max_length=2000)
    target_lang: str = Field(default="English", max_length=50)
    history: list[dict[str, str]] | None = Field(default=None)


@router.post("/{feature}")
@auth_only
async def tenant_ai_writing(
    feature: str,
    body: AIWritingRequest,
    db: DbSession,
    current_user: ActiveTenantAdmin,
):
    """
    AI writing SSE stream endpoint / AI 写作 SSE 流式端点

    Supported features: continue, optimize, proofread, translate,
    summarize, expand, rewrite, custom, chat.
    / 支持的功能：续写、优化、校对、翻译、摘要、扩写、改写、自定义、对话。
    """
    if feature not in VALID_FEATURES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid feature '{feature}'. Valid: {', '.join(sorted(VALID_FEATURES))}",
        )

    tenant_id = current_user.tenant_id

    async def _generate():
        try:
            async for delta in stream_writing_feature(
                db, tenant_id, feature, body.model_dump(),
            ):
                yield SSEFormatter.format_message({"event": "message", "delta": delta})
            yield SSEFormatter.format_message({"event": "done"})
            yield SSEFormatter.format_done()
        except Exception as exc:
            yield SSEFormatter.format_error("AI_WRITING_ERROR", str(exc))
            yield SSEFormatter.format_done()

    return create_sse_response(_generate())


__all__ = ["router"]
