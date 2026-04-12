"""Support helpers for conversation entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi.responses import StreamingResponse

from .execution_state_machine import ExecutionStateMachine
from .stream_handler import StreamExecutionHandler
from .stream_runtime_contract import build_stream_runtime_contract


@dataclass(frozen=True)
class SyncExecutionRuntime:
    selected_skill_names: list[str]
    context_sources: list[Any]
    runtime_contract: Any
    state: ExecutionStateMachine


def _resolve_capability_list(bundle: Any, attr: str) -> list[Any]:
    if bundle is None:
        return []
    values = getattr(bundle, attr, None) or []
    return list(values)


def build_sync_execution_runtime(engine: Any, prep: Any) -> SyncExecutionRuntime:
    capability_bundle = getattr(prep, "capability_bundle", None)
    selected_skill_names = _resolve_capability_list(
        capability_bundle, "selected_skill_names"
    )
    context_sources = _resolve_capability_list(capability_bundle, "context_sources")
    runtime_contract = build_stream_runtime_contract(engine)
    state = ExecutionStateMachine.from_prepared_execution(prep)
    return SyncExecutionRuntime(
        selected_skill_names=selected_skill_names,
        context_sources=context_sources,
        runtime_contract=runtime_contract,
        state=state,
    )


async def prepare_stream_execution(
    engine: Any,
    *,
    agent: Any,
    request: Any,
    skill_result: Any,
) -> Any:
    prep = await engine._prepare_execution(agent, request, skill_result)
    prep.stream_runtime = await engine._prepare_stream_runtime(
        agent=agent,
        messages=prep.messages,
        tenant_id=request.tenant_id,
        route_result=prep.route_result,
    )
    return prep


def build_streaming_response(
    handler: StreamExecutionHandler,
) -> StreamingResponse:
    return StreamingResponse(
        handler.generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
