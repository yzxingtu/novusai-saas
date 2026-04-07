"""Unified turn execution loop for streaming and non-streaming flows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage, ChatResponse

from .execution_state_machine import ExecutionStateMachine
from .failure_classifier import FailureClassifier
from .recovery_manager import RecoveryManager
from .types import RecoveryDecision, ToolUsePolicy


@dataclass
class ModelRoundResult:
    """Result produced by one model call round."""

    response: Any | None
    total_tokens: int = 0
    completion_tokens_used: int = 0


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
    def _active_intent(state: ExecutionStateMachine) -> Any | None:
        for intent in state.intent_plan:
            if intent.status in {"completed", "failed", "skipped"}:
                continue
            if intent.family == "none" or not intent.requires_tools:
                continue
            return intent
        return None

    @staticmethod
    def _scope_tools_to_active_intent(
        *,
        state: ExecutionStateMachine,
        tools: list[Any],
        policy: ToolUsePolicy | None,
        io: TurnIOAdapter,
    ) -> tuple[list[Any], ToolUsePolicy | None, Any | None]:
        active_intent = TurnExecutor._active_intent(state)
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
    def _emit_round_started(
        state: ExecutionStateMachine,
        *,
        round_kind: str,
        policy: ToolUsePolicy | None,
        tools: list[Any] | None = None,
        intent: Any | None = None,
        reason: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "round_kind": round_kind,
            "tool_names": [tool.name for tool in (tools or [])],
            "allowed_tool_names": list(
                getattr(policy, "allowed_tool_names", []) or []
            ),
            "tool_use_policy_family": getattr(policy, "family", None),
            "tool_use_policy_mode": getattr(policy, "mode", None),
            "tool_use_policy_reason": (
                reason
                or str(getattr(policy, "reason", "") or "").strip()
                or None
            ),
        }
        if intent is not None:
            payload["intent_id"] = getattr(intent, "intent_id", None)
            payload["intent_kind"] = getattr(intent, "kind", None)
            payload["intent_family"] = getattr(intent, "family", None)
        state.emit_event("turn.round_started", payload)

    @staticmethod
    def _assistant_tool_round_count(messages: list[ChatMessage]) -> int:
        return sum(
            1
            for message in messages
            if message.role == "assistant" and bool(message.tool_calls)
        )

    @staticmethod
    def _register_tool_round_delta(
        state: ExecutionStateMachine,
        *,
        before_count: int,
        messages: list[ChatMessage],
    ) -> None:
        delta = max(0, TurnExecutor._assistant_tool_round_count(messages) - before_count)
        for _round_idx in range(delta):
            state.register_tool_round()

    @staticmethod
    def _register_tool_failures(
        state: ExecutionStateMachine,
        tool_results: list[ToolResult],
    ) -> None:
        tool_failure_kind, tool_failure_events = (
            FailureClassifier.classify_tool_results(tool_results)
        )
        if tool_failure_kind != "none":
            for event in tool_failure_events:
                state.register_provider_failure(kind=tool_failure_kind, event=event)

    @staticmethod
    def _synthesize_tool_results_from_calls(
        tool_calls: list[dict[str, Any]] | None,
    ) -> list[ToolResult]:
        synthesized: list[ToolResult] = []
        for index, tool_call in enumerate(tool_calls or []):
            function_block = tool_call.get("function") or {}
            tool_name = str(
                function_block.get("name") or tool_call.get("name") or ""
            ).strip()
            if not tool_name:
                continue
            tool_call_id = str(tool_call.get("id") or f"synthetic_tool_call_{index}")
            synthesized.append(
                ToolResult(
                    tool_call_id=tool_call_id,
                    name=tool_name,
                    success=True,
                )
            )
        return synthesized

    @staticmethod
    async def _execute_tool_batch(
        *,
        state: ExecutionStateMachine,
        io: TurnIOAdapter,
        response: ChatResponse,
        tools: list[Any],
        messages: list[ChatMessage],
        tool_use_policy: ToolUsePolicy | None,
        total_tokens: int,
        completion_tokens_used: int,
    ) -> tuple[ChatResponse | None, list[ToolResult], int, int]:
        tool_rounds_before = TurnExecutor._assistant_tool_round_count(messages)
        tool_call_response = response
        tool_batch = await io.handle_tool_calls(
            response=response,
            tools=tools,
            messages=messages,
            tool_use_policy=tool_use_policy,
            starting_total_tokens=total_tokens,
            starting_completion_tokens=completion_tokens_used,
        )
        next_response = tool_batch.response
        tool_results = list(tool_batch.tool_results)
        next_total_tokens = int(tool_batch.total_tokens or 0)
        next_completion_tokens = int(tool_batch.completion_tokens_used or 0)
        if not tool_results:
            tool_results = TurnExecutor._synthesize_tool_results_from_calls(
                getattr(tool_call_response, "tool_calls", None)
            )
        TurnExecutor._register_tool_round_delta(
            state,
            before_count=tool_rounds_before,
            messages=messages,
        )
        state.register_tool_results(
            messages=messages,
            tool_results=tool_results,
        )
        state.register_completion_tokens(next_completion_tokens)
        TurnExecutor._register_tool_failures(state, tool_results)
        return next_response, tool_results, next_total_tokens, next_completion_tokens

    @staticmethod
    def _build_shortcircuit_fallback_response(
        *,
        intent: Any | None,
        response: ChatResponse | None,
        tools: list[Any],
        total_tokens: int,
        completion_tokens_used: int,
    ) -> ChatResponse | None:
        if intent is None or not bool(getattr(intent, "shortcircuit", False)):
            return None
        if str(getattr(intent, "kind", "") or "").strip() != "time_query":
            return None

        time_tool = next(
            (tool for tool in tools if str(getattr(tool, "name", "")).strip() == "get_current_time"),
            None,
        )
        if time_tool is None:
            return None

        synthetic_call = [
            {
                "id": f"synthetic_{getattr(intent, 'intent_id', 'intent')}_get_current_time",
                "type": "function",
                "function": {
                    "name": "get_current_time",
                    "arguments": "{}",
                },
            }
        ]
        metadata = dict(getattr(response, "metadata", {}) or {})
        metadata["synthetic_shortcircuit_tool_call"] = True
        metadata["synthetic_shortcircuit_intent_id"] = getattr(intent, "intent_id", None)
        metadata["synthetic_shortcircuit_tool_name"] = "get_current_time"
        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content="",
                tool_calls=synthetic_call,
            ),
            total_tokens=int(total_tokens or getattr(response, "total_tokens", 0) or 0),
            output_tokens=int(
                completion_tokens_used
                or getattr(response, "output_tokens", 0)
                or 0
            ),
            finish_reason="tool_calls",
            tool_calls=synthetic_call,
            metadata=metadata,
        )

    @staticmethod
    def _intent_missing_args(intent: Any | None) -> list[str]:
        metadata = dict(getattr(intent, "metadata", {}) or {}) if intent is not None else {}
        raw_missing_args = metadata.get("missing_args")
        if not isinstance(raw_missing_args, list):
            return []
        return [str(item).strip() for item in raw_missing_args if str(item).strip()]

    @staticmethod
    def _intent_requires_clarification(intent: Any | None) -> bool:
        return bool(
            intent is not None
            and getattr(intent, "allow_text_response", False)
            and TurnExecutor._intent_missing_args(intent)
        )

    @staticmethod
    def _response_has_visible_content(response: ChatResponse | None) -> bool:
        if response is None:
            return False
        return bool(str(response.message.content or "").strip())

    @staticmethod
    def _latest_auto_fetch_gate_reason(state: ExecutionStateMachine) -> str | None:
        for intent in reversed(state.intent_plan):
            metadata = dict(getattr(intent, "metadata", {}) or {})
            reason = str(metadata.get("auto_fetch_gate_reason") or "").strip()
            if reason:
                return reason
        return None

    @staticmethod
    def _completed_tool_intent_families(state: ExecutionStateMachine) -> set[str]:
        families: set[str] = set()
        for intent in state.intent_plan:
            if intent.status != "completed" or not intent.requires_tools:
                continue
            family = str(intent.family or "").strip()
            if family:
                families.add(family)
        return families

    @staticmethod
    def _post_tool_completion_state(
        *,
        state: ExecutionStateMachine,
        final_output_source: str,
        ran_post_tool_follow_up: bool,
    ) -> str:
        if final_output_source == "tool_evidence_completed":
            auto_fetch_gate_reason = TurnExecutor._latest_auto_fetch_gate_reason(state)
            if auto_fetch_gate_reason == "search_no_results_completed":
                return "completed_no_result"
            return "tool_evidence_completed"
        if final_output_source == "partial_output":
            return "partial_output"
        if final_output_source == "budget_fallback":
            return "budget_fallback"
        if ran_post_tool_follow_up:
            return "llm_follow_up"
        return "assistant"

    @staticmethod
    def _record_contract_breach(
        state: ExecutionStateMachine,
        *,
        breach_type: str,
        diagnostics: dict[str, Any],
    ) -> None:
        state.preparation_diagnostics["contract_breach_type"] = breach_type
        if diagnostics.get("unfinished_intents"):
            state.preparation_diagnostics["unfinished_intents"] = list(
                diagnostics.get("unfinished_intents") or []
            )
        if diagnostics.get("leaked_tool_names"):
            state.preparation_diagnostics["leaked_tool_names"] = list(
                diagnostics.get("leaked_tool_names") or []
            )
        if diagnostics.get("tool_leak_detected") is not None:
            state.preparation_diagnostics["tool_leak_detected"] = bool(
                diagnostics.get("tool_leak_detected")
            )
        if diagnostics.get("assistant_claimed_tool_call_without_tool_event") is not None:
            state.preparation_diagnostics[
                "assistant_claimed_tool_call_without_tool_event"
            ] = bool(
                diagnostics.get("assistant_claimed_tool_call_without_tool_event")
            )

    @staticmethod
    def _constrain_retry_policy_to_active_intent(
        *,
        retry_policy: ToolUsePolicy,
        active_intent: Any | None,
        current_policy: ToolUsePolicy | None,
    ) -> ToolUsePolicy:
        if active_intent is None:
            return retry_policy
        allowed_tool_names = list(
            getattr(active_intent, "allowed_tool_names", None)
            or getattr(current_policy, "allowed_tool_names", None)
            or retry_policy.allowed_tool_names
        )
        family = (
            str(getattr(active_intent, "family", "") or "").strip()
            or str(getattr(current_policy, "family", "") or "").strip()
            or retry_policy.family
        )
        return ToolUsePolicy(
            family=family or retry_policy.family,
            mode="required",
            allowed_tool_names=allowed_tool_names,
            retry_on_contract_breach=False,
            reason=retry_policy.reason,
        )

    @staticmethod
    def _suppress_contract_placeholder_response(
        response: ChatResponse | None,
    ) -> ChatResponse | None:
        if response is None:
            return None
        if getattr(response, "tool_calls", None):
            return response
        response.message.content = ""
        return response

    @staticmethod
    async def _run_missing_args_clarification(
        *,
        state: ExecutionStateMachine,
        io: TurnIOAdapter,
        intent: Any,
        messages: list[ChatMessage],
        total_tokens: int,
        completion_tokens_used: int,
    ) -> tuple[ChatResponse | None, int, int]:
        missing_args = TurnExecutor._intent_missing_args(intent)
        decision = RecoveryDecision(
            action="retry_intent",
            target_intent_id=getattr(intent, "intent_id", None),
            retry_family=getattr(intent, "family", None),
            completed_intent_ids=[
                item.intent_id for item in state.intent_plan if item.status == "completed"
            ],
            unfinished_intent_ids=[
                item.intent_id
                for item in state.intent_plan
                if item.status not in {"completed", "skipped"}
            ],
            reason="missing_args_clarification",
            metadata={"missing_args": missing_args},
        )
        state.register_retry(decision)
        messages.append(
            RecoveryManager.build_missing_args_clarification_message(
                decision=decision,
                intents=state.intent_plan,
                missing_args=missing_args,
            )
        )
        clarification_policy = ToolUsePolicy(
            family="none",
            mode="none",
            allowed_tool_names=[],
            retry_on_contract_breach=False,
            reason="missing_args_clarification",
        )
        TurnExecutor._emit_round_started(
            state,
            round_kind="intent_retry",
            policy=clarification_policy,
            tools=[],
            intent=intent,
            reason="missing_args_clarification",
        )
        clarification_round = await io.call_llm(
            messages=messages,
            tools=None,
            tool_use_policy=clarification_policy,
            breach_retry_result="intent_retry",
        )
        response = clarification_round.response
        total_tokens += int(clarification_round.total_tokens or 0)
        completion_tokens_used += int(
            clarification_round.completion_tokens_used or 0
        )
        state.register_completion_tokens(completion_tokens_used)
        intent.status = "completed"
        intent.metadata = dict(getattr(intent, "metadata", {}) or {})
        intent.metadata["clarification_requested"] = True
        return response, total_tokens, completion_tokens_used

    @staticmethod
    async def _run_post_tool_follow_up_round(
        *,
        state: ExecutionStateMachine,
        io: TurnIOAdapter,
        messages: list[ChatMessage],
        total_tokens: int,
        completion_tokens_used: int,
    ) -> tuple[ChatResponse | None, int, int]:
        follow_up_policy = ToolUsePolicy(
            family="none",
            mode="none",
            allowed_tool_names=[],
            retry_on_contract_breach=False,
            reason="post_tool_follow_up",
        )
        TurnExecutor._emit_round_started(
            state,
            round_kind="normal_follow_up_round",
            policy=follow_up_policy,
            tools=[],
            reason="post_tool_follow_up",
        )
        follow_up_round = await io.call_llm(
            messages=messages,
            tools=None,
            tool_use_policy=follow_up_policy,
            breach_retry_result="normal_follow_up_round",
        )
        response = follow_up_round.response
        total_tokens += int(follow_up_round.total_tokens or 0)
        completion_tokens_used += int(follow_up_round.completion_tokens_used or 0)
        state.register_completion_tokens(completion_tokens_used)
        return response, total_tokens, completion_tokens_used

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
        elif TurnExecutor._intent_requires_clarification(active_intent):
            response, total_tokens, completion_tokens_used = (
                await TurnExecutor._run_missing_args_clarification(
                    state=state,
                    io=io,
                    intent=active_intent,
                    messages=messages,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
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

        if getattr(response, "tool_calls", None) and active_tools:
            response, tool_results, total_tokens, completion_tokens_used = (
                await TurnExecutor._execute_tool_batch(
                    state=state,
                    io=io,
                    response=response,
                    tools=active_tools,
                    messages=messages,
                    tool_use_policy=active_policy,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                )
            )
        elif active_tools:
            fallback_response = TurnExecutor._build_shortcircuit_fallback_response(
                intent=active_intent,
                response=response,
                tools=active_tools,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
            )
            if fallback_response is not None:
                response, tool_results, total_tokens, completion_tokens_used = (
                    await TurnExecutor._execute_tool_batch(
                        state=state,
                        io=io,
                        response=fallback_response,
                        tools=active_tools,
                        messages=messages,
                        tool_use_policy=active_policy,
                        total_tokens=total_tokens,
                        completion_tokens_used=completion_tokens_used,
                    )
                )
        elif state.intent_plan:
            state.intent_plan = RecoveryManager.update_intent_statuses(
                state.intent_plan,
                messages=messages,
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
                    TurnExecutor._record_contract_breach(
                        state,
                        breach_type=breach_type,
                        diagnostics=breach_diagnostics,
                    )
                    response = TurnExecutor._suppress_contract_placeholder_response(
                        response,
                    )
                if retry_policy is not None:
                    retry_policy = TurnExecutor._constrain_retry_policy_to_active_intent(
                        retry_policy=retry_policy,
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
                retry_tools = io.restrict_tools_to_names(
                    contract_tools,
                    retry_policy.allowed_tool_names,
                )
                TurnExecutor._emit_round_started(
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
                    tools=contract_tools,
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
                    tool_rounds_before = TurnExecutor._assistant_tool_round_count(
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
                        extra_tool_results = TurnExecutor._synthesize_tool_results_from_calls(
                            getattr(tool_call_response, "tool_calls", None)
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
                    TurnExecutor._register_tool_round_delta(
                        state,
                        before_count=tool_rounds_before,
                        messages=messages,
                    )
                    state.register_tool_results(
                        messages=messages,
                        tool_results=extra_tool_results,
                    )
                    state.register_completion_tokens(completion_tokens_used)
                    TurnExecutor._register_tool_failures(state, extra_tool_results)
                elif response is not None:
                    response = TurnExecutor._suppress_contract_placeholder_response(
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
        retry_limit = int(
            getattr(state.budget, "max_retry_per_intent", 0)
            if state.budget is not None
            else 0
        )
        retry_attempts = 0
        while (
            decision is not None
            and decision.action == "retry_intent"
            and retry_attempts < retry_limit
        ):
            retry_intent = next(
                (
                    intent
                    for intent in state.intent_plan
                    if intent.intent_id == decision.target_intent_id
                ),
                None,
            )
            if TurnExecutor._intent_requires_clarification(retry_intent):
                response, total_tokens, completion_tokens_used = (
                    await TurnExecutor._run_missing_args_clarification(
                        state=state,
                        io=io,
                        intent=retry_intent,
                        messages=messages,
                        total_tokens=total_tokens,
                        completion_tokens_used=completion_tokens_used,
                    )
                )
                decision = RecoveryManager.decide(
                    state.intent_plan,
                    budget=state.budget,
                    provider_failure_kind=state.provider_failure_kind,
                )
                continue
            retry_attempts += 1
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
            TurnExecutor._emit_round_started(
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
                ) = await TurnExecutor._execute_tool_batch(
                    state=state,
                    io=io,
                    response=response,
                    tools=retry_tools,
                    messages=messages,
                    tool_use_policy=retry_policy,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                )
                tool_results.extend(extra_tool_results)
            elif retry_tools:
                fallback_response = TurnExecutor._build_shortcircuit_fallback_response(
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
                    ) = await TurnExecutor._execute_tool_batch(
                        state=state,
                        io=io,
                        response=fallback_response,
                        tools=retry_tools,
                        messages=messages,
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
            and tool_results
            and TurnExecutor._active_intent(state) is None
            and not TurnExecutor._response_has_visible_content(response)
            and not bool(getattr(response, "tool_calls", None))
            and "web_research" not in TurnExecutor._completed_tool_intent_families(state)
        ):
            ran_post_tool_follow_up = True
            response, total_tokens, completion_tokens_used = (
                await TurnExecutor._run_post_tool_follow_up_round(
                    state=state,
                    io=io,
                    messages=messages,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                )
            )

        if response is None:
            response = ChatResponse(
                message=ChatMessage(role="assistant", content=""),
                total_tokens=0,
                output_tokens=0,
            )
        output = response.message.content
        if decision is not None and decision.action in {"pause_for_consent", "return_partial"}:
            state.recovery_history.append(decision)
        paused_for_consent = bool(
            decision is not None and decision.action == "pause_for_consent"
        )
        partial = bool(decision is not None and decision.action == "return_partial")
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
                    final_output_source = "tool_evidence_completed"

        state.preparation_diagnostics["final_output_source"] = final_output_source
        state.preparation_diagnostics["post_tool_completion_state"] = (
            TurnExecutor._post_tool_completion_state(
                state=state,
                final_output_source=final_output_source,
                ran_post_tool_follow_up=ran_post_tool_follow_up,
            )
        )
        auto_fetch_gate_reason = TurnExecutor._latest_auto_fetch_gate_reason(state)
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
