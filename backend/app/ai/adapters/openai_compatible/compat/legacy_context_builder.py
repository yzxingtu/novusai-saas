"""Build legacy adapter entrypoint plans without embedding runner policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.ai.types import ChatMessage


class LegacyEntrypointAdapterProtocol(Protocol):
    wire_api: str

    def _prepare_protocol_execution_context(
        self,
        *,
        wire_api: str | None,
        model: str,
        stream: bool,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def _convert_messages(
        self,
        messages: list[ChatMessage],
        *,
        supports_vision: bool,
        supports_audio: bool,
        supports_video: bool,
    ) -> list[dict[str, Any]]: ...

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
    ) -> dict[str, Any]: ...

    def _augment_request_metadata(
        self,
        metadata: dict[str, Any] | None,
        *,
        effective_request: dict[str, Any],
    ) -> dict[str, Any]: ...

    def _log_upstream_error(
        self,
        error: Exception,
        *,
        endpoint_path: str,
        model: str,
        wire_api: str,
    ) -> None: ...


@dataclass(frozen=True)
class LegacyEntrypointContext:
    active_endpoint_path: str
    active_wire_api: str
    effective_request: dict[str, Any]
    effective_error_model: str
    runtime_model_config: Any
    supports_vision: bool
    supports_audio: bool
    supports_video: bool
    protocol_kwargs: dict[str, Any]
    runtime_disable_cross_protocol_fallback: bool
    runtime_disable_sync_rescue: bool


@dataclass(frozen=True)
class LegacyEntrypointPlan:
    context: LegacyEntrypointContext
    request_params: dict[str, Any]
    responses_kwargs: dict[str, Any]
    sync_request_params: dict[str, Any] | None


async def build_legacy_entrypoint_plan(
    *,
    adapter: LegacyEntrypointAdapterProtocol,
    messages: list[ChatMessage],
    model: str,
    temperature: float,
    max_tokens: int | None,
    top_p: float,
    tools: list[dict] | None,
    tool_choice: str | None,
    stream: bool,
    kwargs: dict[str, Any],
) -> LegacyEntrypointPlan:
    runtime_kwargs = dict(kwargs)
    runtime_force_wire_api = runtime_kwargs.get("_runtime_force_wire_api")
    runtime_disable_cross_protocol_fallback = bool(
        runtime_kwargs.get("_runtime_disable_cross_protocol_fallback", False)
    )
    runtime_disable_sync_rescue = bool(
        runtime_kwargs.get("_runtime_disable_sync_rescue", False)
    )
    raw_context = adapter._prepare_protocol_execution_context(
        wire_api=runtime_force_wire_api,
        model=model,
        stream=stream,
        kwargs=runtime_kwargs,
    )
    context = LegacyEntrypointContext(
        active_endpoint_path=raw_context["active_endpoint_path"],
        active_wire_api=raw_context["active_wire_api"],
        effective_request=raw_context["effective_request"],
        effective_error_model=raw_context["effective_error_model"],
        runtime_model_config=raw_context["runtime_model_config"],
        supports_vision=raw_context["supports_vision"],
        supports_audio=raw_context["supports_audio"],
        supports_video=raw_context["supports_video"],
        protocol_kwargs=dict(raw_context["kwargs"]),
        runtime_disable_cross_protocol_fallback=runtime_disable_cross_protocol_fallback,
        runtime_disable_sync_rescue=runtime_disable_sync_rescue,
    )
    openai_messages = await adapter._convert_messages(
        messages,
        supports_vision=context.supports_vision,
        supports_audio=context.supports_audio,
        supports_video=context.supports_video,
    )
    request_params = adapter._build_chat_completions_request(
        openai_messages=openai_messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        tools=tools,
        tool_choice=tool_choice,
        stream=stream,
        model_config=context.runtime_model_config,
        _effective_model_request=context.effective_request,
        **context.protocol_kwargs,
    )
    sync_request_params = None
    if stream:
        sync_request_params = adapter._build_chat_completions_request(
            openai_messages=openai_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            stream=False,
            model_config=context.runtime_model_config,
            _effective_model_request=context.effective_request,
            **context.protocol_kwargs,
        )
    responses_kwargs = {
        "messages": messages,
        "model": model,
        "model_config": context.runtime_model_config,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "top_p": top_p,
        "tools": tools,
        "tool_choice": tool_choice,
        "supports_vision": context.supports_vision,
        "supports_audio": context.supports_audio,
        "supports_video": context.supports_video,
        "_effective_model_request": context.effective_request,
        **context.protocol_kwargs,
    }
    return LegacyEntrypointPlan(
        context=context,
        request_params=request_params,
        responses_kwargs=responses_kwargs,
        sync_request_params=sync_request_params,
    )


__all__ = [
    "LegacyEntrypointAdapterProtocol",
    "LegacyEntrypointContext",
    "LegacyEntrypointPlan",
    "build_legacy_entrypoint_plan",
]
