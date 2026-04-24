# FROZEN: do not add new dependencies
"""Execution loop helpers and IO adapter for StreamExecutionHandler.generate()."""
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import suppress
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from app.ai.sse import SSEChunkEncoder
from app.ai.types import ChatMessage, ChatResponse
from app.core.i18n import _
from app.core.response import (
    build_error_event,
    build_exception_debug,
    resolve_public_error_message,
)
from app.enums.common import UserRoleEnum
from app.middleware.trace import trace_id_var
from app.services.ai.conversation_turn_flow_projector import (
    ConversationTurnFlowProjector,
)

from .base import log_user_type_for_call_log
from .failure_classifier import FailureClassifier
from .final_output_policy import is_trusted_assistant_final_output_source
from .recovery_manager import RecoveryManager
from .stream_error_utils import resolve_stream_public_error_message
from .stream_finalization_pipeline import StreamFinalizationArtifacts
from .stream_generation_pipeline import (
    append_partial_assistant_output,
    build_done_event,
    build_initial_events,
    build_terminal_result,
    drain_runtime_events,
    finalize_successful_turn,
    reset_stream_state,
)
from .stream_generation_view import ensure_stream_generation_view
from .stream_llm_round_support import (
    StreamRoundState,
    finalize_model_round,
    handle_stream_chunk,
    prepare_stream_round,
)
from .stream_replay_events import build_replay_events
from .stream_tool_batch_runtime import (
    StreamToolBatchCallbacks,
    StreamToolBatchRuntimeInput,
    run_stream_tool_batch,
)
from .tool_execution_helpers import (
    normalize_tool_call_outcome as _normalize_tool_call_outcome_impl,
)
from .tool_execution_helpers import (
    recover_tool_results_from_messages as _recover_tool_results_from_messages_impl,
)
from .turn_executor import ToolBatchResult

if TYPE_CHECKING:
    from app.ai.tools.types import ToolDefinition, ToolResult

    from .execution_state_machine import ExecutionStateMachine
    from .stream_handler import StreamExecutionHandler
    from .turn_executor import ModelRoundResult
    from .types import ToolUsePolicy


_CANONICAL_TOOL_CALLS_METADATA_KEY = "canonical_tool_calls"
_TRANSPORT_DISCONNECT_TOKENS = (
    "requestresponsecycle.run_asgi",
    "client disconnected",
    "connection closed",
    "transport close",
    "listen_for_disconnect",
)


