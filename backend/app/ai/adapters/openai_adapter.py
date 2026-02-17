"""
OpenAI 兼容适配器

支持 OpenAI 官方 API 及所有兼容服务（如 DeepSeek、智谱、通义千问等国产大模型）
"""

from typing import AsyncIterator, cast
from decimal import Decimal
import asyncio

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types import CreateEmbeddingResponse

from app.ai.adapters.base import BaseAdapter
from app.ai.exceptions import convert_openai_error, AIGatewayError
from app.core.i18n import _
from app.ai.types import (
    ChatMessage,
    ChatResponse,
    ChatChunk,
    EmbeddingResponse,
)
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")


class OpenAIAdapter(BaseAdapter):
    """
    OpenAI 兼容适配器
    
    支持 OpenAI 官方 API 及所有兼容服务
    """
    
    def __init__(self, api_key: str, base_url: str | None = None, **kwargs):
        super().__init__(api_key, base_url, **kwargs)
        
        # 初始化 OpenAI 客户端
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        
        self.client = AsyncOpenAI(**client_kwargs)
    
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
        """
        try:
            # 转换消息格式
            openai_messages = self._convert_messages(messages)
            
            # 构建请求参数
            request_params: dict = {
                "model": model,
                "messages": openai_messages,
                "temperature": temperature,
                "top_p": top_p,
            }
            
            if max_tokens is not None:
                request_params["max_tokens"] = max_tokens
            
            if tools:
                request_params["tools"] = tools
                request_params["tool_choice"] = "auto"
            
            # 添加额外参数
            request_params.update(kwargs)
            
            # 调用 API
            logger.info("Chat request: model=%s messages=%d", model, len(messages))
            response: ChatCompletion = await self.client.chat.completions.create(**request_params)
            
            # 转换响应
            return self._convert_chat_response(response, model)
            
        except AIGatewayError:
            raise
        except Exception as e:
            logger.error("Chat error: model=%s error=%s", model, str(e))
            raise convert_openai_error(e, provider_code="openai", model_code=model)
    
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
        """
        try:
            # 转换消息格式
            openai_messages = self._convert_messages(messages)
            
            # 构建请求参数
            request_params: dict = {
                "model": model,
                "messages": openai_messages,
                "temperature": temperature,
                "top_p": top_p,
                "stream": True,
            }
            
            if max_tokens is not None:
                request_params["max_tokens"] = max_tokens
            
            if tools:
                request_params["tools"] = tools
                request_params["tool_choice"] = "auto"
            
            # 添加额外参数
            request_params.update(kwargs)
            
            # 调用流式 API
            logger.info("Stream chat request: model=%s", model)
            stream = await self.client.chat.completions.create(**request_params)
            
            # 转换流式响应
            async for chunk in stream:
                yield self._convert_chat_chunk(chunk, model)
                
        except AIGatewayError:
            raise
        except Exception as e:
            logger.error("Stream chat error: model=%s error=%s", model, str(e))
            raise convert_openai_error(e, provider_code="openai", model_code=model)
    
    async def embedding(
        self,
        texts: list[str],
        model: str,
        **kwargs
    ) -> EmbeddingResponse:
        """
        文本嵌入
        """
        try:
            # 调用 API
            logger.info("Embedding request: model=%s texts=%d", model, len(texts))
            response: CreateEmbeddingResponse = await self.client.embeddings.create(
                input=texts,
                model=model,
                **kwargs
            )
            
            # 转换响应
            return EmbeddingResponse(
                embeddings=[item.embedding for item in response.data],
                input_tokens=response.usage.prompt_tokens if response.usage else None,
                total_tokens=response.usage.total_tokens if response.usage else None,
                model=model,
            )
            
        except AIGatewayError:
            raise
        except Exception as e:
            logger.error("Embedding error: model=%s error=%s", model, str(e))
            raise convert_openai_error(e, provider_code="openai", model_code=model)
    
    async def list_models(self) -> list[dict]:
        """
        列出供应商可用的模型列表
        
        通过 OpenAI /models API 获取可用模型
        
        Returns:
            模型信息列表
        """
        try:
            response = await self.client.models.list()
            return [
                {
                    "id": model.id,
                    "owned_by": getattr(model, "owned_by", None),
                }
                for model in response.data
            ]
        except Exception as e:
            logger.error("List models error: %s", str(e))
            raise convert_openai_error(e, provider_code="openai", model_code="")
    
    def _convert_messages(self, messages: list[ChatMessage]) -> list[dict]:
        """
        转换消息格式
        
        Args:
            messages: 统一格式的消息列表
            
        Returns:
            OpenAI 格式的消息列表
        """
        openai_messages = []
        
        for msg in messages:
            openai_msg: dict = {
                "role": msg.role,
            }

            # 多模态内容：user 消息含图片附件时，转换为 content 数组
            if msg.role == "user" and msg.attachments:
                content_parts: list[dict] = []
                if msg.content:
                    content_parts.append({"type": "text", "text": msg.content})
                for att in msg.attachments:
                    att_type = att.get("type", "")
                    att_url = att.get("url", "")
                    if att_type == "image" and att_url:
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {"url": att_url},
                        })
                openai_msg["content"] = content_parts if content_parts else msg.content
            else:
                openai_msg["content"] = msg.content
            
            if msg.name:
                openai_msg["name"] = msg.name
            
            if msg.tool_calls:
                openai_msg["tool_calls"] = msg.tool_calls
            
            if msg.tool_call_id:
                openai_msg["tool_call_id"] = msg.tool_call_id
            
            openai_messages.append(openai_msg)
        
        return openai_messages
    
    def _convert_chat_response(self, response: ChatCompletion, model: str) -> ChatResponse:
        """
        转换 OpenAI 聊天响应为统一格式
        """
        if not response.choices:
            return ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                model=model,
                finish_reason="stop",
            )
        choice = response.choices[0]
        message = choice.message
        
        # 将 OpenAI SDK tool_calls 对象转为 dict 列表
        tool_calls_dicts: list[dict] | None = None
        if message.tool_calls:
            tool_calls_dicts = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        # 构建统一消息格式
        chat_message = ChatMessage(
            role=message.role,
            content=message.content or "",
            tool_calls=tool_calls_dicts,
        )
        
        # 提取 Token 使用量
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else None
        output_tokens = usage.completion_tokens if usage else None
        total_tokens = usage.total_tokens if usage else None
        
        return ChatResponse(
            message=chat_message,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            model=model,
            finish_reason=choice.finish_reason,
            tool_calls=tool_calls_dicts,
            raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
        )
    
    def _convert_chat_chunk(self, chunk: ChatCompletionChunk, model: str) -> ChatChunk:
        """
        转换 OpenAI 流式响应块为统一格式
        """
        if not chunk.choices:
            return ChatChunk(delta="")
        choice = chunk.choices[0]
        delta = choice.delta
        
        # 提取增量内容
        delta_content = delta.content or ""
        
        # 提取 Token 使用量（最后一个块包含）
        usage = chunk.usage
        input_tokens = usage.prompt_tokens if usage else None
        output_tokens = usage.completion_tokens if usage else None
        total_tokens = usage.total_tokens if usage else None
        
        return ChatChunk(
            delta=delta_content,
            role=delta.role,
            finish_reason=choice.finish_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            tool_calls=delta.tool_calls,
        )
    
    def get_supported_features(self) -> dict[str, bool]:
        """
        获取支持的功能
        """
        return {
            "chat": True,
            "streaming": True,
            "function_calling": True,
            "vision": True,
            "embedding": True,
        }


__all__ = [
    "OpenAIAdapter",
]
