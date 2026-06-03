"""
对话消息相关 Schema / Conversation Message Schema

定义对话消息的请求和响应数据结构
Defines conversation message request and response data structures.
"""

from pydantic import Field

from app.core.base_schema import (
    BaseCreateSchema,
    TenantResponseSchema,
)
from app.core.i18n import _


class ConversationMessageCreate(BaseCreateSchema):
    """创建对话消息请求 / Create conversation message request."""

    conversation_id: int = Field(
        ..., description=_("enum.conversation_message.conversation_id")
    )
    role: str = Field(
        ..., max_length=20, description=_("enum.conversation_message.role")
    )
    content: str | None = Field(
        None, description=_("enum.conversation_message.content")
    )
    sequence: int = Field(0, ge=0, description=_("enum.conversation_message.sequence"))
    token_count: int = Field(
        0, ge=0, description=_("enum.conversation_message.token_count")
    )
    tool_calls: list | None = Field(
        None, description=_("enum.conversation_message.tool_calls")
    )
    tool_call_id: str | None = Field(
        None, max_length=100, description=_("enum.conversation_message.tool_call_id")
    )
    model_id: int | None = Field(
        None, description=_("enum.conversation_message.model_id")
    )
    metadata_: dict | None = Field(
        None, alias="metadata", description=_("enum.conversation_message.metadata")
    )


class ConversationMessageResponse(TenantResponseSchema):
    """对话消息响应 / Conversation message response."""

    conversation_id: int = Field(
        ..., description=_("enum.conversation_message.conversation_id")
    )
    role: str = Field(..., description=_("enum.conversation_message.role"))
    content: str | None = Field(
        None, description=_("enum.conversation_message.content")
    )
    sequence: int = Field(..., description=_("enum.conversation_message.sequence"))
    token_count: int = Field(
        ..., description=_("enum.conversation_message.token_count")
    )
    tool_calls: list | None = Field(
        None, description=_("enum.conversation_message.tool_calls")
    )
    tool_call_id: str | None = Field(
        None, description=_("enum.conversation_message.tool_call_id")
    )
    model_id: int | None = Field(
        None, description=_("enum.conversation_message.model_id")
    )


__all__ = [
    "ConversationMessageCreate",
    "ConversationMessageResponse",
]