class StreamIOAdapter:
    """Transport adapter for streaming TurnExecutor execution."""

    def __init__(self, handler: StreamExecutionHandler) -> None:
        self.handler = handler

    @staticmethod
    def _normalize_tool_call_outcome(
        outcome: tuple[Any, ...],
    ) -> tuple[ChatResponse | None, list[Any], int, int]:
        return _normalize_tool_call_outcome_impl(outcome)

    def _selected_skill_names(self) -> list[str]:
        capability_bundle = getattr(self.handler.prep, "capability_bundle", None)
        if capability_bundle is None:
            return []
        return list(getattr(capability_bundle, "selected_skill_names", []) or [])

    def _context_sources(self) -> list[Any]:
        capability_bundle = getattr(self.handler.prep, "capability_bundle", None)
        if capability_bundle is None:
            return []
        return list(getattr(capability_bundle, "context_sources", []) or [])

    def _request_with_defaults(self) -> Any:
        request = self.handler.request
        required_attrs = (
            "interaction_mode",
            "input_variables",
            "billing_context",
            "tool_use_policy",
            "user_role",
            "interaction_updates",
        )
        if all(hasattr(request, attr) for attr in required_attrs):
            return request
        payload = dict(getattr(request, "__dict__", {}) or {})
        payload.setdefault("interaction_mode", "trusted_auto")
        payload.setdefault("input_variables", {})
        payload.setdefault("billing_context", None)
        payload.setdefault("tool_use_policy", self.handler.prep.tool_use_policy)
        payload.setdefault("user_role", UserRoleEnum.TENANT_ADMIN.value)
        payload.setdefault("interaction_updates", None)
        return SimpleNamespace(**payload)

    def _sync_runtime_metadata(self, metadata: dict[str, Any] | None) -> None:
        if not isinstance(metadata, dict):
            return
        runtime_model_info = metadata.get("runtime_model_info")
        if isinstance(runtime_model_info, dict):
            generation_view = self.handler._stream_generation_view()
            generation_view.runtime_model_info = dict(runtime_model_info)
            sandbox = getattr(self.handler.engine, "sandbox", None)
            if sandbox is not None and hasattr(sandbox, "set_runtime_model_info"):
                sandbox.set_runtime_model_info(runtime_model_info)
        raw_turn_record = metadata.get("runtime_turn_record")
        self.handler._stream_generation_view().replace_runtime_turn_record(raw_turn_record)

    def _ensure_runtime_turn_record_state(self) -> None:
        if not hasattr(self.handler, "_runtime_turn_record"):
            self.handler._runtime_turn_record = {}
        if not hasattr(self.handler, "_runtime_turn_record_source"):
            self.handler._runtime_turn_record_source = None
        if not hasattr(self.handler, "_runtime_turn_record_overlays"):
            self.handler._runtime_turn_record_overlays = {}

    def _store_canonical_tool_calls(self, tool_calls: Any) -> None:
        normalized_tool_calls = [
            dict(item) for item in (tool_calls or []) if isinstance(item, dict)
        ]
        if not normalized_tool_calls:
            return

        self._ensure_runtime_turn_record_state()
        view = self.handler._stream_generation_view()
        runtime_state = getattr(view, "runtime", None)
        runtime_turn_record_source = getattr(
            runtime_state,
            "runtime_turn_record_source",
            None,
        )
        if runtime_turn_record_source is not None:
            source_metadata = getattr(runtime_turn_record_source, "metadata", None)
            if isinstance(source_metadata, dict):
                source_metadata[_CANONICAL_TOOL_CALLS_METADATA_KEY] = list(
                    normalized_tool_calls
                )
            else:
                with suppress(Exception):
                    runtime_turn_record_source.metadata = {
                        _CANONICAL_TOOL_CALLS_METADATA_KEY: list(
                            normalized_tool_calls
                        )
                    }

        view.refresh_runtime_turn_record()
        turn_record_payload = (
            dict(view.runtime_turn_record)
            if isinstance(view.runtime_turn_record, dict)
            else {}
        )
        turn_record_metadata = (
            dict(turn_record_payload.get("metadata") or {})
            if isinstance(turn_record_payload.get("metadata"), dict)
            else {}
        )
        turn_record_metadata[_CANONICAL_TOOL_CALLS_METADATA_KEY] = list(
            normalized_tool_calls
        )
        turn_record_payload["metadata"] = turn_record_metadata
        view.runtime_turn_record = turn_record_payload

    @staticmethod
    def _store_tool_calls_on_response(
        response: ChatResponse | None,
        *,
        tool_calls: list[dict[str, Any]],
    ) -> None:
        if response is None:
            return
        response.metadata = dict(response.metadata or {})
        response.metadata[_CANONICAL_TOOL_CALLS_METADATA_KEY] = list(tool_calls)
        message_metadata = (
            dict(response.message.metadata or {})
            if isinstance(response.message.metadata, dict)
            else {}
        )
        message_metadata[_CANONICAL_TOOL_CALLS_METADATA_KEY] = list(tool_calls)
        response.message.metadata = message_metadata

    async def call_llm(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[ToolDefinition] | None,
        tool_use_policy: ToolUsePolicy,
        **kwargs: Any,
    ) -> ModelRoundResult:
        round_kind = str(kwargs.get("breach_retry_result") or "").strip()
        runtime_context = await prepare_stream_round(self, round_kind=round_kind)
        req_role = getattr(
            self.handler.request,
            "user_role",
            UserRoleEnum.TENANT_ADMIN.value,
        )
        state = StreamRoundState()
        async for chunk in self.handler.engine._stream_llm_chunks(
            agent=self.handler.agent,
            messages=messages,
            tenant_id=self.handler.request.tenant_id,
            conversation_id=self.handler.request.conversation_id,
            route_result=self.handler.prep.route_result,
            tools=tools,
            execution_path=getattr(self.handler.prep, "execution_path", None),
            user_id=getattr(self.handler.request, "user_id", None),
            billing_context=getattr(self.handler.request, "billing_context", None),
            log_user_type=log_user_type_for_call_log(req_role),
            runtime_context=runtime_context,
            all_tool_names=[
                tool.name
                for tool in (getattr(self.handler.prep, "all_tools", None) or [])
            ],
            selected_skill_names=self._selected_skill_names(),
            context_sources=self._context_sources(),
            tool_use_policy=tool_use_policy,
            **kwargs,
        ):
            await handle_stream_chunk(
                self,
                state,
                chunk=chunk,
            )

        return finalize_model_round(self, state)

    async def handle_tool_calls(
        self,
        *,
        response: ChatResponse,
        tools: list[ToolDefinition],
        messages: list[ChatMessage],
        **kwargs: Any,
    ) -> ToolBatchResult:
        request_proxy = self._request_with_defaults()
        tool_calls = list(response.tool_calls or response.message.tool_calls or [])
        tool_calls, _truncated_after_navigation = (
            self.handler.runtime_contract.truncate_tool_calls_after_navigation(tool_calls)
        )
        starting_total_tokens = int(kwargs.get("starting_total_tokens") or 0)
        starting_completion_tokens = int(
            kwargs.get("starting_completion_tokens") or 0
        )
        reasoning_content = str(
            response.message.reasoning_content or response.message.content or ""
        ).strip() or None
        runtime_outcome = await run_stream_tool_batch(
            runtime=StreamToolBatchRuntimeInput(
                sandbox=self.handler.engine.sandbox,
                request=request_proxy,
                response=response,
                tools=tools,
                all_tools=self.handler.prep.all_tools,
                tool_consent_modes=self.handler.prep.tool_consent_modes,
                messages=messages,
                tool_calls=tool_calls,
                starting_total_tokens=starting_total_tokens,
                starting_completion_tokens=starting_completion_tokens,
                reasoning_content=reasoning_content,
            ),
            callbacks=StreamToolBatchCallbacks(
                emit_event=self.handler._emit_runtime_event,
                emit_chunk=self.emit_chunk,
                budget_exit_reason=self.handler._state.budget_exit_reason,
                register_budget_exit=self.handler._register_budget_exit,
                build_text_round_response=self.handler._build_text_round_response,
            ),
        )
        if runtime_outcome.output_override is not None:
            self.handler._stream_generation_view().output = runtime_outcome.output_override
        if runtime_outcome.effective_tool_calls:
            self._store_canonical_tool_calls(runtime_outcome.effective_tool_calls)
            self._store_tool_calls_on_response(
                response=response,
                tool_calls=runtime_outcome.effective_tool_calls,
            )
            self._store_tool_calls_on_response(
                response=runtime_outcome.response,
                tool_calls=runtime_outcome.effective_tool_calls,
            )

        return ToolBatchResult(
            response=runtime_outcome.response,
            tool_results=runtime_outcome.tool_results,
            total_tokens=runtime_outcome.total_tokens,
            completion_tokens_used=runtime_outcome.completion_tokens_used,
        )

    async def finalize_partial_output(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
    ) -> tuple[str, int, int]:
        output, final_total_tokens, final_completion_tokens = (
            await self.handler.runtime_contract.finalize_partial_output(
                agent=self.handler.agent,
                request=self.handler.request,
                prep=self.handler.prep,
                messages=messages,
                response=response,
                state=state,
                tool_results=tool_results,
                reason=reason,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
                selected_skill_names=self._selected_skill_names(),
                context_sources=self._context_sources(),
            )
        )
        stream_local_output = str(self.handler._stream_generation_view().output or "").strip()
        if not str(output or "").strip() and stream_local_output:
            output = stream_local_output
        return output, final_total_tokens, final_completion_tokens

    async def finalize_completed_output(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
        reason: str,
        total_tokens: int,
        completion_tokens_used: int,
    ) -> tuple[str, int, int]:
        output, final_total_tokens, final_completion_tokens = (
            await self.handler.runtime_contract.finalize_completed_output(
                agent=self.handler.agent,
                request=self.handler.request,
                prep=self.handler.prep,
                messages=messages,
                response=response,
                state=state,
                tool_results=tool_results,
                reason=reason,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
                selected_skill_names=self._selected_skill_names(),
                context_sources=self._context_sources(),
            )
        )
        stream_local_output = str(self.handler._stream_generation_view().output or "").strip()
        if not str(output or "").strip() and stream_local_output:
            output = stream_local_output
        return output, final_total_tokens, final_completion_tokens

    def should_retry_tool_contract_breach(
        self,
        *,
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
    ) -> tuple[bool, ToolUsePolicy | None, str]:
        return self.handler.runtime_contract.should_retry_tool_contract_breach(
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables=input_variables,
        )

    def should_retry_web_research_contract_breach(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[ToolDefinition],
        input_variables: dict[str, Any] | None,
        continuation: Any,
    ) -> tuple[bool, ToolUsePolicy | None, str]:
        return self.handler.runtime_contract.should_retry_web_research_contract_breach(
            messages=messages,
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables=input_variables,
            continuation=continuation,
        )

    def analyze_post_tool_contract_breach(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[Any],
        input_variables: dict[str, Any] | None,
    ) -> tuple[str | None, ToolUsePolicy | None, dict[str, Any]]:
        if response is None:
            return None, None, {}
        return self.handler.runtime_contract.analyze_post_tool_contract_breach(
            messages=messages,
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables=input_variables,
        )

    def restrict_tools_to_names(
        self,
        tools: list[Any],
        allowed_tool_names: list[str] | None,
    ) -> list[Any]:
        return self.handler.runtime_contract.restrict_tools_to_names(
            tools,
            allowed_tool_names,
        )

    def log_tool_contract_diagnostics(
        self,
        *,
        agent: Any,
        messages: list[ChatMessage],
        response: Any,
        tools: list[Any],
        policy: ToolUsePolicy,
        conversation_id: int | None,
        breach_type: str,
        retry_result: str,
        continuation: Any,
    ) -> None:
        self.handler.runtime_contract.log_tool_contract_diagnostics(
            agent=agent,
            messages=messages,
            response=response,
            tools=tools,
            policy=policy,
            conversation_id=conversation_id,
            breach_type=breach_type,
            retry_result=retry_result,
            continuation=continuation,
        )

    async def emit_chunk(self, text: str) -> None:
        if text:
            generation_view = ensure_stream_generation_view(self.handler)
            generation_view.visible_stream_content = (
                generation_view.visible_stream_content + text
            )
            generation_view.output = generation_view.visible_stream_content
            await self.handler._emit_runtime_event(
                {
                    "event": "message",
                    "delta": text,
                }
            )


