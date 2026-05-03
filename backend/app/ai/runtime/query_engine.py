"""
Conversation query runtime (protocol fallback + rescue).
对话查询运行时（协议回退 + 补救）。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import Any

from app.ai.exceptions import AIGatewayError, ProviderError, is_retryable
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
_HOSTED_WEB_SEARCH_FALLBACK_BLOCK_REASONS = frozenset(
    {
        "provider_timeout",
        "provider_connection_error",
    }
)
_WEB_RESEARCH_FALLBACK_TOOL_NAMES = frozenset({"web_search", "fetch_url"})


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
    def _tool_function_name(tool: Any) -> str:
        if not isinstance(tool, dict):
            return ""
        function = tool.get("function")
        if isinstance(function, dict):
            return str(function.get("name") or "").strip()
        return str(tool.get("name") or "").strip()

    @classmethod
    def _has_builtin_web_research_fallback_tools(
        cls,
        tools: list[dict[str, Any]] | None,
    ) -> bool:
        return any(
            cls._tool_function_name(tool) in _WEB_RESEARCH_FALLBACK_TOOL_NAMES
            for tool in (tools or [])
        )

    @classmethod
    def _can_fallback_from_hosted_web_search_unavailable(
        cls,
        *,
        protocol_path: ProtocolPath,
        command: TurnCommand,
        block_reason: str | None,
    ) -> bool:
        if protocol_path != "responses":
            return False
        if block_reason not in _HOSTED_WEB_SEARCH_FALLBACK_BLOCK_REASONS:
            return False
        if not bool(
            (command.extra_kwargs or {}).get("_runtime_hosted_web_search_required")
        ):
            return False
        return cls._has_builtin_web_research_fallback_tools(command.tools)

    @classmethod
    def _is_hosted_web_search_fallback_candidate(
        cls,
        *,
        protocol_path: ProtocolPath,
        command: TurnCommand,
    ) -> bool:
        if protocol_path != "responses":
            return False
        if not bool(
            (command.extra_kwargs or {}).get("_runtime_hosted_web_search_required")
        ):
            return False
        return cls._has_builtin_web_research_fallback_tools(command.tools)

    @staticmethod
    def _hosted_web_search_unavailable_reason(block_reason: str) -> str:
        return f"hosted_web_search_unavailable:{block_reason}"

    @classmethod
    def _empty_or_error_fallback_reason(
        cls,
        *,
        protocol_path: ProtocolPath,
        command: TurnCommand,
        reason: str,
    ) -> str:
        if cls._is_hosted_web_search_fallback_candidate(
            protocol_path=protocol_path,
            command=command,
        ):
            return cls._hosted_web_search_unavailable_reason(reason)
        return reason

    @classmethod
    def _uses_builtin_web_research_fallback_variant(
        cls,
        *,
        session: ProtocolTurnSession,
        protocol_path: ProtocolPath,
        command: TurnCommand,
    ) -> bool:
        if protocol_path != "responses":
            return False
        if not cls._is_hosted_web_search_fallback_candidate(
            protocol_path=protocol_path,
            command=command,
        ):
            return False
        if not session.turn_record.fallback_history:
            return False
        latest_fallback = session.turn_record.fallback_history[-1]
        return (
            latest_fallback.from_protocol == "responses"
            and latest_fallback.to_protocol == "responses"
            and latest_fallback.reason.startswith("hosted_web_search_unavailable:")
        )

    @staticmethod
    def _is_builtin_web_research_fallback_attempt(command: TurnCommand) -> bool:
        return (
            str(
                (command.extra_kwargs or {}).get(
                    "_runtime_native_web_search_fallback_variant"
                )
                or ""
            ).strip()
            == "builtin_web_research_tools"
        )

    @classmethod
    def _can_synthesize_builtin_web_research_fallback(
        cls,
        *,
        command: TurnCommand,
        error: BaseException,
    ) -> bool:
        if not cls._is_builtin_web_research_fallback_attempt(command):
            return False
        if not cls._has_builtin_web_research_fallback_tools(command.tools):
            return False
        if not isinstance(error, AIGatewayError):
            return False
        return is_retryable(error)

    @staticmethod
    def _last_user_query(messages: list[ChatMessage]) -> str:
        for message in reversed(messages or []):
            if str(getattr(message, "role", "") or "").strip() != "user":
                continue
            content = str(getattr(message, "content", "") or "").strip()
            if content:
                return " ".join(content.split())
        return ""

    @classmethod
    def _synthetic_builtin_web_search_tool_call(
        cls,
        *,
        messages: list[ChatMessage],
        command: TurnCommand,
    ) -> list[dict[str, Any]] | None:
        if not cls._has_builtin_web_research_fallback_tools(command.tools):
            return None
        tool_names = {
            cls._tool_function_name(tool)
            for tool in (command.tools or [])
            if cls._tool_function_name(tool)
        }
        if "web_search" not in tool_names:
            return None

        query = cls._last_user_query(messages)
        if not query:
            return None
        arguments = json.dumps(
            {
                "query": query,
                "max_results": 5,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return [
            {
                "id": "synthetic_builtin_web_search_fallback",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": arguments,
                },
            }
        ]

    @classmethod
    def _record_synthetic_builtin_web_research_fallback(
        cls,
        *,
        session: ProtocolTurnSession,
        command: TurnCommand,
        messages: list[ChatMessage],
        error: BaseException,
    ) -> list[dict[str, Any]] | None:
        if not cls._can_synthesize_builtin_web_research_fallback(
            command=command,
            error=error,
        ):
            return None
        tool_call = cls._synthetic_builtin_web_search_tool_call(
            messages=messages,
            command=command,
        )
        if not tool_call:
            return None

        if session.turn_record.fallback_history:
            latest_fallback = session.turn_record.fallback_history[-1]
            latest_fallback.recovered = True
            latest_fallback.metadata["recovery_path"] = (
                "synthetic_builtin_web_search_tool_call"
            )
        metadata = session.turn_record.metadata
        metadata["native_web_search_builtin_fallback_synthesized"] = True
        metadata["native_web_search_builtin_fallback_tool_name"] = "web_search"
        metadata["native_web_search_builtin_fallback_query"] = cls._last_user_query(
            messages
        )
        metadata["native_web_search_builtin_fallback_error_type"] = type(error).__name__
        status_code = ProtocolRecoveryPolicy.extract_status_code(error)
        if status_code is not None:
            metadata["native_web_search_builtin_fallback_error_status_code"] = (
                status_code
            )
        if isinstance(error, ProviderError):
            error_code = str(getattr(error, "error_code", "") or "").strip()
            if error_code:
                metadata["native_web_search_builtin_fallback_error_code"] = error_code
        return tool_call

    @classmethod
    def _synthetic_builtin_web_research_fallback_response(
        cls,
        *,
        session: ProtocolTurnSession,
        command: TurnCommand,
        messages: list[ChatMessage],
        error: BaseException,
    ) -> ChatResponse | None:
        tool_call = cls._record_synthetic_builtin_web_research_fallback(
            session=session,
            command=command,
            messages=messages,
            error=error,
        )
        if not tool_call:
            return None
        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content="",
                tool_calls=tool_call,
            ),
            finish_reason="tool_calls",
            tool_calls=tool_call,
            metadata={
                "native_web_search_builtin_fallback_synthesized": True,
            },
        )

    @classmethod
    def _synthetic_builtin_web_research_fallback_chunk(
        cls,
        *,
        session: ProtocolTurnSession,
        command: TurnCommand,
        messages: list[ChatMessage],
        error: BaseException,
    ) -> ChatChunk | None:
        response = cls._synthetic_builtin_web_research_fallback_response(
            session=session,
            command=command,
            messages=messages,
            error=error,
        )
        if response is None:
            return None
        return cls._response_to_chunk(response)

    @classmethod
    def _command_for_protocol_attempt(
        cls,
        *,
        session: ProtocolTurnSession,
        protocol_path: ProtocolPath,
        command: TurnCommand,
    ) -> TurnCommand:
        if not cls._uses_builtin_web_research_fallback_variant(
            session=session,
            protocol_path=protocol_path,
            command=command,
        ):
            return command

        fallback_reason = session.turn_record.fallback_history[-1].reason
        extra_kwargs = dict(command.extra_kwargs or {})
        extra_kwargs["_runtime_hosted_web_search_required"] = False
        extra_kwargs["_runtime_native_web_search_fallback_reason"] = fallback_reason
        extra_kwargs["_runtime_native_web_search_fallback_variant"] = (
            "builtin_web_research_tools"
        )
        return replace(command, extra_kwargs=extra_kwargs)

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
            attempt_command = self._command_for_protocol_attempt(
                session=session,
                protocol_path=protocol,
                command=command,
            )
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
                    if self._can_fallback_from_hosted_web_search_unavailable(
                        protocol_path=protocol,
                        command=attempt_command,
                        block_reason=block_reason,
                    ) and session.append_fallback(
                        index,
                        from_protocol=protocol,
                        reason=self._hosted_web_search_unavailable_reason(block_reason),
                    ):
                        continue
                    session.mark_failed(block_reason=block_reason)
                    raise
                if session.append_fallback(
                    index,
                    from_protocol=protocol,
                    reason=self._empty_or_error_fallback_reason(
                        protocol_path=protocol,
                        command=attempt_command,
                        reason=f"exception:{type(exc).__name__}",
                    ),
                ):
                    continue
                fallback_response = (
                    self._synthetic_builtin_web_research_fallback_response(
                        session=session,
                        command=attempt_command,
                        messages=messages,
                        error=exc,
                    )
                )
                if fallback_response is not None:
                    return session.finalize_chat_success(fallback_response)
                session.mark_failed()
                raise
            if self.recovery_policy.response_blocks_fallback(response):
                return session.finalize_chat_success(response)

            if session.append_fallback(
                index,
                from_protocol=protocol,
                reason=self._empty_or_error_fallback_reason(
                    protocol_path=protocol,
                    command=attempt_command,
                    reason="chat_empty_no_output",
                ),
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
            attempt_command = self._command_for_protocol_attempt(
                session=session,
                protocol_path=protocol,
                command=command,
            )
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
                    if self._can_fallback_from_hosted_web_search_unavailable(
                        protocol_path=protocol,
                        command=attempt_command,
                        block_reason=block_reason,
                    ) and session.append_fallback(
                        index,
                        from_protocol=protocol,
                        reason=self._hosted_web_search_unavailable_reason(block_reason),
                    ):
                        continue
                    session.mark_failed(block_reason=block_reason)
                    raise stream_exc.cause from stream_exc
                if session.append_fallback(
                    index,
                    from_protocol=protocol,
                    reason=self._empty_or_error_fallback_reason(
                        protocol_path=protocol,
                        command=attempt_command,
                        reason=failure_reason,
                    ),
                ):
                    continue
                fallback_chunk = self._synthetic_builtin_web_research_fallback_chunk(
                    session=session,
                    command=attempt_command,
                    messages=messages,
                    error=stream_exc.cause,
                )
                if fallback_chunk is not None:
                    session.finalize_stream_success(
                        emitted_chunk_count=emitted_chunk_count + 1
                    )
                    yield self._attach_turn_record(fallback_chunk, protocol)
                    return
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
                    reason=self._empty_or_error_fallback_reason(
                        protocol_path=protocol,
                        command=attempt_command,
                        reason=f"stream_exception:{type(exc).__name__}",
                    ),
                ):
                    continue
                session.mark_failed()
                raise

            if self.strict_contract and (
                observed.blocks_fallback
                or not (
                    self._is_hosted_web_search_fallback_candidate(
                        protocol_path=protocol,
                        command=attempt_command,
                    )
                    and session.next_protocol(index) is not None
                )
            ):
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
                reason=self._empty_or_error_fallback_reason(
                    protocol_path=protocol,
                    command=attempt_command,
                    reason=self.recovery_policy.empty_stream_reason(observed),
                ),
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
