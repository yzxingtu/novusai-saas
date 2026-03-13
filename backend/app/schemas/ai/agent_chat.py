"""
智能体对话相关 Schema / Agent Chat Schema

定义对话请求和响应数据结构
Defines chat request and response data structures.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.core.i18n import _
from app.enums.agent import ConfirmActionEnum

PAGE_CONTEXT_KEY = "page_context"

# page_data 序列化后最大字节数（8KB — form_fields + operations 等增强数据需要更大空间）
# Max serialized bytes for page_data (8KB — enhanced form_fields + operations need more space)
MAX_PAGE_DATA_BYTES = 8192


class ChatAttachment(BaseModel):
    """对话附件（图片/文件）"""

    type: Literal["image", "file"] = Field(
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
    """图像生成参数"""

    size: str = Field("1024x1024", description=_("agent_chat.field.image_size"))
    quality: str = Field("standard", description=_("agent_chat.field.image_quality"))
    style: str = Field("vivid", description=_("agent_chat.field.image_style"))
    n: int = Field(1, ge=1, le=4, description=_("agent_chat.field.image_n"))


class AgentChatRequest(BaseModel):
    """对话请求"""

    message: str = Field(
        ..., min_length=1, max_length=32000,
        description=_("agent_chat.field.message"),
    )
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


class AgentChatResponse(BaseModel):
    """对话响应（非流式）"""

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


class PageContext(BaseModel):
    """统一页面上下文（贯穿 Router 路由决策与标准 Agent 聊天执行链）"""

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

    @model_validator(mode="after")
    def _check_page_data_size(self) -> "PageContext":
        if self.page_data is not None:
            import json as _json

            serialized = _json.dumps(self.page_data, ensure_ascii=False, default=str)
            if len(serialized.encode("utf-8")) > MAX_PAGE_DATA_BYTES:
                raise ValueError(
                    f"page_data exceeds {MAX_PAGE_DATA_BYTES} bytes limit"
                )
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
    """智能路由请求"""

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


class AgentRouteResponse(BaseModel):
    """智能路由响应"""

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


class AgentConfirmRequest(BaseModel):
    """确认/取消操作请求"""

    confirm_id: str = Field(
        ..., min_length=1,
        description=_("agent_chat.field.confirm_id"),
    )
    action: Literal[
        ConfirmActionEnum.CONFIRM.value,
        ConfirmActionEnum.CANCEL.value,
    ] = Field(
        ...,
        description=_("agent_chat.field.confirm_action"),
    )


__all__ = [
    "ChatAttachment",
    "ImageParams",
    "PAGE_CONTEXT_KEY",
    "AgentChatRequest",
    "AgentChatResponse",
    "PageContext",
    "AgentRouteRequest",
    "AgentRouteResponse",
    "AgentConfirmRequest",
]