async def _cancel_executor_task(task: asyncio.Task[Any] | None) -> None:
    if task is None or task.done():
        return
    task.cancel()
    with suppress(BaseException):
        await task


def _is_cancelled_base_exception(exc: BaseException) -> bool:
    return isinstance(exc, asyncio.CancelledError) or type(exc).__name__ == "CancelledError"


def _is_transport_disconnect_cancellation(exc: BaseException) -> bool:
    lowered_error = str(exc or "").strip().lower()
    return any(token in lowered_error for token in _TRANSPORT_DISCONNECT_TOKENS)


def _mark_transport_disconnect_result(result: Any) -> None:
    diagnostics = dict(getattr(result, "diagnostics", None) or {})
    diagnostics["transport_disconnect"] = True
    result.diagnostics = diagnostics

    turn_record = (
        dict(result.turn_record)
        if isinstance(getattr(result, "turn_record", None), dict)
        else {}
    )
    turn_record["transport_disconnect"] = True
    metadata = (
        dict(turn_record.get("metadata") or {})
        if isinstance(turn_record.get("metadata"), dict)
        else {}
    )
    metadata["transport_disconnect"] = True
    turn_record["metadata"] = metadata
    result.turn_record = turn_record


def _resolve_canonical_tool_calls(turn_record: Any) -> list[dict[str, Any]]:
    if not isinstance(turn_record, dict):
        return []
    metadata = (
        dict(turn_record.get("metadata") or {})
        if isinstance(turn_record.get("metadata"), dict)
        else {}
    )
    candidates = [
        turn_record.get(_CANONICAL_TOOL_CALLS_METADATA_KEY),
        metadata.get(_CANONICAL_TOOL_CALLS_METADATA_KEY),
    ]
    for metadata_key in ("orchestration", "turn_diagnostics"):
        nested = metadata.get(metadata_key)
        if isinstance(nested, dict):
            candidates.append(nested.get(_CANONICAL_TOOL_CALLS_METADATA_KEY))

    for candidate in candidates:
        if not isinstance(candidate, list):
            continue
        normalized = [dict(item) for item in candidate if isinstance(item, dict)]
        if normalized:
            return normalized
    return []


