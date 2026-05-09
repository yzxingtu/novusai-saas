"""
AI 网关请求/响应 Schema / AI Gateway Request/Response Schema

AI 网关调用的请求和响应数据结构
Data structures for AI gateway call requests and responses.
"""

import json
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.core.i18n import _
from app.schemas.ai.invalid_ai_runtime_input import (
    ensure_no_disallowed_ai_runtime_input,
    is_invalid_ai_runtime_reference,
)


def _validate_tool_function(function: dict[str, Any]) -> dict[str, Any]:
    ensure_no_disallowed_ai_runtime_input(function)
    tool_name = str(function.get("name") or "").strip()
    if tool_name and is_invalid_ai_runtime_reference(tool_name):
        raise ValueError(
            _(
                "agent_chat.error.invalid_ai_runtime_input_tool",
                tool=tool_name,
            )
        )
    arguments = function.get("arguments")
    if isinstance(arguments, str) and arguments.strip().startswith(("{", "[")):
        try:
            parsed_arguments = json.loads(arguments)
        except json.JSONDecodeError:
            parsed_arguments = None
        if isinstance(parsed_arguments, dict):
            ensure_no_disallowed_ai_runtime_input(parsed_arguments)
    return function


class ToolCall(BaseModel):
    """Tool call definition / 工具调用定义"""

    id: str = Field(..., description="Tool call ID")
    type: str = Field(default="function", description="Type")
    function: dict[str, Any] = Field(..., description="Function info")

    @field_validator("function")
    @classmethod
    def validate_function(cls, v: dict[str, Any]) -> dict[str, Any]:
        return _validate_tool_function(v)


class ToolDefinition(BaseModel):
    """Tool definition / 工具定义"""

    type: str = Field(default="function", description="Type")
    function: dict[str, Any] = Field(..., description="Function definition")

    @field_validator("function")
    @classmethod
    def validate_function(cls, v: dict[str, Any]) -> dict[str, Any]:
        return _validate_tool_function(v)


class ChatMessage(BaseModel):
    """Chat message / 对话消息"""

    role: Literal["system", "user", "assistant", "tool"] = Field(
        ..., description="Message role"
    )
    content: str | None = Field(None, description="Message content")
    tool_calls: list[ToolCall] | None = Field(
        default=None, description="Tool call list"
    )
    tool_call_id: str | None = Field(default=None, description="Tool call ID")

    model_config = {"extra": "forbid"}


class UsageInfo(BaseModel):
    """Token usage info / Token 用量信息"""

    input_tokens: int = Field(..., description="Input tokens")
    output_tokens: int = Field(..., description="Output tokens")
    total_tokens: int = Field(..., description="Total tokens")
    cost: Decimal | None = Field(None, description="Cost (USD)")


class ChatChoice(BaseModel):
    """Chat choice / 对话选项"""

    index: int = Field(..., description="Index")
    message: ChatMessage = Field(..., description="Message")
    finish_reason: str | None = Field(default=None, description="Finish reason")


class DeltaContent(BaseModel):
    """Delta content (SSE streaming response) / 增量内容（SSE 流式响应）"""

    role: str | None = Field(default=None, description="Role")
    content: str | None = Field(default=None, description="Content")
    tool_calls: list[ToolCall] | None = Field(default=None, description="Tool calls")


class ChatRequest(BaseModel):
    """Chat request / 对话请求"""

    model_code: str = Field(
        ..., description="Model code", examples=["gpt-4", "claude-3-opus"]
    )
    messages: list[ChatMessage] = Field(..., description="Message list", min_length=1)
    stream: bool = Field(default=False, description="Enable streaming response")
    temperature: float = Field(default=0.7, ge=0, le=2, description="Temperature")
    max_tokens: int | None = Field(
        default=None, ge=1, description="Max generation tokens"
    )
    top_p: float = Field(
        default=1.0, ge=0, le=1, description="Top-p (nucleus sampling)"
    )
    tools: list[ToolDefinition] | None = Field(default=None, description="Tool list")
    user: str | None = Field(default=None, description="User identifier")

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, v: list[ChatMessage]) -> list[ChatMessage]:
        """Validate message list / 校验消息列表"""
        if not v:
            raise ValueError("messages must not be empty")
        return v

    model_config = {"extra": "forbid"}


