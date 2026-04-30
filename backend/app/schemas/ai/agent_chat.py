"""
智能体对话相关 Schema / Agent Chat Schema

定义对话请求和响应数据结构
Defines chat request and response data structures.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.core.i18n import _

InteractionMode = Literal["confirm", "trusted_auto"]


class ChatAttachment(BaseModel):
    """对话附件（图片/文件/音频/视频） / Chat attachment (image/file/audio/video)."""

    attachment_id: int | None = Field(
        None,
        description="Attachment ID for refreshing signed URLs / 用于刷新签名 URL 的附件 ID",
    )
    type: Literal["image", "file", "audio", "video"] = Field(
        ...,
        description=_("agent_chat.field.attachment_type"),
    )
    url: str = Field(
        ...,
        description=_("agent_chat.field.attachment_url"),
    )
    name: str | None = Field(
        None,
        description=_("agent_chat.field.attachment_name"),
    )
    mime_type: str | None = Field(
        None,
        description=_("agent_chat.field.attachment_mime_type"),
    )


class ImageParams(BaseModel):
    """图像生成参数 / Image generation params."""

    size: str = Field("1024x1024", description=_("agent_chat.field.image_size"))
    quality: str = Field("standard", description=_("agent_chat.field.image_quality"))
    style: str = Field("vivid", description=_("agent_chat.field.image_style"))
    n: int = Field(1, ge=1, le=4, description=_("agent_chat.field.image_n"))


class TrustPolicyRef(BaseModel):
    """运行时信任策略引用 / Runtime trust policy reference."""

    policy_ids: list[int] | None = Field(
        None,
        description="Resolved policy ids / 已解析的策略 ID",
    )
    allowed_tool_names: list[str] | None = Field(
        None,
        description="Allowed tool names / 允许的工具名",
    )
    tool_families: list[str] | None = Field(
        None,
        description="Allowed tool families / 允许的工具族",
    )
    risk_level_cap: str | None = Field(
        None,
        description="Highest auto-approved action level / 自动批准的最高风险级别",
    )


class AgentChatRequest(BaseModel):
    """对话请求 / Agent chat request."""

    model_config = ConfigDict(extra="forbid")

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
    def require_message_or_messages(self) -> AgentChatRequest:
        msgs = self.messages or []
        single = (self.message or "").strip()
        has_interaction = bool(self.interaction_updates)
        if not msgs and not single and not has_interaction:
            raise ValueError("message, messages, or interaction_updates required")
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
    trust_policy_ref: TrustPolicyRef | None = Field(
        None,
        description="Runtime trust policy reference / 运行时信任策略引用",
    )
    image_params: ImageParams | None = Field(
        None,
        description=_("agent_chat.field.image_params"),
    )
    route_source: str | None = Field(
        None,
        max_length=32,
        description="Frontend route source hint (e.g. mention)",
    )
    interaction_updates: list[InteractionUpdate] | None = Field(
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
        ...,
        description=_("agent_chat.field.conversation_id"),
    )
    message: str = Field(
        ...,
        description=_("agent_chat.field.reply_message"),
    )
    tool_calls: list[dict[str, Any]] | None = Field(
        None,
        description=_("agent_chat.field.tool_calls"),
    )
    total_tokens: int = Field(
        0,
        description=_("agent_chat.field.total_tokens"),
    )
    duration_ms: int = Field(
        0,
        description=_("agent_chat.field.duration_ms"),
    )
    effective_knowledge_base_ids: list[int] | None = Field(
        None,
        description="Effective knowledge base IDs applied to this turn after sanitization",
    )
    dropped_knowledge_base_ids: list[int] | None = Field(
        None,
        description="Client-selected knowledge base IDs dropped during sanitization",
    )
    context_compacted: bool = Field(
        False,
        description="Whether compacted context was used during this turn",
    )
    memory_recalled: bool = Field(
        False,
        description="Whether long-term memory recall was injected during this turn",
    )
    prune_stats: dict[str, Any] | None = Field(
        None,
        description="Prompt-only pruning diagnostics for this turn",
    )
    rag_source_kinds: list[str] = Field(
        default_factory=list,
        description="Kinds of RAG sources used in this turn",
    )
    context_diagnostics: dict[str, Any] | None = Field(
        None,
        description="Context diagnostics for this turn / 本轮上下文诊断",
    )
    last_run_summary: dict[str, Any] | None = Field(
        None,
        description="Execution summary for this turn / 本轮执行摘要",
    )


class InteractionUpdate(BaseModel):
    kind: Literal["action_buttons", "pending_confirmation", "pending_consent"]
    action: str | None = None
    auto_approved: bool | None = None
    rejected: bool | None = None
    table: str | None = None
    tool_name: str | None = None
    value: str | None = None


class UpdateConversationInteractionStateRequest(BaseModel):
    updates: list[InteractionUpdate] = Field(default_factory=list)


class AgentRouteRequest(BaseModel):
    """智能路由请求 / Agent route request."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        ...,
        min_length=1,
        max_length=32000,
        description=_("agent_chat.field.message"),
    )
    conversation_id: int | None = Field(
        None,
        description=_("agent_chat.field.conversation_id"),
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
        ...,
        description=_("agent_chat.field.routed_agent_id"),
    )
    agent_name: str = Field(
        ...,
        description=_("agent_chat.field.routed_agent_name"),
    )
    confidence: float = Field(
        1.0,
        description=_("agent_chat.field.route_confidence"),
    )
    routed_by: str = Field(
        ...,
        description=_("agent_chat.field.routed_by"),
    )


__all__ = [
    "ChatAttachment",
    "ImageParams",
    "TrustPolicyRef",
    "InteractionMode",
    "AgentChatRequest",
    "AgentChatResponse",
    "InteractionUpdate",
    "AgentRouteRequest",
    "AgentRouteResponse",
    "UpdateConversationInteractionStateRequest",
]
