from __future__ import annotations

from app.ai.page_locale import page_language_name
from app.ai.prompt_contracts import render_prompt_contract


def test_page_language_name_prefers_native_chinese_label() -> None:
    assert page_language_name("zh_CN") == "中文(Chinese)"
    assert page_language_name("en") == "English"


def test_page_locale_thinking_prompt_is_bilingual_with_chinese_first() -> None:
    prompt = render_prompt_contract(
        "page_locale_thinking",
        page_locale="zh_CN",
        page_language=page_language_name("zh_CN"),
    )

    assert prompt.startswith("[页面语言 / PAGE LANGUAGE]")
    assert "当前页面语言：zh_CN。" in prompt
    assert "请使用 中文(Chinese) 进行思考推理和最终回复。" in prompt
    assert (
        "Write the visible thinking/reasoning stream and the final answer in 中文(Chinese)."
        in prompt
    )
