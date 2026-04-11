"""Protocol entrypoints kept outside the public OpenAI adapter facade."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.ai.adapters.openai_compatible import attach_protocol_metadata
from app.ai.exceptions import AIGatewayError, convert_openai_error
from app.ai.types import ChatChunk, ChatMessage, ChatResponse
from app.core.logging import LogManager

logger = LogManager.get_logger("ai")


class OpenAIAdapterProtocolEntrypointsMixin:
    """Owns protocol-specific execution branching for adapter callers."""

    async def _build_protocol_chat_completions_request(
        self,
        *,
        messages: list[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int | None,
        top_p: float,
        tools: list[dict] | None,
        tool_choice: str | None,
        stream: bool,
        context: dict[str, Any],
        runtime_model_config: Any,
        effective_request: dict[str, Any],
        protocol_kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        openai_messages = await self._convert_messages(
            messages,
            supports_vision=context["supports_vision"],
            supports_audio=context["supports_audio"],
            supports_video=context["supports_video"],
        )
        return self._build_chat_completions_request(
            openai_messages=openai_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            stream=stream,
            model_config=runtime_model_config,
            _effective_model_request=effective_request,
            **protocol_kwargs,
        )

    def _raise_protocol_execution_error(
        self,
        error: Exception,
        *,
        operation: str,
        model: str,
        effective_error_model: str,
        endpoint_path: str,
        wire_api: str,
    ) -> None:
        self._log_upstream_error(
            error,
            endpoint_path=endpoint_path,
            model=effective_error_model,
            wire_api=wire_api,
        )
        logger.error("Protocol {} error: model={} error={}", operation, model, str(error))
        raise convert_openai_error(
            error,
            provider_code="openai",
            model_code=model,
        ) from error

    async def execute_protocol_chat(
        self,
        *,
        wire_api: str,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        context = self._prepare_protocol_execution_context(
            wire_api=wire_api,
            model=model,
            stream=False,
            kwargs=kwargs,
        )
        active_endpoint_path = context["active_endpoint_path"]
        active_wire_api = context["active_wire_api"]
        effective_request = context["effective_request"]
        effective_error_model = context["effective_error_model"]
        runtime_model_config = context["runtime_model_config"]
        protocol_kwargs = dict(context["kwargs"])

        try:
            if active_wire_api == "responses":
                response = await self._chat_via_responses(
                    messages=messages,
                    model=model,
                    model_config=runtime_model_config,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    tools=tools,
                    tool_choice=tool_choice,
                    supports_vision=context["supports_vision"],
                    supports_audio=context["supports_audio"],
                    supports_video=context["supports_video"],
                    _effective_model_request=effective_request,
                    **protocol_kwargs,
                )
            else:
                request_params = await self._build_protocol_chat_completions_request(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    tools=tools,
                    tool_choice=tool_choice,
                    stream=False,
                    context=context,
                    runtime_model_config=runtime_model_config,
                    effective_request=effective_request,
                    protocol_kwargs=protocol_kwargs,
                )
                response = await self._chat_via_chat_completions(
                    request_params=request_params,
                    messages=messages,
                    model=model,
                    fallback_to_responses=False,
                )

            response.metadata = attach_protocol_metadata(
                response.metadata,
                protocol_path=active_wire_api,
            )
            response.metadata = self._augment_request_metadata(
                response.metadata,
                effective_request=effective_request,
            )
            return response
        except AIGatewayError:
            raise
        except Exception as exc:  # noqa: BLE001
            self._raise_protocol_execution_error(
                exc,
                operation="chat",
                model=model,
                effective_error_model=effective_error_model,
                endpoint_path=active_endpoint_path,
                wire_api=active_wire_api,
            )

    async def execute_protocol_stream(
        self,
        *,
        wire_api: str,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        top_p: float = 1.0,
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatChunk]:
        context = self._prepare_protocol_execution_context(
            wire_api=wire_api,
            model=model,
            stream=True,
            kwargs=kwargs,
        )
        active_endpoint_path = context["active_endpoint_path"]
        active_wire_api = context["active_wire_api"]
        effective_request = context["effective_request"]
        effective_error_model = context["effective_error_model"]
        runtime_model_config = context["runtime_model_config"]
        protocol_kwargs = dict(context["kwargs"])

        try:
            if active_wire_api == "responses":
                stream_iter = self._stream_chat_via_responses(
                    messages=messages,
                    model=model,
                    model_config=runtime_model_config,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    tools=tools,
                    tool_choice=tool_choice,
                    supports_vision=context["supports_vision"],
                    supports_audio=context["supports_audio"],
                    supports_video=context["supports_video"],
                    _effective_model_request=effective_request,
                    **protocol_kwargs,
                )
            else:
                request_params = await self._build_protocol_chat_completions_request(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    tools=tools,
                    tool_choice=tool_choice,
                    stream=True,
                    context=context,
                    runtime_model_config=runtime_model_config,
                    effective_request=effective_request,
                    protocol_kwargs=protocol_kwargs,
                )
                stream_iter = self._stream_chat_via_chat_completions(
                    request_params=request_params,
                    model=model,
                    fallback_to_responses=False,
                )

            async for chunk in stream_iter:
                chunk.metadata = self._augment_request_metadata(
                    getattr(chunk, "metadata", None),
                    effective_request=effective_request,
                )
                yield chunk
        except AIGatewayError:
            raise
        except Exception as exc:  # noqa: BLE001
            self._raise_protocol_execution_error(
                exc,
                operation="stream",
                model=model,
                effective_error_model=effective_error_model,
                endpoint_path=active_endpoint_path,
                wire_api=active_wire_api,
            )


__all__ = ["OpenAIAdapterProtocolEntrypointsMixin"]
