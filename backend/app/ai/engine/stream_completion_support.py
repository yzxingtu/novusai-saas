"""Focused on_complete/background-callback helpers for stream handling."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .types import ExecutionResult


def pop_post_done_callback(
    extra: dict[str, Any] | None,
) -> Callable[[], Awaitable[None]] | None:
    if not isinstance(extra, dict):
        return None
    callback = extra.pop("__post_done_callback__", None)
    if callable(callback):
        return callback
    return None


async def await_if_needed(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def run_post_done_callback(
    callback: Callable[[], Awaitable[None]],
) -> None:
    await await_if_needed(callback())


async def run_context_after_turn(
    handler: Any,
    result: ExecutionResult,
) -> None:
    context_engine = getattr(handler.prep, "context_engine", None)
    if context_engine is None:
        return None
    after_turn = getattr(context_engine, "after_turn", None)
    if not callable(after_turn):
        return None
    return await await_if_needed(
        after_turn(
            handler.agent,
            handler.request,
            result,
        )
    )


async def invoke_on_complete(
    handler: Any,
    result: ExecutionResult,
) -> Any:
    return await await_if_needed(handler.on_complete(result))


def schedule_background_callback(
    handler: Any,
    callback: Callable[[], Awaitable[None]],
    *,
    logger: Any,
) -> None:
    async def _runner() -> None:
        try:
            await run_post_done_callback(callback)
        except Exception as exc:  # noqa: BLE001
            logger.error("post-done callback error: {}", str(exc), exc_info=True)
        except BaseException as exc:  # pragma: no cover
            logger.error(
                "post-done callback base exception: type={} error={}",
                type(exc).__name__,
                str(exc),
                exc_info=True,
            )

    task = asyncio.create_task(_runner())
    handler._background_tasks.add(task)
    task.add_done_callback(handler._background_tasks.discard)


def start_on_complete_task(
    handler: Any,
    result: ExecutionResult,
    *,
    defer_post_done: bool,
    logger: Any,
) -> asyncio.Task[dict[str, Any] | None] | None:
    if not handler.on_complete or handler._on_complete_called:
        return None

    handler._on_complete_called = True

    def _record_after_turn_failure(exc: BaseException) -> None:
        diagnostics = dict(getattr(result, "diagnostics", {}) or {})
        diagnostics["after_turn_failed"] = True
        diagnostics["after_turn_error"] = str(exc)
        result.diagnostics = diagnostics
        if isinstance(result.turn_record, dict):
            metadata = dict(result.turn_record.get("metadata") or {})
            metadata["after_turn_failed"] = True
            metadata["after_turn_error"] = str(exc)
            result.turn_record["metadata"] = metadata

    async def _runner() -> dict[str, Any] | None:
        try:
            if getattr(handler.prep, "context_engine", None) is not None:
                try:
                    await run_context_after_turn(handler, result)
                except Exception as ctx_exc:  # noqa: BLE001
                    _record_after_turn_failure(ctx_exc)
                    logger.error(
                        "context_engine.after_turn error: conversation_id={} error={}",
                        handler.request.conversation_id,
                        str(ctx_exc),
                    )
                except BaseException as ctx_base_exc:  # pragma: no cover
                    _record_after_turn_failure(ctx_base_exc)
                    logger.error(
                        "context_engine.after_turn base exception: conversation_id={} type={} error={}",
                        handler.request.conversation_id,
                        type(ctx_base_exc).__name__,
                        str(ctx_base_exc),
                        exc_info=True,
                    )
            extra = await invoke_on_complete(handler, result)
            if not defer_post_done:
                post_done_callback = pop_post_done_callback(extra)
                if post_done_callback is not None:
                    await run_post_done_callback(post_done_callback)
            return extra if isinstance(extra, dict) else None
        except Exception as cb_exc:  # noqa: BLE001
            logger.error("on_complete callback error: {}", str(cb_exc))
        except BaseException as cb_base_exc:  # pragma: no cover
            logger.error(
                "on_complete callback base exception: type={} error={}",
                type(cb_base_exc).__name__,
                str(cb_base_exc),
                exc_info=True,
            )
        return None

    task = asyncio.create_task(_runner())
    handler._background_tasks.add(task)
    task.add_done_callback(handler._background_tasks.discard)
    return task


async def await_on_complete_before_done(
    handler: Any,
    result: ExecutionResult,
    *,
    logger: Any,
) -> dict[str, Any] | None:
    task = start_on_complete_task(
        handler,
        result,
        defer_post_done=True,
        logger=logger,
    )
    if task is None:
        return None
    return await asyncio.shield(task)
