"""
OpenAI Compatible Adapter / OpenAI 兼容适配器

Supports OpenAI official API and all compatible services
(e.g. DeepSeek, Zhipu, Tongyi Qianwen and other domestic LLMs).
支持 OpenAI 官方 API 及所有兼容服务（如 DeepSeek、智谱、通义千问等国产大模型）。
"""

from __future__ import annotations

import base64
import re

from collections.abc import AsyncIterator

import httpx
from openai import AsyncOpenAI
from openai.types import CreateEmbeddingResponse
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from app.ai.adapters.base import BaseAdapter
from app.ai.exceptions import AIGatewayError, convert_openai_error
from app.ai.types import (
    ChatChunk,
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    ImageGenerationResponse,
    ImageResponse,
)
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")

# Native audio: when True and supports_audio, convert audio attachments to OpenAI input_audio block
# 原生音频：为 True 且 supports_audio 时，将音频附件转为 OpenAI input_audio 块
SUPPORTS_NATIVE_AUDIO: bool = True

# MIME type → OpenAI input_audio format (no magic strings)
# MIME 类型 → OpenAI input_audio format
_AUDIO_MIME_TO_OPENAI_FORMAT: dict[str, str] = {
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/flac": "flac",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
    "audio/aac": "m4a",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
    "audio/mpeg3": "mpeg",
    "audio/mpg": "mpeg",
}

# Fetch timeout (seconds) and max size for audio URL → bytes
# 音频 URL 拉取超时（秒）与最大字节数
_AUDIO_FETCH_TIMEOUT_SEC: float = 30.0
_AUDIO_MAX_BYTES: int = 25 * 1024 * 1024  # 25 MB


