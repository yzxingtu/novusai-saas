"""Compatibility facade for ConversationEngine sync/stream entrypoints."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from fastapi.responses import StreamingResponse

from app.core.logging import LogManager
from app.models.ai.agent import Agent

from .conversation_stream_entrypoint import execute_stream_conversation_entrypoint
from .conversation_sync_entrypoint import execute_sync_conversation_entrypoint
from .conversation_sync_io_adapter import _SyncIOAdapter
from .stream_handler import StreamExecutionHandler
from .stream_runtime_contract import build_stream_runtime_contract
from .turn_executor import TurnExecutor
from .types import ExecutionRequest, ExecutionResult

if TYPE_CHECKING:
    from app.ai.skills.resolver import SkillResolveResult

logger = LogManager.get_logger("ai.engine.conversation")


async def execute_conversation(
    engine: Any,
    *,
    agent: Agent,
    request: ExecutionRequest,
    skill_result: SkillResolveResult | None = None,
) -> ExecutionResult:
    """Execute conversation mode / 执行对话模式."""
    return await execute_sync_conversation_entrypoint(
        engine=engine,
        agent=agent,
        request=request,
        skill_result=skill_result,
        sync_io_cls=_SyncIOAdapter,
        runtime_contract_builder=build_stream_runtime_contract,
        turn_executor_run=TurnExecutor.run,
        engine_logger=logger,
    )


async def stream_execute_conversation(
    engine: Any,
    *,
    agent: Agent,
    request: ExecutionRequest,
    on_complete: Callable[[ExecutionResult], Awaitable[dict[str, Any] | None]]
    | None = None,
    skill_result: SkillResolveResult | None = None,
) -> StreamingResponse:
    """SSE streaming conversation execution / SSE 流式执行对话。"""
    return await execute_stream_conversation_entrypoint(
        engine=engine,
        agent=agent,
        request=request,
        on_complete=on_complete,
        skill_result=skill_result,
        stream_handler_cls=StreamExecutionHandler,
    )


__all__ = [
    "_SyncIOAdapter",
    "StreamExecutionHandler",
    "TurnExecutor",
    "build_stream_runtime_contract",
    "execute_conversation",
    "stream_execute_conversation",
]
