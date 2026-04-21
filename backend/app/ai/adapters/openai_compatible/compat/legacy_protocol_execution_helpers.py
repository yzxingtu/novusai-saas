"""Support helpers for legacy protocol execution orchestration."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol

from app.ai.types import ChatChunk, ChatMessage, ChatResponse

from .legacy_protocol_fallback_support import (
    log_responses_tool_call_fallback,
    should_fallback_after_responses_error,
)
from .legacy_protocol_stream_rescue import (
    build_chat_completions_stream_iterator,
    stream_chat_completions_with_sync_rescue,
)


class LegacyCompatAdapterProtocol(Protocol):
    provider_config: dict[str, Any]
    protocol_capabilities: Any

    async def _chat_via_responses(self, **kwargs: Any) -> ChatResponse: ...

    async def _stream_chat_via_responses(
        self,
        **kwargs: Any,
    ) -> AsyncIterator[ChatChunk]: ...

    async def _chat_via_chat_completions(
        self,
        *,
        request_params: dict[str, Any],
        messages: list[ChatMessage],
        model: str,
        fallback_to_responses: bool = True,
        responses_kwargs: dict[str, Any] | None = None,
    ) -> ChatResponse: ...

    async def _stream_chat_via_chat_completions(
        self,
        *,
        request_params: dict[str, Any],
        model: str,
        fallback_to_responses: bool = True,
        responses_kwargs: dict[str, Any] | None = None,
    ) -> AsyncIterator[ChatChunk]: ...

    @staticmethod
    def _stream_chunk_blocks_fallback(chunk: ChatChunk) -> bool: ...

    def _chat_response_to_stream_chunk(self, response: ChatResponse) -> ChatChunk: ...


@dataclass(frozen=True, slots=True)
class LegacyProtocolGuardSnapshot:
    """Internal runtime guard flags for OpenAI-compatible protocol execution."""

    runtime_disable_cross_protocol_fallback: bool = False
    runtime_disable_sync_rescue: bool = False


def _activate_chat_completions_state(execution_state: dict[str, str]) -> None:
    execution_state["active_endpoint_path"] = "chat/completions"
    execution_state["active_wire_api"] = "chat_completions"


async def execute_legacy_chat(
    *,
    adapter: LegacyCompatAdapterProtocol,
    execution_state: dict[str, str],
    messages: list[ChatMessage],
    model: str,
    tools: list[dict] | None,
    tool_choice: str | None,
    use_responses_api: bool,
    guard_snapshot: LegacyProtocolGuardSnapshot,
    request_params: dict[str, Any],
    responses_kwargs: dict[str, Any],
) -> ChatResponse:
    """Run the legacy smart chat path without keeping policy inside the adapter."""

    if use_responses_api:
        try:
            return await adapter._chat_via_responses(**responses_kwargs)
        except Exception as responses_error:
            if should_fallback_after_responses_error(
                capabilities=adapter.protocol_capabilities,
                provider_config=adapter.provider_config,
                error=responses_error,
                tools=tools,
                tool_choice=tool_choice,
                use_responses_api=use_responses_api,
                runtime_disable_cross_protocol_fallback=(
                    guard_snapshot.runtime_disable_cross_protocol_fallback
                ),
            ):
                log_responses_tool_call_fallback(
                    model=model,
                    stream=False,
                    error=responses_error,
                )
                _activate_chat_completions_state(execution_state)
                return await adapter._chat_via_chat_completions(
                    request_params=request_params,
                    messages=messages,
                    model=model,
                    fallback_to_responses=False,
                )
            raise

    return await adapter._chat_via_chat_completions(
        request_params=request_params,
        messages=messages,
        model=model,
        fallback_to_responses=(
            not guard_snapshot.runtime_disable_cross_protocol_fallback
        ),
        responses_kwargs=(
            responses_kwargs
            if not guard_snapshot.runtime_disable_cross_protocol_fallback
            else None
        ),
    )


async def execute_legacy_stream(
    *,
    adapter: LegacyCompatAdapterProtocol,
    execution_state: dict[str, str],
    messages: list[ChatMessage],
    model: str,
    tools: list[dict] | None,
    tool_choice: str | None,
    use_responses_api: bool,
    guard_snapshot: LegacyProtocolGuardSnapshot,
    request_params: dict[str, Any],
    sync_request_params: dict[str, Any],
    responses_kwargs: dict[str, Any],
) -> AsyncIterator[ChatChunk]:
    """Run the legacy smart stream path without keeping policy inside the adapter."""

    if use_responses_api:
        responses_stream_emitted_fallback_blocking_chunk = False
        try:
            async for chunk in adapter._stream_chat_via_responses(**responses_kwargs):
                if adapter._stream_chunk_blocks_fallback(chunk):
                    responses_stream_emitted_fallback_blocking_chunk = True
                yield chunk
            return
        except Exception as responses_error:
            if should_fallback_after_responses_error(
                capabilities=adapter.protocol_capabilities,
                provider_config=adapter.provider_config,
                error=responses_error,
                tools=tools,
                tool_choice=tool_choice,
                use_responses_api=use_responses_api,
                runtime_disable_cross_protocol_fallback=(
                    guard_snapshot.runtime_disable_cross_protocol_fallback
                ),
                fallback_blocked_by_visible_chunk=(
                    responses_stream_emitted_fallback_blocking_chunk
                ),
                model=model,
                stream=True,
            ):
                _activate_chat_completions_state(execution_state)
                stream_iterator = build_chat_completions_stream_iterator(
                    adapter=adapter,
                    request_params=request_params,
                    sync_request_params=sync_request_params,
                    messages=messages,
                    model=model,
                    guard_snapshot=guard_snapshot,
                    rescue_reason="responses_fallback",
                )
                async for chunk in stream_iterator:
                    yield chunk
                return
            raise

    stream_iterator = build_chat_completions_stream_iterator(
        adapter=adapter,
        request_params=request_params,
        sync_request_params=sync_request_params,
        messages=messages,
        model=model,
        guard_snapshot=guard_snapshot,
        rescue_reason="chat_completions_primary",
    )
    async for chunk in stream_iterator:
        yield chunk


@dataclass(frozen=True, slots=True)
class LegacyProtocolExecutionSupport:
    adapter: LegacyCompatAdapterProtocol
    execution_state: dict[str, str]
    model: str
    tools: list[dict] | None
    tool_choice: str | None
    guard_snapshot: LegacyProtocolGuardSnapshot

    async def execute_responses_chat(
        self,
        *,
        messages: list[ChatMessage],
        request_params: dict[str, Any],
        responses_kwargs: dict[str, Any],
    ) -> ChatResponse:
        return await execute_legacy_chat(
            adapter=self.adapter,
            execution_state=self.execution_state,
            messages=messages,
            model=self.model,
            tools=self.tools,
            tool_choice=self.tool_choice,
            use_responses_api=True,
            guard_snapshot=self.guard_snapshot,
            request_params=request_params,
            responses_kwargs=responses_kwargs,
        )

    async def execute_chat_completions_chat(
        self,
        *,
        messages: list[ChatMessage],
        request_params: dict[str, Any],
        responses_kwargs: dict[str, Any],
    ) -> ChatResponse:
        return await execute_legacy_chat(
            adapter=self.adapter,
            execution_state=self.execution_state,
            messages=messages,
            model=self.model,
            tools=self.tools,
            tool_choice=self.tool_choice,
            use_responses_api=False,
            guard_snapshot=self.guard_snapshot,
            request_params=request_params,
            responses_kwargs=responses_kwargs,
        )

    async def execute_responses_stream(
        self,
        *,
        messages: list[ChatMessage],
        request_params: dict[str, Any],
        sync_request_params: dict[str, Any],
        responses_kwargs: dict[str, Any],
    ) -> AsyncIterator[ChatChunk]:
        async for chunk in execute_legacy_stream(
            adapter=self.adapter,
            execution_state=self.execution_state,
            messages=messages,
            model=self.model,
            tools=self.tools,
            tool_choice=self.tool_choice,
            use_responses_api=True,
            guard_snapshot=self.guard_snapshot,
            request_params=request_params,
            sync_request_params=sync_request_params,
            responses_kwargs=responses_kwargs,
        ):
            yield chunk

    async def execute_chat_completions_stream(
        self,
        *,
        messages: list[ChatMessage],
        request_params: dict[str, Any],
        sync_request_params: dict[str, Any],
    ) -> AsyncIterator[ChatChunk]:
        async for chunk in execute_legacy_stream(
            adapter=self.adapter,
            execution_state=self.execution_state,
            messages=messages,
            model=self.model,
            tools=self.tools,
            tool_choice=self.tool_choice,
            use_responses_api=False,
            guard_snapshot=self.guard_snapshot,
            request_params=request_params,
            sync_request_params=sync_request_params,
            responses_kwargs={},
        ):
            yield chunk


__all__ = [
    "LegacyCompatAdapterProtocol",
    "LegacyProtocolGuardSnapshot",
    "LegacyProtocolExecutionSupport",
    "build_chat_completions_stream_iterator",
    "execute_legacy_chat",
    "execute_legacy_stream",
    "stream_chat_completions_with_sync_rescue",
]