def _persist_canonical_turn_flow_metadata(
    turn_record: dict[str, Any],
    *,
    turn_flow: dict[str, Any],
    tool_calls: list[dict[str, Any]],
) -> None:
    turn_record["turn_flow"] = turn_flow
    metadata = (
        dict(turn_record.get("metadata") or {})
        if isinstance(turn_record.get("metadata"), dict)
        else {}
    )
    metadata["turn_flow"] = turn_flow
    metadata[_CANONICAL_TOOL_CALLS_METADATA_KEY] = list(tool_calls)
    for metadata_key in ("orchestration", "turn_diagnostics"):
        nested = (
            dict(metadata.get(metadata_key) or {})
            if isinstance(metadata.get(metadata_key), dict)
            else {}
        )
        nested["turn_flow"] = turn_flow
        nested[_CANONICAL_TOOL_CALLS_METADATA_KEY] = list(tool_calls)
        metadata[metadata_key] = nested
    turn_record["metadata"] = metadata


def _hydrate_artifacts_turn_flow_from_canonical_tool_calls(
    artifacts: StreamFinalizationArtifacts,
) -> None:
    turn_record = (
        dict(artifacts.result.turn_record)
        if isinstance(artifacts.result.turn_record, dict)
        else {}
    )
    if not turn_record:
        return

    canonical_tool_calls = _resolve_canonical_tool_calls(turn_record)
    if not canonical_tool_calls:
        return

    diagnostics_payload = (
        dict(artifacts.diagnostics_payload)
        if isinstance(artifacts.diagnostics_payload, dict)
        else {}
    )
    metadata_payload = dict(diagnostics_payload)
    metadata_payload["turn_record"] = turn_record
    normalized_turn_flow = ConversationTurnFlowProjector.normalize_turn_flow(
        turn_record.get("turn_flow"),
        turn_outcome=str(turn_record.get("turn_outcome") or "").strip() or None,
        completion_reason=artifacts.result.completion_reason,
        interrupted=bool(getattr(artifacts.result, "interrupted", False)),
        failure_kind=(
            str(
                diagnostics_payload.get("failure_kind")
                or turn_record.get("failure_kind")
                or ""
            ).strip()
            or None
        ),
        final_output_source=(
            str(
                diagnostics_payload.get("final_output_source")
                or turn_record.get("final_output_source")
                or ""
            ).strip()
            or None
        ),
        metadata=metadata_payload,
        content=getattr(artifacts.result, "output", ""),
        tool_calls=canonical_tool_calls,
    )
    if not isinstance(normalized_turn_flow, dict):
        return

    diagnostics_payload["turn_flow"] = normalized_turn_flow
    artifacts.diagnostics_payload = diagnostics_payload
    if isinstance(getattr(artifacts.result, "diagnostics", None), dict):
        artifacts.result.diagnostics["turn_flow"] = normalized_turn_flow
    _persist_canonical_turn_flow_metadata(
        turn_record,
        turn_flow=normalized_turn_flow,
        tool_calls=canonical_tool_calls,
    )
    artifacts.result.turn_record = turn_record


def _resolve_stream_exception_completion_reason(handler: Any) -> str:
    state = getattr(handler, "_state", None)
    if state is None:
        return "stream_execution_error"

    failure_kind = str(getattr(state, "provider_failure_kind", "") or "").strip().lower()
    if failure_kind in {"", "none"}:
        return "stream_execution_error"
    if failure_kind == "budget_exit":
        resolver = getattr(state, "budget_exit_reason", None)
        if callable(resolver):
            reason = str(resolver() or "").strip()
            if reason:
                return reason
        return "budget_exit"
    if failure_kind == "provider_timeout":
        return "provider_timeout"
    if failure_kind == "provider_unavailable":
        return "provider_unavailable"
    if failure_kind in {"provider_http_5xx", "provider_bad_response", "provider_rate_limit"}:
        return "provider_error"
    if failure_kind in {"tool_timeout", "tool_execution_error"}:
        return "tool_error"
    if failure_kind == "server_interrupt":
        return "interrupted"
    return failure_kind


def _resolve_completion_reason_public_error_message(
    *,
    completion_reason: str,
    fallback_message: str | None,
) -> str:
    normalized_reason = str(completion_reason or "").strip().lower()
    if normalized_reason == "provider_timeout":
        return _("ai.error.provider_timeout")
    if normalized_reason == "provider_unavailable":
        return _("ai.error.provider_connection")
    if normalized_reason == "provider_error":
        return _("ai.error.provider_server_error")
    if normalized_reason == "tool_error":
        return _("common.server_error")
    return resolve_public_error_message(fallback_message=fallback_message)


