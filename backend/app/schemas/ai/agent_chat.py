"""
智能体对话相关 Schema / Agent Chat Schema

定义对话请求和响应数据结构
Defines chat request and response data structures.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.i18n import _
PAGE_CONTEXT_KEY = "page_context"


class ChatAttachment(BaseModel):
    """对话附件（图片/文件/音频/视频） / Chat attachment (image/file/audio/video)."""

    attachment_id: int | None = Field(
        None,
        description="Attachment ID for refreshing signed URLs / 用于刷新签名 URL 的附件 ID",
    )
    type: Literal["image", "file", "audio", "video"] = Field(
        ..., description=_("agent_chat.field.attachment_type"),
    )
    url: str = Field(
        ..., description=_("agent_chat.field.attachment_url"),
    )
    name: str | None = Field(
        None, description=_("agent_chat.field.attachment_name"),
    )
    mime_type: str | None = Field(
        None, description=_("agent_chat.field.attachment_mime_type"),
    )


class ImageParams(BaseModel):
    """图像生成参数 / Image generation params."""

    size: str = Field("1024x1024", description=_("agent_chat.field.image_size"))
    quality: str = Field("standard", description=_("agent_chat.field.image_quality"))
    style: str = Field("vivid", description=_("agent_chat.field.image_style"))
    n: int = Field(1, ge=1, le=4, description=_("agent_chat.field.image_n"))


class AgentChatRequest(BaseModel):
    """对话请求 / Agent chat request."""

    message: str = Field(
        "",
        min_length=0,
        max_length=32000,
        description=_("agent_chat.field.message"),
    )
    messages: list[str] | None = Field(
        None,
        max_length=10,
        description=_("agent_chat.field.messages_batch"),
    )

    @model_validator(mode="after")
    def require_message_or_messages(self) -> "AgentChatRequest":
        msgs = self.messages or []
        single = (self.message or "").strip()
        if not msgs and not single:
            raise ValueError("message or messages required")
        if msgs and any(not (m or "").strip() for m in msgs):
            raise ValueError("messages must not contain empty strings")
        return self

    conversation_id: int | None = Field(
        None,
        description=_("agent_chat.field.conversation_id"),
    )
    variables: dict[str, Any] | None = Field(
        None,
        description=_("agent_chat.field.variables"),
    )
    page_context: PageContext | None = Field(
        None,
        description=_("agent_chat.field.page_context"),
    )
    knowledge_base_ids: list[int] | None = Field(
        None,
        description=_("agent_chat.field.knowledge_base_ids"),
    )
    consented_actions: list[str] | None = Field(
        None,
        description=_("agent_chat.field.consented_actions"),
    )
    attachments: list[ChatAttachment] | None = Field(
        None,
        description=_("agent_chat.field.attachments"),
    )
    image_params: ImageParams | None = Field(
        None,
        description=_("agent_chat.field.image_params"),
    )
    page_session_id: str | None = Field(
        None,
        max_length=64,
        description=_("agent_chat.field.page_session_id"),
    )
    route_source: str | None = Field(
        None,
        max_length=32,
        description="Frontend route source hint (e.g. mention)",
    )
    interaction_updates: list["InteractionUpdate"] | None = Field(
        None,
        description="Client-side interaction state updates to persist before processing the next turn",
    )


class UpdateConversationTitleRequest(BaseModel):
    """更新对话标题请求 / Update conversation title request."""

    title: str = Field(
        "",
        min_length=0,
        max_length=200,
        description=_("agent_chat.field.conversation_title"),
    )


class AgentChatResponse(BaseModel):
    """对话响应（非流式） / Agent chat response (non-streaming)."""

    conversation_id: int = Field(
        ..., description=_("agent_chat.field.conversation_id"),
    )
    message: str = Field(
        ..., description=_("agent_chat.field.reply_message"),
    )
    tool_calls: list[dict[str, Any]] | None = Field(
        None, description=_("agent_chat.field.tool_calls"),
    )
    total_tokens: int = Field(
        0, description=_("agent_chat.field.total_tokens"),
    )
    duration_ms: int = Field(
        0, description=_("agent_chat.field.duration_ms"),
    )
    effective_knowledge_base_ids: list[int] | None = Field(
        None,
        description="Effective knowledge base IDs applied to this turn after sanitization",
    )
    dropped_knowledge_base_ids: list[int] | None = Field(
        None,
        description="Client-selected knowledge base IDs dropped during sanitization",
    )


class InteractionUpdate(BaseModel):
    kind: Literal["action_buttons", "pending_confirmation", "pending_consent"]
    action: str | None = None
    rejected: bool | None = None
    table: str | None = None
    tool_name: str | None = None
    value: str | None = None


class UpdateConversationInteractionStateRequest(BaseModel):
    updates: list[InteractionUpdate] = Field(default_factory=list)


class PageContext(BaseModel):
    """统一页面上下文（贯穿 Router 路由决策与标准 Agent 聊天执行链） / Unified page context (Router + Agent chat chain)."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    page_key: str = Field(
        ...,
        validation_alias=AliasChoices("page_key", "page_type"),
        description=_("agent_chat.field.page_key"),
    )
    page_title: str | None = Field(
        None,
        validation_alias=AliasChoices("page_title", "summary"),
        description=_("agent_chat.field.page_title"),
    )
    page_data: dict[str, Any] | None = Field(
        None,
        validation_alias=AliasChoices("page_data", "detail"),
        description=_("agent_chat.field.page_data"),
    )

    @classmethod
    def normalize(cls, value: Any) -> dict[str, Any] | None:
        if not value:
            return None

        if isinstance(value, cls):
            page_context = value
        elif isinstance(value, dict):
            try:
                page_context = cls.model_validate(value)
            except ValidationError:
                return None
        else:
            return None

        return page_context.model_dump(exclude_none=True)

    @classmethod
    def normalize_variables(
        cls,
        variables: dict[str, Any] | None,
        page_context: Any = None,
    ) -> dict[str, Any] | None:
        normalized_variables = dict(variables or {})
        raw_page_context = (
            page_context
            if page_context is not None
            else normalized_variables.get(PAGE_CONTEXT_KEY)
        )
        normalized_page_context = cls.normalize(raw_page_context)

        if normalized_page_context is not None:
            normalized_variables[PAGE_CONTEXT_KEY] = normalized_page_context
        else:
            normalized_variables.pop(PAGE_CONTEXT_KEY, None)

        return normalized_variables or None


