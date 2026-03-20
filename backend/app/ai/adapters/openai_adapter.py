"""
OpenAI Compatible Adapter / OpenAI 兼容适配器

Supports OpenAI official API and all compatible services
(e.g. DeepSeek, Zhipu, Tongyi Qianwen and other domestic LLMs).
支持 OpenAI 官方 API 及所有兼容服务（如 DeepSeek、智谱、通义千问等国产大模型）。
"""

from __future__ import annotations

import base64
import json
import re

from collections.abc import AsyncIterator
from typing import Any

import httpx
from openai import AsyncOpenAI
from openai.types import CreateEmbeddingResponse
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from app.ai.adapters.base import BaseAdapter
from app.ai.utils.chat_attachment_media import resolve_image_url_for_llm
from app.ai.constants import OPENAI_COMPATIBLE_URL_SUFFIX_TO_WIRE_API
from app.ai.exceptions import AIGatewayError, convert_openai_error
from app.ai.tools.security import SSRFBlockedError, UrlValidator
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

        provider_config = self.config.get("provider_config")
        self.provider_config = provider_config.copy() if isinstance(provider_config, dict) else {}
        self.base_url, inferred_wire_api = self._normalize_base_url(base_url)

        # Initialize OpenAI client / 初始化 OpenAI 客户端
        client_kwargs = {"api_key": api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        self.client = AsyncOpenAI(**client_kwargs)
        self.wire_api = self._resolve_wire_api(
            self.provider_config.get("wire_api"),
            inferred_wire_api=inferred_wire_api,
        )

    def _normalize_base_url(self, base_url: str | None) -> tuple[str | None, str | None]:
        normalized = str(base_url or "").strip()
        if not normalized:
            return None, None

        normalized = normalized.rstrip("/")
        lower_normalized = normalized.lower()
        for suffix, inferred_wire_api in OPENAI_COMPATIBLE_URL_SUFFIX_TO_WIRE_API.items():
            if lower_normalized.endswith(suffix):
                stripped_base_url = normalized[: -len(suffix)].rstrip("/")
                if stripped_base_url:
                    logger.warning(
                        "AI provider base_url includes endpoint path; normalized base_url from {} to {} and inferred wire_api={}",
                        normalized,
                        stripped_base_url,
                        inferred_wire_api,
                    )
                    return stripped_base_url, inferred_wire_api
                return normalized, inferred_wire_api

        return normalized, None

    def _resolve_wire_api(self, wire_api: Any, *, inferred_wire_api: str | None = None) -> str:
        configured_wire_api = str(wire_api or "").strip()
        if configured_wire_api:
            normalized_wire_api = self._normalize_wire_api(configured_wire_api)
            if inferred_wire_api and normalized_wire_api != inferred_wire_api:
                logger.warning(
                    "AI provider wire_api overrides inferred endpoint: configured={} inferred={}",
                    normalized_wire_api,
                    inferred_wire_api,
                )
            return normalized_wire_api

        if inferred_wire_api:
            return self._normalize_wire_api(inferred_wire_api)
        return self._normalize_wire_api(None)

    def _get_effective_base_url(self) -> str:
        return (self.base_url or "https://api.openai.com/v1").rstrip("/")

    def _build_endpoint_url(self, endpoint_path: str) -> str:
        return f"{self._get_effective_base_url()}/{endpoint_path.lstrip('/')}"

    def _chat_endpoint_path(self) -> str:
        return "responses" if self._use_responses_api() else "chat/completions"

    def _format_preview(self, payload: Any, limit: int = 400) -> str:
        if payload is None:
            return ""
        if isinstance(payload, str):
            text = payload
        else:
            try:
                text = json.dumps(payload, ensure_ascii=False)
            except TypeError:
                text = repr(payload)
        return text[:limit]

    def _log_upstream_request(
        self,
        *,
        endpoint_path: str,
        model: str,
        stream: bool,
    ) -> None:
        logger.info(
            "AI upstream request: wire_api={} method=POST url={} model={} stream={} auth_header=Bearer content_type=application/json accept={}",
            self.wire_api,
            self._build_endpoint_url(endpoint_path),
            model,
            stream,
            "text/event-stream" if stream else "application/json",
        )

    def _log_upstream_error(
        self,
        error: Exception,
        *,
        endpoint_path: str,
        model: str,
    ) -> None:
        response = getattr(error, "response", None)
        request = getattr(response, "request", None)
        request_url = str(getattr(request, "url", "") or self._build_endpoint_url(endpoint_path))
        status_code = getattr(error, "status_code", None)
        if status_code is None and response is not None:
            status_code = getattr(response, "status_code", None)
        content_type = None
        if response is not None:
            headers = getattr(response, "headers", None)
            if headers is not None:
                content_type = headers.get("content-type")
        body_preview = self._format_preview(getattr(error, "body", None) or getattr(response, "text", None))
        logger.warning(
            "AI upstream error: wire_api={} url={} model={} status_code={} content_type={} response_preview={}",
            self.wire_api,
            request_url,
            model,
            status_code,
            content_type or "",
            body_preview,
        )

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

            if self._use_responses_api():
                return await self._chat_via_responses(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    tools=tools,
                    supports_vision=vision_flag,
                    supports_audio=audio_flag,
                    supports_video=video_flag,
                    **kwargs,
                )

            # Call API / 调用 API
            self._log_upstream_request(endpoint_path=self._chat_endpoint_path(), model=model, stream=False)
            logger.info("Chat request: model={} messages={}", model, len(messages))
            response = await self.client.chat.completions.create(**request_params)

            if self._should_fallback_to_responses(response):
                logger.warning(
                    "Chat response missing choices; fallback to responses API: model={} response_type={}",
                    model,
                    type(response).__name__,
                )
                return await self._chat_via_responses(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    tools=tools,
                    supports_vision=vision_flag,
                    supports_audio=audio_flag,
                    supports_video=video_flag,
                    **kwargs,
                )

            # Convert response / 转换响应
            return self._convert_chat_response(response, model)

        except AIGatewayError:
            raise
        except Exception as e:
            self._log_upstream_error(e, endpoint_path=self._chat_endpoint_path(), model=model)
            logger.error("Chat error: model={} error={}", model, str(e))
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

            if self._use_responses_api():
                async for chunk in self._stream_chat_via_responses(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    tools=tools,
                    supports_vision=vision_flag,
                    supports_audio=audio_flag,
                    supports_video=video_flag,
                    **kwargs,
                ):
                    yield chunk
                return

            # Call streaming API / 调用流式 API
            self._log_upstream_request(endpoint_path=self._chat_endpoint_path(), model=model, stream=True)
            logger.info("Stream chat request: model={}", model)
            stream = await self.client.chat.completions.create(**request_params)

            # Convert streaming response / 转换流式响应
            first_chunk = await anext(stream, None)
            if first_chunk is None:
                return

            if self._should_fallback_to_responses(first_chunk):
                logger.warning(
                    "Stream chunk missing choices; fallback to responses API: model={} chunk_type={}",
                    model,
                    type(first_chunk).__name__,
                )
                if hasattr(stream, "aclose"):
                    await stream.aclose()
                async for chunk in self._stream_chat_via_responses(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    tools=tools,
                    supports_vision=vision_flag,
                    supports_audio=audio_flag,
                    supports_video=video_flag,
                    **kwargs,
                ):
                    yield chunk
                return

            yield self._convert_chat_chunk(first_chunk, model)
            async for chunk in stream:
                yield self._convert_chat_chunk(chunk, model)

        except AIGatewayError:
            raise
        except Exception as e:
            self._log_upstream_error(e, endpoint_path=self._chat_endpoint_path(), model=model)
            logger.error("Stream chat error: model={} error={}", model, str(e))
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
            self._log_upstream_request(endpoint_path="embeddings", model=model, stream=False)
            logger.info("Embedding request: model={} texts={}", model, len(texts))
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
            self._log_upstream_error(e, endpoint_path="embeddings", model=model)
            logger.error("Embedding error: model={} error={}", model, str(e))
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
            self._log_upstream_request(endpoint_path="models", model="", stream=False)
            response = await self.client.models.list()
            return [
                {
                    "id": model.id,
                    "owned_by": getattr(model, "owned_by", None),
                }
                for model in response.data
            ]
        except Exception as e:
            self._log_upstream_error(e, endpoint_path="models", model="")
            logger.error("List models error: {}", str(e))
            raise convert_openai_error(e, provider_code="openai", model_code="")

    def _normalize_wire_api(self, wire_api: Any) -> str:
        value = str(wire_api or "").strip().lower().replace("-", "_")
        if value in {"responses", "response", "responses_api"}:
            return "responses"
        return "chat_completions"

    def _use_responses_api(self) -> bool:
        return self.wire_api == "responses"

    def _payload_looks_like_api_error(self, payload: Any) -> bool:
        """True when upstream returned an error object, not a misrouted success body."""
        if payload is None:
            return False
        if getattr(payload, "error", None) is not None:
            return True
        if isinstance(payload, dict) and payload.get("error") is not None:
            return True
        return False

    def _payload_resembles_responses_api_body(self, payload: Any) -> bool:
        """
        True when payload looks like OpenAI Responses API JSON, not arbitrary missing choices.
        仅在响应体像 Responses 结构时才 fallback，避免对 HTML/空对象等误触发二次请求。
        """
        if payload is None:
            return False
        if getattr(payload, "object", None) == "response":
            return True
        if isinstance(payload, dict) and payload.get("object") == "response":
            return True
        if hasattr(payload, "output"):
            return True
        if isinstance(payload, dict) and "output" in payload:
            return True
        if hasattr(payload, "output_text"):
            return True
        if isinstance(payload, dict) and "output_text" in payload:
            return True
        return False

    def _should_fallback_to_responses(self, payload: Any) -> bool:
        if self._use_responses_api():
            return False
        if hasattr(payload, "choices"):
            return False
        if self._payload_looks_like_api_error(payload):
            return False
        return self._payload_resembles_responses_api_body(payload)

    async def _chat_via_responses(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> ChatResponse:
        request_params = await self._build_responses_request(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            **kwargs,
        )
        self._log_upstream_request(endpoint_path="responses", model=model, stream=False)
        logger.info("Responses chat request: model={} messages={}", model, len(messages))
        response = await self.client.responses.create(**request_params)
        return self._convert_responses_chat_response(response, model)

    async def _stream_chat_via_responses(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        **kwargs,
    ) -> AsyncIterator[ChatChunk]:
        request_params = await self._build_responses_request(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            stream=True,
            **kwargs,
        )
        self._log_upstream_request(endpoint_path="responses", model=model, stream=True)
        logger.info("Responses stream request: model={}", model)
        stream = await self.client.responses.create(**request_params)
        emitted_text = False

        async for event in stream:
            event_type = getattr(event, "type", "")

            if event_type == "response.output_text.delta":
                delta = getattr(event, "delta", "") or ""
                if delta:
                    emitted_text = True
                    yield ChatChunk(delta=delta)
                continue

            if event_type in {"response.reasoning_text.delta", "response.reasoning_summary_text.delta"}:
                delta = getattr(event, "delta", "") or ""
                if delta:
                    yield ChatChunk(delta="", reasoning_delta=delta)
                continue

            if event_type == "response.output_item.added":
                item = getattr(event, "item", None)
                if getattr(item, "type", None) == "function_call":
                    yield ChatChunk(
                        delta="",
                        tool_calls=[{
                            "index": getattr(event, "output_index", None),
                            "id": getattr(item, "call_id", None) or getattr(item, "id", None) or "",
                            "function": {
                                "name": getattr(item, "name", None) or "",
                                "arguments": getattr(item, "arguments", None) or "",
                            },
                        }],
                    )
                continue

            if event_type == "response.function_call_arguments.delta":
                yield ChatChunk(
                    delta="",
                    tool_calls=[{
                        "index": getattr(event, "output_index", None),
                        "id": getattr(event, "item_id", None) or "",
                        "function": {"arguments": getattr(event, "delta", "") or ""},
                    }],
                )
                continue

            if event_type == "response.function_call_arguments.done":
                yield ChatChunk(
                    delta="",
                    tool_calls=[{
                        "index": getattr(event, "output_index", None),
                        "id": getattr(event, "item_id", None) or "",
                        "function": {
                            "name": getattr(event, "name", None) or "",
                            "arguments": getattr(event, "arguments", None) or "{}",
                        },
                    }],
                )
                continue

            if event_type == "response.completed":
                response = getattr(event, "response", None)
                if response is not None and not emitted_text:
                    final_text = self._extract_responses_text(response)
                    if final_text:
                        yield ChatChunk(delta=final_text)
                usage = getattr(response, "usage", None)
                yield ChatChunk(
                    delta="",
                    finish_reason="stop",
                    input_tokens=getattr(usage, "input_tokens", None),
                    output_tokens=getattr(usage, "output_tokens", None),
                    total_tokens=getattr(usage, "total_tokens", None),
                )
                continue

            if event_type in {"response.error", "response.failed"}:
                error_obj = getattr(event, "error", None)
                if error_obj is not None:
                    raise RuntimeError(str(error_obj))
                raise RuntimeError(event_type)

    async def _build_responses_request(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        stream: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        supports_vision = kwargs.pop("supports_vision", True)
        supports_audio = kwargs.pop("supports_audio", False)
        supports_video = kwargs.pop("supports_video", False)
        request_params: dict[str, Any] = {
            "model": model,
            "input": await self._convert_messages_to_responses_input(
                messages,
                supports_vision=supports_vision,
                supports_audio=supports_audio,
                supports_video=supports_video,
            ),
            "temperature": temperature,
            "top_p": top_p,
        }
        if max_tokens is not None:
            request_params["max_output_tokens"] = max_tokens
        if stream:
            request_params["stream"] = True
        if tools:
            request_params["tools"] = self._convert_tools_for_responses(tools)
        request_params.update(kwargs)
        return request_params

    def _convert_tools_for_responses(self, tools: list[dict]) -> list[dict]:
        converted: list[dict] = []
        for tool in tools:
            if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
                function = tool["function"]
                # Omit strict: many OpenAI-compatible gateways reject or mishandle it / 省略 strict：多数兼容网关不支持或行为不一致
                converted.append({
                    "type": "function",
                    "name": function.get("name", ""),
                    "description": function.get("description"),
                    "parameters": function.get("parameters"),
                })
                continue
            converted.append(tool)
        return converted

    async def _convert_messages_to_responses_input(
        self,
        messages: list[ChatMessage],
        *,
        supports_vision: bool = True,
        supports_audio: bool = False,
        supports_video: bool = False,
    ) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == "tool":
                converted.append({
                    "type": "function_call_output",
                    "call_id": msg.tool_call_id or "",
                    "output": msg.content or "",
                })
                continue

            if msg.role == "assistant" and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    function = tool_call.get("function") or {}
                    tc_id = tool_call.get("call_id") or tool_call.get("id") or ""
                    converted.append({
                        "type": "function_call",
                        "call_id": tc_id,
                        "id": tool_call.get("id") or tc_id,
                        "name": function.get("name", ""),
                        "arguments": function.get("arguments", "{}") or "{}",
                        "status": "completed",
                    })
                if not (msg.content or "").strip():
                    continue

            content = await self._build_responses_message_content(
                msg,
                supports_vision=supports_vision,
                supports_audio=supports_audio,
                supports_video=supports_video,
            )
            converted.append({
                "type": "message",
                "role": msg.role,
                "content": content,
            })

        return converted

    async def _build_responses_message_content(
        self,
        msg: ChatMessage,
        *,
        supports_vision: bool = True,
        supports_audio: bool = False,
        supports_video: bool = False,
    ) -> str | list[dict[str, Any]]:
        if msg.role != "user" or not msg.attachments:
            return msg.content or ""

        parts: list[dict[str, Any]] = []
        if msg.content:
            parts.append({"type": "input_text", "text": msg.content})

        for att in msg.attachments:
            att_type = str(att.get("type") or "").lower()
            url = str(att.get("url") or "").strip()
            name = att.get("name") or att.get("filename") or "file"
            att_mime = str(att.get("mime_type") or "")

            if att_type == "image":
                if supports_vision and url:
                    resolved = await self._resolve_image_url_for_llm(url, att_mime)
                    if resolved:
                        parts.append({
                            "type": "input_image",
                            "image_url": resolved,
                            "detail": "auto",
                        })
                    else:
                        hint = (
                            f"[Image: {name or 'uploaded image'} "
                            "(could not load for model)]"
                        )
                        parts.append({"type": "input_text", "text": hint})
                else:
                    parts.append({"type": "input_text", "text": f"[Image: {name}]"})
                continue

            if att_type == "file":
                if url:
                    parts.append({
                        "type": "input_file",
                        "file_url": url,
                        "filename": str(name),
                    })
                else:
                    parts.append({"type": "input_text", "text": f"[File: {name}]"})
                continue

            if att_type == "audio":
                if supports_audio and url:
                    parts.append({
                        "type": "input_file",
                        "file_url": url,
                        "filename": str(name),
                    })
                else:
                    parts.append({"type": "input_text", "text": f"[Audio: {name}]"})
                continue

            if att_type == "video":
                if supports_video and url:
                    parts.append({
                        "type": "input_file",
                        "file_url": url,
                        "filename": str(name),
                    })
                else:
                    parts.append({"type": "input_text", "text": f"[Video: {name}]"})
                continue

            parts.append({"type": "input_text", "text": f"[Attachment: {name}]"})

        return parts or (msg.content or "")

    def _extract_responses_text(self, response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text:
            return output_text

        parts: list[str] = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) != "message":
                continue
            for content in getattr(item, "content", []) or []:
                if getattr(content, "type", None) == "output_text":
                    text = getattr(content, "text", None)
                    if text:
                        parts.append(text)
        return "".join(parts)

    def _extract_responses_tool_calls(self, response: Any) -> list[dict] | None:
        tool_calls: list[dict] = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) != "function_call":
                continue
            call_id = getattr(item, "call_id", None) or getattr(item, "id", None) or ""
            tool_calls.append({
                "id": call_id,
                "type": "function",
                "function": {
                    "name": getattr(item, "name", None) or "",
                    "arguments": getattr(item, "arguments", None) or "{}",
                },
            })
        return tool_calls or None

    def _convert_responses_chat_response(self, response: Any, model: str) -> ChatResponse:
        tool_calls = self._extract_responses_tool_calls(response)
        usage = getattr(response, "usage", None)
        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content=self._extract_responses_text(response),
                tool_calls=tool_calls,
            ),
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
            model=model,
            finish_reason="stop" if getattr(response, "status", None) == "completed" else getattr(response, "status", None),
            tool_calls=tool_calls,
            raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
        )

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
                    logger.warning("Audio data URL base64 decode failed: {}", e)
                    return None
            return None
        try:
            await UrlValidator.validate(url)
        except SSRFBlockedError as e:
            logger.warning("Audio fetch URL blocked (SSRF): {}", e)
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
                        "Audio too large (content-length={} > {}), skip native",
                        cl,
                        _AUDIO_MAX_BYTES,
                    )
                    return None
                data = resp.content
                if len(data) > _AUDIO_MAX_BYTES:
                    logger.warning(
                        "Audio body too large ({} > {}), skip native",
                        len(data),
                        _AUDIO_MAX_BYTES,
                    )
                    return None
                return data
        except Exception as e:
            logger.warning("Fetch audio URL failed: {}", e)
            return None

    async def _resolve_image_url_for_llm(self, att_url: str, att_mime: str) -> str | None:
        """
        Convert attachment / remote image URL to data URL for vendor multimodal APIs.
        """
        db = self.config.get("internal_db")
        tenant_id = self.config.get("internal_tenant_id")
        return await resolve_image_url_for_llm(
            att_url,
            att_mime or None,
            db=db,
            tenant_id=tenant_id,
        )

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
                            resolved = await self._resolve_image_url_for_llm(
                                att_url, att_mime,
                            )
                            if resolved:
                                content_parts.append({
                                    "type": "image_url",
                                    "image_url": {"url": resolved},
                                })
                            else:
                                hint = (
                                    f"[Image: {att_name or 'uploaded image'} "
                                    "(could not load for model)]"
                                )
                                content_parts.append({"type": "text", "text": hint})
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

        # Keep reasoning delta separate so frontend can render "thinking" independently
        # from the final answer / 将 reasoning 增量与最终答复分离，便于前端单独展示“思考内容”
        delta_content = delta.content or ""
        reasoning_delta = getattr(delta, "reasoning_content", None) or ""

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
            reasoning_delta=reasoning_delta,
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
                "Image generation request: model={} size={} quality={} n={}",
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
            logger.error("Image generation error: model={} error={}", model, str(e))
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