def _sync_exception_runtime_metadata(handler: Any, exc: BaseException) -> None:
    view = ensure_stream_generation_view(handler)

    runtime_model_info = getattr(exc, "_novusai_runtime_model_info", None)
    if isinstance(runtime_model_info, dict) and runtime_model_info:
        view.runtime_model_info = dict(runtime_model_info)
        sandbox = getattr(handler.engine, "sandbox", None)
        if sandbox is not None and hasattr(sandbox, "set_runtime_model_info"):
            sandbox.set_runtime_model_info(runtime_model_info)

    runtime_turn_record = getattr(exc, "_novusai_runtime_turn_record", None)
    if runtime_turn_record is not None:
        view.replace_runtime_turn_record(runtime_turn_record)
        return

    protocol_path = str(getattr(exc, "_novusai_runtime_protocol_path", "") or "").strip()
    if protocol_path:
        handler._update_turn_progress(protocol_path=protocol_path)


def _register_stream_exception_failure(handler: Any, exc: BaseException) -> None:
    failure_kind, failure_event = FailureClassifier.classify_exception(exc)
    if failure_kind == "none":
        return

    state = getattr(handler, "_state", None)
    if state is None:
        return

    existing_failure_kind = str(
        getattr(state, "provider_failure_kind", "") or ""
    ).strip().lower()
    event_payload = dict(failure_event or {})
    protocol_path = str(getattr(exc, "_novusai_runtime_protocol_path", "") or "").strip()
    if not protocol_path:
        protocol_path = str(
            (ensure_stream_generation_view(handler).runtime_turn_record or {}).get(
                "protocol_path",
            )
            or "",
        ).strip()
    if protocol_path and "protocol_path" not in event_payload:
        event_payload["protocol_path"] = protocol_path

    # Preserve the original classified provider/tool failure when cancellation is only
    # the outer transport symptom after a more specific runtime failure was already
    # recorded. This keeps graceful timeout/interruption copy and done semantics aligned.
    if (
        failure_kind == "server_interrupt"
        and existing_failure_kind not in {"", "none", "server_interrupt"}
    ):
        if event_payload:
            state.provider_events.append(dict(event_payload))
        return

    state.register_provider_failure(
        kind=failure_kind,
        event=event_payload or None,
    )


def _should_emit_graceful_exception_done(handler: Any) -> bool:
    state = getattr(handler, "_state", None)
    if state is None:
        return False
    failure_kind = str(getattr(state, "provider_failure_kind", "") or "").strip().lower()
    return failure_kind not in {"", "none"}


def _should_surface_exception_partial_output(
    *,
    generated_partial_output: bool,
    had_visible_output: bool,
    provider_failure_kind: str,
    final_output_source: str | None,
) -> bool:
    if not generated_partial_output:
        return True
    if not had_visible_output:
        return True
    if is_trusted_assistant_final_output_source(final_output_source):
        return True
    return str(provider_failure_kind or "").strip() == "budget_exit"


def _resolve_exception_final_output_source(
    *,
    partial_output: str,
    state: Any,
    tool_results: list[Any],
) -> str | None:
    if not str(partial_output or "").strip():
        return None
    intent_plan = list(getattr(state, "intent_plan", []) or []) if state is not None else []
    if RecoveryManager.has_completed_output_evidence(
        intent_plan,
        tool_results=tool_results,
    ):
        return "recovery_evidence"
    return "partial_output"


def _resolve_exception_tool_results(
    *,
    all_tool_results: list[Any],
    messages: list[Any],
    turn_start_message_index: int,
) -> list[Any]:
    recovered_tool_results = list(all_tool_results or [])
    if recovered_tool_results:
        return recovered_tool_results
    return _recover_tool_results_from_messages_impl(
        messages,
        start_index=turn_start_message_index,
        skip_unresolved_interactions=True,
    )


