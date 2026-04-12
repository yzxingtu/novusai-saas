"""
Compatibility seam for stream runtime hook resolution.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.ai.tools.types import ToolResult
from app.ai.types import ChatMessage, ChatResponse

from .base_helpers import truncate_tool_calls_after_page_navigation
from .execution_state_machine import ExecutionStateMachine
from .stream_runtime_hooks import (
    StreamRuntimeHookSource,
    resolve_explicit_stream_runtime_hooks,
)
from .tool_contract_retry_helpers import (
    analyze_post_tool_contract_breach as _analyze_post_tool_contract_breach_impl,
)
from .tool_contract_retry_helpers import (
    should_retry_tool_contract_breach as _should_retry_tool_contract_breach_impl,
)
from .tool_contract_retry_helpers import (
    should_retry_web_research_contract_breach as _should_retry_web_research_contract_breach_impl,
)
from .tool_policy_helpers import (
    restrict_tools_to_names as _restrict_tools_to_names_impl,
)
from .types import ExecutionRequest, ToolUsePolicy


async def _await_if_needed(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


_PUBLIC_LEGACY_STREAM_HOOK_NAMES = (
    "truncate_tool_calls_after_navigation",
    "should_retry_tool_contract_breach",
    "should_retry_web_research_contract_breach",
    "analyze_post_tool_contract_breach",
    "restrict_tools_to_names",
    "log_tool_contract_diagnostics",
    "finalize_partial_output",
    "finalize_completed_output",
)


def _resolve_compat_callable(
    engine: Any,
    *candidate_names: str,
    fallback: Callable[..., Any],
) -> Callable[..., Any]:
    for name in candidate_names:
        value = getattr(engine, name, None)
        if callable(value):
            return value
    return fallback


def _noop_log_tool_contract_diagnostics(**_kwargs: Any) -> None:
    return None


def _should_prefer_public_legacy_helpers(engine: Any) -> bool:
    public_count = sum(
        1
        for name in _PUBLIC_LEGACY_STREAM_HOOK_NAMES
        if callable(getattr(engine, name, None))
    )
    return public_count == len(_PUBLIC_LEGACY_STREAM_HOOK_NAMES)


def _compat_candidates(
    *,
    public_name: str,
    private_name: str | None = None,
    prefer_public: bool,
) -> tuple[str, ...]:
    candidates: list[str] = []
    if prefer_public:
        candidates.append(public_name)
    if private_name:
        candidates.append(private_name)
    return tuple(candidates)


@dataclass(slots=True)
class LegacyStreamRuntimeHooks:
    """Compat shim for legacy BaseEngine helper names and stubs."""

    truncate_tool_calls_after_navigation: Callable[
        [list[dict[str, Any]]],
        tuple[list[dict[str, Any]], bool],
    ]
    should_retry_tool_contract_breach: Callable[
        ...,
        tuple[bool, ToolUsePolicy | None, str],
    ]
    should_retry_web_research_contract_breach: Callable[
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
    _finalize_partial_output: Callable[..., Any]
    _finalize_completed_output: Callable[..., Any]

    @classmethod
    def from_engine(
        cls,
        engine: Any,
        *,
        finalize_partial_fallback: Callable[..., Awaitable[tuple[str, int, int]]],
        finalize_completed_fallback: Callable[..., Awaitable[tuple[str, int, int]]],
    ) -> LegacyStreamRuntimeHooks:
        prefer_public_legacy_helpers = _should_prefer_public_legacy_helpers(engine)
        return cls(
            truncate_tool_calls_after_navigation=_resolve_compat_callable(
                engine,
                *_compat_candidates(
                    public_name="truncate_tool_calls_after_navigation",
                    private_name="_truncate_tool_calls_after_navigation",
                    prefer_public=prefer_public_legacy_helpers,
                ),
                fallback=truncate_tool_calls_after_page_navigation,
            ),
            should_retry_tool_contract_breach=_resolve_compat_callable(
                engine,
                *_compat_candidates(
                    public_name="should_retry_tool_contract_breach",
                    private_name="_should_retry_tool_contract_breach",
                    prefer_public=prefer_public_legacy_helpers,
                ),
                fallback=_should_retry_tool_contract_breach_impl,
            ),
            should_retry_web_research_contract_breach=_resolve_compat_callable(
                engine,
                *_compat_candidates(
                    public_name="should_retry_web_research_contract_breach",
                    private_name="_should_retry_web_research_contract_breach",
                    prefer_public=prefer_public_legacy_helpers,
                ),
                fallback=_should_retry_web_research_contract_breach_impl,
            ),
            analyze_post_tool_contract_breach=_resolve_compat_callable(
                engine,
                *_compat_candidates(
                    public_name="analyze_post_tool_contract_breach",
                    private_name="_analyze_post_tool_contract_breach",
                    prefer_public=prefer_public_legacy_helpers,
                ),
                fallback=_analyze_post_tool_contract_breach_impl,
            ),
            restrict_tools_to_names=_resolve_compat_callable(
                engine,
                *_compat_candidates(
                    public_name="restrict_tools_to_names",
                    private_name="_restrict_tools_to_names",
                    prefer_public=prefer_public_legacy_helpers,
                ),
                fallback=_restrict_tools_to_names_impl,
            ),
            log_tool_contract_diagnostics=_resolve_compat_callable(
                engine,
                *_compat_candidates(
                    public_name="log_tool_contract_diagnostics",
                    private_name="_log_tool_contract_diagnostics",
                    prefer_public=prefer_public_legacy_helpers,
                ),
                fallback=_noop_log_tool_contract_diagnostics,
            ),
            _finalize_partial_output=_resolve_compat_callable(
                engine,
                *_compat_candidates(
                    public_name="finalize_partial_output",
                    prefer_public=prefer_public_legacy_helpers,
                ),
                fallback=finalize_partial_fallback,
            ),
            _finalize_completed_output=_resolve_compat_callable(
                engine,
                *_compat_candidates(
                    public_name="finalize_completed_output",
                    prefer_public=prefer_public_legacy_helpers,
                ),
                fallback=finalize_completed_fallback,
            ),
        )

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
        return await _await_if_needed(
            self._finalize_partial_output(
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
        return await _await_if_needed(
            self._finalize_completed_output(
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


def resolve_stream_runtime_hooks(
    engine: Any,
    *,
    finalize_partial_fallback: Callable[..., Awaitable[tuple[str, int, int]]],
    finalize_completed_fallback: Callable[..., Awaitable[tuple[str, int, int]]],
) -> StreamRuntimeHookSource:
    explicit = resolve_explicit_stream_runtime_hooks(engine)
    if explicit is not None:
        return explicit
    return LegacyStreamRuntimeHooks.from_engine(
        engine,
        finalize_partial_fallback=finalize_partial_fallback,
        finalize_completed_fallback=finalize_completed_fallback,
    )


__all__ = ["LegacyStreamRuntimeHooks", "resolve_stream_runtime_hooks"]
