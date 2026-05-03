"""
Test type: behavioral
Scope: web_search query-year rewriting across builtin/public search entrypoints.
Mock strategy: only wall-clock year is patched; query policy logic runs real.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.ai.tools.executors import builtin_executor as legacy_builtin_executor
from app.ai.tools.executors.builtin import search_support
from app.ai.web_search import public_html_policy


def test_web_search_year_policy_preserves_user_requested_non_current_year() -> None:
    query = "帮我搜索一下2025年大模型使用token排行"

    with (
        patch("app.ai.web_search.public_html_policy.datetime") as public_datetime,
        patch(
            "app.ai.tools.executors.builtin.search_support.datetime"
        ) as support_datetime,
        patch("app.ai.tools.executors.builtin_executor.datetime") as legacy_datetime,
    ):
        public_datetime.now.return_value = SimpleNamespace(year=2026)
        support_datetime.now.return_value = SimpleNamespace(year=2026)
        legacy_datetime.now.return_value = SimpleNamespace(year=2026)

        assert public_html_policy.correct_query_year(query) == query
        assert search_support.correct_query_year(query) == query
        assert legacy_builtin_executor._correct_query_year(query) == query


def test_web_search_year_policy_updates_stale_year_for_currentness_queries() -> None:
    query = "最新 2025 年大模型使用 token 排行"

    with (
        patch("app.ai.web_search.public_html_policy.datetime") as public_datetime,
        patch(
            "app.ai.tools.executors.builtin.search_support.datetime"
        ) as support_datetime,
        patch("app.ai.tools.executors.builtin_executor.datetime") as legacy_datetime,
    ):
        public_datetime.now.return_value = SimpleNamespace(year=2026)
        support_datetime.now.return_value = SimpleNamespace(year=2026)
        legacy_datetime.now.return_value = SimpleNamespace(year=2026)

        assert public_html_policy.correct_query_year(query) == (
            "最新 2026 年大模型使用 token 排行"
        )
        assert search_support.correct_query_year(query) == (
            "最新 2026 年大模型使用 token 排行"
        )
        assert legacy_builtin_executor._correct_query_year(query) == (
            "最新 2026 年大模型使用 token 排行"
        )
