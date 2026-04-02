"""
Conversation query runtime (protocol fallback + rescue).
对话查询运行时（协议回退 + 补救）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.runtime.tool_executor import ToolExecutor
from app.ai.runtime.types import ContextSource, FallbackRecord, ProtocolPath, TurnRecord
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


@dataclass
class _CollectedStream:
    chunks: list[ChatChunk]
    has_visible_output: bool = False
    has_reasoning_output: bool = False
    has_tool_calls: bool = False

    @property
    def is_meaningful(self) -> bool:
        return self.has_visible_output or self.has_reasoning_output or self.has_tool_calls


class _StreamCollectionError(RuntimeError):
    def __init__(self, *, cause: Exception, collected: _CollectedStream) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.collected = collected


class ConversationQueryEngine:
    """
    Runtime-level protocol orchestration for one turn.
    单轮 runtime 协议编排（第一版）。
    """

    def __init__(
        self,
        *,
        adapter: Any,
        strict_contract: bool = False,
    ) -> None:
        self.adapter = adapter
        self.strict_contract = strict_contract
        self.turn_record = TurnRecord()

    @staticmethod
    def _resolve_preferred_protocol(adapter: Any) -> ProtocolPath:
        wire_api = str(getattr(adapter, "wire_api", "") or "").strip().lower()
        return "responses" if wire_api == "responses" else "chat_completions"

    @staticmethod
    def _build_protocol_chain(preferred: ProtocolPath) -> list[ProtocolPath]:
        if preferred == "responses":
            return ["responses", "chat_completions"]
        return ["chat_completions"]

    @staticmethod
    def _selected_tool_names(tools: list[dict[str, Any]] | None) -> list[str]:
        if not tools:
            return []
        selected: list[str] = []
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            function_block = tool.get("function") or {}
            tool_name = str(function_block.get("name") or "").strip()
            if tool_name:
                selected.append(tool_name)
        return selected

    @staticmethod
    def _response_is_meaningful(response: ChatResponse) -> bool:
        return ToolExecutor.has_meaningful_chunk(
            delta=response.message.content,
            reasoning_delta=response.message.reasoning_content,
            tool_calls=response.tool_calls or response.message.tool_calls,
        )

    def _attach_turn_record(self, chunk: ChatChunk, protocol_path: ProtocolPath) -> ChatChunk:
        metadata = dict(chunk.metadata or {})
        metadata.setdefault("runtime_protocol_path", protocol_path)
        metadata["runtime_turn_record"] = self.turn_record
        chunk.metadata = metadata
        return chunk

    async def _collect_stream(
        self,
        *,
        protocol_path: ProtocolPath,
        messages: list[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int | None,
        top_p: float,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | None,
        supports_vision: bool,
        supports_audio: bool,
        supports_video: bool,
        extra_kwargs: dict[str, Any],
    ) -> _CollectedStream:
        chunks: list[ChatChunk] = []
        has_visible_output = False
        has_reasoning_output = False
        has_tool_calls = False
        try:
            async for chunk in self.adapter.stream_chat(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                tools=tools,
                tool_choice=tool_choice,
                supports_vision=supports_vision,
                supports_audio=supports_audio,
                supports_video=supports_video,
                _runtime_force_wire_api=protocol_path,
                _runtime_disable_cross_protocol_fallback=True,
                **extra_kwargs,
            ):
                delta = getattr(chunk, "delta", None)
                reasoning_delta = getattr(chunk, "reasoning_delta", None)
                tool_calls = getattr(chunk, "tool_calls", None)
                has_visible_output = has_visible_output or ToolExecutor.has_visible_output(
                    delta,
                )
                has_reasoning_output = has_reasoning_output or ToolExecutor.has_reasoning_output(
                    reasoning_delta,
                )
                has_tool_calls = has_tool_calls or ToolExecutor.has_tool_calls(
                    tool_calls,
                )
                chunks.append(self._attach_turn_record(chunk, protocol_path))
        except Exception as exc:  # noqa: BLE001
            raise _StreamCollectionError(
                cause=exc,
                collected=_CollectedStream(
                    chunks=chunks,
                    has_visible_output=has_visible_output,
                    has_reasoning_output=has_reasoning_output,
                    has_tool_calls=has_tool_calls,
                ),
            ) from exc

        return _CollectedStream(
            chunks=chunks,
            has_visible_output=has_visible_output,
            has_reasoning_output=has_reasoning_output,
            has_tool_calls=has_tool_calls,
        )

    async def _sync_rescue(
        self,
        *,
        protocol_path: ProtocolPath,
        messages: list[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int | None,
        top_p: float,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | None,
        supports_vision: bool,
        supports_audio: bool,
        supports_video: bool,
        extra_kwargs: dict[str, Any],
    ) -> ChatResponse:
        response = await self.adapter.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            tools=tools,
            tool_choice=tool_choice,
            supports_vision=supports_vision,
            supports_audio=supports_audio,
            supports_video=supports_video,
            _runtime_force_wire_api=protocol_path,
            _runtime_disable_cross_protocol_fallback=True,
            **extra_kwargs,
        )
        if self.strict_contract:
            ToolExecutor.enforce_required_contract(
                tool_choice=tool_choice,
                output_text=response.message.content,
                tool_calls=response.tool_calls or response.message.tool_calls,
                turn_record=self.turn_record,
            )
        return response

    @staticmethod
    def _response_to_chunk(response: ChatResponse) -> ChatChunk:
        finish_reason = response.finish_reason
        if not finish_reason:
            finish_reason = "tool_calls" if (response.tool_calls or response.message.tool_calls) else "stop"
        return ChatChunk(
            delta=response.message.content or "",
            reasoning_delta=response.message.reasoning_content or "",
            role=response.message.role,
            finish_reason=finish_reason,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            total_tokens=response.total_tokens,
            tool_calls=response.tool_calls or response.message.tool_calls,
            metadata=dict(response.metadata or {}),
        )

    async def run_chat_turn(
        self,
        *,
        messages: list[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int | None,
        top_p: float,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | None,
        supports_vision: bool,
        supports_audio: bool,
        supports_video: bool,
        selected_skill_names: list[str] | None = None,
        context_sources: list[ContextSource] | None = None,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> ChatResponse:
        runtime_kwargs = dict(extra_kwargs or {})
        preferred_protocol = self._resolve_preferred_protocol(self.adapter)
        protocol_chain = self._build_protocol_chain(preferred_protocol)
        self.turn_record = TurnRecord(
            protocol_path=preferred_protocol,
            selected_tool_names=self._selected_tool_names(tools),
            selected_skill_names=list(selected_skill_names or []),
            context_sources=list(context_sources or []),
        )
        last_error: Exception | None = None
        for index, protocol in enumerate(protocol_chain):
            self.turn_record.protocol_path = protocol
            try:
                response = await self.adapter.chat(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    tools=tools,
                    tool_choice=tool_choice,
                    supports_vision=supports_vision,
                    supports_audio=supports_audio,
                    supports_video=supports_video,
                    _runtime_force_wire_api=protocol,
                    _runtime_disable_cross_protocol_fallback=True,
                    **runtime_kwargs,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if index + 1 < len(protocol_chain):
                    self.turn_record.fallback_history.append(
                        FallbackRecord(
                            from_protocol=protocol,
                            to_protocol=protocol_chain[index + 1],
                            reason=f"exception:{type(exc).__name__}",
                        )
                    )
                    continue
                self.turn_record.turn_outcome = "failed"
                self.turn_record.termination_reason = "error"
                raise

            if self.strict_contract:
                ToolExecutor.enforce_required_contract(
                    tool_choice=tool_choice,
                    output_text=response.message.content,
                    tool_calls=response.tool_calls or response.message.tool_calls,
                    turn_record=self.turn_record,
                )
            if self._response_is_meaningful(response):
                self.turn_record.turn_outcome = "success"
                self.turn_record.termination_reason = (
                    "protocol_fallback" if self.turn_record.fallback_history else "completed"
                )
                metadata = dict(response.metadata or {})
                metadata["runtime_turn_record"] = self.turn_record
                response.metadata = metadata
                return response

            if index + 1 < len(protocol_chain):
                self.turn_record.fallback_history.append(
                    FallbackRecord(
                        from_protocol=protocol,
                        to_protocol=protocol_chain[index + 1],
                        reason="chat_empty_no_output",
                    )
                )
                continue

            self.turn_record.turn_outcome = "failed"
            self.turn_record.termination_reason = "stream_empty_after_fallback"
            raise RuntimeError("chat_empty_after_fallback")

        self.turn_record.turn_outcome = "failed"
        self.turn_record.termination_reason = "error"
        if last_error is not None:
            raise last_error
        raise RuntimeError("chat_query_failed")

    async def run_stream_turn(
        self,
        *,
        messages: list[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int | None,
        top_p: float,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | None,
        supports_vision: bool,
        supports_audio: bool,
        supports_video: bool,
        selected_skill_names: list[str] | None = None,
        context_sources: list[ContextSource] | None = None,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> list[ChatChunk]:
        runtime_kwargs = dict(extra_kwargs or {})
        preferred_protocol = self._resolve_preferred_protocol(self.adapter)
        protocol_chain = self._build_protocol_chain(preferred_protocol)
        self.turn_record = TurnRecord(
            protocol_path=preferred_protocol,
            selected_tool_names=self._selected_tool_names(tools),
            selected_skill_names=list(selected_skill_names or []),
            context_sources=list(context_sources or []),
        )

        for index, protocol in enumerate(protocol_chain):
            self.turn_record.protocol_path = protocol
            try:
                collected = await self._collect_stream(
                    protocol_path=protocol,
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    tools=tools,
                    tool_choice=tool_choice,
                    supports_vision=supports_vision,
                    supports_audio=supports_audio,
                    supports_video=supports_video,
                    extra_kwargs=runtime_kwargs,
                )
            except _StreamCollectionError as stream_exc:
                has_meaningful_chunk = stream_exc.collected.is_meaningful
                self.turn_record.metadata["stream_failure_chunk_count"] = len(
                    stream_exc.collected.chunks,
                )
                self.turn_record.metadata[
                    "stream_failure_has_meaningful_chunk"
                ] = has_meaningful_chunk
                self.turn_record.metadata["stream_failure_error_type"] = type(
                    stream_exc.cause,
                ).__name__
                if has_meaningful_chunk:
                    self.turn_record.turn_outcome = "partial"
                    self.turn_record.termination_reason = "error"
                    raise stream_exc.cause from stream_exc
                if index + 1 < len(protocol_chain):
                    self.turn_record.fallback_history.append(
                        FallbackRecord(
                            from_protocol=protocol,
                            to_protocol=protocol_chain[index + 1],
                            reason=(
                                "stream_exception_before_first_meaningful_chunk:"
                                f"{type(stream_exc.cause).__name__}"
                            ),
                        )
                    )
                    continue
                self.turn_record.turn_outcome = "failed"
                self.turn_record.termination_reason = "error"
                raise stream_exc.cause from stream_exc
            except Exception as exc:  # noqa: BLE001
                if index + 1 < len(protocol_chain):
                    self.turn_record.fallback_history.append(
                        FallbackRecord(
                            from_protocol=protocol,
                            to_protocol=protocol_chain[index + 1],
                            reason=f"stream_exception:{type(exc).__name__}",
                        )
                    )
                    continue
                self.turn_record.turn_outcome = "failed"
                self.turn_record.termination_reason = "error"
                raise

            if self.strict_contract:
                ToolExecutor.enforce_required_contract(
                    tool_choice=tool_choice,
                    output_text="".join(chunk.delta for chunk in collected.chunks),
                    tool_calls=[
                        tool_call
                        for chunk in collected.chunks
                        for tool_call in (chunk.tool_calls or [])
                        if isinstance(tool_call, dict)
                    ],
                    turn_record=self.turn_record,
                )

            if collected.is_meaningful:
                self.turn_record.turn_outcome = "success"
                self.turn_record.termination_reason = (
                    "protocol_fallback" if self.turn_record.fallback_history else "completed"
                )
                self.turn_record.metadata["stream_chunk_count"] = len(collected.chunks)
                return collected.chunks

            if index + 1 < len(protocol_chain):
                self.turn_record.fallback_history.append(
                    FallbackRecord(
                        from_protocol=protocol,
                        to_protocol=protocol_chain[index + 1],
                        reason="stream_empty_no_output",
                    )
                )
                continue

            rescue_response = await self._sync_rescue(
                protocol_path=protocol,
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                tools=tools,
                tool_choice=tool_choice,
                supports_vision=supports_vision,
                supports_audio=supports_audio,
                supports_video=supports_video,
                extra_kwargs=runtime_kwargs,
            )
            if self._response_is_meaningful(rescue_response):
                if self.turn_record.fallback_history:
                    self.turn_record.fallback_history[-1].recovered = True
                    self.turn_record.fallback_history[-1].metadata[
                        "recovery_path"
                    ] = "sync_chat_completions"
                self.turn_record.turn_outcome = "success"
                self.turn_record.termination_reason = "protocol_fallback"
                self.turn_record.metadata["sync_rescue"] = True
                rescue_chunk = self._response_to_chunk(rescue_response)
                return [self._attach_turn_record(rescue_chunk, protocol)]

            self.turn_record.turn_outcome = "failed"
            self.turn_record.termination_reason = "stream_empty_after_fallback"
            self.turn_record.metadata["sync_rescue"] = True
            raise RuntimeError("stream_empty_after_fallback")

        self.turn_record.turn_outcome = "failed"
        self.turn_record.termination_reason = "error"
        raise RuntimeError("stream_query_failed")


__all__ = ["ConversationQueryEngine"]
