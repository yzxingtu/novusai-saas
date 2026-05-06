"""Shared rich-text AI request schemas / 富文本 AI 共享请求 schema。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PlainTextInputAiAction = Literal[
    "continue",
    "custom",
    "expand",
    "format",
    "insert",
    "optimize",
    "proofread",
    "rewrite",
    "summarize",
    "translate",
    "chat",
]
PlainTextInputAiFieldKind = Literal[
    "code",
    "description",
    "markdown",
    "plain",
    "secret",
    "structured",
    "title",
]


class AIWritingHistoryTurn(BaseModel):
    """Editor-local chat history turn / 编辑器本地对话历史轮次。"""

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class PlainTextInputAiPolicyEnvelope(BaseModel):
    """Plain input field policy envelope / 普通输入框字段策略信封。"""

    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    field_kind: PlainTextInputAiFieldKind = "plain"
    allowed_actions: list[PlainTextInputAiAction] = Field(max_length=11)


__all__ = [
    "AIWritingHistoryTurn",
    "PlainTextInputAiAction",
    "PlainTextInputAiFieldKind",
    "PlainTextInputAiPolicyEnvelope",
]
