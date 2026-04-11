"""Explicit prep/state/runtime seam for stream generation support."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

from app.ai.types import ChatMessage

from .stream_output_helpers import (
    current_turn_has_finalized_output as _current_turn_has_finalized_output_impl,
)
from .stream_output_helpers import (
    last_visible_assistant_content as _last_visible_assistant_content_impl,
)
from .stream_output_helpers import (
    should_preserve_streamed_assistant_output as _should_preserve_streamed_assistant_output_impl,
)
from .stream_output_helpers import (
    should_replay_finalized_output as _should_replay_finalized_output_impl,
)
from .stream_tool_call_helpers import (
    chunk_text_for_streaming as _chunk_text_for_streaming_impl,
)


@dataclass(slots=True, frozen=True)
class StreamGenerationPrepView:
    """Stable prep data consumed by stream-generation helpers."""

    stream_runtime: Any = None
    tool_planner: dict[str, Any] | None = None
    rag_source_kinds: list[str] = None  # type: ignore[assignment]
    context_compacted: bool = False
    memory_flush_triggered: bool = False
    memory_recalled: bool = False
    prune_stats: dict[str, Any] | None = None
    execution_path: str | None = None

    @classmethod
    def from_source(cls, source: Any) -> StreamGenerationPrepView:
        return cls(
            stream_runtime=getattr(source, "stream_runtime", None),
            tool_planner=getattr(source, "tool_planner", None),
            rag_source_kinds=list(getattr(source, "rag_source_kinds", []) or []),
            context_compacted=bool(getattr(source, "context_compacted", False)),
            memory_flush_triggered=bool(
                getattr(source, "memory_flush_triggered", False)
            ),
            memory_recalled=bool(getattr(source, "memory_recalled", False)),
            prune_stats=getattr(source, "prune_stats", None),
            execution_path=getattr(source, "execution_path", None),
        )


class StreamGenerationStateView:
    """Read-only projection of execution state for generation support."""

    def __init__(self, source: Any) -> None:
        self._source = source

    @property
    def provider_failure_kind(self) -> Any:
        return getattr(self._source, "provider_failure_kind", None)

    @property
    def intent_plan(self) -> list[Any]:
        return list(getattr(self._source, "intent_plan", []) or [])

    @property
    def budget(self) -> Any:
        return getattr(self._source, "budget", None)

    @property
    def recovery_history(self) -> list[Any]:
        return list(getattr(self._source, "recovery_history", []) or [])

    @property
    def provider_events(self) -> list[Any]:
        return list(getattr(self._source, "provider_events", []) or [])

    def build_diagnostics_payload(self) -> dict[str, Any]:
        builder = getattr(self._source, "build_diagnostics_payload", None)
        if not callable(builder):
            return {}
        payload = builder() or {}
        return dict(payload) if isinstance(payload, dict) else {}


class StreamGenerationRuntimeStateView:
    """Mutable runtime state proxy used during stream generation."""

    def __init__(self, source: Any, *, default_next_runtime_context: Any) -> None:
        self._source = source
        self._default_next_runtime_context = default_next_runtime_context

    def _get(self, name: str, default: Any = None) -> Any:
        return getattr(self._source, name, default)

    def _set(self, name: str, value: Any) -> None:
        setattr(self._source, name, value)

    def reset(self) -> None:
        self.output = ""
        self.reasoning_output = ""
        self.total_tokens = 0
        self.completion_tokens_used = 0
        self.runtime_model_info = None
        self.runtime_turn_record = None
        self.runtime_turn_record_source = None
        self.runtime_turn_record_overlays = {}
        self.on_complete_called = False
        self.visible_stream_content = ""
        self.clear_before_next_message = False
        self.next_runtime_context = self._default_next_runtime_context

    @property
    def output(self) -> str:
        return str(self._get("_output", "") or "")

    @output.setter
    def output(self, value: Any) -> None:
        self._set("_output", str(value or ""))

    @property
    def reasoning_output(self) -> str:
        return str(self._get("_reasoning_output", "") or "")

    @reasoning_output.setter
    def reasoning_output(self, value: Any) -> None:
        self._set("_reasoning_output", str(value or ""))

    @property
    def total_tokens(self) -> int:
        return int(self._get("_total_tokens", 0) or 0)

    @total_tokens.setter
    def total_tokens(self, value: Any) -> None:
        self._set("_total_tokens", int(value or 0))

    @property
    def completion_tokens_used(self) -> int:
        return int(self._get("_completion_tokens_used", 0) or 0)

    @completion_tokens_used.setter
    def completion_tokens_used(self, value: Any) -> None:
        self._set("_completion_tokens_used", int(value or 0))

    @property
    def runtime_model_info(self) -> Any:
        return self._get("_runtime_model_info", None)

    @runtime_model_info.setter
    def runtime_model_info(self, value: Any) -> None:
        if isinstance(value, dict):
            self._set("_runtime_model_info", dict(value))
            return
        self._set("_runtime_model_info", value)

    @property
    def runtime_turn_record(self) -> Any:
        return self._get("_runtime_turn_record", None)

    @runtime_turn_record.setter
    def runtime_turn_record(self, value: Any) -> None:
        if isinstance(value, dict):
            self._set("_runtime_turn_record", dict(value))
            return
        self._set("_runtime_turn_record", value)

    @property
    def runtime_turn_record_source(self) -> Any:
        return self._get("_runtime_turn_record_source", None)

    @runtime_turn_record_source.setter
    def runtime_turn_record_source(self, value: Any) -> None:
        self._set("_runtime_turn_record_source", value)

    @property
    def runtime_turn_record_overlays(self) -> Any:
        return self._get("_runtime_turn_record_overlays", None)

    @runtime_turn_record_overlays.setter
    def runtime_turn_record_overlays(self, value: Any) -> None:
        if isinstance(value, dict):
            self._set("_runtime_turn_record_overlays", dict(value))
            return
        self._set("_runtime_turn_record_overlays", value)

    @property
    def on_complete_called(self) -> bool:
        return bool(self._get("_on_complete_called", False))

    @on_complete_called.setter
    def on_complete_called(self, value: Any) -> None:
        self._set("_on_complete_called", bool(value))

    @property
    def visible_stream_content(self) -> str:
        return str(self._get("_visible_stream_content", "") or "")

    @visible_stream_content.setter
    def visible_stream_content(self, value: Any) -> None:
        self._set("_visible_stream_content", str(value or ""))

    @property
    def clear_before_next_message(self) -> bool:
        return bool(self._get("_clear_before_next_message", False))

    @clear_before_next_message.setter
    def clear_before_next_message(self, value: Any) -> None:
        self._set("_clear_before_next_message", bool(value))

    @property
    def next_runtime_context(self) -> Any:
        return self._get("_next_runtime_context", None)

    @next_runtime_context.setter
    def next_runtime_context(self, value: Any) -> None:
        self._set("_next_runtime_context", value)


@dataclass(slots=True)
class StreamGenerationView:
    """Explicit dependency bundle for stream_generation_support."""

    request: Any
    start_time: float
    prep: StreamGenerationPrepView
    state: StreamGenerationStateView
    runtime: StreamGenerationRuntimeStateView
    event_queue: Any
    update_turn_progress: Callable[..., None]
    replace_runtime_turn_record: Callable[[Any], None]
    refresh_runtime_turn_record: Callable[[], None]
    messages_to_dicts: Callable[[list[ChatMessage]], list[dict[str, Any]]]
    extract_action_buttons: Callable[[str], tuple[str, list[dict[str, str]] | None]]
    last_visible_assistant_content: Callable[[list[ChatMessage]], str]
    current_turn_has_finalized_output: Callable[..., bool]
    should_replay_finalized_output: Callable[..., bool]
    should_preserve_streamed_assistant_output: Callable[..., bool]
    build_budget_exit_fallback_output: Callable[..., str]
    chunk_text_for_streaming: Callable[..., list[str]]
    resolved_protocol_path: Callable[..., str]

    def reset_runtime_state(self) -> None:
        """Reset stream-local runtime state before running TurnExecutor."""

        self.runtime.reset()

    @property
    def output(self) -> str:
        return self.runtime.output

    @output.setter
    def output(self, value: Any) -> None:
        self.runtime.output = value

    @property
    def reasoning_output(self) -> str:
        return self.runtime.reasoning_output

    @reasoning_output.setter
    def reasoning_output(self, value: Any) -> None:
        self.runtime.reasoning_output = value

    @property
    def visible_stream_content(self) -> str:
        return self.runtime.visible_stream_content

    @visible_stream_content.setter
    def visible_stream_content(self, value: Any) -> None:
        self.runtime.visible_stream_content = value

    @property
    def runtime_model_info(self) -> Any:
        return self.runtime.runtime_model_info

    @runtime_model_info.setter
    def runtime_model_info(self, value: Any) -> None:
        self.runtime.runtime_model_info = value

    @property
    def runtime_turn_record(self) -> Any:
        return self.runtime.runtime_turn_record

    @runtime_turn_record.setter
    def runtime_turn_record(self, value: Any) -> None:
        self.runtime.runtime_turn_record = value

    @property
    def completion_tokens_used(self) -> int:
        return self.runtime.completion_tokens_used

    @completion_tokens_used.setter
    def completion_tokens_used(self, value: Any) -> None:
        self.runtime.completion_tokens_used = value

    @property
    def total_tokens(self) -> int:
        return self.runtime.total_tokens

    @total_tokens.setter
    def total_tokens(self, value: Any) -> None:
        self.runtime.total_tokens = value

    @property
    def provider_failure_kind(self) -> Any:
        return self.state.provider_failure_kind

    @property
    def intent_plan(self) -> list[Any]:
        return self.state.intent_plan

    @property
    def budget_snapshot(self) -> Any:
        return self.state.budget

    @property
    def recovery_history_dicts(self) -> list[dict[str, Any]]:
        return [_message_to_dict(item) for item in (self.state.recovery_history or [])]

    @property
    def provider_events(self) -> list[Any]:
        return self.state.provider_events

    def build_diagnostics_payload(self) -> dict[str, Any]:
        return self.state.build_diagnostics_payload()

    @property
    def rag_source_kinds(self) -> list[str]:
        return list(self.prep.rag_source_kinds or [])

    @property
    def context_compacted(self) -> bool:
        return bool(self.prep.context_compacted)

    @property
    def memory_flush_triggered(self) -> bool:
        return bool(self.prep.memory_flush_triggered)

    @property
    def memory_recalled(self) -> bool:
        return bool(self.prep.memory_recalled)

    @property
    def prune_stats(self) -> dict[str, Any] | None:
        return self.prep.prune_stats

    @property
    def tool_planner(self) -> dict[str, Any] | None:
        return self.prep.tool_planner

    @property
    def execution_path(self) -> str | None:
        return self.prep.execution_path


def _message_to_dict(message: Any) -> dict[str, Any]:
    if is_dataclass(message):
        return asdict(message)
    model_dump = getattr(message, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return dict(dumped)
    if hasattr(message, "__dict__"):
        return dict(getattr(message, "__dict__", {}) or {})
    return {
        "role": getattr(message, "role", None),
        "content": getattr(message, "content", None),
    }


def _messages_to_dicts_fallback(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    return [_message_to_dict(message) for message in messages]


def _apply_runtime_turn_record_overlays(
    runtime: StreamGenerationRuntimeStateView,
) -> None:
    if not isinstance(runtime.runtime_turn_record, dict):
        runtime.runtime_turn_record = {}
    if not isinstance(runtime.runtime_turn_record_overlays, dict):
        runtime.runtime_turn_record_overlays = {}
    if not runtime.runtime_turn_record_overlays:
        return

    record = dict(runtime.runtime_turn_record)
    for key, value in runtime.runtime_turn_record_overlays.items():
        if key == "tool_loop_progress" and isinstance(value, dict):
            current_progress = (
                dict(record.get("tool_loop_progress") or {})
                if isinstance(record.get("tool_loop_progress"), dict)
                else {}
            )
            current_progress.update(value)
            record[key] = current_progress
            continue
        record[key] = value
    runtime.runtime_turn_record = record


def _replace_runtime_turn_record_fallback(
    runtime: StreamGenerationRuntimeStateView,
    raw_turn_record: Any,
) -> None:
    if isinstance(raw_turn_record, dict):
        runtime.runtime_turn_record_source = None
        runtime.runtime_turn_record = dict(raw_turn_record)
    elif raw_turn_record is not None and hasattr(raw_turn_record, "__dict__"):
        runtime.runtime_turn_record_source = raw_turn_record
        runtime.runtime_turn_record = dict(getattr(raw_turn_record, "__dict__", {}) or {})
    else:
        return
    _apply_runtime_turn_record_overlays(runtime)


def _refresh_runtime_turn_record_fallback(
    runtime: StreamGenerationRuntimeStateView,
) -> None:
    source = runtime.runtime_turn_record_source
    if source is not None and hasattr(source, "__dict__"):
        runtime.runtime_turn_record = dict(getattr(source, "__dict__", {}) or {})
    elif not isinstance(runtime.runtime_turn_record, dict):
        runtime.runtime_turn_record = {}
    _apply_runtime_turn_record_overlays(runtime)


def _resolved_protocol_path_fallback(
    runtime: StreamGenerationRuntimeStateView,
    *,
    diagnostics_payload: dict[str, Any] | None = None,
    turn_record: dict[str, Any] | None = None,
    response_metadata: dict[str, Any] | None = None,
) -> str:
    candidates = [
        (diagnostics_payload or {}).get("protocol_path"),
        (turn_record or {}).get("protocol_path"),
        (response_metadata or {}).get("protocol_path"),
        (runtime.runtime_turn_record or {}).get("protocol_path")
        if isinstance(runtime.runtime_turn_record, dict)
        else None,
        (runtime.runtime_model_info or {}).get("wire_api")
        if isinstance(runtime.runtime_model_info, dict)
        else None,
    ]
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return value
    return "chat_completions"


def build_stream_generation_view(source: Any) -> StreamGenerationView:
    if isinstance(source, StreamGenerationView):
        return source

    prep_source = getattr(source, "prep", None)
    engine = getattr(source, "engine", None)
    runtime = StreamGenerationRuntimeStateView(
        source,
        default_next_runtime_context=getattr(prep_source, "stream_runtime", None),
    )
    update_turn_progress = getattr(source, "_update_turn_progress", None)
    replace_runtime_turn_record = getattr(source, "_replace_runtime_turn_record", None)
    refresh_runtime_turn_record = getattr(source, "_refresh_runtime_turn_record", None)
    resolved_protocol_path = getattr(source, "_resolved_protocol_path", None)
    messages_to_dicts = getattr(engine, "_messages_to_dicts", None)
    extract_action_buttons = getattr(source, "_extract_action_buttons", None)
    last_visible_assistant_content = getattr(
        source,
        "_last_visible_assistant_content",
        None,
    )
    current_turn_has_finalized_output = getattr(
        source,
        "_current_turn_has_finalized_output",
        None,
    )
    should_replay_finalized_output = getattr(
        source,
        "_should_replay_finalized_output",
        None,
    )
    should_preserve_streamed_assistant_output = getattr(
        source,
        "_should_preserve_streamed_assistant_output",
        None,
    )
    build_budget_exit_fallback_output = getattr(
        source,
        "_build_budget_exit_fallback_output",
        None,
    )
    chunk_text_for_streaming = getattr(source, "_chunk_text_for_streaming", None)

    return StreamGenerationView(
        request=getattr(source, "request", None),
        start_time=float(getattr(source, "start_time", 0.0) or 0.0),
        prep=StreamGenerationPrepView.from_source(prep_source),
        state=StreamGenerationStateView(getattr(source, "_state", None)),
        runtime=runtime,
        event_queue=getattr(source, "_event_queue", None),
        update_turn_progress=(
            update_turn_progress if callable(update_turn_progress) else lambda **_fields: None
        ),
        replace_runtime_turn_record=(
            replace_runtime_turn_record
            if callable(replace_runtime_turn_record)
            else lambda raw_turn_record: _replace_runtime_turn_record_fallback(
                runtime,
                raw_turn_record,
            )
        ),
        refresh_runtime_turn_record=(
            refresh_runtime_turn_record
            if callable(refresh_runtime_turn_record)
            else lambda: _refresh_runtime_turn_record_fallback(runtime)
        ),
        messages_to_dicts=(
            messages_to_dicts
            if callable(messages_to_dicts)
            else _messages_to_dicts_fallback
        ),
        extract_action_buttons=(
            extract_action_buttons
            if callable(extract_action_buttons)
            else lambda output: (output, None)
        ),
        last_visible_assistant_content=(
            last_visible_assistant_content
            if callable(last_visible_assistant_content)
            else _last_visible_assistant_content_impl
        ),
        current_turn_has_finalized_output=(
            current_turn_has_finalized_output
            if callable(current_turn_has_finalized_output)
            else _current_turn_has_finalized_output_impl
        ),
        should_replay_finalized_output=(
            should_replay_finalized_output
            if callable(should_replay_finalized_output)
            else _should_replay_finalized_output_impl
        ),
        should_preserve_streamed_assistant_output=(
            should_preserve_streamed_assistant_output
            if callable(should_preserve_streamed_assistant_output)
            else _should_preserve_streamed_assistant_output_impl
        ),
        build_budget_exit_fallback_output=(
            build_budget_exit_fallback_output
            if callable(build_budget_exit_fallback_output)
            else lambda **_kwargs: ""
        ),
        chunk_text_for_streaming=(
            chunk_text_for_streaming
            if callable(chunk_text_for_streaming)
            else lambda text, chunk_size=32: _chunk_text_for_streaming_impl(
                text,
                chunk_size=chunk_size,
            )
        ),
        resolved_protocol_path=(
            resolved_protocol_path
            if callable(resolved_protocol_path)
            else lambda **kwargs: _resolved_protocol_path_fallback(runtime, **kwargs)
        ),
    )


def ensure_stream_generation_view(source: Any) -> StreamGenerationView:
    """Compat alias used by stream_generation_support."""

    return build_stream_generation_view(source)


__all__ = [
    "StreamGenerationPrepView",
    "StreamGenerationRuntimeStateView",
    "StreamGenerationStateView",
    "StreamGenerationView",
    "build_stream_generation_view",
]
