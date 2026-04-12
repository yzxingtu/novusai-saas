"""Unified turn execution loop for streaming and non-streaming flows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage, ChatResponse

from .execution_state_machine import ExecutionStateMachine
from .recovery_manager import RecoveryManager
from .tool_execution_helpers import (
    register_tool_failures as _register_tool_failures_impl,
)
from .tool_execution_helpers import (
    synthesize_tool_results_from_calls as _synthesize_tool_results_from_calls_impl,
)
from .turn_executor_completion import (
    completed_tool_intent_families as _completed_tool_intent_families_impl,
)
from .turn_executor_completion import (
    latest_auto_fetch_gate_reason as _latest_auto_fetch_gate_reason_impl,
)
from .turn_executor_completion import (
    post_tool_completion_state as _post_tool_completion_state_impl,
)
from .turn_executor_completion import (
    response_has_visible_content as _response_has_visible_content_impl,
)
from .turn_executor_completion import (
    should_complete_from_budgeted_web_research_evidence as _should_complete_from_budgeted_web_research_evidence_impl,
)
from .turn_executor_contracts import (
    constrain_retry_policy_to_active_intent as _constrain_retry_policy_to_active_intent_impl,
)
from .turn_executor_contracts import (
    record_contract_breach as _record_contract_breach_impl,
)
from .turn_executor_contracts import (
    suppress_contract_placeholder_response as _suppress_contract_placeholder_response_impl,
)
from .turn_executor_events import (
    emit_round_started as _emit_round_started_impl,
)
from .turn_executor_helpers import (
    active_intent as _active_intent_impl,
)
from .turn_executor_helpers import (
    assistant_tool_round_count as _assistant_tool_round_count_impl,
)
from .turn_executor_helpers import (
    current_turn_messages as _current_turn_messages_impl,
)
from .turn_executor_helpers import (
    current_turn_start_index as _current_turn_start_index_impl,
)
from .turn_executor_helpers import (
    register_tool_round_delta as _register_tool_round_delta_impl,
)
from .turn_executor_rounds import (
    intent_requires_clarification as _intent_requires_clarification_impl,
)
from .turn_executor_rounds import (
    run_missing_args_clarification as _run_missing_args_clarification_impl,
)
from .turn_executor_rounds import (
    run_post_tool_follow_up_round as _run_post_tool_follow_up_round_impl,
)
from .turn_executor_tool_batch import (
    build_shortcircuit_fallback_response as _build_shortcircuit_fallback_response_impl,
)
from .turn_executor_tool_batch import (
    execute_tool_batch as _execute_tool_batch_impl,
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

        initial_budget_exit = state.budget_exit_reason()
        if initial_budget_exit:
            state.register_provider_failure(
                kind="budget_exit",
                event={"kind": "budget_exit", "reason": initial_budget_exit},
            )
            response = ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                total_tokens=0,
                output_tokens=0,
            )
        elif _intent_requires_clarification_impl(active_intent):
            response, total_tokens, completion_tokens_used = (
                await _run_missing_args_clarification_impl(
                    state=state,
                    io=io,
                    intent=active_intent,
                    messages=messages,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                    emit_round_started=_emit_round_started_impl,
                )
            )
        else:
            model_round = await io.call_llm(
                messages=messages,
                tools=active_tools or None,
                tool_use_policy=active_policy,
            )
            response = model_round.response
            total_tokens = int(model_round.total_tokens or 0)
            completion_tokens_used = int(model_round.completion_tokens_used or 0)
            state.register_completion_tokens(completion_tokens_used)
            # Native Responses API search produced visible content — mark
            # web_research intents complete so the orchestrator skips retry.
            if (
                getattr(model_round, "native_search_observed", False)
                and _response_has_visible_content_impl(response)
                and state.intent_plan
            ):
                state.intent_plan = RecoveryManager.complete_native_search_intents(
                    state.intent_plan
                )

        if getattr(response, "tool_calls", None) and active_tools:
            response, tool_results, total_tokens, completion_tokens_used = (
                await _execute_tool_batch_impl(
                    state=state,
                    io=io,
                    response=response,
                    tools=active_tools,
                    messages=messages,
                    turn_messages=current_turn_messages(),
                    tool_use_policy=active_policy,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                )
            )
        elif active_tools:
            fallback_response = _build_shortcircuit_fallback_response_impl(
                intent=active_intent,
                response=response,
                tools=active_tools,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
            )
            if fallback_response is not None:
                response, tool_results, total_tokens, completion_tokens_used = (
                    await _execute_tool_batch_impl(
                        state=state,
                        io=io,
                        response=fallback_response,
                        tools=active_tools,
                        messages=messages,
                        turn_messages=current_turn_messages(),
                        tool_use_policy=active_policy,
                        total_tokens=total_tokens,
                        completion_tokens_used=completion_tokens_used,
                    )
                )
        elif state.intent_plan:
            state.intent_plan = RecoveryManager.update_intent_statuses(
                state.intent_plan,
                messages=messages,
                turn_messages=current_turn_messages(),
                tool_results=[],
            )

        contract_tools = list(active_tools or prep.all_tools or tools)
        if (
            active_policy is not None
            and active_policy.retry_on_contract_breach
            and contract_tools
            and not tool_results
        ):
            should_retry = False
            retry_policy: ToolUsePolicy | None = None
            breach_type: str | None = None
            non_intent_breach_type: str | None = None

            if state.intent_plan:
                breach_type, retry_policy, breach_diagnostics = (
                    io.analyze_post_tool_contract_breach(
                        messages=messages,
                        response=response,
                        current_policy=active_policy,
                        tools=contract_tools,
                        input_variables=request.input_variables,
                    )
                )
                if breach_type:
                    _record_contract_breach_impl(
                        state,
                        breach_type=breach_type,
                        diagnostics=breach_diagnostics,
                    )
                    response = _suppress_contract_placeholder_response_impl(
                        response,
                    )
                if retry_policy is not None:
                    retry_policy = _constrain_retry_policy_to_active_intent_impl(
                        retry_policy=retry_policy,
                        breach_type=breach_type,
                        active_intent=active_intent,
                        current_policy=active_policy,
                    )
                    should_retry = True
            else:
                should_retry, retry_policy, _breach_response_text = (
                    io.should_retry_tool_contract_breach(
                        response=response,
                        current_policy=active_policy,
                        tools=contract_tools,
                        input_variables=request.input_variables,
                    )
                )
                if not should_retry:
                    should_retry, retry_policy, _breach_response_text = (
                        io.should_retry_web_research_contract_breach(
                            messages=messages,
                            response=response,
                            current_policy=active_policy,
                            tools=contract_tools,
                            input_variables=request.input_variables,
                            continuation=prep.continuation_context,
                        )
                    )
                if should_retry and retry_policy is not None:
                    non_intent_breach_type = (
                        retry_policy.reason or "tool_contract_breach"
                    )
            if should_retry and retry_policy is not None:
                if non_intent_breach_type:
                    _record_contract_breach_impl(
                        state,
                        breach_type=non_intent_breach_type,
                        diagnostics={},
                    )
                retry_tool_pool = list(prep.all_tools or tools or contract_tools)
                retry_tools = io.restrict_tools_to_names(
                    retry_tool_pool,
                    retry_policy.allowed_tool_names,
                )
                _emit_round_started_impl(
                    state,
                    round_kind="contract_retry",
                    policy=retry_policy,
                    tools=retry_tools,
                    reason=retry_policy.reason or "contract_retry",
                )
                io.log_tool_contract_diagnostics(
                    agent=agent,
                    messages=messages,
                    response=response,
                    tools=retry_tool_pool,
                    policy=retry_policy,
                    conversation_id=request.conversation_id,
                    breach_type=retry_policy.reason or "contract_breach",
                    retry_result="retrying",
                    continuation=prep.continuation_context,
                )
                active_policy = retry_policy
                active_tools = list(retry_tools or [])
                retry_round = await io.call_llm(
                    messages=messages,
                    tools=retry_tools or None,
                    tool_use_policy=retry_policy,
                    breach_retry_result="contract_retry",
                )
                response = retry_round.response
                total_tokens += int(retry_round.total_tokens or 0)
                completion_tokens_used += int(retry_round.completion_tokens_used or 0)
                state.register_completion_tokens(completion_tokens_used)
                if getattr(response, "tool_calls", None) and retry_tools:
                    tool_rounds_before = _assistant_tool_round_count_impl(
                        messages
                    )
                    tool_call_response = response
                    tool_batch = await io.handle_tool_calls(
                        response=response,
                        tools=retry_tools,
                        messages=messages,
                        tool_use_policy=retry_policy,
                        starting_total_tokens=total_tokens,
                        starting_completion_tokens=completion_tokens_used,
                    )
                    response = tool_batch.response
                    extra_tool_results = list(tool_batch.tool_results)
                    total_tokens = int(tool_batch.total_tokens or 0)
                    completion_tokens_used = int(
                        tool_batch.completion_tokens_used or 0
                    )
                    if not extra_tool_results:
                        extra_tool_results = _synthesize_tool_results_from_calls_impl(
                            getattr(tool_call_response, "tool_calls", None),
                            skip_unresolved_interactions=True,
                        )
                    tool_results.extend(extra_tool_results)
                    if state.intent_plan and retry_policy.allowed_tool_names:
                        for intent in state.intent_plan:
                            if (
                                intent.status not in {"completed", "failed", "skipped"}
                                and not intent.allowed_tool_names
                                and (
                                    retry_policy.family == "none"
                                    or intent.family == retry_policy.family
                                )
                            ):
                                intent.allowed_tool_names = list(
                                    retry_policy.allowed_tool_names
                                )
                    _register_tool_round_delta_impl(
                        state,
                        before_count=tool_rounds_before,
                        messages=messages,
                    )
                    state.register_tool_results(
                        messages=messages,
                        turn_messages=current_turn_messages(),
                        tool_results=extra_tool_results,
                    )
                    state.register_completion_tokens(completion_tokens_used)
                    _register_tool_failures_impl(state, extra_tool_results)
                elif response is not None:
                    response = _suppress_contract_placeholder_response_impl(
                        response,
                    )
                    io.log_tool_contract_diagnostics(
                        agent=agent,
                        messages=messages,
                        response=response,
                        tools=retry_tools,
                        policy=retry_policy,
                        conversation_id=request.conversation_id,
                        breach_type=retry_policy.reason or "contract_breach",
                        retry_result="failed",
                        continuation=prep.continuation_context,
                    )
                elif state.intent_plan:
                    state.intent_plan = RecoveryManager.update_intent_statuses(
                        state.intent_plan,
                        messages=messages,
                        turn_messages=current_turn_messages(),
                        tool_results=[],
                    )

        budget_exit_reason = state.budget_exit_reason()
        if budget_exit_reason:
            state.register_provider_failure(
                kind="budget_exit",
                event={"kind": "budget_exit", "reason": budget_exit_reason},
            )

        decision = RecoveryManager.decide(
            state.intent_plan,
            budget=state.budget,
            provider_failure_kind=state.provider_failure_kind,
        )
        while decision is not None and decision.action == "retry_intent":
            retry_intent = next(
                (
                    intent
                    for intent in state.intent_plan
                    if intent.intent_id == decision.target_intent_id
                ),
                None,
            )
            if _intent_requires_clarification_impl(retry_intent):
                response, total_tokens, completion_tokens_used = (
                    await _run_missing_args_clarification_impl(
                        state=state,
                        io=io,
                        intent=retry_intent,
                        messages=messages,
                        total_tokens=total_tokens,
                        completion_tokens_used=completion_tokens_used,
                        emit_round_started=_emit_round_started_impl,
                    )
                )
                decision = RecoveryManager.decide(
                    state.intent_plan,
                    budget=state.budget,
                    provider_failure_kind=state.provider_failure_kind,
                )
                continue
            state.register_retry(decision)
            messages.append(
                RecoveryManager.build_recovery_message(
                    decision=decision,
                    intents=state.intent_plan,
                )
            )
            retry_tools = io.restrict_tools_to_names(
                prep.all_tools or tools,
                decision.allowed_tool_names,
            )
            retry_policy = ToolUsePolicy(
                family=decision.retry_family or prep.tool_use_policy.family,
                mode="required",
                allowed_tool_names=decision.allowed_tool_names
                or [tool.name for tool in retry_tools],
                retry_on_contract_breach=False,
                reason=decision.reason,
            )
            _emit_round_started_impl(
                state,
                round_kind="intent_retry",
                policy=retry_policy,
                tools=retry_tools,
                intent=retry_intent,
                reason=decision.reason or "intent_retry",
            )
            if retry_policy.mode == "required" and retry_tools:
                io.log_tool_contract_diagnostics(
                    agent=agent,
                    messages=messages,
                    response=response,
                    tools=retry_tools,
                    policy=retry_policy,
                    conversation_id=request.conversation_id,
                    breach_type=decision.reason or "intent_retry",
                    retry_result="retrying",
                    continuation=prep.continuation_context,
                )
            retry_round = await io.call_llm(
                messages=messages,
                tools=retry_tools or None,
                tool_use_policy=retry_policy,
                breach_retry_result="intent_retry",
            )
            response = retry_round.response
            total_tokens += int(retry_round.total_tokens or 0)
            completion_tokens_used += int(retry_round.completion_tokens_used or 0)
            state.register_completion_tokens(completion_tokens_used)
            if getattr(response, "tool_calls", None) and retry_tools:
                (
                    response,
                    extra_tool_results,
                    total_tokens,
                    completion_tokens_used,
                ) = await _execute_tool_batch_impl(
                    state=state,
                    io=io,
                    response=response,
                    tools=retry_tools,
                    messages=messages,
                    turn_messages=current_turn_messages(),
                    tool_use_policy=retry_policy,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                )
                tool_results.extend(extra_tool_results)
            elif retry_tools:
                fallback_response = _build_shortcircuit_fallback_response_impl(
                    intent=retry_intent,
                    response=response,
                    tools=retry_tools,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                )
                if fallback_response is not None:
                    (
                        response,
                        extra_tool_results,
                        total_tokens,
                        completion_tokens_used,
                    ) = await _execute_tool_batch_impl(
                        state=state,
                        io=io,
                        response=fallback_response,
                        tools=retry_tools,
                        messages=messages,
                        turn_messages=current_turn_messages(),
                        tool_use_policy=retry_policy,
                        total_tokens=total_tokens,
                        completion_tokens_used=completion_tokens_used,
                    )
                    tool_results.extend(extra_tool_results)
                    decision = RecoveryManager.decide(
                        state.intent_plan,
                        budget=state.budget,
                        provider_failure_kind=state.provider_failure_kind,
                    )
                    continue
            if state.intent_plan and not getattr(response, "tool_calls", None):
                state.intent_plan = RecoveryManager.update_intent_statuses(
                    state.intent_plan,
                    messages=messages,
                    turn_messages=current_turn_messages(),
                    tool_results=[],
                )
                if retry_policy.mode == "required" and retry_tools and response is not None:
                    io.log_tool_contract_diagnostics(
                        agent=agent,
                        messages=messages,
                        response=response,
                        tools=retry_tools,
                        policy=retry_policy,
                        conversation_id=request.conversation_id,
                        breach_type=decision.reason or "intent_retry",
                        retry_result="failed",
                        continuation=prep.continuation_context,
                    )
            budget_exit_reason = state.budget_exit_reason()
            if budget_exit_reason:
                state.register_provider_failure(
                    kind="budget_exit",
                    event={"kind": "budget_exit", "reason": budget_exit_reason},
                )
            decision = RecoveryManager.decide(
                state.intent_plan,
                budget=state.budget,
                provider_failure_kind=state.provider_failure_kind,
            )

        if (
            decision is None
            and response is not None
            and tool_results
            and not bool(getattr(response, "tool_calls", None))
        ):
            should_retry_web_research, web_research_retry_policy, _ = (
                io.should_retry_web_research_contract_breach(
                    messages=messages,
                    response=response,
                    current_policy=active_policy,
                    tools=contract_tools,
                    input_variables=request.input_variables,
                    continuation=prep.continuation_context,
                )
            )
            if (
                should_retry_web_research
                and web_research_retry_policy is not None
                and web_research_retry_policy.mode == "none"
                and not web_research_retry_policy.allowed_tool_names
            ):
                retry_tools: list[Any] = []
                _record_contract_breach_impl(
                    state,
                    breach_type=(
                        web_research_retry_policy.reason
                        or "web_research_contract_breach"
                    ),
                    diagnostics={},
                )
                _emit_round_started_impl(
                    state,
                    round_kind="contract_retry",
                    policy=web_research_retry_policy,
                    tools=retry_tools,
                    reason=(
                        web_research_retry_policy.reason
                        or "web_research_contract_breach"
                    ),
                )
                io.log_tool_contract_diagnostics(
                    agent=agent,
                    messages=messages,
                    response=response,
                    tools=contract_tools,
                    policy=web_research_retry_policy,
                    conversation_id=request.conversation_id,
                    breach_type=(
                        web_research_retry_policy.reason
                        or "web_research_contract_breach"
                    ),
                    retry_result="retrying",
                    continuation=prep.continuation_context,
                )
                active_policy = web_research_retry_policy
                retry_round = await io.call_llm(
                    messages=messages,
                    tools=retry_tools or None,
                    tool_use_policy=web_research_retry_policy,
                    breach_retry_result="contract_retry",
                )
                response = retry_round.response
                total_tokens += int(retry_round.total_tokens or 0)
                completion_tokens_used += int(
                    retry_round.completion_tokens_used or 0
                )
                state.register_completion_tokens(completion_tokens_used)
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

        if response is None:
            response = ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                total_tokens=0,
                output_tokens=0,
            )
        output = response.message.content
        paused_for_consent = bool(
            decision is not None and decision.action == "pause_for_consent"
        )
        partial = bool(decision is not None and decision.action == "return_partial")
        budgeted_web_research_completion_mode: Literal[
            "none",
            "keep_visible_output",
            "replace_with_tool_evidence",
        ] = (
            _should_complete_from_budgeted_web_research_evidence_impl(
                state=state,
                response=response,
                tool_results=tool_results,
                reason=decision.reason or "return_partial",
            )
            if partial and decision is not None
            else "none"
        )
        promote_budget_partial_to_completed = bool(
            partial
            and decision is not None
            and budgeted_web_research_completion_mode != "none"
        )
        replace_budgeted_web_research_output = (
            budgeted_web_research_completion_mode == "replace_with_tool_evidence"
        )
        if decision is not None and (
            decision.action == "pause_for_consent"
            or (decision.action == "return_partial" and not promote_budget_partial_to_completed)
        ):
            state.recovery_history.append(decision)
        completion_reason = "completed"
        final_output_source: Literal[
            "assistant",
            "tool_evidence_completed",
            "partial_output",
            "budget_fallback",
        ] = "assistant"
        if paused_for_consent:
            state.transition("awaiting_consent")
            completion_reason = decision.reason or "pause_for_consent"
            RecoveryManager.ensure_latest_assistant_pending_consent(
                messages,
                RecoveryManager.pending_consent_payload_from_decision(decision),
            )
        elif promote_budget_partial_to_completed:
            partial = False
            state.transition("completed")
            state.preparation_diagnostics["budgeted_web_research_completion_mode"] = (
                budgeted_web_research_completion_mode
            )
            if replace_budgeted_web_research_output and response is not None:
                response.message.content = ""
            # Budget was exceeded during tool-selection thinking, but tool evidence is
            # complete.  Attempt one no-tool synthesis call so the user sees a proper
            # answer instead of raw tool-result text.
            if replace_budgeted_web_research_output and tool_results:
                synthesis_policy = ToolUsePolicy(
                    family="none",
                    mode="none",
                    allowed_tool_names=[],
                    retry_on_contract_breach=False,
                    reason="budget_exceeded_synthesis",
                )
                _emit_round_started_impl(
                    state,
                    round_kind="budget_exceeded_synthesis",
                    policy=synthesis_policy,
                    tools=[],
                    reason="budget_exceeded_synthesis",
                )
                synthesis_round = await io.call_llm(
                    messages=messages,
                    tools=None,
                    tool_use_policy=synthesis_policy,
                    breach_retry_result="budget_exceeded_synthesis",
                )
                synthesis_text = str(
                    getattr(
                        getattr(synthesis_round.response, "message", None),
                        "content",
                        "",
                    ) or ""
                ).strip()
                if synthesis_text:
                    output = synthesis_text
                    total_tokens += int(synthesis_round.total_tokens or 0)
                    completion_tokens_used += int(
                        synthesis_round.completion_tokens_used or 0
                    )
                    state.register_completion_tokens(completion_tokens_used)
                    final_output_source = "assistant"
            if not str(output or "").strip():
                output, total_tokens, completion_tokens_used = (
                    await io.finalize_completed_output(
                        messages=messages,
                        response=response,
                        state=state,
                        tool_results=tool_results,
                        reason=decision.reason or "completed",
                        total_tokens=total_tokens,
                        completion_tokens_used=completion_tokens_used,
                    )
                )
                if str(output or "").strip():
                    final_output_source = "tool_evidence_completed"
        elif partial:
            state.transition("partial_exit")
            completion_reason = decision.reason or "return_partial"
            had_visible_output = bool(str(output or "").strip())
            output, total_tokens, completion_tokens_used = (
                await io.finalize_partial_output(
                    messages=messages,
                    response=response,
                    state=state,
                    tool_results=tool_results,
                    reason=completion_reason,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                )
            )
            if (
                not had_visible_output
                and state.provider_failure_kind == "budget_exit"
                and str(output or "").strip()
            ):
                final_output_source = "budget_fallback"
            else:
                final_output_source = "partial_output"
        else:
            state.transition("completed")
            if not str(output or "").strip() and state.intent_plan:
                output, total_tokens, completion_tokens_used = (
                    await io.finalize_completed_output(
                        messages=messages,
                        response=response,
                        state=state,
                        tool_results=tool_results,
                        reason=completion_reason,
                        total_tokens=total_tokens,
                        completion_tokens_used=completion_tokens_used,
                    )
                )
                if str(output or "").strip():
                    if (
                        str(
                            state.preparation_diagnostics.get(
                                "contract_breach_type"
                            )
                            or ""
                        ).strip()
                        and not RecoveryManager.has_completed_output_evidence(
                            state.intent_plan,
                            tool_results=tool_results,
                        )
                    ):
                        final_output_source = "partial_output"
                    else:
                        final_output_source = "tool_evidence_completed"

        state.preparation_diagnostics["final_output_source"] = final_output_source
        state.preparation_diagnostics["post_tool_completion_state"] = (
            _post_tool_completion_state_impl(
                state=state,
                final_output_source=final_output_source,
                ran_post_tool_follow_up=ran_post_tool_follow_up,
            )
        )
        auto_fetch_gate_reason = _latest_auto_fetch_gate_reason_impl(state)
        if auto_fetch_gate_reason:
            state.preparation_diagnostics["auto_fetch_gate_reason"] = (
                auto_fetch_gate_reason
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
