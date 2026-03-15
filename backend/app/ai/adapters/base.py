"""
AI Adapter Abstract Base Class / AI 适配器抽象基类

Defines the interface that all provider adapters must implement.
定义所有供应商适配器必须实现的接口。
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.ai.types import (
    ChatChunk,
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    ImageGenerationResponse,
)


class BaseAdapter(ABC):
    """
    AI Provider Adapter Abstract Base Class / AI 供应商适配器抽象基类

    All provider adapters must inherit this class and implement abstract methods.
    所有供应商适配器必须继承此类并实现抽象方法。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        **kwargs
    ):
        """
        Initialize adapter / 初始化适配器

        Args:
            api_key: API key / API 密钥
            base_url: API base URL (optional, for custom endpoints) / API 基础 URL（可选）
            **kwargs: Other provider-specific configuration / 其他供应商特定配置
        """
        self.api_key = api_key
        self.base_url = base_url
        self.config = kwargs

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        stream: bool = False,
        tools: list[dict] | None = None,
        **kwargs
    ) -> ChatResponse:
        """
        Chat conversation (synchronous mode) / 聊天对话（同步模式）

        Args:
            messages: Chat message list / 聊天消息列表
            model: Model name / 模型名称
            temperature: Temperature parameter (0-2) / 温度参数
            max_tokens: Maximum generated tokens / 最大生成 tokens
            top_p: Nucleus sampling parameter / 核采样参数
            stream: Whether to use streaming response / 是否使用流式响应
            tools: Tool list (Function Calling) / 工具列表
            **kwargs: Other parameters / 其他参数

        Returns:
            ChatResponse: Chat response / 聊天响应
        """
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        **kwargs
    ) -> AsyncIterator[ChatChunk]:
        """
        Chat conversation (streaming mode) / 聊天对话（流式模式）

        Args:
            messages: Chat message list / 聊天消息列表
            model: Model name / 模型名称
            temperature: Temperature parameter / 温度参数
            max_tokens: Maximum generated tokens / 最大生成 tokens
            top_p: Nucleus sampling parameter / 核采样参数
            tools: Tool list / 工具列表
            **kwargs: Other parameters / 其他参数

        Yields:
            ChatChunk: Streaming response chunk / 流式响应块
        """
        pass

    @abstractmethod
    async def embedding(
        self,
        texts: list[str],
        model: str,
        **kwargs
    ) -> EmbeddingResponse:
        """
        Text embedding / 文本嵌入

        Args:
            texts: Text list / 文本列表
            model: Model name / 模型名称
            **kwargs: Other parameters / 其他参数

        Returns:
            EmbeddingResponse: Embedding vector response / 嵌入向量响应
        """
        pass

    async def generate_image(
        self,
        prompt: str,
        model: str,
        size: str = "1024x1024",
        quality: str = "standard",
        style: str = "vivid",
        n: int = 1,
        **kwargs,
    ) -> ImageGenerationResponse:
        """
        Image generation / 图像生成

        Args:
            prompt: Generation prompt / 生成提示词
            model: Model name (e.g. dall-e-3) / 模型名称
            size: Image size (e.g. 1024x1024, 1792x1024, 1024x1792) / 图片尺寸
            quality: Quality (standard / hd) / 质量
            style: Style (vivid / natural) / 风格
            n: Number to generate / 生成数量
            **kwargs: Other parameters / 其他参数

        Returns:
            ImageGenerationResponse: Image generation response / 图像生成响应

        Raises:
            NotImplementedError: Raised when subclass not implemented / 子类未实现时抛出
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support image generation"
        )

    async def list_models(self) -> list[dict]:
        """
        List available models for the provider / 列出供应商可用的模型列表

        Returns:
            Model info list, each containing id (model code) and owned_by (owner)
            模型信息列表，每项包含 id和 owned_by
        """
        # Default implementation: return empty list (subclass can override) / 默认实现：返回空列表
        return []

    def validate_model(self, model: str) -> bool:
        """
        Validate model name / 验证模型名称是否有效

        Args:
            model: Model name / 模型名称

        Returns:
            Whether valid / 是否有效
        """
        # Default implementation: non-empty string is valid / 默认实现：非空字符串即可
        return bool(model and isinstance(model, str))

    def get_supported_features(self) -> dict[str, bool]:
        """
        Get adapter supported features / 获取适配器支持的功能

        Returns:
            Feature dictionary / 功能字典，例如：
            {
                "chat": True,
                "streaming": True,
                "function_calling": True,
                "vision": False,
                "embedding": True,
            }
        """
        return {
            "chat": True,
            "streaming": True,
            "function_calling": False,
            "vision": False,
            "embedding": False,
            "image_generation": False,
        }


__all__ = [
    "BaseAdapter",
]
