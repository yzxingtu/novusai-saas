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
    ValidationError,
    model_validator,
)

from app.ai.runtime.contracts import PAGE_CONTEXT_KEY
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
    trust_policy_ref: TrustPolicyRef | None = Field(
        None,
        description="Runtime trust policy reference / 运行时信任策略引用",
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


class ThinSurfaceSummary(BaseModel):
    """Surface summary for thin page context / 薄页面上下文中的 surface 摘要。"""

    model_config = ConfigDict(extra="ignore")

    surface_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="UI surface id / UI surface 标识",
    )
    kind: Literal["page", "drawer", "modal", "dropdown", "popover"] = Field(
        ...,
        description="Surface kind / surface 类型",
    )
    title: str | None = Field(
        None,
        max_length=200,
        description="Surface title / surface 标题",
    )


class ActiveFormSummary(BaseModel):
    """Active form summary for thin page context / 活跃表单薄摘要。"""

    model_config = ConfigDict(extra="ignore")

    form_session_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Form session id / 表单会话 ID",
    )
    entity_name: str | None = Field(
        None,
        max_length=128,
        description="Entity name / 实体名",
    )
    mode: Literal["create", "edit", "view", "unknown"] = Field(
        "unknown",
        description="Form mode / 表单模式",
    )
    stage: Literal[
        "opening",
        "ready",
        "filled_partial",
        "validating",
        "ready_to_submit",
        "submitting",
        "submitted",
        "failed",
    ] = Field(
        "ready",
        description="Form stage / 表单阶段",
    )
    record_id: int | str | None = Field(
        None,
        description="Editing record id / 编辑目标记录 ID",
    )
    remaining_required_fields: list[str] = Field(
        default_factory=list,
        description="Remaining required fields / 剩余必填字段",
    )
    can_submit: bool = Field(
        False,
        description="Whether the form can submit / 是否可提交",
    )
    submit_policy: Literal["auto", "confirm", "off"] = Field(
        "confirm",
        description="Submit policy / 提交策略",
    )

    @model_validator(mode="after")
    def normalize_remaining_required_fields(self) -> ActiveFormSummary:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in self.remaining_required_fields:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text[:128])
            if len(normalized) >= 32:
                break
        self.remaining_required_fields = normalized
        return self


class SuggestedTools(BaseModel):
    """Suggested UI tools for current page / 当前页面推荐工具。"""

    model_config = ConfigDict(extra="ignore")

    primary: list[str] = Field(
        default_factory=list,
        description="Primary suggested tools / 主要推荐工具",
    )
    secondary: list[str] = Field(
        default_factory=list,
        description="Secondary suggested tools / 次要推荐工具",
    )
    reason: str | None = Field(
        None,
        max_length=240,
        description="Suggestion reason / 推荐理由",
    )

    @model_validator(mode="after")
    def normalize_tools(self) -> SuggestedTools:
        def _normalize(values: list[str]) -> list[str]:
            normalized: list[str] = []
            seen: set[str] = set()
            for item in values:
                name = str(item or "").strip()
                if not name or name in seen:
                    continue
                seen.add(name)
                normalized.append(name[:64])
                if len(normalized) >= 8:
                    break
            return normalized

        self.primary = _normalize(self.primary)
        self.secondary = _normalize(self.secondary)
        return self


