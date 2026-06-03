"""中文: AI 测试模块分类标记。

EN: AI test module classification marker.

Test type: structural / behavioral
Scope: Existing AI tests in this module; no real-dialogue smoke acceptance is claimed.
"""

from __future__ import annotations

import sys
import types
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

from app.ai.types import ChatMessage

ENGINE_DIR = Path(__file__).resolve().parents[3] / "app" / "ai" / "engine"
if "app.ai.engine" not in sys.modules:
    engine_pkg = types.ModuleType("app.ai.engine")
    engine_pkg.__path__ = [str(ENGINE_DIR)]
    sys.modules["app.ai.engine"] = engine_pkg

stream_output_projection = import_module("app.ai.engine.stream_output_projection")
assistant_message_has_content = stream_output_projection.assistant_message_has_content
build_budget_exit_fallback_output = (
    stream_output_projection.build_budget_exit_fallback_output
)
current_turn_has_finalized_output = (
    stream_output_projection.current_turn_has_finalized_output
)
is_streamed_prefix_expansion = stream_output_projection.is_streamed_prefix_expansion
should_preserve_streamed_assistant_output = (
    stream_output_projection.should_preserve_streamed_assistant_output
)


def test_assistant_message_has_content_matches_last_assistant_text() -> None:
    messages = [
        ChatMessage(role="user", content="hello"),
        ChatMessage(role="assistant", content="first"),
        ChatMessage(role="assistant", content="final answer"),
    ]

    assert assistant_message_has_content(messages, "final answer") is True
    assert assistant_message_has_content(messages, "missing") is False


def test_current_turn_has_finalized_output_accepts_matching_assistant_message() -> None:
    messages = [
        ChatMessage(role="assistant", content="stream preview"),
        ChatMessage(role="assistant", content="final answer"),
    ]

    assert (
        current_turn_has_finalized_output(
            messages=messages,
            streamed_output="stream preview",
            finalized_output="final answer",
        )
        is True
    )


def test_current_turn_has_finalized_output_requires_persisted_assistant_message() -> (
    None
):
    messages = [
        ChatMessage(role="assistant", content="stream preview"),
    ]

    assert (
        current_turn_has_finalized_output(
            messages=messages,
            streamed_output="final answer",
            finalized_output="final answer",
        )
        is False
    )


def test_should_preserve_streamed_assistant_output_only_for_prefix_expansion() -> None:
    assert (
        is_streamed_prefix_expansion(
            streamed_output="final answer with more detail",
            finalized_output="final answer",
        )
        is True
    )
    assert (
        should_preserve_streamed_assistant_output(
            final_output_source="assistant",
            streamed_output="final answer with more detail",
            finalized_output="final answer",
        )
        is True
    )
    assert (
        should_preserve_streamed_assistant_output(
            final_output_source="tool_evidence_completed",
            streamed_output="final answer with more detail",
            finalized_output="final answer",
        )
        is False
    )


def test_build_budget_exit_fallback_output_uses_resolved_locale(
    monkeypatch,
) -> None:
    helpers = stream_output_projection

    monkeypatch.setattr(helpers, "resolve_budget_exit_locale", lambda _input: "zh-CN")
    monkeypatch.setattr(
        helpers,
        "_",
        lambda key, *, locale=None: f"{key}:{locale}",
    )

    output = build_budget_exit_fallback_output(
        SimpleNamespace(request=SimpleNamespace(input_variables={"locale": "zh-CN"})),
        tool_results=[],
    )

    assert output == "ai.stream.partial.budget_exit:zh-CN"
