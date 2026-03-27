"""
AI Unified Data Types / AI 统一数据类型

Cross-provider unified data structures, abstracting away API differences.
定义跨供应商的统一数据结构，屏蔽不同供应商 API 差异。
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal


@dataclass
class ChatMessage:
    """
    Chat Message / 聊天消息

    Unified chat message format, compatible with all providers.
    统一的聊天消息格式，适配所有供应商。

    Multimodal: when attachments is non-empty, adapter layer converts
    content + attachments to OpenAI content array format (text + image_url).
    多模态：当 attachments 不为空时，adapter 层会将 content + attachments
    转换为 OpenAI 的 content 数组格式。

    reasoning_content: For chain-of-thought models (e.g. DeepSeek R1), kept
    separate from content for display. Persisted in message metadata.
    思考/推理内容（链式思考模型如 DeepSeek R1），与最终答复分离，存入 metadata。
    """

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    attachments: list[dict] | None = None
    reasoning_content: str | None = None
    metadata: dict[str, Any] | None = None
    internal_only: bool = False


@dataclass
class ChatResponse:
    """
    Chat Response / 聊天响应

    Unified chat response format.
    统一的聊天响应格式。
    """

    # Message content / 消息内容
    message: ChatMessage

    # Token usage / Token 使用量
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    # Cost (USD) / 费用（美元）
    cost: Decimal | None = None

    # Model info / 模型信息
    model: str | None = None

    # Finish reason / 完成原因
    finish_reason: str | None = None

    # Tool calls / 工具调用
    tool_calls: list[dict] | None = None

    # Provider raw response (for debugging) / 供应商原始响应（用于调试）
    raw_response: dict | None = None

    # Metadata / 元数据
    metadata: dict = field(default_factory=dict)


@dataclass
class ChatChunk:
    """
    Chat Streaming Chunk / 聊天流式响应块

    Used for SSE streaming responses.
    用于 SSE 流式响应。
    """

    # Delta content / 增量内容
    delta: str

    # Reasoning/thinking delta kept separate from final answer / 与最终答复分离的思考增量
    reasoning_delta: str = ""

    # Role / 角色
    role: str | None = None

    # Finish reason / 是否结束
    finish_reason: str | None = None

    # Cumulative token usage (last chunk contains) / 累计 Token 使用量（最后一个块包含）
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    # Tool calls (incremental) / 工具调用（增量）
    tool_calls: list[dict] | None = None

    # Metadata / 元数据
    metadata: dict = field(default_factory=dict)


@dataclass
class EmbeddingResponse:
    """
    Embedding Response / 嵌入向量响应

    Unified embedding vector format.
    统一的嵌入向量格式。
    """

    # Embedding vectors (list of lists, supports multi-text) / 嵌入向量（列表的列表，支持多文本）
    embeddings: list[list[float]]

    # Token usage / Token 使用量
    input_tokens: int | None = None
    total_tokens: int | None = None

    # Model info / 模型信息
    model: str | None = None

    # Cost / 费用
    cost: Decimal | None = None

    # Metadata / 元数据
    metadata: dict = field(default_factory=dict)


@dataclass
class ImageResponse:
    """
    Image Response / 图像生成响应

    Unified image generation format.
    统一的图像生成格式。
    """

    # Image URL (or base64) / 图像 URL（或 base64）
    url: str

    # Whether base64 / 是否为 base64
    is_base64: bool = False

    # Revised prompt / 修正参数
    revised_prompt: str | None = None

    # Metadata / 元数据
    metadata: dict = field(default_factory=dict)


@dataclass
class ImageGenerationResponse:
    """
    Image Generation Aggregate Response / 图像生成聚合响应

    Contains all images and metadata from a single generation request.
    包含一次生图请求返回的所有图像及元数据。
    """

    # Generated images / 生成的图像列表
    images: list[ImageResponse]

    # Model info / 模型信息
    model: str | None = None

    # Revised prompt (some models rewrite prompt) / 修订后的提示词（某些模型会重写 prompt）
    revised_prompt: str | None = None

    # Metadata / 元数据
    metadata: dict = field(default_factory=dict)


@dataclass
class TestModelResult:
    """
    Model Test Result / 模型测试结果

    Typed return value for the test_model method.
    test_model 方法的类型化返回值。
    """

    connected: bool
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    response_text: str = ""
    error: str | None = None
    model: str = ""
    provider: str = ""


def messages_to_dicts(messages: list[ChatMessage]) -> list[dict]:
    """Convert ChatMessage list to dict list (avoids repeated dataclasses.asdict calls) / 将 ChatMessage 列表转换为 dict 列表"""
    from dataclasses import asdict

    return [asdict(msg) for msg in messages]


__all__ = [
    "ChatMessage",
    "ChatResponse",
    "ChatChunk",
    "EmbeddingResponse",
    "ImageResponse",
    "ImageGenerationResponse",
    "TestModelResult",
    "messages_to_dicts",
]
