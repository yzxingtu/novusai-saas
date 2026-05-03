"""
Test type: behavioral
Scope: stream completion callback scheduling and post-done background handling.
Mock strategy: callback/logger seams are mocked; lifecycle callback behavior runs real.
"""

from __future__ import annotations

import asyncio
import sys
import types
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

ENGINE_DIR = Path(__file__).resolve().parents[3] / "app" / "ai" / "engine"
if "app.ai.engine" not in sys.modules:
    engine_pkg = types.ModuleType("app.ai.engine")
    engine_pkg.__path__ = [str(ENGINE_DIR)]
    sys.modules["app.ai.engine"] = engine_pkg

stream_completion_support = import_module("app.ai.engine.stream_completion_support")
await_if_needed = stream_completion_support.await_if_needed
pop_post_done_callback = stream_completion_support.pop_post_done_callback
schedule_background_callback = stream_completion_support.schedule_background_callback
start_on_complete_task = stream_completion_support.start_on_complete_task


@pytest.mark.asyncio
async def test_await_if_needed_supports_sync_and_async_values() -> None:
    async def _async_value():
        return "async"

    assert await await_if_needed("sync") == "sync"
    assert await await_if_needed(_async_value()) == "async"


def test_pop_post_done_callback_returns_and_removes_callback() -> None:
    def callback():
        return None

    extra = {"value": 1, "__post_done_callback__": callback}

    popped = pop_post_done_callback(extra)

    assert popped is callback
    assert "__post_done_callback__" not in extra
    assert extra == {"value": 1}


@pytest.mark.asyncio
async def test_start_on_complete_task_accepts_sync_lifecycle_callbacks() -> None:
    events: list[str] = []

    def _after_turn(*_args):
        events.append("after_turn")

    def _post_done():
        events.append("post_done")

    def _on_complete(_result):
        events.append("on_complete")
        return {
            "ok": True,
            "__post_done_callback__": _post_done,
        }

    handler = SimpleNamespace(
        on_complete=_on_complete,
        _on_complete_called=False,
        _background_tasks=set(),
        prep=SimpleNamespace(context_engine=SimpleNamespace(after_turn=_after_turn)),
        agent=SimpleNamespace(id=1),
        request=SimpleNamespace(conversation_id=42),
    )
    result = SimpleNamespace(
        diagnostics={},
        turn_record={},
    )
    logger = SimpleNamespace(error=MagicMock())

    task = start_on_complete_task(
        handler,
        result,
        defer_post_done=False,
        logger=logger,
    )

    assert task is not None
    extra = await task

    assert extra == {"ok": True}
    assert events == ["after_turn", "on_complete", "post_done"]
    assert handler._on_complete_called is True
    logger.error.assert_not_called()


@pytest.mark.asyncio
async def test_start_on_complete_task_records_after_turn_failure_metadata() -> None:
    handler = SimpleNamespace(
        on_complete=lambda _result: None,
        _on_complete_called=False,
        _background_tasks=set(),
        prep=SimpleNamespace(
            context_engine=SimpleNamespace(
                after_turn=AsyncMock(side_effect=RuntimeError("after turn boom"))
            )
        ),
        agent=SimpleNamespace(id=1),
        request=SimpleNamespace(conversation_id=99),
    )
    result = SimpleNamespace(
        diagnostics={},
        turn_record={},
    )
    logger = SimpleNamespace(error=MagicMock())

    task = start_on_complete_task(
        handler,
        result,
        defer_post_done=True,
        logger=logger,
    )
    assert task is not None

    extra = await task

    assert extra is None
    assert result.diagnostics["after_turn_failed"] is True
    assert "after turn boom" in result.diagnostics["after_turn_error"]
    assert result.turn_record["metadata"]["after_turn_failed"] is True
    logger.error.assert_called()


@pytest.mark.asyncio
async def test_schedule_background_callback_accepts_sync_callback() -> None:
    events: list[str] = []
    handler = SimpleNamespace(_background_tasks=set())
    logger = SimpleNamespace(error=MagicMock())

    def _callback():
        events.append("done")

    schedule_background_callback(
        handler,
        _callback,
        logger=logger,
    )

    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert events == ["done"]
    assert not handler._background_tasks
    logger.error.assert_not_called()


@pytest.mark.asyncio
async def test_schedule_background_callback_treats_shutdown_cancel_as_non_error() -> (
    None
):
    handler = SimpleNamespace(_background_tasks=set())
    logger = SimpleNamespace(debug=MagicMock(), error=MagicMock())

    async def _callback():
        raise asyncio.CancelledError()

    schedule_background_callback(
        handler,
        _callback,
        logger=logger,
    )

    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert not handler._background_tasks
    logger.error.assert_not_called()
    logger.debug.assert_called_once()
