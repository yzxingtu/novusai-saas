"""
Test type: behavioral
Scope: explicit builtin web-search request policy.
Mock strategy: no mocks; verifies deterministic text policy decisions.
"""

from app.ai.web_search.request_policy import is_explicit_builtin_web_search_request


def test_generic_search_about_tools_still_prefers_native_path() -> None:
    assert (
        is_explicit_builtin_web_search_request(
            "联网搜索最新 AI 工具发布，给我三个来源",
        )
        is False
    )
    assert (
        is_explicit_builtin_web_search_request(
            "请搜索 web search tool design 的最新资料",
        )
        is False
    )


def test_direct_tool_names_require_token_boundary() -> None:
    assert (
        is_explicit_builtin_web_search_request("请调用 web_search 工具搜索新闻") is True
    )
    assert (
        is_explicit_builtin_web_search_request("请用 `fetch_url` 抓取这个页面") is True
    )
    assert (
        is_explicit_builtin_web_search_request(
            "解释 response.web_search_call 事件是什么意思",
        )
        is False
    )
    assert (
        is_explicit_builtin_web_search_request(
            "fetch_url_not_allowed 这个错误怎么排查？",
        )
        is False
    )


def test_flexible_builtin_search_phrases_are_explicit() -> None:
    assert (
        is_explicit_builtin_web_search_request("请使用联网搜索技能查今天新闻") is True
    )
    assert (
        is_explicit_builtin_web_search_request("请用内置的搜索工具查今天新闻") is True
    )
    assert is_explicit_builtin_web_search_request("走一下内置的联网搜索") is True
    assert (
        is_explicit_builtin_web_search_request("使用系统内置的搜索能力查这个 URL")
        is True
    )
    assert (
        is_explicit_builtin_web_search_request("please use the built-in web search")
        is True
    )
    assert (
        is_explicit_builtin_web_search_request(
            "using the search tool, compare today's releases",
        )
        is True
    )
