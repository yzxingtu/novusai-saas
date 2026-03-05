"""
AI 适配器抽象基类

定义所有供应商适配器必须实现的接口
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
    AI 供应商适配器抽象基类

    所有供应商适配器必须继承此类并实现抽象方法
    """

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        **kwargs
    ):
        """
        初始化适配器

        Args:
            api_key: API 密钥
            base_url: API 基础 URL（可选，用于自定义端点）
            **kwargs: 其他供应商特定配置
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
        聊天对话（同步模式）

        Args:
            messages: 聊天消息列表
            model: 模型名称
            temperature: 温度参数（0-2）
            max_tokens: 最大生成 tokens
            top_p: 核采样参数
            stream: 是否使用流式响应
            tools: 工具列表（Function Calling）
            **kwargs: 其他参数

        Returns:
            ChatResponse: 聊天响应
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
        聊天对话（流式模式）

        Args:
            messages: 聊天消息列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大生成 tokens
            top_p: 核采样参数
            tools: 工具列表
            **kwargs: 其他参数

        Yields:
            ChatChunk: 流式响应块
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
        文本嵌入

        Args:
            texts: 文本列表
            model: 模型名称
            **kwargs: 其他参数

        Returns:
            EmbeddingResponse: 嵌入向量响应
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
        图像生成

        Args:
            prompt: 生成提示词
            model: 模型名称（如 dall-e-3）
            size: 图片尺寸（如 1024x1024, 1792x1024, 1024x1792）
            quality: 质量（standard / hd）
            style: 风格（vivid / natural）
            n: 生成数量
            **kwargs: 其他参数

        Returns:
            ImageGenerationResponse: 图像生成响应

        Raises:
            NotImplementedError: 子类未实现时抛出
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support image generation"
        )

    async def list_models(self) -> list[dict]:
        """
        列出供应商可用的模型列表

        Returns:
            模型信息列表，每项包含 id（模型代码）和 owned_by（所属者）
        """
        # 默认实现：返回空列表（子类可覆盖）
        return []

    def validate_model(self, model: str) -> bool:
        """
        验证模型名称是否有效

        Args:
            model: 模型名称

        Returns:
            是否有效
        """
        # 默认实现：非空字符串即可
        return bool(model and isinstance(model, str))

    def get_supported_features(self) -> dict[str, bool]:
        """
        获取适配器支持的功能

        Returns:
            功能字典，例如：
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
