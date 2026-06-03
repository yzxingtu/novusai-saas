"""Protocol bridge helpers for OpenAI-compatible adapter facades."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from openai.types.chat import ChatCompletion, ChatCompletionChunk

from app.ai.adapters.openai_compatible.protocol_chat_completions import (
    convert_chat_chunk as convert_chat_completions_chunk,
)
from app.ai.adapters.openai_compatible.protocol_chat_completions import (
    convert_chat_response as convert_chat_completions_response,
)
from app.ai.adapters.openai_compatible.protocol_chat_completions import (
    execute_chat_via_chat_completions,
    execute_stream_chat_via_chat_completions,
)
from app.ai.adapters.openai_compatible.protocol_responses import (
    convert_responses_chat_response as convert_responses_chat_response_impl,
)
from app.ai.adapters.openai_compatible.protocol_responses import (
    execute_chat_via_responses as execute_chat_via_responses_impl,
)
from app.ai.adapters.openai_compatible.protocol_responses import (
    extract_responses_text as extract_responses_text_impl,
)
from app.ai.adapters.openai_compatible.protocol_responses import (
    extract_responses_tool_calls as extract_responses_tool_calls_impl,
)
from app.ai.adapters.openai_compatible.protocol_responses_stream import (
    execute_stream_chat_via_responses as execute_stream_chat_via_responses_impl,
)
from app.ai.adapters.openai_compatible.protocol_runtime_context import (
    prepare_protocol_execution_context as prepare_protocol_execution_context_impl,
)
from app.ai.adapters.openai_compatible.request_payload_builders import (
    build_chat_completions_request as build_chat_completions_request_impl,
)
from app.ai.adapters.openai_compatible.request_payload_builders import (
    build_responses_reasoning_config as build_responses_reasoning_config_impl,
)
from app.ai.adapters.openai_compatible.request_payload_builders import (
    build_responses_request as build_responses_request_impl,
)
from app.ai.adapters.openai_compatible.request_payload_builders import (
    convert_tools_for_responses as convert_tools_for_responses_impl,
)
from app.ai.adapters.openai_compatible.request_payload_builders import (
    supports_responses_reasoning_summary as supports_responses_reasoning_summary_impl,
)
from app.ai.adapters.openai_compatible.support.model_request_runtime import (
    RESPONSES_REASONING_SUMMARY_MODEL_PREFIXES,
)
from app.ai.adapters.openai_compatible.support.responses_reasoning_parser import (
    extract_responses_reasoning_text as extract_responses_reasoning_text_impl,
)
from app.ai.adapters.openai_compatible.support.stream_cleanup import (
    aclose_openai_stream,
)
from app.ai.adapters.openai_compatible.timeout_policy import (
    DEFAULT_STREAM_TIMEOUT_SECONDS,
)
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


class OpenAIAdapterProtocolBridgeMixin:
    """Protocol-facing adapter helpers kept out of the public facade."""

    def _build_chat_completions_request(
        self,
        *,
        openai_messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int | None,
        top_p: float,
        tools: list[dict] | None,
        tool_choice: str | None,
        stream: bool,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return build_chat_completions_request_impl(
            adapter=self,
            openai_messages=openai_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            stream=stream,
            kwargs=kwargs,
        )

    def _prepare_protocol_execution_context(
        self,
        *,
        wire_api: str,
        model: str,
        stream: bool,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        return prepare_protocol_execution_context_impl(
            adapter=self,
            wire_api=wire_api,
            model=model,
            stream=stream,
            kwargs=kwargs,
            default_stream_timeout_seconds=DEFAULT_STREAM_TIMEOUT_SECONDS,
        )

    async def _chat_via_chat_completions(
        self,
        *,
        request_params: dict[str, Any],
        messages: list[ChatMessage],
        model: str,
    ) -> ChatResponse:
        return await execute_chat_via_chat_completions(
            adapter=self,
            request_params=request_params,
            messages=messages,
            model=model,
        )

    async def _stream_chat_via_chat_completions(
        self,
        *,
        request_params: dict[str, Any],
        model: str,
    ) -> AsyncIterator[ChatChunk]:
        async for chunk in execute_stream_chat_via_chat_completions(
            adapter=self,
            request_params=request_params,
            model=model,
            aclose_stream=aclose_openai_stream,
            normalize_timeout=self._normalize_timeout_seconds,
        ):
            yield chunk

    def _normalize_wire_api(self, wire_api: Any) -> str:
        return self._normalize_wire_api_value(wire_api)

    @staticmethod
    def _stream_chunk_blocks_fallback(chunk: ChatChunk) -> bool:
        if chunk is None:
            return False
        if str(getattr(chunk, "delta", "") or "").strip():
            return True
        return bool(getattr(chunk, "tool_calls", None))

    async def _chat_via_responses(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        request_params = await self._build_responses_request(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            **kwargs,
        )
        return await execute_chat_via_responses_impl(
            adapter=self,
            messages=messages,
            model=model,
            request_params=request_params,
        )

    async def _stream_chat_via_responses(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatChunk]:
        request_params = await self._build_responses_request(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            stream=True,
            **kwargs,
        )
        async for chunk in execute_stream_chat_via_responses_impl(
            adapter=self,
            messages=messages,
            model=model,
            request_params=request_params,
            aclose_stream=aclose_openai_stream,
        ):
            yield chunk

    async def _build_responses_request(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return await build_responses_request_impl(
            adapter=self,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            stream=stream,
            kwargs=kwargs,
            reasoning_summary_model_prefixes=RESPONSES_REASONING_SUMMARY_MODEL_PREFIXES,
        )

    def _build_responses_reasoning_config(
        self,
        *,
        model: str,
        explicit_reasoning: Any = None,
    ) -> Any:
        return build_responses_reasoning_config_impl(
            model=model,
            explicit_reasoning=explicit_reasoning,
            reasoning_summary_model_prefixes=RESPONSES_REASONING_SUMMARY_MODEL_PREFIXES,
        )

    def _supports_responses_reasoning_summary(self, model: str) -> bool:
        return supports_responses_reasoning_summary_impl(
            model=model,
            reasoning_summary_model_prefixes=RESPONSES_REASONING_SUMMARY_MODEL_PREFIXES,
        )

    def _convert_tools_for_responses(self, tools: list[dict]) -> list[dict]:
        return convert_tools_for_responses_impl(tools)

    def _extract_responses_text(self, response: Any) -> str:
        return extract_responses_text_impl(response)

    def _extract_responses_tool_calls(self, response: Any) -> list[dict] | None:
        return extract_responses_tool_calls_impl(response)

    def _extract_responses_reasoning_text(self, response: Any) -> str | None:
        return extract_responses_reasoning_text_impl(response)

    def _convert_responses_chat_response(
        self, response: Any, model: str
    ) -> ChatResponse:
        return convert_responses_chat_response_impl(
            adapter=self,
            response=response,
            model=model,
        )

    def _convert_chat_response(
        self, response: ChatCompletion, model: str
    ) -> ChatResponse:
        return convert_chat_completions_response(
            adapter=self,
            response=response,
            model=model,
        )

    def _convert_chat_chunk(self, chunk: ChatCompletionChunk, model: str) -> ChatChunk:
        return convert_chat_completions_chunk(
            adapter=self,
            chunk=chunk,
            model=model,
        )


__all__ = ["OpenAIAdapterProtocolBridgeMixin"]
