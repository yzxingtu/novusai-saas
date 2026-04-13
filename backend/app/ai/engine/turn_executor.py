"""Unified turn execution loop for streaming and non-streaming flows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage, ChatResponse

from .execution_state_machine import ExecutionStateMachine
from .recovery_manager import RecoveryManager
from .turn_executor_completion import (
    completed_tool_intent_families as _completed_tool_intent_families_impl,
)
from .turn_executor_completion import (
    finalize_turn_execution as _finalize_turn_execution_impl,
)
from .turn_executor_completion import (
    response_has_visible_content as _response_has_visible_content_impl,
)
from .turn_executor_events import (
    emit_round_started as _emit_round_started_impl,
)
from .turn_executor_helpers import (
    active_intent as _active_intent_impl,
)
from .turn_executor_helpers import (
    current_turn_messages as _current_turn_messages_impl,
)
from .turn_executor_helpers import (
    current_turn_start_index as _current_turn_start_index_impl,
)
from .turn_executor_rounds import (
    run_initial_round as _run_initial_round_impl,
)
from .turn_executor_rounds import (
    run_intent_retry_loop as _run_intent_retry_loop_impl,
)
from .turn_executor_rounds import (
    run_post_tool_follow_up_round as _run_post_tool_follow_up_round_impl,
)
from .turn_executor_tool_batch import (
    maybe_retry_web_research_contract as _maybe_retry_web_research_contract_impl,
)
from .turn_executor_tool_batch import (
    run_contract_retry_round as _run_contract_retry_round_impl,
)
from .turn_executor_tool_batch import (
    run_tool_batch_or_update_intents as _run_tool_batch_or_update_intents_impl,
)
from .types import ToolUsePolicy


@dataclass
class ModelRoundResult:
    """Result produced by one model call round."""

    response: Any | None
    total_tokens: int = 0
    completion_tokens_used: int = 0
    # True when the provider ran native web search (Responses API) and the
    # response text was generated from those inline results.
    native_search_observed: bool = False


@dataclass
class ToolBatchResult:
    """Result produced by handling one batch of tool calls."""

    response: Any | None
    tool_results: list[Any] = field(default_factory=list)
    total_tokens: int = 0
    completion_tokens_used: int = 0


@dataclass
class TurnExecutionResult:
    """Unified execution output for sync/stream adapters."""

    output: str
    total_tokens: int
    completion_tokens_used: int
    tool_results: list[Any]
    response: Any | None
    partial: bool
    paused_for_consent: bool
    completion_reason: str
    final_output_source: Literal[
        "assistant",
        "tool_evidence_completed",
        "partial_output",
        "budget_fallback",
    ]
    action_buttons: list[dict[str, Any]] | None = None


class TurnIOAdapter(Protocol):
    """Transport/helper adapter; execution loop remains in TurnExecutor."""

    async def call_llm(
        self,
        *,
        messages: list[Any],
        tools: list[Any] | None,
        tool_use_policy: Any,
        **kwargs: Any,
    ) -> ModelRoundResult: ...

    async def handle_tool_calls(
        self,
        *,
        response: Any,
        tools: list[Any],
        messages: list[Any],
        **kwargs: Any,
    ) -> ToolBatchResult: ...

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
    ) -> tuple[str, int, int]: ...

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
    ) -> tuple[str, int, int]: ...

    def should_retry_tool_contract_breach(
        self,
        *,
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[Any],
        input_variables: dict[str, Any] | None,
    ) -> tuple[bool, ToolUsePolicy | None, str]: ...

    def should_retry_web_research_contract_breach(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[Any],
        input_variables: dict[str, Any] | None,
        continuation: Any,
    ) -> tuple[bool, ToolUsePolicy | None, str]: ...

    def analyze_post_tool_contract_breach(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[Any],
        input_variables: dict[str, Any] | None,
    ) -> tuple[str | None, ToolUsePolicy | None, dict[str, Any]]: ...

    def restrict_tools_to_names(
        self,
        tools: list[Any],
        allowed_tool_names: list[str] | None,
    ) -> list[Any]: ...

    def log_tool_contract_diagnostics(
        self,
        *,
        agent: Any,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        tools: list[Any],
        policy: ToolUsePolicy,
        conversation_id: int | None,
        breach_type: str,
        retry_result: str,
        continuation: Any,
    ) -> None: ...

    async def emit_chunk(self, text: str) -> None: ...


class TurnExecutor:
    """State-machine-driven execution entrypoint shared by sync/stream paths."""

    @staticmethod
    def _scope_tools_to_active_intent(
        *,
        state: ExecutionStateMachine,
        tools: list[Any],
        policy: ToolUsePolicy | None,
        io: TurnIOAdapter,
    ) -> tuple[list[Any], ToolUsePolicy | None, Any | None]:
        active_intent = _active_intent_impl(state)
        if active_intent is None or policy is None:
            return list(tools), policy, active_intent

        allowed_tool_names = list(
            active_intent.allowed_tool_names or policy.allowed_tool_names or []
        )
        if not allowed_tool_names:
            return list(tools), policy, active_intent

        scoped_tools = list(io.restrict_tools_to_names(list(tools), allowed_tool_names))
        if not scoped_tools:
            return list(tools), policy, active_intent

        scoped_tool_names = [tool.name for tool in scoped_tools]
        if scoped_tool_names == list(policy.allowed_tool_names or []):
            return scoped_tools, policy, active_intent

        return (
            scoped_tools,
            ToolUsePolicy(
                family=active_intent.family or policy.family,
                mode=policy.mode,
                allowed_tool_names=scoped_tool_names,
                retry_on_contract_breach=policy.retry_on_contract_breach,
                reason=policy.reason or f"intent:{active_intent.kind}",
            ),
            active_intent,
        )

    @staticmethod
    async def run(
        *,
        state: ExecutionStateMachine,
        io: TurnIOAdapter,
        prep: Any,
        request: Any,
        agent: Any,
    ) -> TurnExecutionResult:
        """Run one turn using a shared orchestration loop (sync path ready)."""
        messages: list[ChatMessage] = prep.messages
        current_turn_start_index = _current_turn_start_index_impl(messages)
        tools = list(prep.tools or [])
        active_policy = prep.tool_use_policy
        active_tools, active_policy, active_intent = (
            TurnExecutor._scope_tools_to_active_intent(
                state=state,
                tools=tools,
                policy=active_policy,
                io=io,
            )
        )
        completion_tokens_used = 0
        total_tokens = 0
        response: ChatResponse | None = None
        tool_results: list[ToolResult] = []
        decision = None
        ran_post_tool_follow_up = False

        def current_turn_messages() -> list[ChatMessage]:
            return _current_turn_messages_impl(
                messages,
                start_index=current_turn_start_index,
            )

        response, total_tokens, completion_tokens_used = (
            await _run_initial_round_impl(
                state=state,
                io=io,
                intent=active_intent,
                messages=messages,
                tools=active_tools or None,
                tool_use_policy=active_policy,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
                emit_round_started=_emit_round_started_impl,
            )
        )

        response, tool_results, total_tokens, completion_tokens_used = (
            await _run_tool_batch_or_update_intents_impl(
                state=state,
                io=io,
                intent=active_intent,
                response=response,
                tools=active_tools,
                messages=messages,
                turn_messages=current_turn_messages(),
                tool_use_policy=active_policy,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
            )
        )

        (
            response,
            tool_results,
            total_tokens,
            completion_tokens_used,
            active_policy,
            active_tools,
        ) = await _run_contract_retry_round_impl(
            state=state,
            io=io,
            agent=agent,
            request=request,
            prep=prep,
            messages=messages,
            turn_messages=current_turn_messages(),
            response=response,
            active_policy=active_policy,
            active_intent=active_intent,
            active_tools=active_tools,
            tools=tools,
            tool_results=tool_results,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            emit_round_started=_emit_round_started_impl,
        )

        (
            response,
            tool_results,
            total_tokens,
            completion_tokens_used,
            decision,
        ) = await _run_intent_retry_loop_impl(
            state=state,
            io=io,
            prep=prep,
            request=request,
            agent=agent,
            messages=messages,
            start_index=current_turn_start_index,
            tools=tools,
            response=response,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            tool_results=tool_results,
            emit_round_started=_emit_round_started_impl,
        )

        if (
            decision is None
            and response is not None
            and tool_results
            and not bool(getattr(response, "tool_calls", None))
        ):
            (
                response,
                total_tokens,
                completion_tokens_used,
                retried_web_research,
                active_policy,
            ) = await _maybe_retry_web_research_contract_impl(
                state=state,
                io=io,
                agent=agent,
                request=request,
                prep=prep,
                messages=messages,
                response=response,
                active_policy=active_policy,
                active_tools=active_tools,
                tools=tools,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
                emit_round_started=_emit_round_started_impl,
            )
            if retried_web_research:
                ran_post_tool_follow_up = True

        if (
            decision is None
            and tool_results
            and _active_intent_impl(state) is None
            and not _response_has_visible_content_impl(response)
            and not bool(getattr(response, "tool_calls", None))
            and "web_research" not in _completed_tool_intent_families_impl(state)
        ):
            ran_post_tool_follow_up = True
            response, total_tokens, completion_tokens_used = (
                await _run_post_tool_follow_up_round_impl(
                    state=state,
                    io=io,
                    messages=messages,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                    emit_round_started=_emit_round_started_impl,
                )
            )

        (
            output,
            partial,
            paused_for_consent,
            completion_reason,
            final_output_source,
            total_tokens,
            completion_tokens_used,
            response,
        ) = await _finalize_turn_execution_impl(
            state=state,
            io=io,
            messages=messages,
            response=response,
            decision=decision,
            tool_results=tool_results,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            ran_post_tool_follow_up=ran_post_tool_follow_up,
            emit_round_started=_emit_round_started_impl,
        )

        return TurnExecutionResult(
            output=str(output or ""),
            total_tokens=int(total_tokens or 0),
            completion_tokens_used=int(completion_tokens_used or 0),
            tool_results=tool_results,
            response=response,
            partial=partial,
            paused_for_consent=paused_for_consent,
            completion_reason=completion_reason,
            final_output_source=final_output_source,
            action_buttons=None,
        )


__all__ = [
    "ModelRoundResult",
    "ToolBatchResult",
    "TurnExecutionResult",
    "TurnIOAdapter",
    "TurnExecutor",
]
