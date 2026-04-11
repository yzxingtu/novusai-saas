from __future__ import annotations

from app.ai.page_locale import (
    infer_page_locale_from_page_context,
    infer_user_message_locale,
    looks_like_locale_key,
    page_language_name,
    resolve_page_locale,
    resolve_visible_reply_locale,
)
from app.ai.prompt_contracts import render_prompt_contract
from app.ai.types import ChatMessage


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


def test_visible_output_locale_prompt_is_bilingual_with_chinese_first() -> None:
    prompt = render_prompt_contract(
        "visible_output_locale",
        reply_locale="zh_CN",
        reply_language=page_language_name("zh_CN"),
    )

    assert prompt.startswith("[可见输出语言 / VISIBLE OUTPUT LANGUAGE]")
    assert "本轮可见输出默认语言：zh_CN。" in prompt
    assert "请使用 中文(Chinese) 进行可见的思考推理和最终回复。" in prompt
    assert (
        "Write the visible thinking/reasoning stream and the final answer in 中文(Chinese)."
        in prompt
    )


def test_looks_like_locale_key_detects_route_meta_keys() -> None:
    assert looks_like_locale_key("page.dashboard.title") is True
    assert looks_like_locale_key("admin.ai.agents.title") is True
    assert looks_like_locale_key("Dashboard") is False
    assert looks_like_locale_key("仪表盘") is False


def test_infer_page_locale_ignores_locale_keys_without_real_language_signal() -> None:
    assert (
        infer_page_locale_from_page_context(
            {
                "page_key": "tenant.dashboard",
                "page_title": "page.dashboard.title",
            }
        )
        is None
    )


def test_resolve_page_locale_prefers_explicit_locale_over_route_title_key() -> None:
    assert (
        resolve_page_locale(
            {
                "page_context": {
                    "page_key": "tenant.dashboard",
                    "page_title": "page.dashboard.title",
                    "locale": "zh-CN",
                }
            }
        )
        == "zh_CN"
    )


def test_infer_user_message_locale_requires_stronger_english_signal() -> None:
    assert infer_user_message_locale("请帮我看下天气") == "zh_CN"
    assert infer_user_message_locale("Weather in Shanghai today?") == "en"
    assert infer_user_message_locale("Okay") is None


def test_resolve_visible_reply_locale_prefers_latest_user_language_signal() -> None:
    assert (
        resolve_visible_reply_locale(
            [
                ChatMessage(role="user", content="How is the weather in Shanghai today?"),
            ],
            {
                "page_context": {
                    "locale": "zh-CN",
                }
            },
        )
        == "en"
    )


def test_resolve_visible_reply_locale_skips_ambiguous_confirmation_and_uses_prior_user_language() -> None:
    assert (
        resolve_visible_reply_locale(
            [
                ChatMessage(role="user", content="请查一下北京今天的天气。"),
                ChatMessage(role="assistant", content=""),
                ChatMessage(role="user", content="Okay"),
            ],
            {
                "page_context": {
                    "locale": "en",
                }
            },
        )
        == "zh_CN"
    )