async def _build_stream_exception_artifacts(
    handler: Any,
    *,
    messages: list[Any],
    rag_sources: list[dict[str, Any]] | None,
    output: str,
    total_tokens: int,
    all_tool_results: list[Any],
    turn_start_message_index: int = 0,
    public_error_message: str,
    completion_reason: str,
) -> StreamFinalizationArtifacts:
    view = ensure_stream_generation_view(handler)
    duration_ms = int((time.perf_counter() - handler.start_time) * 1000)
    recovered_tool_results = _resolve_exception_tool_results(
        all_tool_results=all_tool_results,
        messages=messages,
        turn_start_message_index=turn_start_message_index,
    )
    partial_output = str(view.output or output or "").strip()
    generated_partial_output = False
    partial_tokens = view.total_tokens
    if partial_tokens is None:
        partial_tokens = total_tokens
    partial_completion_tokens = int(view.completion_tokens_used or 0)

    if not partial_output:
        partial_output, partial_tokens, partial_completion_tokens = (
            await handler.runtime_contract.finalize_partial_output(
                agent=handler.agent,
                request=handler.request,
                prep=handler.prep,
                messages=messages,
                response=None,
                state=handler._state,
                tool_results=recovered_tool_results,
                reason=completion_reason,
                total_tokens=partial_tokens,
                completion_tokens_used=partial_completion_tokens,
                selected_skill_names=[],
                context_sources=[],
            )
        )
        generated_partial_output = bool(str(partial_output or "").strip())

    partial_output = str(partial_output or "").strip()
    state = getattr(handler, "_state", None)
    final_output_source = _resolve_exception_final_output_source(
        partial_output=partial_output,
        state=state,
        tool_results=recovered_tool_results,
    )
    if state is not None:
        state.preparation_diagnostics["final_output_source"] = (
            final_output_source
        )
    surfaced_output = (
        partial_output
        if _should_surface_exception_partial_output(
            generated_partial_output=generated_partial_output,
            had_visible_output=bool(str(view.visible_stream_content or "").strip()),
            provider_failure_kind=str(view.provider_failure_kind or ""),
            final_output_source=final_output_source,
        )
        else ""
    )
    if surfaced_output:
        view.output = surfaced_output
        append_partial_assistant_output(
            messages,
            output=surfaced_output,
            reasoning_output=view.reasoning_output,
        )

    failed_result = build_terminal_result(
        handler,
        messages=messages,
        rag_sources=rag_sources,
        output=surfaced_output,
        total_tokens=partial_tokens,
        tool_results=recovered_tool_results,
        duration_ms=duration_ms,
        error=resolve_public_error_message(fallback_message=public_error_message),
        completion_reason=completion_reason,
        interrupted=False,
        include_provider_state=True,
    )
    diagnostics_payload = dict(failed_result.diagnostics or {})
    turn_record = dict(failed_result.turn_record or {})
    resolved_protocol_path = str(
        turn_record.get("protocol_path")
        or diagnostics_payload.get("protocol_path")
        or "",
    ).strip()

    replay_events: list[str] = []
    if surfaced_output:
        streamed_output = view.visible_stream_content.strip()
        partial_reply_stream_chunks = (
            view.chunk_text_for_streaming(surfaced_output)
            if view.should_replay_finalized_output(
                streamed_output=streamed_output,
                finalized_output=surfaced_output,
            )
            else []
        )
        replay_events = build_replay_events(
            streamed_output=streamed_output,
            finalized_output=surfaced_output,
            final_output_source=diagnostics_payload.get("final_output_source"),
            partial_reply_stream_chunks=partial_reply_stream_chunks,
            completed_reply_stream_chunks=[],
        )

    return StreamFinalizationArtifacts(
        result=failed_result,
        diagnostics_payload=diagnostics_payload,
        response_metadata={},
        resolved_protocol_path=resolved_protocol_path,
        replay_events=replay_events,
    )


async def _handle_stream_exception(
    handler: Any,
    *,
    exc: Exception,
    executor_task: asyncio.Task[Any] | None,
    messages: list[Any],
    rag_sources: list[dict[str, Any]] | None,
    output: str,
    total_tokens: int,
    all_tool_results: list[Any],
    turn_start_message_index: int,
    logger: Any,
) -> AsyncIterator[str]:
    await _cancel_executor_task(executor_task)
    _sync_exception_runtime_metadata(handler, exc)
    _register_stream_exception_failure(handler, exc)
    completion_reason = _resolve_stream_exception_completion_reason(handler)
    recovered_tool_results = _resolve_exception_tool_results(
        all_tool_results=all_tool_results,
        messages=messages,
        turn_start_message_index=turn_start_message_index,
    )

    public_error_message = resolve_stream_public_error_message(exc)
    if completion_reason == "provider_timeout":
        logger.info(
            "Stream provider timeout: agent={} error={}",
            getattr(handler.agent, "id", None),
            str(exc),
        )
    else:
        logger.error(
            "Stream execution failed: agent={} error={}",
            getattr(handler.agent, "id", None),
            str(exc),
            exc_info=True,
        )
    view = ensure_stream_generation_view(handler)
    if _should_emit_graceful_exception_done(handler):
        try:
            artifacts = await _build_stream_exception_artifacts(
                handler,
                messages=messages,
                rag_sources=rag_sources,
                output=output,
                total_tokens=total_tokens,
                all_tool_results=recovered_tool_results,
                turn_start_message_index=turn_start_message_index,
                public_error_message=public_error_message,
                completion_reason=completion_reason,
            )
            on_complete_extra: dict[str, Any] | None = None
            if handler.on_complete and not view.runtime.on_complete_called:
                on_complete_extra = await handler._await_on_complete_before_done(
                    artifacts.result
                )
                post_done_callback = handler._pop_post_done_callback(on_complete_extra)
                if post_done_callback is not None:
                    handler._schedule_background_callback(post_done_callback)

            for replay_event in artifacts.replay_events:
                yield replay_event
            yield build_done_event(
                handler,
                artifacts=artifacts,
                on_complete_extra=on_complete_extra,
            )
            yield SSEChunkEncoder.done()
            return
        except Exception as graceful_exc:
            logger.warning(
                "Graceful stream exception finalization failed: agent={} error={}",
                getattr(handler.agent, "id", None),
                str(graceful_exc),
                exc_info=True,
            )

    try:
        yield SSEChunkEncoder.encode(
            build_error_event(
                code="STREAM_EXECUTION_ERROR",
                message=public_error_message,
                trace_id=trace_id_var.get() or None,
                debug=build_exception_debug(exc),
                extra={"conversation_id": handler.request.conversation_id},
            )
        )
    except Exception as yield_exc:
        logger.debug(
            "stream_handler error yield skipped (client disconnected?): {}",
            yield_exc,
        )

    if handler.on_complete and not view.runtime.on_complete_called:
        duration_ms = int((time.perf_counter() - handler.start_time) * 1000)
        partial_output = view.output or output
        partial_tokens = view.total_tokens
        if partial_tokens is None:
            partial_tokens = total_tokens
        append_partial_assistant_output(
            messages,
            output=partial_output,
            reasoning_output=view.reasoning_output,
        )
        failed_result = build_terminal_result(
            handler,
            messages=messages,
            rag_sources=rag_sources,
            output=partial_output,
            total_tokens=partial_tokens,
            tool_results=recovered_tool_results,
            duration_ms=duration_ms,
            error=resolve_public_error_message(fallback_message=public_error_message),
            completion_reason=completion_reason,
            interrupted=False,
            include_provider_state=True,
        )
        on_complete_extra = await handler._await_on_complete_before_done(failed_result)
        post_done_callback = handler._pop_post_done_callback(on_complete_extra)
        if post_done_callback is not None:
            handler._schedule_background_callback(post_done_callback)

    try:
        yield SSEChunkEncoder.done()
    except Exception as yield_done_exc:
        logger.debug(
            "stream_handler done yield skipped (client disconnected?): {}",
            yield_done_exc,
        )


