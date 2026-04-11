"""Prepare and dispatch legacy adapter entrypoints across clear seams."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from app.ai.adapters.openai_compatible.compat.legacy_context_builder import (
    LegacyEntrypointAdapterProtocol,
    LegacyEntrypointPlan,
    build_legacy_entrypoint_plan,
)
from app.ai.adapters.openai_compatible.compat.legacy_entrypoint_runner import (
    run_legacy_chat_plan,
    run_legacy_stream_plan,
)
from app.ai.exceptions import AIGatewayError
from app.ai.types import ChatChunk, ChatMessage, ChatResponse


class LegacyEntrypointDispatchError(RuntimeError):
    """Carries the prepared legacy plan when runner execution fails."""

    def __init__(self, *, plan: LegacyEntrypointPlan, cause: Exception) -> None:
        self.plan = plan
        self.cause = cause
        super().__init__(str(cause))


async def dispatch_legacy_chat_entrypoint(
    *,
    adapter: LegacyEntrypointAdapterProtocol,
    messages: list[ChatMessage],
    model: str,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    top_p: float = 1.0,
    tools: list[dict] | None = None,
    tool_choice: str | None = None,
    kwargs: dict[str, Any],
) -> tuple[LegacyEntrypointPlan, ChatResponse]:
    plan = await build_legacy_entrypoint_plan(
        adapter=adapter,
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        tools=tools,
        tool_choice=tool_choice,
        stream=False,
        kwargs=kwargs,
    )
    try:
        response = await run_legacy_chat_plan(
            adapter=adapter,
            plan=plan,
            messages=messages,
            model=model,
            tools=tools,
            tool_choice=tool_choice,
        )
    except AIGatewayError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise LegacyEntrypointDispatchError(plan=plan, cause=exc) from exc
    return plan, response


async def dispatch_legacy_stream_entrypoint(
    *,
    adapter: LegacyEntrypointAdapterProtocol,
    messages: list[ChatMessage],
    model: str,
    temperature: float = 0.7,
    max_tokens: int | None = None,
    top_p: float = 1.0,
    tools: list[dict] | None = None,
    tool_choice: str | None = None,
    kwargs: dict[str, Any],
) -> tuple[LegacyEntrypointPlan, AsyncIterator[ChatChunk]]:
    plan = await build_legacy_entrypoint_plan(
        adapter=adapter,
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        tools=tools,
        tool_choice=tool_choice,
        stream=True,
        kwargs=kwargs,
    )
    async def _dispatch_stream() -> AsyncIterator[ChatChunk]:
        try:
            async for chunk in run_legacy_stream_plan(
                adapter=adapter,
                plan=plan,
                messages=messages,
                model=model,
                tools=tools,
                tool_choice=tool_choice,
            ):
                yield chunk
        except AIGatewayError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise LegacyEntrypointDispatchError(plan=plan, cause=exc) from exc

    return plan, _dispatch_stream()


__all__ = [
    "LegacyEntrypointDispatchError",
    "dispatch_legacy_chat_entrypoint",
    "dispatch_legacy_stream_entrypoint",
]
