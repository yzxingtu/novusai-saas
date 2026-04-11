"""Explicit hook-source contracts for streaming runtime collaborators."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage, ChatResponse

from .execution_state_machine import ExecutionStateMachine
from .types import ExecutionRequest, ToolUsePolicy

if TYPE_CHECKING:
    from .base import BaseEngine


async def _await_if_needed(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


@runtime_checkable
class StreamRuntimeHookSource(Protocol):
    """Public collaborator surface consumed by StreamExecutionHandler."""

    def truncate_tool_calls_after_navigation(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], bool]: ...

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

    def log_tool_contract_diagnostics(self, **kwargs: Any) -> None: ...

    async def finalize_partial_output(
        self,
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
    ) -> tuple[str, int, int]: ...

    async def finalize_completed_output(
        self,
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
    ) -> tuple[str, int, int]: ...


def resolve_explicit_stream_runtime_hooks(
    owner: Any,
) -> StreamRuntimeHookSource | None:
    """Prefer explicit runtime hooks over implicit method-name probing."""

    explicit = getattr(owner, "stream_runtime_hooks", None)
    if isinstance(explicit, StreamRuntimeHookSource):
        return explicit
    if isinstance(owner, StreamRuntimeHookSource):
        return owner
    return None


@dataclass(slots=True)
class BaseEngineStreamRuntimeHooks:
    """Bridge BaseEngine internals onto the explicit stream hook contract."""

    engine: BaseEngine
    finalize_partial_fallback: Callable[..., Awaitable[tuple[str, int, int]]]
    finalize_completed_fallback: Callable[..., Awaitable[tuple[str, int, int]]]

    def truncate_tool_calls_after_navigation(
        self,
        tool_calls: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], bool]:
        return self.engine._truncate_tool_calls_after_navigation(tool_calls)

    def should_retry_tool_contract_breach(
        self,
        *,
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[Any],
        input_variables: dict[str, Any] | None,
    ) -> tuple[bool, ToolUsePolicy | None, str]:
        return self.engine._should_retry_tool_contract_breach(
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables=input_variables,
        )

    def should_retry_web_research_contract_breach(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[Any],
        input_variables: dict[str, Any] | None,
        continuation: Any,
    ) -> tuple[bool, ToolUsePolicy | None, str]:
        return self.engine._should_retry_web_research_contract_breach(
            messages=messages,
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables=input_variables,
            continuation=continuation,
        )

    def analyze_post_tool_contract_breach(
        self,
        *,
        messages: list[ChatMessage],
        response: ChatResponse | None,
        current_policy: ToolUsePolicy,
        tools: list[Any],
        input_variables: dict[str, Any] | None,
    ) -> tuple[str | None, ToolUsePolicy | None, dict[str, Any]]:
        if response is None:
            return None, None, {}
        return self.engine._analyze_post_tool_contract_breach(
            messages=messages,
            response=response,
            current_policy=current_policy,
            tools=tools,
            input_variables=input_variables,
        )

    def restrict_tools_to_names(
        self,
        tools: list[Any],
        allowed_tool_names: list[str] | None,
    ) -> list[Any]:
        return self.engine._restrict_tools_to_names(tools, allowed_tool_names)

    def log_tool_contract_diagnostics(self, **kwargs: Any) -> None:
        self.engine._log_tool_contract_diagnostics(**kwargs)

    async def finalize_partial_output(
        self,
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
        finalize = getattr(self.engine, "finalize_partial_output", None)
        if callable(finalize):
            return await _await_if_needed(
                finalize(
                    agent=agent,
                    request=request,
                    prep=prep,
                    messages=messages,
                    response=response,
                    state=state,
                    tool_results=tool_results,
                    reason=reason,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                    selected_skill_names=selected_skill_names,
                    context_sources=context_sources,
                )
            )
        return await self.finalize_partial_fallback(
            agent=agent,
            request=request,
            prep=prep,
            messages=messages,
            response=response,
            state=state,
            tool_results=tool_results,
            reason=reason,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            selected_skill_names=selected_skill_names,
            context_sources=context_sources,
        )

    async def finalize_completed_output(
        self,
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
        finalize = getattr(self.engine, "finalize_completed_output", None)
        if callable(finalize):
            return await _await_if_needed(
                finalize(
                    agent=agent,
                    request=request,
                    prep=prep,
                    messages=messages,
                    response=response,
                    state=state,
                    tool_results=tool_results,
                    reason=reason,
                    total_tokens=total_tokens,
                    completion_tokens_used=completion_tokens_used,
                    selected_skill_names=selected_skill_names,
                    context_sources=context_sources,
                )
            )
        return await self.finalize_completed_fallback(
            agent=agent,
            request=request,
            prep=prep,
            messages=messages,
            response=response,
            state=state,
            tool_results=tool_results,
            reason=reason,
            total_tokens=total_tokens,
            completion_tokens_used=completion_tokens_used,
            selected_skill_names=selected_skill_names,
            context_sources=context_sources,
        )


__all__ = [
    "BaseEngineStreamRuntimeHooks",
    "StreamRuntimeHookSource",
    "resolve_explicit_stream_runtime_hooks",
]