class PageContext(BaseModel):
    """统一页面上下文（贯穿 Router 路由决策与标准 Agent 聊天执行链） / Unified page context (Router + Agent chat chain)."""

    model_config = ConfigDict(extra="ignore")

    page_key: str = Field(
        ...,
        description=_("agent_chat.field.page_key"),
        min_length=1,
        max_length=200,
    )
    page_title: str | None = Field(
        None,
        description=_("agent_chat.field.page_title"),
        max_length=200,
    )
    locale: str | None = Field(
        None,
        max_length=32,
        description="Frontend runtime locale / 前端运行时语言",
    )
    page_session_id: str | None = Field(
        None,
        max_length=64,
        description="Page session id / 页面会话 ID",
    )
    ui_epoch: int | None = Field(
        None,
        ge=0,
        description="UI epoch / UI 版本序号",
    )
    active_surface_id: str | None = Field(
        None,
        max_length=128,
        description="Active surface id / 当前活跃 surface",
    )
    active_form_session_id: str | None = Field(
        None,
        max_length=128,
        description="Active form session id / 当前活跃表单会话",
    )
    surface_stack: list[ThinSurfaceSummary] = Field(
        default_factory=list,
        description="Current UI surface stack / 当前 UI surface 栈",
    )
    active_form_summary: ActiveFormSummary | None = Field(
        None,
        description="Active form summary / 活跃表单摘要",
    )
    suggested_tools: SuggestedTools | None = Field(
        None,
        description="Suggested tools for current page / 当前页推荐工具",
    )

    @model_validator(mode="after")
    def normalize_context(self) -> PageContext:
        self.page_key = self.page_key.strip()[:200]
        if self.page_title is not None:
            title = self.page_title.strip()
            self.page_title = title[:200] if title else None
        if self.locale is not None:
            locale = self.locale.strip()
            self.locale = locale[:32] if locale else None
        if self.page_session_id is not None:
            session_id = self.page_session_id.strip()
            self.page_session_id = session_id[:64] if session_id else None
        if self.active_surface_id is not None:
            active_surface_id = self.active_surface_id.strip()
            self.active_surface_id = (
                active_surface_id[:128] if active_surface_id else None
            )
        if self.active_form_session_id is not None:
            active_form_session_id = self.active_form_session_id.strip()
            self.active_form_session_id = (
                active_form_session_id[:128] if active_form_session_id else None
            )

        normalized_stack: list[ThinSurfaceSummary] = []
        seen_surface_ids: set[str] = set()
        for surface in self.surface_stack:
            surface_id = str(surface.surface_id or "").strip()[:128]
            if not surface_id or surface_id in seen_surface_ids:
                continue
            seen_surface_ids.add(surface_id)
            normalized_stack.append(
                surface.model_copy(
                    update={
                        "surface_id": surface_id,
                        "title": (
                            str(surface.title).strip()[:200]
                            if isinstance(surface.title, str) and surface.title.strip()
                            else None
                        ),
                    }
                )
            )
            if len(normalized_stack) >= 12:
                break
        self.surface_stack = normalized_stack

        if self.ui_epoch is not None:
            self.ui_epoch = max(int(self.ui_epoch), 0)

        if self.active_form_summary:
            if self.active_form_summary.entity_name:
                self.active_form_summary = self.active_form_summary.model_copy(
                    update={
                        "entity_name": self.active_form_summary.entity_name.strip()[
                            :128
                        ]
                    }
                )
            if self.active_form_session_id:
                self.active_form_summary = self.active_form_summary.model_copy(
                    update={"form_session_id": self.active_form_session_id}
                )
            elif not self.active_form_session_id:
                self.active_form_session_id = self.active_form_summary.form_session_id

        if self.suggested_tools and not self.suggested_tools.primary:
            self.suggested_tools = None

        if self.active_surface_id and self.surface_stack:
            if self.active_surface_id not in {
                surface.surface_id for surface in self.surface_stack
            }:
                self.active_surface_id = self.surface_stack[-1].surface_id
        elif not self.active_surface_id and self.surface_stack:
            self.active_surface_id = self.surface_stack[-1].surface_id

        return self

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
        ...,
        min_length=1,
        max_length=32000,
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
    "PAGE_CONTEXT_KEY",
    "InteractionMode",
    "AgentChatRequest",
    "AgentChatResponse",
    "InteractionUpdate",
    "PageContext",
    "AgentRouteRequest",
    "AgentRouteResponse",
    "UpdateConversationInteractionStateRequest",
]