class ChatResponse(BaseModel):
    """Chat response / 对话响应"""

    id: str = Field(..., description="Response ID")
    model: str = Field(..., description="Model name")
    choices: list[ChatChoice] = Field(..., description="Choice list")
    usage: UsageInfo = Field(..., description="Usage info")
    created: int = Field(..., description="Created timestamp")

    model_config = {"extra": "allow"}


class ChatChunk(BaseModel):
    """Chat chunk (SSE streaming response) / 对话分片（SSE 流式响应）"""

    id: str = Field(..., description="Response ID")
    model: str = Field(..., description="Model name")
    choices: list[dict] = Field(..., description="Choice list")
    created: int = Field(..., description="Created timestamp")

    model_config = {"extra": "allow"}


class EmbeddingRequest(BaseModel):
    """Embedding request / 向量化请求"""

    model_code: str = Field(
        ..., description="Model code", examples=["text-embedding-ada-002"]
    )
    texts: list[str] = Field(
        ..., description="Text list", min_length=1, max_length=2048
    )
    user: str | None = Field(default=None, description="User identifier")

    @field_validator("texts")
    @classmethod
    def validate_texts(cls, v: list[str]) -> list[str]:
        """Validate text list / 校验文本列表"""
        if not v:
            raise ValueError("texts must not be empty")
        if len(v) > 2048:
            raise ValueError("texts supports a maximum of 2048 items")
        return v


class EmbeddingData(BaseModel):
    """Embedding vector data / 向量数据"""

    index: int = Field(..., description="Index")
    embedding: list[float] = Field(..., description="Vector")
    object: str = Field(default="embedding", description="Object type")


class EmbeddingResponse(BaseModel):
    """Embedding response / 向量化响应"""

    id: str = Field(..., description="Response ID")
    model: str = Field(..., description="Model name")
    data: list[EmbeddingData] = Field(..., description="Embedding vector data")
    usage: UsageInfo = Field(..., description="Usage info")

    model_config = {"extra": "allow"}


class ModelTestRequest(BaseModel):
    """Model test request / 模型测试请求"""

    provider_id: int = Field(..., description="Provider ID")
    model_code: str = Field(
        ..., description="Model code", examples=["gpt-4", "claude-3-opus"]
    )
    test_prompt: str = Field(default="Hello", description="Test prompt")
    stream: bool = Field(default=False, description="Enable streaming response")
    temperature: float = Field(default=0.7, ge=0, le=2, description="Temperature")
    max_tokens: int | None = Field(
        default=500, ge=1, description="Max generation tokens"
    )

    model_config = {"extra": "allow"}


class ModelTestResponse(BaseModel):
    """Model test response / 模型测试响应"""

    connected: bool = Field(..., description="Connection successful")
    latency_ms: int = Field(..., description="Response time (ms)")
    input_tokens: int = Field(default=0, description="Input tokens")
    output_tokens: int = Field(default=0, description="Output tokens")
    total_tokens: int = Field(default=0, description="Total tokens")
    response_text: str = Field(default="", description="Response text")
    error: str | None = Field(default=None, description="Error message")
    model: str = Field(..., description="Model name")
    provider: str = Field(..., description="Provider code")
    trace_id: str | None = Field(default=None, description="Trace ID")
    wire_api: str | None = Field(default=None, description="Wire API")
    effective_upstream_model: str | None = Field(
        default=None,
        description="Effective upstream model id",
    )
    effective_reasoning_effort: str | None = Field(
        default=None,
        description="Effective reasoning effort",
    )
    applied_overrides: list[str] | None = Field(
        default=None,
        description="Applied runtime override keys",
    )
    ignored_overrides: list[str] | None = Field(
        default=None,
        description="Ignored runtime override keys",
    )
    ignore_reasons: dict[str, str] | None = Field(
        default=None,
        description="Reasons why runtime overrides were ignored",
    )

    model_config = {"extra": "allow"}


__all__ = [
    "ToolCall",
    "ToolDefinition",
    "ChatMessage",
    "UsageInfo",
    "ChatChoice",
    "DeltaContent",
    "ChatRequest",
    "ChatResponse",
    "ChatChunk",
    "EmbeddingRequest",
    "EmbeddingData",
    "EmbeddingResponse",
    "ModelTestRequest",
    "ModelTestResponse",
]
