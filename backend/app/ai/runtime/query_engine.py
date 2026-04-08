"""
Conversation query runtime (protocol fallback + rescue).
对话查询运行时（协议回退 + 补救）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from app.ai.runtime.tool_executor import ToolExecutor
from app.ai.runtime.types import ContextSource, FallbackRecord, ProtocolPath, TurnRecord
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


@dataclass
class _ObservedStream:
    chunk_count: int = 0
    has_visible_output: bool = False
    has_reasoning_output: bool = False
    has_tool_calls: bool = False
    has_progress_signal: bool = False
    output_parts: list[str] = field(default_factory=list)
    collected_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    progress_kinds: list[str] = field(default_factory=list)

    @property
    def is_meaningful(self) -> bool:
        return (
            self.has_visible_output or self.has_reasoning_output or self.has_tool_calls
        )

    @property
    def blocks_fallback(self) -> bool:
        return self.has_visible_output or self.has_tool_calls

    @property
    def output_text(self) -> str:
        return "".join(self.output_parts)

    def observe(
        self,
        chunk: ChatChunk,
        *,
        progress_kinds: list[str] | None = None,
    ) -> None:
        self.chunk_count += 1

        delta = getattr(chunk, "delta", None)
        reasoning_delta = getattr(chunk, "reasoning_delta", None)
        tool_calls = getattr(chunk, "tool_calls", None)

        if ToolExecutor.has_visible_output(delta):
            self.has_visible_output = True
            self.output_parts.append(str(delta or ""))
        if ToolExecutor.has_reasoning_output(reasoning_delta):
            self.has_reasoning_output = True
        if ToolExecutor.has_tool_calls(tool_calls):
            self.has_tool_calls = True
            for tool_call in tool_calls or []:
                if isinstance(tool_call, dict):
                    self.collected_tool_calls.append(tool_call)

        for progress_kind in progress_kinds or []:
            normalized = str(progress_kind or "").strip()
            if not normalized:
                continue
            self.has_progress_signal = True
            if normalized not in self.progress_kinds:
                self.progress_kinds.append(normalized)


class _StreamObservationError(RuntimeError):
    def __init__(self, *, cause: Exception, observed: _ObservedStream) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.observed = observed


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
    def _response_blocks_fallback(response: ChatResponse) -> bool:
        return ToolExecutor.has_meaningful_chunk(
            delta=response.message.content,
            tool_calls=response.tool_calls or response.message.tool_calls,
        )

    @staticmethod
    def _partial_failure_reason(exc: BaseException) -> str:
        known_reasons = {
            "provider_failure_after_partial_progress",
            "budget_exit",
            "tool_timeout",
            "tool_execution_error",
            "provider_timeout",
            "provider_rate_limit",
            "provider_unavailable",
            "provider_http_5xx",
            "provider_bad_response",
            "server_interrupt",
            "interrupted",
            "elapsed_budget_exceeded",
            "completion_budget_exceeded",
            "tool_round_budget_exceeded",
            "retry_budget_exhausted",
            "prompt_budget_exceeded",
            "tool_result_budget_exceeded",
            "candidate_tool_budget_exceeded",
        }
        for attr_name in (
            "partial_exit_reason",
            "termination_reason",
            "completion_reason",
            "provider_failure_kind",
            "failure_kind",
            "reason",
        ):
            value = getattr(exc, attr_name, None)
            if not isinstance(value, str):
                continue
            normalized = value.strip()
            if not normalized:
                continue
            if normalized in known_reasons:
                return normalized
            if " " not in normalized:
                return normalized
        if "timeout" in exc.__class__.__name__.lower():
            return "tool_timeout"
        if exc.__class__.__name__ in {"CancelledError", "GeneratorExit"}:
            return "interrupted"
        return "provider_failure_after_partial_progress"

    def _attach_turn_record(
        self, chunk: ChatChunk, protocol_path: ProtocolPath
    ) -> ChatChunk:
        metadata = dict(chunk.metadata or {})
        metadata.setdefault("runtime_protocol_path", protocol_path)
        metadata["runtime_turn_record"] = self.turn_record
        chunk.metadata = metadata
        return chunk

    @staticmethod
    def _extract_progress_kinds(metadata: dict[str, Any] | None) -> list[str]:
        if not isinstance(metadata, dict):
            return []

        progress_kinds: list[str] = []
        if metadata.get("web_search_in_progress"):
            progress_kinds.append("web_search_in_progress")
        return progress_kinds

    @staticmethod
    def _progress_tool_family(progress_kind: str) -> str | None:
        if progress_kind == "web_search_in_progress":
            return "web_research"
        return None

    def _record_progress_kinds(
        self,
        *,
        protocol_path: ProtocolPath,
        progress_kinds: list[str],
    ) -> None:
        if not progress_kinds:
            return

        metadata = self.turn_record.metadata
        metadata["stream_progress_event_count"] = int(
            metadata.get("stream_progress_event_count") or 0,
        ) + len(progress_kinds)

        recorded_kinds = [
            str(kind or "").strip()
            for kind in (metadata.get("stream_progress_kinds") or [])
            if str(kind or "").strip()
        ]
        provider_events = self.turn_record.provider_events

        for progress_kind in progress_kinds:
            normalized = str(progress_kind or "").strip()
            if not normalized:
                continue
            if normalized not in recorded_kinds:
                recorded_kinds.append(normalized)
            if any(
                isinstance(event, dict)
                and str(event.get("kind") or "").strip() == normalized
                and str(event.get("protocol_path") or "").strip() == protocol_path
                for event in provider_events
            ):
                continue
            event = {
                "kind": normalized,
                "protocol_path": protocol_path,
            }
            tool_family = self._progress_tool_family(normalized)
            if tool_family:
                event["tool_family"] = tool_family
            provider_events.append(event)

        metadata["stream_progress_kinds"] = recorded_kinds

    @staticmethod
    def _empty_stream_reason(
        observed: _ObservedStream,
        *,
        error_type: str | None = None,
    ) -> str:
        if error_type:
            if observed.has_progress_signal:
                return (
                    "stream_exception_after_progress_before_meaningful_chunk:"
                    f"{error_type}"
                )
            return f"stream_exception_before_first_meaningful_chunk:{error_type}"
        if observed.has_progress_signal:
            return "stream_progress_only_no_meaningful_output"
        return "stream_empty_no_output"

    @staticmethod
    def _chunk_is_meaningful(chunk: ChatChunk) -> bool:
        return ToolExecutor.has_meaningful_chunk(
            delta=getattr(chunk, "delta", None),
            reasoning_delta=getattr(chunk, "reasoning_delta", None),
            tool_calls=getattr(chunk, "tool_calls", None),
        )

    def _chunk_should_emit_immediately(self, chunk: ChatChunk) -> bool:
        if self._extract_progress_kinds(getattr(chunk, "metadata", None)):
            return True
        return self._chunk_is_meaningful(chunk)

    async def _iter_protocol_stream(
        self,
        *,
        protocol_path: ProtocolPath,
        observed: _ObservedStream,
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
    ) -> AsyncIterator[ChatChunk]:
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
                attached_chunk = self._attach_turn_record(chunk, protocol_path)
                progress_kinds = self._extract_progress_kinds(attached_chunk.metadata)
                observed.observe(
                    attached_chunk,
                    progress_kinds=progress_kinds,
                )
                self._record_progress_kinds(
                    protocol_path=protocol_path,
                    progress_kinds=progress_kinds,
                )
                yield attached_chunk
        except Exception as exc:  # noqa: BLE001
            raise _StreamObservationError(
                cause=exc,
                observed=observed,
            ) from exc

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
            finish_reason = (
                "tool_calls"
                if (response.tool_calls or response.message.tool_calls)
                else "stop"
            )
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
            if self._response_blocks_fallback(response):
                self.turn_record.turn_outcome = "success"
                self.turn_record.termination_reason = (
                    "protocol_fallback"
                    if self.turn_record.fallback_history
                    else "completed"
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
        chunks: list[ChatChunk] = []
        async for chunk in self.iter_stream_turn(
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
            selected_skill_names=selected_skill_names,
            context_sources=context_sources,
            extra_kwargs=extra_kwargs,
        ):
            chunks.append(chunk)
        return chunks

    async def iter_stream_turn(
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
    ) -> AsyncIterator[ChatChunk]:
        runtime_kwargs = dict(extra_kwargs or {})
        preferred_protocol = self._resolve_preferred_protocol(self.adapter)
        protocol_chain = self._build_protocol_chain(preferred_protocol)
        self.turn_record = TurnRecord(
            protocol_path=preferred_protocol,
            selected_tool_names=self._selected_tool_names(tools),
            selected_skill_names=list(selected_skill_names or []),
            context_sources=list(context_sources or []),
        )
        emitted_chunk_count = 0

        for index, protocol in enumerate(protocol_chain):
            self.turn_record.protocol_path = protocol
            observed = _ObservedStream()
            buffered_chunks: list[ChatChunk] = []
            try:
                async for chunk in self._iter_protocol_stream(
                    protocol_path=protocol,
                    observed=observed,
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
                ):
                    if self._chunk_should_emit_immediately(chunk):
                        emitted_chunk_count += 1
                        yield chunk
                    else:
                        buffered_chunks.append(chunk)
            except _StreamObservationError as stream_exc:
                has_meaningful_chunk = stream_exc.observed.is_meaningful
                blocks_fallback = stream_exc.observed.blocks_fallback
                self.turn_record.metadata["stream_failure_chunk_count"] = (
                    stream_exc.observed.chunk_count
                )
                self.turn_record.metadata["stream_failure_has_meaningful_chunk"] = (
                    has_meaningful_chunk
                )
                self.turn_record.metadata["stream_failure_blocks_fallback"] = (
                    blocks_fallback
                )
                self.turn_record.metadata["stream_failure_error_type"] = type(
                    stream_exc.cause,
                ).__name__
                if stream_exc.observed.has_progress_signal:
                    self.turn_record.metadata["stream_failure_after_progress_only"] = (
                        not has_meaningful_chunk
                    )
                if (
                    stream_exc.observed.has_reasoning_output
                    and not blocks_fallback
                ):
                    self.turn_record.metadata[
                        "stream_failure_reasoning_only_before_visible_output"
                    ] = True
                if blocks_fallback:
                    self.turn_record.turn_outcome = "partial"
                    self.turn_record.termination_reason = self._partial_failure_reason(
                        stream_exc.cause
                    )
                    raise stream_exc.cause from stream_exc
                if index + 1 < len(protocol_chain):
                    self.turn_record.fallback_history.append(
                        FallbackRecord(
                            from_protocol=protocol,
                            to_protocol=protocol_chain[index + 1],
                            reason=self._empty_stream_reason(
                                stream_exc.observed,
                                error_type=type(stream_exc.cause).__name__,
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
                    output_text=observed.output_text,
                    tool_calls=observed.collected_tool_calls,
                    turn_record=self.turn_record,
                )

            if observed.blocks_fallback:
                for buffered_chunk in buffered_chunks:
                    emitted_chunk_count += 1
                    yield buffered_chunk
                self.turn_record.turn_outcome = "success"
                self.turn_record.termination_reason = (
                    "protocol_fallback"
                    if self.turn_record.fallback_history
                    else "completed"
                )
                self.turn_record.metadata["stream_chunk_count"] = emitted_chunk_count
                return

            if index + 1 < len(protocol_chain):
                self.turn_record.fallback_history.append(
                    FallbackRecord(
                        from_protocol=protocol,
                        to_protocol=protocol_chain[index + 1],
                        reason=self._empty_stream_reason(observed),
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
            if self._response_blocks_fallback(rescue_response):
                if self.turn_record.fallback_history:
                    self.turn_record.fallback_history[-1].recovered = True
                    self.turn_record.fallback_history[-1].metadata["recovery_path"] = (
                        "sync_chat_completions"
                    )
                self.turn_record.turn_outcome = "success"
                self.turn_record.termination_reason = "protocol_fallback"
                self.turn_record.metadata["sync_rescue"] = True
                self.turn_record.metadata["stream_chunk_count"] = emitted_chunk_count + 1
                rescue_chunk = self._response_to_chunk(rescue_response)
                yield self._attach_turn_record(rescue_chunk, protocol)
                return

            self.turn_record.turn_outcome = "failed"
            self.turn_record.termination_reason = "stream_empty_after_fallback"
            self.turn_record.metadata["sync_rescue"] = True
            self.turn_record.metadata["stream_empty_reason"] = (
                self._empty_stream_reason(observed)
            )
            raise RuntimeError("stream_empty_after_fallback")

        self.turn_record.turn_outcome = "failed"
        self.turn_record.termination_reason = "error"
        raise RuntimeError("stream_query_failed")


__all__ = ["ConversationQueryEngine"]
