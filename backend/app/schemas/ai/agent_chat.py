"""
智能体对话相关 Schema

定义对话请求和响应数据结构
"""

from typing import Any

from pydantic import BaseModel, Field

from app.core.i18n import _


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


__all__ = [
    "AgentChatRequest",
    "AgentChatResponse",
]
