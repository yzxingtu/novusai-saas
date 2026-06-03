"""Focused sync conversation entrypoint support."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage, ChatResponse
from app.exceptions import BusinessException, NotFoundException
from app.models.ai.agent import Agent

from .conversation_sync_result_support import (
    build_sync_exception_result,
    build_sync_success_result,
)
from .execution_state_machine import ExecutionStateMachine
from .types import ExecutionRequest, ExecutionResult

if TYPE_CHECKING:
    from app.ai.skills.resolver import SkillResolveResult


async def execute_sync_conversation_entrypoint(
    *,
    engine: Any,
    agent: Agent,
    request: ExecutionRequest,
    skill_result: SkillResolveResult | None,
    sync_io_cls: type[Any],
    runtime_contract_builder: Any,
    turn_executor_run: Any,
    engine_logger: Any,
) -> ExecutionResult:
    start = time.perf_counter()

    prep = None
    messages: list[ChatMessage] = []
    response: ChatResponse | None = None
    tool_results: list[ToolResult] = []
    state: ExecutionStateMachine | None = None

    try:
        prep = await engine._prepare_execution(agent, request, skill_result)
        messages = prep.messages
        runtime_selected_skill_names = (
            list(getattr(prep.capability_bundle, "selected_skill_names", []) or [])
            if prep.capability_bundle is not None
            else []
        )
        runtime_context_sources = (
            list(getattr(prep.capability_bundle, "context_sources", []) or [])
            if prep.capability_bundle is not None
            else []
        )
        runtime_contract = runtime_contract_builder(engine)
        state = ExecutionStateMachine.from_prepared_execution(prep)
        sync_io = sync_io_cls(
            engine=engine,
            agent=agent,
            request=request,
            prep=prep,
            selected_skill_names=runtime_selected_skill_names,
            context_sources=runtime_context_sources,
            runtime_contract=runtime_contract,
        )
        turn_execution = await turn_executor_run(
            state=state,
            io=sync_io,
            prep=prep,
            request=request,
            agent=agent,
        )
        response = turn_execution.response
        tool_results = list(turn_execution.tool_results)
        total_tokens = turn_execution.total_tokens
        output = turn_execution.output
        paused_for_consent = turn_execution.paused_for_consent
        partial = turn_execution.partial
        completion_reason = turn_execution.completion_reason
        final_output_source = turn_execution.final_output_source

        result = build_sync_success_result(
            output=output,
            response=response,
            messages=messages,
            tool_results=tool_results,
            total_tokens=total_tokens,
            start_time=start,
            request=request,
            prep=prep,
            state=state,
            paused_for_consent=paused_for_consent,
            partial=partial,
            completion_reason=completion_reason,
            final_output_source=final_output_source,
            messages_to_dicts=engine._messages_to_dicts,
        )

        if prep.context_engine is not None:
            await prep.context_engine.after_turn(agent, request, result)

        return result

    except (BusinessException, NotFoundException):
        raise
    except Exception as exc:
        engine_logger.error(
            "Conversation execution failed: agent={} error={}",
            agent.id,
            str(exc),
            exc_info=True,
        )
        return build_sync_exception_result(
            exc=exc,
            request=request,
            messages=messages,
            tool_results=tool_results,
            state=state,
            prep=prep,
            start_time=start,
            messages_to_dicts=engine._messages_to_dicts,
        )


__all__ = ["execute_sync_conversation_entrypoint"]