async def _handle_stream_base_exception(
    handler: Any,
    *,
    exc: BaseException,
    executor_task: asyncio.Task[Any] | None,
    messages: list[Any],
    rag_sources: list[dict[str, Any]] | None,
    output: str,
    total_tokens: int,
    all_tool_results: list[Any],
    logger: Any,
) -> AsyncIterator[str]:
    await _cancel_executor_task(executor_task)
    logger.error(
        "Stream BaseException: agent={} type={} error={}",
        getattr(handler.agent, "id", None),
        type(exc).__name__,
        str(exc),
        exc_info=True,
    )
    handler._update_turn_progress(interrupted_stage=handler._interrupted_stage)

    view = ensure_stream_generation_view(handler)
    if handler.on_complete and not view.runtime.on_complete_called:
        duration_ms = int((time.perf_counter() - handler.start_time) * 1000)
        partial_output = view.output or output
        partial_tokens = view.total_tokens
        if partial_tokens is None:
            partial_tokens = total_tokens
        append_partial_assistant_output(
            messages,
            output=partial_output,
            reasoning_output=view.reasoning_output,
        )
        interrupted_result = build_terminal_result(
            handler,
            messages=messages,
            rag_sources=rag_sources,
            output=partial_output,
            total_tokens=partial_tokens,
            tool_results=all_tool_results,
            duration_ms=duration_ms,
            error=resolve_public_error_message(
                fallback_message="Execution interrupted",
            ),
            completion_reason="interrupted",
            interrupted=True,
            include_provider_state=False,
        )
        handler._schedule_on_complete(interrupted_result)

    if False:  # pragma: no cover - keep async-generator contract explicit
        yield ""


async def _handle_stream_cancelled_exception(
    handler: Any,
    *,
    exc: BaseException,
    executor_task: asyncio.Task[Any] | None,
    messages: list[Any],
    rag_sources: list[dict[str, Any]] | None,
    output: str,
    total_tokens: int,
    all_tool_results: list[Any],
    turn_start_message_index: int,
    logger: Any,
) -> AsyncIterator[str]:
    await _cancel_executor_task(executor_task)
    _sync_exception_runtime_metadata(handler, exc)
    _register_stream_exception_failure(handler, exc)
    completion_reason = _resolve_stream_exception_completion_reason(handler)
    transport_disconnect = _is_transport_disconnect_cancellation(exc)
    recovered_tool_results = _resolve_exception_tool_results(
        all_tool_results=all_tool_results,
        messages=messages,
        turn_start_message_index=turn_start_message_index,
    )
    if transport_disconnect:
        logger.info(
            "Stream cancelled after client disconnect: agent={} error={}",
            getattr(handler.agent, "id", None),
            str(exc),
        )
    elif completion_reason == "provider_timeout":
        logger.info(
            "Stream cancelled after provider timeout: agent={} error={}",
            getattr(handler.agent, "id", None),
            str(exc),
        )
    else:
        logger.warning(
            "Stream cancelled: agent={} error={}",
            getattr(handler.agent, "id", None),
            str(exc),
            exc_info=True,
        )
    handler._update_turn_progress(interrupted_stage=handler._interrupted_stage)

    view = ensure_stream_generation_view(handler)
    duration_ms = int((time.perf_counter() - handler.start_time) * 1000)
    partial_output = str(view.output or output or "").strip()
    public_error_message = _resolve_completion_reason_public_error_message(
        completion_reason=completion_reason,
        fallback_message=resolve_stream_public_error_message(exc),
    )
    if not partial_output and not transport_disconnect:
        partial_output = public_error_message
        if partial_output:
            for chunk in handler._chunk_text_for_streaming(partial_output):
                try:
                    yield SSEChunkEncoder.encode({"event": "message", "delta": chunk})
                except Exception as yield_exc:
                    logger.debug(
                        "stream_handler interruption message yield skipped: {}",
                        yield_exc,
                    )
                    break
    elif (
        not transport_disconnect
        and
        completion_reason != "interrupted"
        and public_error_message
        and public_error_message not in partial_output
    ):
        interruption_suffix = f"\n\n{public_error_message}"
        partial_output = f"{partial_output}{interruption_suffix}"
        for chunk in handler._chunk_text_for_streaming(interruption_suffix):
            try:
                yield SSEChunkEncoder.encode({"event": "message", "delta": chunk})
            except Exception as yield_exc:
                logger.debug(
                    "stream_handler interruption suffix yield skipped: {}",
                    yield_exc,
                )
                break

    partial_tokens = view.total_tokens
    if partial_tokens is None:
        partial_tokens = total_tokens
    append_partial_assistant_output(
        messages,
        output=partial_output,
        reasoning_output=view.reasoning_output,
    )
    interrupted_result = build_terminal_result(
        handler,
        messages=messages,
        rag_sources=rag_sources,
        output=partial_output,
        total_tokens=partial_tokens,
        tool_results=recovered_tool_results,
        duration_ms=duration_ms,
        error=public_error_message or resolve_public_error_message(exc),
        completion_reason=completion_reason,
        interrupted=True,
        include_provider_state=completion_reason != "interrupted",
    )
    if transport_disconnect:
        _mark_transport_disconnect_result(interrupted_result)
    on_complete_extra = None
    if handler.on_complete and not view.runtime.on_complete_called:
        on_complete_extra = await handler._await_on_complete_before_done(
            interrupted_result
        )
        post_done_callback = handler._pop_post_done_callback(on_complete_extra)
        if post_done_callback is not None:
            handler._schedule_background_callback(post_done_callback)

    try:
        yield build_done_event(
            handler,
            artifacts=StreamFinalizationArtifacts(
                result=interrupted_result,
                diagnostics_payload=dict(interrupted_result.diagnostics or {}),
                response_metadata={},
                resolved_protocol_path=str(
                    (interrupted_result.turn_record or {}).get("protocol_path") or ""
                ).strip(),
            ),
            on_complete_extra=on_complete_extra,
        )
    except Exception as yield_exc:
        logger.debug(
            "stream_handler cancelled done event yield skipped: {}",
            yield_exc,
        )

    try:
        yield SSEChunkEncoder.done()
    except Exception as yield_done_exc:
        logger.debug(
            "stream_handler cancelled done yield skipped (client disconnected?): {}",
            yield_done_exc,
        )


