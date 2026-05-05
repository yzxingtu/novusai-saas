"""
Retired admin AI writing router / 已退役的管理端 AI 写作路由。

Rich-text AI no longer exposes independent `/ai/writing/*` or
`/ai/rich-text/operations/*` SSE endpoints. Editors should resolve the
`system.ai_writing` assignment and send the rendered operation message through
the global AgentChat conversation route.
/ 富文本 AI 不再暴露独立 `/ai/writing/*` 或 `/ai/rich-text/operations/*` SSE
端点。编辑器应解析 `system.ai_writing` 绑定，并通过全局 AgentChat 会话路由发送
渲染后的操作消息。
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.core.i18n import _

router = APIRouter(tags=[_("menu.tags.ai_writing")], include_in_schema=False)


class AIWritingRequest(BaseModel):
    """Internal rich-text AI payload schema / 内部富文本 AI 载荷 schema。"""

    model_config = ConfigDict(extra="forbid")

    selected_text: str = Field(default="", max_length=10000)
    selection_html: str = Field(default="", max_length=20000)
    before_text: str = Field(default="", max_length=5000)
    after_text: str = Field(default="", max_length=5000)
    context_title: str = Field(default="", max_length=200)
    document_title: str = Field(default="", max_length=200)
    document_id: int | None = Field(default=None, ge=1)
    document_type: str = Field(default="novusdoc", max_length=100)
    surface: str = Field(default="rich_text", max_length=100)
    instruction: str = Field(default="", max_length=2000)
    format_instruction: str = Field(default="", max_length=1000)
    target_lang: str = Field(default="English", max_length=50)
    history: list[dict[str, str]] | None = Field(default=None, max_length=20)


__all__ = ["AIWritingRequest", "router"]
