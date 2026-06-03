"""Focused stream conversation entrypoint support."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from fastapi.responses import StreamingResponse

from app.models.ai.agent import Agent

from .types import ExecutionRequest, ExecutionResult

if TYPE_CHECKING:
    from app.ai.skills.resolver import SkillResolveResult


async def execute_stream_conversation_entrypoint(
    *,
    engine: Any,
    agent: Agent,
    request: ExecutionRequest,
    on_complete: Callable[[ExecutionResult], Awaitable[dict[str, Any] | None]] | None,
    skill_result: SkillResolveResult | None,
    stream_handler_cls: type[Any],
) -> StreamingResponse:
    start = time.perf_counter()

    prep = await engine._prepare_execution(agent, request, skill_result)
    prep.stream_runtime = await engine._prepare_stream_runtime(
        agent=agent,
        messages=prep.messages,
        tenant_id=request.tenant_id,
        route_result=prep.route_result,
    )

    handler = stream_handler_cls(
        engine=engine,
        agent=agent,
        request=request,
        prep=prep,
        start_time=start,
        on_complete=on_complete,
    )

    return StreamingResponse(
        handler.generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


__all__ = ["execute_stream_conversation_entrypoint"]