async def run_stream_execution(
    handler: Any,
    *,
    logger: Any,
) -> AsyncIterator[str]:
    messages = handler.prep.messages
    rag_sources = handler.prep.rag_sources
    optimize_event = handler.prep.optimize_event
    turn_start_message_index = len(messages)

    total_tokens = 0
    all_tool_results: list[Any] = []
    output = ""
    executor_task: asyncio.Task[Any] | None = None
    reset_stream_state(handler)

    try:
        handler._interrupted_stage = "stream_generating"
        for initial_event in build_initial_events(
            handler,
            optimize_event=optimize_event,
        ):
            yield initial_event

        executor_task = asyncio.create_task(handler._run_with_turn_executor())
        async for queued_event in drain_runtime_events(
            handler,
            executor_task=executor_task,
        ):
            yield queued_event

        turn_execution = await executor_task
        output = turn_execution.output
        total_tokens = turn_execution.total_tokens
        all_tool_results = list(turn_execution.tool_results)
        artifacts = finalize_successful_turn(
            handler,
            messages=messages,
            rag_sources=rag_sources,
            turn_start_message_index=turn_start_message_index,
            turn_execution=turn_execution,
            logger=logger,
        )
        _hydrate_artifacts_turn_flow_from_canonical_tool_calls(artifacts)
        for immediate_event in artifacts.immediate_events:
            yield immediate_event
        for replay_event in artifacts.replay_events:
            yield replay_event

        on_complete_extra = await handler._await_on_complete_before_done(artifacts.result)
        post_done_callback = handler._pop_post_done_callback(on_complete_extra)
        if post_done_callback is not None:
            handler._schedule_background_callback(post_done_callback)
        yield build_done_event(
            handler,
            artifacts=artifacts,
            on_complete_extra=on_complete_extra,
        )
        yield SSEChunkEncoder.done()

    except Exception as exc:
        async for event in _handle_stream_exception(
            handler,
            exc=exc,
            executor_task=executor_task,
            messages=messages,
            rag_sources=rag_sources,
            output=output,
            total_tokens=total_tokens,
            all_tool_results=all_tool_results,
            turn_start_message_index=turn_start_message_index,
            logger=logger,
        ):
            yield event

    except BaseException as exc:
        if _is_cancelled_base_exception(exc):
            current_task = asyncio.current_task()
            if isinstance(exc, asyncio.CancelledError) and current_task is not None and hasattr(
                current_task,
                "uncancel",
            ):
                with suppress(Exception):
                    current_task.uncancel()
            async for event in _handle_stream_cancelled_exception(
                handler,
                exc=exc,
                executor_task=executor_task,
                messages=messages,
                rag_sources=rag_sources,
                output=output,
                total_tokens=total_tokens,
                all_tool_results=all_tool_results,
                turn_start_message_index=turn_start_message_index,
                logger=logger,
            ):
                yield event
            return
        async for event in _handle_stream_base_exception(
            handler,
            exc=exc,
            executor_task=executor_task,
            messages=messages,
            rag_sources=rag_sources,
            output=output,
            total_tokens=total_tokens,
            all_tool_results=all_tool_results,
            logger=logger,
        ):
            yield event
        raise


__all__ = ["StreamIOAdapter", "run_stream_execution"]
