"""
Conversation query runtime (protocol fallback + rescue).
对话查询运行时（协议回退 + 补救）。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import Any

from app.ai.exceptions import AIGatewayError, is_retryable
from app.ai.runtime.contracts import TurnCommand
from app.ai.runtime.protocol_planner import ProtocolPlanner
from app.ai.runtime.protocol_recovery_policy import (
    ObservedStream,
    ProtocolRecoveryPolicy,
    StreamObservationError,
)
from app.ai.runtime.protocol_runner import ProtocolRunner
from app.ai.runtime.protocol_turn_session import ProtocolTurnSession
from app.ai.runtime.tool_executor import ToolExecutor
from app.ai.runtime.types import ContextSource, ProtocolPath, TurnRecord
from app.ai.types import ChatChunk, ChatMessage, ChatResponse

_SYNC_RESCUE_MAX_ATTEMPTS = 1
_SYNC_RESCUE_RETRY_BASE_DELAY_SECONDS = 0.5
_SYNC_RESCUE_REASONING_EFFORT = "low"


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
        self.planner = ProtocolPlanner(adapter=adapter)
        self.recovery_policy = ProtocolRecoveryPolicy()
        self.runner = ProtocolRunner(adapter=adapter, strict_contract=strict_contract)
        self.turn_record = TurnRecord()

    def _attach_turn_record(
        self, chunk: ChatChunk, protocol_path: ProtocolPath
    ) -> ChatChunk:
        return self.runner.attach_turn_record(
            chunk,
            protocol_path=protocol_path,
            turn_record=self.turn_record,
        )

    @staticmethod
    def _progress_tool_family(progress_kind: str) -> str | None:
        _ = progress_kind
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

    async def _iter_protocol_stream(
        self,
        *,
        protocol_path: ProtocolPath,
        observed: ObservedStream,
        command: TurnCommand,
    ) -> AsyncIterator[ChatChunk]:
        try:
            async for chunk in self.runner.stream(
                protocol_path=protocol_path,
                command=command,
                turn_record=self.turn_record,
            ):
                attached_chunk = self._attach_turn_record(chunk, protocol_path)
                progress_kinds = self.recovery_policy.extract_progress_kinds(
                    attached_chunk.metadata
                )
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
            raise StreamObservationError(
                cause=exc,
                observed=observed,
            ) from exc

    async def _sync_rescue(
        self,
        *,
        protocol_path: ProtocolPath,
        command: TurnCommand,
    ) -> ChatResponse:
        return await self.runner.chat(
            protocol_path=protocol_path,
            command=command,
            turn_record=self.turn_record,
        )

    @staticmethod
    def _response_to_chunk(response: ChatResponse) -> ChatChunk:
        return ProtocolRunner.response_to_chunk(response)

    @staticmethod
    def _is_retryable_sync_rescue_error(exc: BaseException) -> bool:
        return isinstance(exc, AIGatewayError) and is_retryable(exc)

    async def _run_sync_rescue_with_retry(
        self,
        *,
        protocol_path: ProtocolPath,
        command: TurnCommand,
        session: ProtocolTurnSession,
    ) -> ChatResponse:
        rescue_extra_kwargs = dict(command.extra_kwargs or {})
        rescue_extra_kwargs.setdefault(
            "_runtime_reasoning_effort_override",
            _SYNC_RESCUE_REASONING_EFFORT,
        )
        rescue_command = replace(
            command,
            extra_kwargs=rescue_extra_kwargs,
        )
        delay_seconds = _SYNC_RESCUE_RETRY_BASE_DELAY_SECONDS
        retry_count = 0

        while True:
            session.turn_record.metadata["sync_rescue_attempt_count"] = retry_count + 1
            try:
                session.turn_record.metadata["sync_rescue_retry_count"] = retry_count
                return await self._sync_rescue(
                    protocol_path=protocol_path,
                    command=rescue_command,
                )
            except Exception as exc:  # noqa: BLE001
                if not self._is_retryable_sync_rescue_error(exc) or retry_count >= (
                    _SYNC_RESCUE_MAX_ATTEMPTS - 1
                ):
                    session.turn_record.metadata["sync_rescue_retry_count"] = (
                        retry_count
                    )
                    raise
                retry_count += 1
                session.turn_record.metadata["sync_rescue_retry_count"] = retry_count
                session.turn_record.metadata["sync_rescue_last_retry_error"] = type(
                    exc
                ).__name__
                await asyncio.sleep(delay_seconds)
                delay_seconds *= 2

    async def _attempt_sync_rescue_chunk(
        self,
        *,
        protocol_path: ProtocolPath,
        command: TurnCommand,
        session: ProtocolTurnSession,
        emitted_chunk_count: int,
        rescue_source: str,
    ) -> ChatChunk | None:
        rescue_response = await self._run_sync_rescue_with_retry(
            protocol_path=protocol_path,
            command=command,
            session=session,
        )
        if rescue_response is None:
            return None
        if not self.recovery_policy.response_blocks_fallback(rescue_response):
            return None

        session.finalize_sync_rescue_success(emitted_chunk_count=emitted_chunk_count)
        session.turn_record.metadata["sync_rescue_source"] = rescue_source
        return self._attach_turn_record(
            self._response_to_chunk(rescue_response),
            protocol_path,
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
        session = ProtocolTurnSession.create(
            planner=self.planner,
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
        )
        command = session.command
        self.turn_record = session.turn_record
        last_error: Exception | None = None
        for index, protocol in enumerate(session.plan.protocol_chain):
            session.use_protocol(protocol)
            attempt_command = command
            try:
                response = await self.runner.chat(
                    protocol_path=protocol,
                    command=attempt_command,
                    turn_record=self.turn_record,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                block_reason = self.recovery_policy.fallback_block_reason(exc)
                if block_reason:
                    session.mark_failed(block_reason=block_reason)
                    raise
                if session.append_fallback(
                    index,
                    from_protocol=protocol,
                    reason=f"exception:{type(exc).__name__}",
                ):
                    continue
                session.mark_failed()
                raise
            if self.recovery_policy.response_blocks_fallback(response):
                return session.finalize_chat_success(response)

            if session.append_fallback(
                index,
                from_protocol=protocol,
                reason="chat_empty_no_output",
            ):
                continue

            session.mark_failed(termination_reason="stream_empty_after_fallback")
            raise RuntimeError("chat_empty_after_fallback")

        session.mark_failed()
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
        session = ProtocolTurnSession.create(
            planner=self.planner,
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
        )
        command = session.command
        self.turn_record = session.turn_record
        emitted_chunk_count = 0

        for index, protocol in enumerate(session.plan.protocol_chain):
            session.use_protocol(protocol)
            attempt_command = command
            observed = ObservedStream()
            buffered_chunks: list[ChatChunk] = []
            try:
                async for chunk in self._iter_protocol_stream(
                    protocol_path=protocol,
                    observed=observed,
                    command=attempt_command,
                ):
                    if self.recovery_policy.chunk_should_emit_immediately(chunk):
                        emitted_chunk_count += 1
                        yield chunk
                    else:
                        buffered_chunks.append(chunk)
            except StreamObservationError as stream_exc:
                blocks_fallback = stream_exc.observed.blocks_fallback
                block_reason = self.recovery_policy.fallback_block_reason(
                    stream_exc.cause
                )
                failure_reason = self.recovery_policy.empty_stream_reason(
                    stream_exc.observed,
                    error_type=type(stream_exc.cause).__name__,
                )
                self.recovery_policy.record_stream_failure_metadata(
                    self.turn_record,
                    observed=stream_exc.observed,
                    cause=stream_exc.cause,
                )
                if blocks_fallback:
                    session.mark_partial_failure(
                        termination_reason=self.recovery_policy.partial_failure_reason(
                            stream_exc.cause
                        )
                    )
                    raise stream_exc.cause from stream_exc
                if block_reason:
                    session.mark_failed(block_reason=block_reason)
                    raise stream_exc.cause from stream_exc
                if session.append_fallback(
                    index,
                    from_protocol=protocol,
                    reason=failure_reason,
                ):
                    continue
                if self.recovery_policy.should_skip_sync_rescue_after_stream_error(
                    stream_exc.cause
                ):
                    session.mark_failed()
                    raise stream_exc.cause from stream_exc
                session.turn_record.metadata["sync_rescue_attempted"] = True
                try:
                    rescue_chunk = await self._attempt_sync_rescue_chunk(
                        protocol_path=protocol,
                        command=attempt_command,
                        session=session,
                        emitted_chunk_count=emitted_chunk_count,
                        rescue_source="stream_error",
                    )
                except Exception as rescue_exc:  # noqa: BLE001
                    rescue_block_reason = self.recovery_policy.fallback_block_reason(
                        rescue_exc
                    )
                    if rescue_block_reason:
                        session.mark_failed(block_reason=rescue_block_reason)
                    else:
                        session.mark_failed()
                    raise rescue_exc from stream_exc.cause
                if rescue_chunk is not None:
                    yield rescue_chunk
                    return
                session.mark_failed()
                raise stream_exc.cause from stream_exc
            except Exception as exc:  # noqa: BLE001
                if session.append_fallback(
                    index,
                    from_protocol=protocol,
                    reason=f"stream_exception:{type(exc).__name__}",
                ):
                    continue
                session.mark_failed()
                raise

            if self.strict_contract:
                ToolExecutor.enforce_required_contract(
                    tool_choice=attempt_command.tool_choice,
                    output_text=observed.output_text,
                    tool_calls=observed.collected_tool_calls,
                    turn_record=self.turn_record,
                )

            if observed.blocks_fallback:
                for buffered_chunk in buffered_chunks:
                    emitted_chunk_count += 1
                    yield buffered_chunk
                session.finalize_stream_success(emitted_chunk_count=emitted_chunk_count)
                return

            if session.append_fallback(
                index,
                from_protocol=protocol,
                reason=self.recovery_policy.empty_stream_reason(observed),
            ):
                continue

            rescue_chunk = await self._attempt_sync_rescue_chunk(
                protocol_path=protocol,
                command=attempt_command,
                session=session,
                emitted_chunk_count=emitted_chunk_count,
                rescue_source="stream_empty",
            )
            if rescue_chunk is not None:
                yield rescue_chunk
                return

            session.finalize_stream_empty_failure(
                reason=self.recovery_policy.empty_stream_reason(observed)
            )
            raise RuntimeError("stream_empty_after_fallback")

        session.mark_failed()
        raise RuntimeError("stream_query_failed")


__all__ = ["ConversationQueryEngine"]
