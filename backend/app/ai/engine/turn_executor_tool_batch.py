"""Tool batch helpers for turn execution."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage, ChatResponse

from .execution_state_machine import ExecutionStateMachine
from .page_flow_recovery_helpers import (
    build_page_deterministic_recovery_step_default,
    build_page_no_progress_recovery_default,
)
from .recovery_manager import RecoveryManager
from .tool_execution_helpers import (
    register_tool_failures,
    synthesize_tool_results_from_calls,
)
from .tool_loop_session import (
    project_page_recovery_into_runtime_intent_plan,
)
from .turn_executor_contracts import (
    constrain_retry_policy_to_active_intent,
    record_contract_breach,
    suppress_contract_placeholder_response,
)
from .types import ToolUsePolicy

if TYPE_CHECKING:
    from .turn_executor import TurnIOAdapter

_MAX_SYNTHETIC_PAGE_STEPS = 3


def _assistant_tool_round_count(messages: list[ChatMessage]) -> int:
    return sum(
        1
        for message in messages
        if message.role == "assistant" and bool(message.tool_calls)
    )


def _register_tool_round_delta(
    state: ExecutionStateMachine,
    *,
    before_count: int,
    messages: list[ChatMessage],
) -> None:
    delta = max(0, _assistant_tool_round_count(messages) - before_count)
    for _round_idx in range(delta):
        state.register_tool_round()


def _tool_calls_from_response(response: ChatResponse | None) -> list[dict[str, Any]]:
    if response is None:
        return []
    tool_calls = list(getattr(response, "tool_calls", None) or [])
    if not tool_calls and getattr(response, "message", None) is not None:
        tool_calls = list(getattr(response.message, "tool_calls", None) or [])
    return [tool_call for tool_call in tool_calls if isinstance(tool_call, dict)]


def _tool_call_name(tool_call: dict[str, Any]) -> str:
    function_block = tool_call.get("function")
    if isinstance(function_block, dict):
        return str(function_block.get("name") or "").strip()
    return str(tool_call.get("name") or "").strip()


def _tool_call_arguments_text(tool_call: dict[str, Any]) -> str:
    function_block = tool_call.get("function")
    if not isinstance(function_block, dict):
        return ""
    return str(function_block.get("arguments") or "").strip()


def _synthetic_tool_call_key(tool_call: dict[str, Any]) -> str:
    name = _tool_call_name(tool_call)
    if not name:
        return ""
    return f"{name}:{_tool_call_arguments_text(tool_call)}"


def _issued_synthetic_page_step_keys(state: ExecutionStateMachine) -> list[str]:
    raw_keys = state.preparation_diagnostics.get(
        "issued_deterministic_page_step_keys"
    )
    if isinstance(raw_keys, list):
        return raw_keys
    keys: list[str] = []
    state.preparation_diagnostics["issued_deterministic_page_step_keys"] = keys
    return keys


def _dedupe_synthetic_tool_calls(
    state: ExecutionStateMachine,
    tool_calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    issued_keys = _issued_synthetic_page_step_keys(state)
    issued = {str(key or "").strip() for key in issued_keys if str(key or "").strip()}
    deduped: list[dict[str, Any]] = []
    for tool_call in tool_calls:
        key = _synthetic_tool_call_key(tool_call)
        if not key or key in issued:
            continue
        issued.add(key)
        issued_keys.append(key)
        deduped.append(tool_call)
    return deduped


def _build_synthetic_page_response(
    *,
    base_response: ChatResponse,
    tool_calls: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    total_tokens: int,
    completion_tokens_used: int,
) -> ChatResponse:
    tool_names = [name for call in tool_calls if (name := _tool_call_name(call))]
    metadata = dict(getattr(base_response, "metadata", {}) or {})
    metadata.update(
        {
            "synthetic_page_workflow_recovery": True,
            "synthetic_tool_names": tool_names,
            "page_recovery_diagnostics": diagnostics,
        }
    )
    return ChatResponse(
        message=ChatMessage(
            role="assistant",
            content="",
            tool_calls=tool_calls,
            metadata=metadata,
        ),
        total_tokens=int(total_tokens or getattr(base_response, "total_tokens", 0) or 0),
        output_tokens=int(
            completion_tokens_used or getattr(base_response, "output_tokens", 0) or 0
        ),
        finish_reason="tool_calls",
        tool_calls=tool_calls,
        metadata=metadata,
    )


def _restrict_tools_to_names(
    io: TurnIOAdapter,
    tools: list[Any],
    tool_names: list[str],
) -> list[Any]:
    if not tool_names:
        return list(tools)
    restrict = getattr(io, "restrict_tools_to_names", None)
    if callable(restrict):
        return list(restrict(tools, tool_names))
    allowed = set(tool_names)
    return [
        tool
        for tool in tools
        if str(getattr(tool, "name", "") or "").strip() in allowed
    ]


def _build_deterministic_page_tool_calls(
    *,
    state: ExecutionStateMachine,
    messages: list[ChatMessage],
    tool_calls: list[dict[str, Any]],
    tool_results: list[ToolResult],
    tools: list[Any],
    input_variables: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    synthetic_tool_calls, recovery_diagnostics = (
        build_page_deterministic_recovery_step_default(
            messages=messages,
            tool_calls=tool_calls,
            tool_results=tool_results,
            tools=tools,
            input_variables=input_variables,
        )
    )
    if not synthetic_tool_calls:
        return [], {}
    deduped_calls = _dedupe_synthetic_tool_calls(state, synthetic_tool_calls)
    if not deduped_calls:
        return [], {}
    synthetic_tool_names = [
        name for tool_call in deduped_calls if (name := _tool_call_name(tool_call))
    ]
    state.preparation_diagnostics["deterministic_page_recovery"] = dict(
        recovery_diagnostics
    )
    state.preparation_diagnostics["deterministic_page_recovery_tool_names"] = list(
        synthetic_tool_names
    )
    project_page_recovery_into_runtime_intent_plan(
        intent_plan=state.intent_plan,
        input_variables=input_variables,
        recovery_diagnostics=recovery_diagnostics,
        recovery_tool_names=synthetic_tool_names,
    )
    return deduped_calls, recovery_diagnostics


def _apply_page_no_progress_recovery(
    *,
    state: ExecutionStateMachine,
    response: ChatResponse,
    messages: list[ChatMessage],
    tool_results: list[ToolResult],
    tools: list[Any],
    input_variables: dict[str, Any] | None,
) -> None:
    if not state.intent_plan or not tool_results:
        return
    tool_calls = list(getattr(response, "tool_calls", None) or [])
    if not tool_calls and getattr(response, "message", None) is not None:
        tool_calls = list(getattr(response.message, "tool_calls", None) or [])
    if not tool_calls:
        return
    recovery_tool_names, recovery_diagnostics = build_page_no_progress_recovery_default(
        messages=messages,
        tool_calls=tool_calls,
        tool_results=tool_results,
        tools=tools,
        input_variables=input_variables,
    )
    if not recovery_tool_names:
        return
    project_page_recovery_into_runtime_intent_plan(
        intent_plan=state.intent_plan,
        input_variables=input_variables,
        recovery_diagnostics=recovery_diagnostics,
        recovery_tool_names=recovery_tool_names,
    )


async def _execute_deterministic_page_steps(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    base_response: ChatResponse,
    all_tools: list[Any],
    messages: list[ChatMessage],
    turn_messages: list[ChatMessage] | None,
    tool_use_policy: ToolUsePolicy | None,
    input_variables: dict[str, Any] | None,
    previous_tool_calls: list[dict[str, Any]],
    previous_tool_results: list[ToolResult],
    next_response: ChatResponse | None,
    total_tokens: int,
    completion_tokens_used: int,
) -> tuple[ChatResponse | None, list[ToolResult], int, int, bool]:
    collected_results: list[ToolResult] = []
    current_tool_calls = list(previous_tool_calls)
    current_tool_results = list(previous_tool_results)
    current_response = next_response
    current_total_tokens = int(total_tokens or 0)
    current_completion_tokens = int(completion_tokens_used or 0)
    executed_any_step = False

    for _step_idx in range(_MAX_SYNTHETIC_PAGE_STEPS):
        synthetic_tool_calls, diagnostics = _build_deterministic_page_tool_calls(
            state=state,
            messages=messages,
            tool_calls=current_tool_calls,
            tool_results=current_tool_results,
            tools=all_tools,
            input_variables=input_variables,
        )
        if not synthetic_tool_calls:
            break

        synthetic_tool_names = [
            name for call in synthetic_tool_calls if (name := _tool_call_name(call))
        ]
        synthetic_tools = _restrict_tools_to_names(
            io,
            all_tools,
            synthetic_tool_names,
        )
        if not synthetic_tools:
            break

        synthetic_response = _build_synthetic_page_response(
            base_response=base_response,
            tool_calls=synthetic_tool_calls,
            diagnostics=diagnostics,
            total_tokens=current_total_tokens,
            completion_tokens_used=current_completion_tokens,
        )
        tool_rounds_before = _assistant_tool_round_count(messages)
        synthetic_batch = await io.handle_tool_calls(
            response=synthetic_response,
            tools=synthetic_tools,
            messages=messages,
            tool_use_policy=tool_use_policy,
            starting_total_tokens=current_total_tokens,
            starting_completion_tokens=current_completion_tokens,
        )
        synthetic_results = list(synthetic_batch.tool_results)
        if not synthetic_results:
            synthetic_results = synthesize_tool_results_from_calls(
                synthetic_tool_calls,
                skip_unresolved_interactions=True,
            )
        _register_tool_round_delta(
            state,
            before_count=tool_rounds_before,
            messages=messages,
        )
        state.register_tool_results(
            messages=messages,
            turn_messages=turn_messages,
            tool_results=synthetic_results,
        )
        register_tool_failures(state, synthetic_results)
        collected_results.extend(synthetic_results)
        executed_any_step = True
        current_total_tokens = int(
            synthetic_batch.total_tokens or current_total_tokens or 0
        )
        current_completion_tokens = int(
            synthetic_batch.completion_tokens_used
            or current_completion_tokens
            or 0
        )
        state.register_completion_tokens(current_completion_tokens)
        if synthetic_batch.response is not None:
            current_response = synthetic_batch.response
        if not synthetic_results:
            break
        current_tool_calls = synthetic_tool_calls
        current_tool_results = synthetic_results

    return (
        current_response,
        collected_results,
        current_total_tokens,
        current_completion_tokens,
        executed_any_step,
    )


async def execute_tool_batch(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    response: ChatResponse,
    tools: list[Any],
    all_tools: list[Any] | None = None,
    messages: list[ChatMessage],
    turn_messages: list[ChatMessage] | None,
    tool_use_policy: ToolUsePolicy | None,
    input_variables: dict[str, Any] | None = None,
    total_tokens: int,
    completion_tokens_used: int,
) -> tuple[ChatResponse | None, list[ToolResult], int, int]:
    tool_rounds_before = _assistant_tool_round_count(messages)
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
        tool_results = synthesize_tool_results_from_calls(
            getattr(tool_call_response, "tool_calls", None),
            skip_unresolved_interactions=True,
        )
    _register_tool_round_delta(
        state,
        before_count=tool_rounds_before,
        messages=messages,
    )
    state.register_tool_results(
        messages=messages,
        turn_messages=turn_messages,
        tool_results=tool_results,
    )
    state.register_completion_tokens(next_completion_tokens)
    register_tool_failures(state, tool_results)
    resolved_all_tools = list(all_tools or tools)
    (
        next_response,
        synthetic_results,
        next_total_tokens,
        next_completion_tokens,
        executed_synthetic_page_step,
    ) = await _execute_deterministic_page_steps(
        state=state,
        io=io,
        base_response=tool_call_response,
        all_tools=resolved_all_tools,
        messages=messages,
        turn_messages=turn_messages,
        tool_use_policy=tool_use_policy,
        input_variables=input_variables,
        previous_tool_calls=_tool_calls_from_response(tool_call_response),
        previous_tool_results=tool_results,
        next_response=next_response,
        total_tokens=next_total_tokens,
        completion_tokens_used=next_completion_tokens,
    )
    if synthetic_results:
        tool_results.extend(synthetic_results)
    if not executed_synthetic_page_step:
        _apply_page_no_progress_recovery(
            state=state,
            response=tool_call_response,
            messages=messages,
            tool_results=tool_results,
            tools=resolved_all_tools,
            input_variables=input_variables,
        )
    return next_response, tool_results, next_total_tokens, next_completion_tokens


def build_shortcircuit_fallback_response(
    *,
    intent: Any | None,
    response: ChatResponse | None,
    tools: list[Any],
    total_tokens: int,
    completion_tokens_used: int,
) -> ChatResponse | None:
    if _is_editor_read_intent(intent):
        editor_tool = next(
            (
                tool
                for tool in tools
                if str(getattr(tool, "name", "") or "").strip() == "editor_ops"
            ),
            None,
        )
        if editor_tool is None:
            return None
        synthetic_call = [
            {
                "id": (
                    f"synthetic_{getattr(intent, 'intent_id', 'intent')}"
                    "_editor_ops_read_body"
                ),
                "type": "function",
                "function": {
                    "name": "editor_ops",
                    "arguments": '{"operation_name":"read_body"}',
                },
                "metadata": {
                    "synthetic_page_workflow_tool_call": True,
                    "reason": "editor_read_required_tool_fallback",
                },
            }
        ]
        metadata = dict(getattr(response, "metadata", {}) or {})
        metadata["synthetic_editor_read_tool_call"] = True
        metadata["synthetic_shortcircuit_intent_id"] = getattr(
            intent, "intent_id", None
        )
        metadata["synthetic_shortcircuit_tool_name"] = "editor_ops"
        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content="",
                tool_calls=synthetic_call,
            ),
            total_tokens=int(total_tokens or getattr(response, "total_tokens", 0) or 0),
            output_tokens=int(
                completion_tokens_used or getattr(response, "output_tokens", 0) or 0
            ),
            finish_reason="tool_calls",
            tool_calls=synthetic_call,
            metadata=metadata,
        )
    if _is_page_summary_intent(intent):
        read_region_tool = next(
            (
                tool
                for tool in tools
                if str(getattr(tool, "name", "") or "").strip()
                == "ui_read_region"
            ),
            None,
        )
        if read_region_tool is not None:
            synthetic_call = [
                {
                    "id": (
                        f"synthetic_{getattr(intent, 'intent_id', 'intent')}"
                        "_ui_read_region_main"
                    ),
                    "type": "function",
                    "function": {
                        "name": "ui_read_region",
                        "arguments": '{"locator":"main"}',
                    },
                    "metadata": {
                        "synthetic_page_workflow_tool_call": True,
                        "reason": "page_summary_builtin_main_region",
                    },
                }
            ]
            metadata = dict(getattr(response, "metadata", {}) or {})
            metadata["synthetic_page_summary_main_region_tool_call"] = True
            metadata["synthetic_shortcircuit_intent_id"] = getattr(
                intent, "intent_id", None
            )
            metadata["synthetic_shortcircuit_tool_name"] = "ui_read_region"
            return ChatResponse(
                message=ChatMessage(
                    role="assistant",
                    content="",
                    tool_calls=synthetic_call,
                ),
                total_tokens=int(
                    total_tokens or getattr(response, "total_tokens", 0) or 0
                ),
                output_tokens=int(
                    completion_tokens_used
                    or getattr(response, "output_tokens", 0)
                    or 0
                ),
                finish_reason="tool_calls",
                tool_calls=synthetic_call,
                metadata=metadata,
            )
        snapshot_tool = next(
            (
                tool
                for tool in tools
                if str(getattr(tool, "name", "") or "").strip()
                == "ui_get_snapshot"
            ),
            None,
        )
        if snapshot_tool is None:
            return None
        synthetic_call = [
            {
                "id": (
                    f"synthetic_{getattr(intent, 'intent_id', 'intent')}"
                    "_ui_get_snapshot"
                ),
                "type": "function",
                "function": {
                    "name": "ui_get_snapshot",
                    "arguments": '{"mode":"full"}',
                },
                "metadata": {
                    "synthetic_page_workflow_tool_call": True,
                    "reason": "page_summary_builtin_snapshot",
                },
            }
        ]
        metadata = dict(getattr(response, "metadata", {}) or {})
        metadata["synthetic_page_summary_snapshot_tool_call"] = True
        metadata["synthetic_shortcircuit_intent_id"] = getattr(
            intent, "intent_id", None
        )
        metadata["synthetic_shortcircuit_tool_name"] = "ui_get_snapshot"
        return ChatResponse(
            message=ChatMessage(
                role="assistant",
                content="",
                tool_calls=synthetic_call,
            ),
            total_tokens=int(total_tokens or getattr(response, "total_tokens", 0) or 0),
            output_tokens=int(
                completion_tokens_used or getattr(response, "output_tokens", 0) or 0
            ),
            finish_reason="tool_calls",
            tool_calls=synthetic_call,
            metadata=metadata,
        )
    if intent is None or not bool(getattr(intent, "shortcircuit", False)):
        return None
    if str(getattr(intent, "kind", "") or "").strip() != "time_query":
        return None

    time_tool = next(
        (
            tool
            for tool in tools
            if str(getattr(tool, "name", "")).strip() == "get_current_time"
        ),
        None,
    )
    if time_tool is None:
        return None

    synthetic_call = [
        {
            "id": (
                f"synthetic_{getattr(intent, 'intent_id', 'intent')}_get_current_time"
            ),
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
            completion_tokens_used or getattr(response, "output_tokens", 0) or 0
        ),
        finish_reason="tool_calls",
        tool_calls=synthetic_call,
        metadata=metadata,
    )


def _is_editor_read_intent(intent: Any | None) -> bool:
    if intent is None:
        return False
    if str(getattr(intent, "family", "") or "").strip() != "page_ops":
        return False
    metadata = dict(getattr(intent, "metadata", {}) or {})
    return str(metadata.get("page_workflow_goal") or "").strip() == "editor_read"


def _is_page_summary_intent(intent: Any | None) -> bool:
    if intent is None:
        return False
    if str(getattr(intent, "family", "") or "").strip() != "page_ops":
        return False
    if not bool(getattr(intent, "shortcircuit", False)):
        return False
    metadata = dict(getattr(intent, "metadata", {}) or {})
    return str(metadata.get("page_workflow_goal") or "").strip() == "page_summary"


async def run_tool_batch_or_update_intents(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    intent: Any | None,
    response: ChatResponse | None,
    tools: list[Any],
    all_tools: list[Any] | None = None,
    messages: list[ChatMessage],
    turn_messages: list[ChatMessage],
    tool_use_policy: ToolUsePolicy | None,
    input_variables: dict[str, Any] | None,
    total_tokens: int,
    completion_tokens_used: int,
) -> tuple[ChatResponse | None, list[ToolResult], int, int]:
    if getattr(response, "tool_calls", None) and tools:
        return await execute_tool_batch(
            state=state,
            io=io,
            response=response,
            tools=tools,
            all_tools=all_tools or tools,
            messages=messages,
            turn_messages=turn_messages,
            tool_use_policy=tool_use_policy,
            input_variables=input_variables,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
        )

    if tools:
        fallback_response = build_shortcircuit_fallback_response(
            intent=intent,
            response=response,
            tools=tools,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
        )
        if fallback_response is not None:
            return await execute_tool_batch(
                state=state,
                io=io,
                response=fallback_response,
                tools=tools,
                all_tools=all_tools or tools,
                messages=messages,
                turn_messages=turn_messages,
                tool_use_policy=tool_use_policy,
                input_variables=input_variables,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
            )

    if state.intent_plan:
        state.intent_plan = RecoveryManager.update_intent_statuses(
            state.intent_plan,
            messages=messages,
            turn_messages=turn_messages,
            tool_results=[],
        )

    return response, [], total_tokens, completion_tokens_used


async def run_contract_retry_round(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    agent: Any,
    request: Any,
    prep: Any,
    messages: list[ChatMessage],
    turn_messages: list[ChatMessage],
    response: ChatResponse | None,
    active_policy: ToolUsePolicy | None,
    active_intent: Any | None,
    active_tools: list[Any],
    tools: list[Any],
    tool_results: list[ToolResult],
    total_tokens: int,
    completion_tokens_used: int,
    emit_round_started: Callable[..., None],
) -> tuple[
    ChatResponse | None,
    list[ToolResult],
    int,
    int,
    ToolUsePolicy | None,
    list[Any],
]:
    contract_tools = list(active_tools or prep.all_tools or tools)
    if (
        active_policy is None
        or not active_policy.retry_on_contract_breach
        or not contract_tools
        or tool_results
    ):
        return (
            response,
            tool_results,
            total_tokens,
            completion_tokens_used,
            active_policy,
            list(active_tools or []),
        )

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
            record_contract_breach(
                state,
                breach_type=breach_type,
                diagnostics=breach_diagnostics,
            )
            response = suppress_contract_placeholder_response(response)
        if retry_policy is not None:
            retry_policy = constrain_retry_policy_to_active_intent(
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
            non_intent_breach_type = retry_policy.reason or "tool_contract_breach"

    if should_retry and retry_policy is not None:
        if non_intent_breach_type:
            record_contract_breach(
                state,
                breach_type=non_intent_breach_type,
                diagnostics={},
            )
        retry_tool_pool = list(prep.all_tools or tools or contract_tools)
        retry_tools = io.restrict_tools_to_names(
            retry_tool_pool,
            retry_policy.allowed_tool_names,
        )
        emit_round_started(
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
            (
                response,
                extra_tool_results,
                total_tokens,
                completion_tokens_used,
            ) = await execute_tool_batch(
                state=state,
                io=io,
                response=response,
                tools=retry_tools,
                all_tools=retry_tool_pool,
                messages=messages,
                turn_messages=turn_messages,
                tool_use_policy=retry_policy,
                input_variables=request.input_variables,
                total_tokens=total_tokens,
                completion_tokens_used=completion_tokens_used,
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
        elif response is not None:
            response = suppress_contract_placeholder_response(response)
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
                turn_messages=turn_messages,
                tool_results=[],
            )

    return (
        response,
        tool_results,
        total_tokens,
        completion_tokens_used,
        active_policy,
        list(active_tools or []),
    )


async def maybe_retry_web_research_contract(
    *,
    state: ExecutionStateMachine,
    io: TurnIOAdapter,
    agent: Any,
    request: Any,
    prep: Any,
    messages: list[ChatMessage],
    response: ChatResponse | None,
    active_policy: ToolUsePolicy | None,
    active_tools: list[Any],
    tools: list[Any],
    total_tokens: int,
    completion_tokens_used: int,
    emit_round_started: Callable[..., None],
) -> tuple[ChatResponse | None, int, int, bool, ToolUsePolicy | None]:
    if response is None or getattr(response, "tool_calls", None):
        return response, total_tokens, completion_tokens_used, False, active_policy

    contract_tools = list(active_tools or prep.all_tools or tools)
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
        not should_retry_web_research
        or web_research_retry_policy is None
        or web_research_retry_policy.mode != "none"
        or web_research_retry_policy.allowed_tool_names
    ):
        return response, total_tokens, completion_tokens_used, False, active_policy

    record_contract_breach(
        state,
        breach_type=(
            web_research_retry_policy.reason or "web_research_contract_breach"
        ),
        diagnostics={},
    )
    emit_round_started(
        state,
        round_kind="contract_retry",
        policy=web_research_retry_policy,
        tools=[],
        reason=(web_research_retry_policy.reason or "web_research_contract_breach"),
    )
    io.log_tool_contract_diagnostics(
        agent=agent,
        messages=messages,
        response=response,
        tools=contract_tools,
        policy=web_research_retry_policy,
        conversation_id=request.conversation_id,
        breach_type=(
            web_research_retry_policy.reason or "web_research_contract_breach"
        ),
        retry_result="retrying",
        continuation=prep.continuation_context,
    )
    active_policy = web_research_retry_policy
    retry_round = await io.call_llm(
        messages=messages,
        tools=None,
        tool_use_policy=web_research_retry_policy,
        breach_retry_result="contract_retry",
    )
    response = retry_round.response
    total_tokens += int(retry_round.total_tokens or 0)
    completion_tokens_used += int(retry_round.completion_tokens_used or 0)
    state.register_completion_tokens(completion_tokens_used)
    return response, total_tokens, completion_tokens_used, True, active_policy


__all__ = [
    "build_shortcircuit_fallback_response",
    "execute_tool_batch",
    "maybe_retry_web_research_contract",
    "run_contract_retry_round",
    "run_tool_batch_or_update_intents",
]
