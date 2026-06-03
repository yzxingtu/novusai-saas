"""Tests for OpenAI adapter reasoning delta separation. / OpenAI 适配器 reasoning 增量分离测试。"""

from __future__ import annotations

from types import SimpleNamespace

from app.ai.adapters.openai_adapter import OpenAIAdapter


def test_convert_chat_chunk_keeps_reasoning_delta_separate() -> None:
    adapter = OpenAIAdapter(api_key="test-key", base_url="https://api.example.com")

    chunk = SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    content="",
                    reasoning_content="先分析用户意图，再决定调用哪个工具。",
                    role="assistant",
                    tool_calls=None,
                ),
                finish_reason=None,
            )
        ],
        usage=None,
    )

    result = adapter._convert_chat_chunk(chunk, "deepseek-chat")

    assert result.delta == ""
    assert result.reasoning_delta == "先分析用户意图，再决定调用哪个工具。"
