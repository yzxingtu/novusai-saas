from __future__ import annotations

from types import SimpleNamespace

from app.ai.adapters.openai_adapter import OpenAIAdapter


def _make_adapter() -> OpenAIAdapter:
    return OpenAIAdapter.__new__(OpenAIAdapter)


def test_extract_reasoning_from_summary() -> None:
    adapter = _make_adapter()
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="reasoning",
                summary=[SimpleNamespace(text="思考过程")],
                content=None,
            )
        ]
    )

    assert adapter._extract_responses_reasoning_text(response) == "思考过程"


def test_extract_reasoning_from_content_string() -> None:
    adapter = _make_adapter()
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="reasoning",
                content="直接内容",
                summary=[],
            )
        ]
    )

    assert adapter._extract_responses_reasoning_text(response) == "直接内容"


def test_extract_reasoning_from_content_list() -> None:
    adapter = _make_adapter()
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="reasoning",
                content=[SimpleNamespace(text="列表内容")],
                summary=[],
            )
        ]
    )

    assert adapter._extract_responses_reasoning_text(response) == "列表内容"


def test_extract_reasoning_from_top_level_reasoning_content() -> None:
    adapter = _make_adapter()
    response = SimpleNamespace(
        output=[SimpleNamespace(type="message", content=[])],
        reasoning_content="顶级思考",
    )

    assert adapter._extract_responses_reasoning_text(response) == "顶级思考"


def test_extract_reasoning_from_top_level_reasoning() -> None:
    adapter = _make_adapter()
    response = SimpleNamespace(
        output=[],
        reasoning="顶级 reasoning",
    )

    assert adapter._extract_responses_reasoning_text(response) == "顶级 reasoning"


def test_extract_reasoning_returns_none_when_empty() -> None:
    adapter = _make_adapter()
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="message",
                content=[SimpleNamespace(type="output_text", text="普通文本")],
            )
        ]
    )

    assert adapter._extract_responses_reasoning_text(response) is None
