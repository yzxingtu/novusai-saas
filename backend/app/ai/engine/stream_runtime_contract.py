"""
Explicit runtime contract for streaming turn execution.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage, ChatResponse

from .execution_state_machine import ExecutionStateMachine
from .recovery_manager import RecoveryManager
from .stream_runtime_hooks import StreamRuntimeHookSource, build_stream_runtime_hooks
from .types import ExecutionRequest, ToolUsePolicy


@dataclass(slots=True)
class StreamRuntimeContract:
    keep_tool_calls_for_round: Callable[
        [list[dict[str, Any]]],
        tuple[list[dict[str, Any]], bool],
    ]
    should_retry_tool_contract_breach: Callable[
        ...,
        tuple[bool, ToolUsePolicy | None, str],
    ]
    analyze_post_tool_contract_breach: Callable[
        ...,
        tuple[str | None, ToolUsePolicy | None, dict[str, Any]],
    ]
    restrict_tools_to_names: Callable[
        [list[Any], list[str] | None],
        list[Any],
    ]
    log_tool_contract_diagnostics: Callable[..., None]
    finalize_partial_output: Callable[
        ...,
        Awaitable[tuple[str, int, int]],
    ]
    finalize_completed_output: Callable[
        ...,
        Awaitable[tuple[str, int, int]],
    ]


async def finalize_partial_turn_output(
    *,
    agent: Any,
    request: ExecutionRequest,
    prep: Any,
    messages: list[ChatMessage],
    response: ChatResponse | None,
    state: ExecutionStateMachine,
    tool_results: list[ToolResult],
    reason: str,
    total_tokens: int,
    completion_tokens_used: int,
    selected_skill_names: list[str],
    context_sources: list[Any],
) -> tuple[str, int, int]:
    _ = (
        agent,
        request,
        prep,
        messages,
        tool_results,
        selected_skill_names,
        context_sources,
    )
    visible_output = (
        str(response.message.content or "").strip() if response is not None else ""
    )
    if visible_output:
        return visible_output, total_tokens, completion_tokens_used
    return (
        RecoveryManager.build_partial_output(
            state.intent_plan,
            tool_results=tool_results,
            reason=reason,
            provider_failure_kind=state.provider_failure_kind,
        ),
        total_tokens,
        completion_tokens_used,
    )


async def finalize_completed_turn_output(
    *,
    agent: Any,
    request: ExecutionRequest,
    prep: Any,
    messages: list[ChatMessage],
    response: ChatResponse | None,
    state: ExecutionStateMachine,
    tool_results: list[ToolResult],
    reason: str,
    total_tokens: int,
    completion_tokens_used: int,
    selected_skill_names: list[str],
    context_sources: list[Any],
) -> tuple[str, int, int]:
    _ = (
        agent,
        request,
        prep,
        messages,
        reason,
        selected_skill_names,
        context_sources,
    )
    visible_output = (
        str(response.message.content or "").strip() if response is not None else ""
    )
    contract_breach_type = str(
        (state.preparation_diagnostics or {}).get("contract_breach_type") or ""
    ).strip()
    if visible_output:
        return visible_output, total_tokens, completion_tokens_used
    return (
        RecoveryManager.build_completed_output(
            state.intent_plan,
            tool_results=tool_results,
            reason=reason,
            contract_breach_type=contract_breach_type or None,
        ),
        total_tokens,
        completion_tokens_used,
    )


def _build_contract_from_hook_source(
    hook_source: StreamRuntimeHookSource,
) -> StreamRuntimeContract:
    return StreamRuntimeContract(
        keep_tool_calls_for_round=hook_source.keep_tool_calls_for_round,
        should_retry_tool_contract_breach=hook_source.should_retry_tool_contract_breach,
        analyze_post_tool_contract_breach=hook_source.analyze_post_tool_contract_breach,
        restrict_tools_to_names=hook_source.restrict_tools_to_names,
        log_tool_contract_diagnostics=hook_source.log_tool_contract_diagnostics,
        finalize_partial_output=hook_source.finalize_partial_output,
        finalize_completed_output=hook_source.finalize_completed_output,
    )


def build_stream_runtime_contract(engine: Any) -> StreamRuntimeContract:
    hook_source = build_stream_runtime_hooks(
        engine,
        finalize_partial_fallback=finalize_partial_turn_output,
        finalize_completed_fallback=finalize_completed_turn_output,
    )
    return _build_contract_from_hook_source(hook_source)


__all__ = [
    "StreamRuntimeContract",
    "build_stream_runtime_contract",
    "finalize_completed_turn_output",
    "finalize_partial_turn_output",
]
