"""
AI 统一数据类型

定义跨供应商的统一数据结构，屏蔽不同供应商 API 差异
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal


@dataclass
class ChatMessage:
    """
    聊天消息

    统一的聊天消息格式，适配所有供应商

    多模态内容：当 attachments 不为空时，adapter 层会将 content + attachments
    转换为 OpenAI 的 content 数组格式（text + image_url 部分）。
    """
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    attachments: list[dict] | None = None


@dataclass
class ChatResponse:
    """
    聊天响应

    统一的聊天响应格式
    """
    # 消息内容
    message: ChatMessage

    # Token 使用量
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    # 费用（美元）
    cost: Decimal | None = None

    # 模型信息
    model: str | None = None

    # 完成原因
    finish_reason: str | None = None

    # 工具调用
    tool_calls: list[dict] | None = None

    # 供应商原始响应（用于调试）
    raw_response: dict | None = None

    # 元数据
    metadata: dict = field(default_factory=dict)


@dataclass
class ChatChunk:
    """
    聊天流式响应块

    用于 SSE 流式响应
    """
    # 增量内容
    delta: str

    # 角色
    role: str | None = None

    # 是否结束
    finish_reason: str | None = None

    # 累计 Token 使用量（最后一个块包含）
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    # 工具调用（增量）
    tool_calls: list[dict] | None = None

    # 元数据
    metadata: dict = field(default_factory=dict)


@dataclass
class EmbeddingResponse:
    """
    嵌入向量响应

    统一的嵌入向量格式
    """
    # 嵌入向量（列表的列表，支持多文本）
    embeddings: list[list[float]]

    # Token 使用量
    input_tokens: int | None = None
    total_tokens: int | None = None

    # 模型信息
    model: str | None = None

    # 费用
    cost: Decimal | None = None

    # 元数据
    metadata: dict = field(default_factory=dict)


@dataclass
class ImageResponse:
    """
    图像生成响应

    统一的图像生成格式
    """
    # 图像 URL（或 base64）
    url: str

    # 是否为 base64
    is_base64: bool = False

    # 修正参数
    revised_prompt: str | None = None

    # 元数据
    metadata: dict = field(default_factory=dict)


@dataclass
class ImageGenerationResponse:
    """
    图像生成聚合响应

    包含一次生图请求返回的所有图像及元数据
    """
    # 生成的图像列表
    images: list[ImageResponse]

    # 模型信息
    model: str | None = None

    # 修订后的提示词（某些模型会重写 prompt）
    revised_prompt: str | None = None

    # 元数据
    metadata: dict = field(default_factory=dict)


@dataclass
class TestModelResult:
    """
    模型测试结果

    test_model 方法的类型化返回值
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
    """将 ChatMessage 列表转换为 dict 列表（避免重复 dataclasses.asdict 调用）"""
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
