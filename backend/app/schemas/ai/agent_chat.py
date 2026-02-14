"""
智能体对话相关 Schema

定义对话请求和响应数据结构
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.i18n import _
from app.enums.agent import ConfirmActionEnum


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
    "AgentChatRequest",
    "AgentChatResponse",
    "AgentConfirmRequest",
]