class AgentRouteRequest(BaseModel):
    """智能路由请求 / Agent route request."""

    message: str = Field(
        ..., min_length=1, max_length=32000,
        description=_("agent_chat.field.message"),
    )
    conversation_id: int | None = Field(
        None,
        description=_("agent_chat.field.conversation_id"),
    )
    page_context: PageContext | None = Field(
        None,
        description=_("agent_chat.field.page_context"),
    )
    pinned_agent_id: int | None = Field(
        None,
        description=_("agent_chat.field.pinned_agent_id"),
    )
    force_reroute: bool = Field(
        False,
        description="Force rerouting even when the conversation is already bound to an agent / 即使当前对话已绑定智能体也强制重新路由",
    )
    has_image_attachments: bool = Field(
        False,
        description="Whether the user message includes image attachments / 是否包含图片附件",
    )
    has_audio_attachments: bool = Field(
        False,
        description="Whether the user message includes audio attachments / 是否包含音频附件",
    )
    has_video_attachments: bool = Field(
        False,
        description="Whether the user message includes video attachments / 是否包含视频附件",
    )
    has_file_attachments: bool = Field(
        False,
        description="Whether the user message includes generic file attachments / 是否包含通用文件附件",
    )


class AgentRouteResponse(BaseModel):
    """智能路由响应 / Agent route response."""

    agent_id: int = Field(
        ..., description=_("agent_chat.field.routed_agent_id"),
    )
    agent_name: str = Field(
        ..., description=_("agent_chat.field.routed_agent_name"),
    )
    confidence: float = Field(
        1.0, description=_("agent_chat.field.route_confidence"),
    )
    routed_by: str = Field(
        ..., description=_("agent_chat.field.routed_by"),
    )


__all__ = [
    "ChatAttachment",
    "ImageParams",
    "PAGE_CONTEXT_KEY",
    "AgentChatRequest",
    "AgentChatResponse",
    "InteractionUpdate",
    "PageContext",
    "AgentRouteRequest",
    "AgentRouteResponse",
    "UpdateConversationInteractionStateRequest",
]
