"""
Anthropic Claude 适配器

通过 Anthropic Messages API 调用 Claude 系列模型。
支持 chat 和 stream_chat，不支持 embedding。
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from app.ai.adapters.base import BaseAdapter
from app.ai.exceptions import (
    ProviderError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderConnectionError,
    ProviderTimeoutError,
)
from app.ai.types import (
    ChatMessage,
    ChatResponse,
    ChatChunk,
    EmbeddingResponse,
)
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")

ANTHROPIC_API_VERSION = "2023-06-01"
DEFAULT_BASE_URL = "https://api.anthropic.com"


class AnthropicAdapter(BaseAdapter):
    """
    Anthropic Claude 适配器

    通过 Messages API 调用 Claude 系列模型。
    """

    def __init__(self, api_key: str, base_url: str | None = None, **kwargs: Any):
        super().__init__(api_key, base_url, **kwargs)
        self._base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self._headers = {
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_API_VERSION,
            "content-type": "application/json",
        }

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _convert_messages(
        self, messages: list[ChatMessage]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """
        将统一消息格式转换为 Anthropic Messages API 格式。

        Returns:
            (system_prompt, messages_list)
        """
        system_prompt: str | None = None
        converted: list[dict[str, Any]] = []

        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
                continue

            role = "user" if msg.role in ("user", "tool") else "assistant"

            if msg.role == "tool" and msg.tool_call_id:
                converted.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content,
                        }
                    ],
                })
            else:
                converted.append({"role": role, "content": msg.content})

        return system_prompt, converted

    def _convert_tools(self, tools: list[dict] | None) -> list[dict[str, Any]] | None:
        """将 OpenAI 格式的 tools 转换为 Anthropic tool 格式。"""
        if not tools:
            return None

        anthropic_tools: list[dict[str, Any]] = []
        for tool in tools:
            fn = tool.get("function", tool)
            anthropic_tools.append({
                "name": fn.get("name", ""),
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {}),
            })
        return anthropic_tools

    def _handle_error(self, status: int, body: dict[str, Any], model: str) -> None:
        """根据 HTTP 状态码抛出对应异常。"""
        error_msg = body.get("error", {}).get("message", str(body))

        if status == 401:
            raise ProviderAuthError(
                message=error_msg,
                provider_code="anthropic",
                model_code=model,
            )
        if status == 429:
            raise ProviderRateLimitError(
                message=error_msg,
                provider_code="anthropic",
                model_code=model,
            )
        raise ProviderError(
            message=error_msg,
            provider_code="anthropic",
            model_code=model,
        )

    # ------------------------------------------------------------------
    # chat (non-streaming)
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        stream: bool = False,
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        system_prompt, converted = self._convert_messages(messages)

        payload: dict[str, Any] = {
            "model": model,
            "messages": converted,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "top_p": top_p,
        }
        if system_prompt:
            payload["system"] = system_prompt

        anthropic_tools = self._convert_tools(tools)
        if anthropic_tools:
            payload["tools"] = anthropic_tools

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self._base_url}/v1/messages",
                    headers=self._headers,
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                message=str(exc),
                provider_code="anthropic",
                model_code=model,
            ) from exc
        except httpx.ConnectError as exc:
            raise ProviderConnectionError(
                message=str(exc),
                provider_code="anthropic",
                model_code=model,
            ) from exc

        body = resp.json()
        if resp.status_code != 200:
            self._handle_error(resp.status_code, body, model)

        # 解析响应
        content_blocks = body.get("content", [])
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block.get("id"),
                    "type": "function",
                    "function": {
                        "name": block.get("name"),
                        "arguments": json.dumps(block.get("input", {})),
                    },
                })

        usage = body.get("usage", {})

        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content="\n".join(text_parts),
                tool_calls=tool_calls if tool_calls else None,
            ),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            total_tokens=(usage.get("input_tokens", 0) + usage.get("output_tokens", 0)) or None,
            model=body.get("model", model),
            finish_reason=body.get("stop_reason"),
            tool_calls=tool_calls if tool_calls else None,
            raw_response=body,
        )

    # ------------------------------------------------------------------
    # stream_chat
    # ------------------------------------------------------------------

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatChunk]:
        system_prompt, converted = self._convert_messages(messages)

        payload: dict[str, Any] = {
            "model": model,
            "messages": converted,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt

        anthropic_tools = self._convert_tools(tools)
        if anthropic_tools:
            payload["tools"] = anthropic_tools

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/v1/messages",
                    headers=self._headers,
                    json=payload,
                ) as resp:
                    if resp.status_code != 200:
                        body = json.loads(await resp.aread())
                        self._handle_error(resp.status_code, body, model)

                    input_tokens: int | None = None
                    output_tokens: int | None = None

                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break

                        try:
                            event = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        event_type = event.get("type", "")

                        if event_type == "message_start":
                            usage = event.get("message", {}).get("usage", {})
                            input_tokens = usage.get("input_tokens")

                        elif event_type == "content_block_delta":
                            delta = event.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield ChatChunk(
                                    delta=delta.get("text", ""),
                                    role="assistant",
                                )

                        elif event_type == "message_delta":
                            usage = event.get("usage", {})
                            output_tokens = usage.get("output_tokens")
                            stop_reason = event.get("delta", {}).get("stop_reason")

                            yield ChatChunk(
                                delta="",
                                finish_reason=stop_reason,
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                                total_tokens=(
                                    (input_tokens or 0) + (output_tokens or 0)
                                ) or None,
                            )

        except httpx.TimeoutException as exc:
            raise ProviderTimeoutError(
                message=str(exc),
                provider_code="anthropic",
                model_code=model,
            ) from exc
        except httpx.ConnectError as exc:
            raise ProviderConnectionError(
                message=str(exc),
                provider_code="anthropic",
                model_code=model,
            ) from exc

    # ------------------------------------------------------------------
    # embedding (not supported)
    # ------------------------------------------------------------------

    async def embedding(
        self,
        texts: list[str],
        model: str,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        raise ProviderError(
            message="Anthropic does not support embedding API",
            provider_code="anthropic",
            model_code=model,
        )

    def get_supported_features(self) -> dict[str, bool]:
        return {
            "chat": True,
            "streaming": True,
            "function_calling": True,
            "vision": True,
            "embedding": False,
        }


__all__ = ["AnthropicAdapter"]