class OpenAIAdapter(BaseAdapter):
    """
    OpenAI Compatible Adapter / OpenAI 兼容适配器

    Supports OpenAI official API and all compatible services.
    支持 OpenAI 官方 API 及所有兼容服务。
    """

    def __init__(self, api_key: str, base_url: str | None = None, **kwargs):
        super().__init__(api_key, base_url, **kwargs)

        # Initialize OpenAI client / 初始化 OpenAI 客户端
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
        Chat conversation (synchronous mode) / 聊天对话（同步模式）
        """
        _ = stream
        try:
            # Pop adapter-only flags before building request params / 提取适配器专用标志，避免传入 API
            vision_flag = kwargs.pop("supports_vision", True)
            audio_flag = kwargs.pop("supports_audio", False)
            video_flag = kwargs.pop("supports_video", False)

            # Convert message format / 转换消息格式
            openai_messages = await self._convert_messages(
                messages,
                supports_vision=vision_flag,
                supports_audio=audio_flag,
                supports_video=video_flag,
            )

            # Build request parameters / 构建请求参数
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

            # Add extra parameters / 添加额外参数
            request_params.update(kwargs)

            # Call API / 调用 API
            logger.info("Chat request: model=%s messages=%d", model, len(messages))
            response: ChatCompletion = await self.client.chat.completions.create(**request_params)

            # Convert response / 转换响应
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
        Chat conversation (streaming mode) / 聊天对话（流式模式）
        """
        try:
            # Pop adapter-only flags before building request params / 提取适配器专用标志，避免传入 API
            vision_flag = kwargs.pop("supports_vision", True)
            audio_flag = kwargs.pop("supports_audio", False)
            video_flag = kwargs.pop("supports_video", False)

            # Convert message format / 转换消息格式
            openai_messages = await self._convert_messages(
                messages,
                supports_vision=vision_flag,
                supports_audio=audio_flag,
                supports_video=video_flag,
            )

            # Build request parameters / 构建请求参数
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

            # Add extra parameters / 添加额外参数
            request_params.update(kwargs)

            # Call streaming API / 调用流式 API
            logger.info("Stream chat request: model=%s", model)
            stream = await self.client.chat.completions.create(**request_params)

            # Convert streaming response / 转换流式响应
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
        Text embedding / 文本嵌入
        """
        try:
            # Call API / 调用 API
            logger.info("Embedding request: model=%s texts=%d", model, len(texts))
            response: CreateEmbeddingResponse = await self.client.embeddings.create(
                input=texts,
                model=model,
                **kwargs
            )

            # Convert response / 转换响应
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
        List available models for the provider / 列出供应商可用的模型列表

        Fetches available models via OpenAI /models API.
        通过 OpenAI /models API 获取可用模型。

        Returns:
            Model info list / 模型信息列表
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

    async def _fetch_audio_bytes(self, url: str) -> bytes | None:
        """
        Resolve audio URL to bytes for input_audio. Supports data URL or HTTP GET.
        / 将音频 URL 解析为字节供 input_audio 使用。支持 data URL 或 HTTP GET。

        Returns:
            Audio bytes, or None on failure / 成功返回音频字节，失败返回 None
        """
        if not url or not url.strip():
            return None
        url = url.strip()
        # data URL: data:audio/xxx;base64,<b64>
        if url.startswith("data:audio"):
            match = re.match(r"data:audio/[^;]+;base64,(.+)", url, re.DOTALL)
            if match:
                try:
                    return base64.b64decode(match.group(1))
                except Exception as e:
                    logger.warning("Audio data URL base64 decode failed: %s", e)
                    return None
            return None
        try:
            async with httpx.AsyncClient(timeout=_AUDIO_FETCH_TIMEOUT_SEC) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                content_length = resp.headers.get("content-length")
                try:
                    cl = int(content_length) if (content_length and content_length.strip().isdigit()) else None
                except (ValueError, AttributeError):
                    cl = None
                if cl is not None and cl > _AUDIO_MAX_BYTES:
                    logger.warning(
                        "Audio too large (content-length=%s > %s), skip native",
                        cl,
                        _AUDIO_MAX_BYTES,
                    )
                    return None
                data = resp.content
                if len(data) > _AUDIO_MAX_BYTES:
                    logger.warning(
                        "Audio body too large (%d > %d), skip native",
                        len(data),
                        _AUDIO_MAX_BYTES,
                    )
                    return None
                return data
        except Exception as e:
            logger.warning("Fetch audio URL failed: %s", e)
            return None

    async def _convert_messages(
        self,
        messages: list[ChatMessage],
        *,
        supports_vision: bool = True,
        supports_audio: bool = False,
        supports_video: bool = False,
    ) -> list[dict]:
        """
        Convert message format / 转换消息格式

        Args:
            messages: Unified format message list / 统一格式的消息列表
            supports_vision: Whether the target model supports vision (image_url content).
                             When False, image attachments are converted to text hints.
                             目标模型是否支持视觉（image_url 内容）。为 False 时图片附件转为文字提示。
            supports_audio: Whether the target model supports audio input. When False, audio → text hint.
                            目标模型是否支持音频输入。为 False 时音频附件转为文字提示。
            supports_video: Whether the target model supports video input. When False, video → text hint.
                            目标模型是否支持视频输入。为 False 时视频附件转为文字提示。

        Returns:
            OpenAI format message list / OpenAI 格式的消息列表
        """
        openai_messages = []

        for msg in messages:
            openai_msg: dict = {
                "role": msg.role,
            }

            # Multimodal content: when user message has attachments, convert to content array
            # 多模态内容：user 消息含附件时转换为 content 数组（image/audio/video/file）
            if msg.role == "user" and msg.attachments:
                content_parts: list[dict] = []
                if msg.content:
                    content_parts.append({"type": "text", "text": msg.content})
                for att in msg.attachments:
                    att_type = att.get("type", "")
                    att_url = att.get("url", "")
                    att_name = att.get("name", "")
                    att_mime = att.get("mime_type", "")
                    if att_type == "image" and att_url:
                        if supports_vision:
                            content_parts.append({
                                "type": "image_url",
                                "image_url": {"url": att_url},
                            })
                        else:
                            # Non-vision model: degrade to text hint / 非视觉模型：降级为文字提示
                            hint = f"[Image: {att_name or 'uploaded image'}]"
                            content_parts.append({"type": "text", "text": hint})
                    elif att_type == "audio":
                        # Audio: when supports_audio and native supported, use input_audio block; else text hint
                        # 音频：supports_audio 且支持原生时使用 input_audio 块；否则文字提示
                        hint = f"[Audio: {att_name or 'uploaded audio'}]"
                        if not att_url:
                            content_parts.append({"type": "text", "text": hint})
                        elif supports_audio and SUPPORTS_NATIVE_AUDIO:
                            bytes_result = await self._fetch_audio_bytes(att_url)
                            if bytes_result is None:
                                content_parts.append({"type": "text", "text": hint})
                            else:
                                fmt = _AUDIO_MIME_TO_OPENAI_FORMAT.get(att_mime) or "mpeg"
                                b64_str = base64.b64encode(bytes_result).decode("ascii")
                                content_parts.append({
                                    "type": "input_audio",
                                    "input_audio": {"data": b64_str, "format": fmt},
                                })
                        else:
                            content_parts.append({"type": "text", "text": hint})
                    elif att_type == "video" and att_url:
                        # Video: native format to be extended when vendor API supports it; for now text hint
                        # 视频：原生格式待厂商支持后扩展；当前为文字提示
                        if supports_video:
                            hint = f"[Video: {att_name or 'uploaded video'}]"
                            content_parts.append({"type": "text", "text": hint})
                        else:
                            hint = f"[Video: {att_name or 'uploaded video'}]"
                            content_parts.append({"type": "text", "text": hint})
                    elif att_type == "file" and att_name:
                        file_hint = f"[Attached file: {att_name}"
                        if att_mime:
                            file_hint += f", type: {att_mime}"
                        file_hint += "]"
                        content_parts.append({"type": "text", "text": file_hint})
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
        Convert OpenAI chat response to unified format / 转换 OpenAI 聊天响应为统一格式
        """
        if not response.choices:
            return ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                model=model,
                finish_reason="stop",
            )
        choice = response.choices[0]
        message = choice.message

        # Convert OpenAI SDK tool_calls objects to dict list / 将 OpenAI SDK tool_calls 对象转为 dict 列表
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

        # Build unified message format / 构建统一消息格式
        chat_message = ChatMessage(
            role=message.role,
            content=message.content or "",
            tool_calls=tool_calls_dicts,
        )

        # Extract token usage / 提取 Token 使用量
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
        Convert OpenAI streaming response chunk to unified format / 转换 OpenAI 流式响应块为统一格式
        """
        _ = model
        if not chunk.choices:
            return ChatChunk(delta="")
        choice = chunk.choices[0]
        delta = choice.delta

        # Extract delta content (compatible with reasoning_content used by some relay models) / 提取增量内容（兼容 reasoning_content）
        delta_content = delta.content or ""
        if not delta_content:
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                delta_content = reasoning

        # Extract token usage (included in the last chunk) / 提取 Token 使用量（最后一个块包含）
        usage = chunk.usage
        input_tokens = usage.prompt_tokens if usage else None
        output_tokens = usage.completion_tokens if usage else None
        total_tokens = usage.total_tokens if usage else None

        # Convert OpenAI SDK tool_calls to serializable dict list (with index for incremental merging) / 将 OpenAI SDK tool_calls 对象转为可序列化 dict 列表
        tool_calls_dicts: list[dict] | None = None
        if delta.tool_calls:
            tool_calls_dicts = []
            for tc in delta.tool_calls:
                func = getattr(tc, "function", None)
                tool_calls_dicts.append(
                    {
                        "index": getattr(tc, "index", None),
                        "id": getattr(tc, "id", None) or "",
                        "type": getattr(tc, "type", None) or "function",
                        "function": {
                            "name": getattr(func, "name", None) or "",
                            "arguments": getattr(func, "arguments", None) or "",
                        },
                    }
                )

        return ChatChunk(
            delta=delta_content,
            role=delta.role,
            finish_reason=choice.finish_reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            tool_calls=tool_calls_dicts,
        )

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
        Image generation (calls OpenAI /v1/images/generations) / 图像生成
        """
        try:
            logger.info(
                "Image generation request: model=%s size=%s quality=%s n=%d",
                model, size, quality, n,
            )

            request_params: dict = {
                "model": model,
                "prompt": prompt,
                "size": size,
                "quality": quality,
                "n": n,
                "response_format": "url",
            }
            # style only supported by dall-e-3 / style 仅 dall-e-3 支持
            if "dall-e-3" in model:
                request_params["style"] = style

            request_params.update(kwargs)

            response = await self.client.images.generate(**request_params)

            images: list[ImageResponse] = []
            revised_prompt: str | None = None
            for item in response.data:
                url = item.url or ""
                b64 = item.b64_json or ""
                is_base64 = bool(b64 and not url)
                rp = getattr(item, "revised_prompt", None)
                if rp and not revised_prompt:
                    revised_prompt = rp
                images.append(ImageResponse(
                    url=b64 if is_base64 else url,
                    is_base64=is_base64,
                    revised_prompt=rp,
                ))

            return ImageGenerationResponse(
                images=images,
                model=model,
                revised_prompt=revised_prompt,
            )

        except AIGatewayError:
            raise
        except Exception as e:
            logger.error("Image generation error: model=%s error=%s", model, str(e))
            raise convert_openai_error(e, provider_code="openai", model_code=model)

    def get_supported_features(self) -> dict[str, bool]:
        """
        Get supported features / 获取支持的功能
        """
        return {
            "chat": True,
            "streaming": True,
            "function_calling": True,
            "vision": True,
            "embedding": True,
            "image_generation": True,
        }


__all__ = [
    "OpenAIAdapter",
]
