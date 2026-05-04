"""
Test type: behavioral
Scope: builtin web-search orchestration, builtin tool injection, cache isolation,
and provider-config disable behavior.
Mock strategy: orchestrator logic runs real while public provider/network
boundaries are faked. No LLM, native search, or provider-hosted search return is
mocked into the expected answer.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.skills.resolver import SkillResolver, SkillResolveResult
from app.ai.web_research import SearchOptions
from app.ai.web_research.providers import BuiltinWebSearchProvider
from app.ai.web_search import orchestrator as ws_orchestrator
from app.ai.web_search import public_html as public_html
from app.ai.web_search.orchestrator import WebSearchOrchestrator
from app.ai.web_search.public_html import PublicHtmlSearchProvider
from app.ai.web_search.types import (
    PROVIDER_MODE_PUBLIC,
    STATUS_NO_RESULTS,
    STATUS_SUCCESS,
    STATUS_UNSUPPORTED,
    STATUS_UPSTREAM_ERROR,
    WEB_SEARCH_POLICY_BUILTIN_PUBLIC,
    SearchProviderRun,
    SearchResultItem,
)


@pytest.fixture(autouse=True)
def _clear_orchestrator_state() -> None:
    ws_orchestrator._DUPLICATE_QUERY_SIGNATURES.clear()
    public_html._BACKEND_QUERY_CACHE.clear()
    public_html._BACKEND_FAIL_STREAK.clear()
    public_html._BACKEND_DISABLED.clear()


def _make_context(conversation_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        conversation_id=conversation_id,
        variables={},
        runtime_provider_name="OpenAI",
        runtime_model_code="gpt-5.4",
    )


def _make_item(
    *,
    title: str = "Example",
    url: str = "https://example.com",
    snippet: str = "summary",
    source: str = "public:baidu",
    provider: str = "baidu_public",
    provider_mode: str = PROVIDER_MODE_PUBLIC,
    rank: int = 1,
) -> SearchResultItem:
    return SearchResultItem(
        title=title,
        url=url,
        snippet=snippet,
        source=source,
        provider=provider,
        provider_mode=provider_mode,
        rank=rank,
    )


def _make_public_run(
    *,
    status: str,
    items: list[SearchResultItem] | None = None,
    failure_reason: str | None = None,
    backend_key: str | None = "public:baidu",
    cache_hit: bool = False,
) -> SearchProviderRun:
    return SearchProviderRun(
        provider="baidu_public" if status == STATUS_SUCCESS else None,
        provider_mode=PROVIDER_MODE_PUBLIC,
        backend_key=backend_key,
        status=status,
        items=list(items or []),
        failure_reason=failure_reason,
        attempted_backends=[backend_key] if backend_key else [],
        cache_hit=cache_hit,
    )


def test_skill_resolver_injects_baseline_web_research_tools() -> None:
    """
    Test type: structural
    """

    result = SkillResolveResult()
    SkillResolver()._inject_baseline_runtime_builtins(result)

    tool_names = [tool.name for tool in result.tools]
    assert tool_names == ["get_current_time", "web_search", "fetch_url"]
    assert result.tool_consent_modes["get_current_time"] == "auto"
    assert result.tool_consent_modes["web_search"] == "auto"
    assert result.tool_consent_modes["fetch_url"] == "auto"
    assert any(tool.semantic_family == "web_research" for tool in result.tools)


@pytest.mark.asyncio
async def test_skill_resolver_does_not_resolve_runtime_builtins_from_db_skills() -> (
    None
):
    """
    Test type: structural
    """

    package = SimpleNamespace(
        id=100,
        name="legacy.runtime",
        source_plugin=None,
        valves_config=None,
        is_active=True,
        is_deleted=False,
    )
    result = await SkillResolver().resolve(
        [
            SimpleNamespace(
                id=1,
                name="editor_ops",
                type="builtin",
                config={},
                package_id=package.id,
                package=package,
                is_active=True,
                is_deleted=False,
                input_schema=None,
                description="Legacy rich text skill",
                timeout=30,
            ),
            SimpleNamespace(
                id=2,
                name="legacy_bundle",
                type="builtin",
                config={
                    "tools": [
                        {"name": "web_search"},
                        {"name": "crm_lookup"},
                        {"name": "custom_builtin_tool"},
                    ]
                },
                package_id=package.id,
                package=package,
                is_active=True,
                is_deleted=False,
                input_schema=None,
                description="Legacy bundle",
                timeout=30,
            ),
        ]
    )

    assert [tool.name for tool in result.tools] == [
        "crm_lookup",
        "custom_builtin_tool",
    ]


@pytest.mark.asyncio
async def test_orchestrator_uses_public_builtin_provider_by_default() -> None:
    """
    Test type: behavioral
    """

    orchestrator = WebSearchOrchestrator()
    public_run = _make_public_run(status=STATUS_SUCCESS, items=[_make_item()])

    with patch.object(
        PublicHtmlSearchProvider,
        "search",
        AsyncMock(return_value=public_run),
    ) as public_search:
        execution = await orchestrator.search(
            query="OpenAI",
            max_results=5,
            context=_make_context(),
        )

    assert execution.meta.status == STATUS_SUCCESS
    assert execution.meta.provider == "baidu_public"
    assert execution.meta.provider_mode == PROVIDER_MODE_PUBLIC
    assert execution.meta.selected_backend == "public:baidu"
    assert execution.meta.used_fallback is False
    assert execution.meta.fallback_reason is None
    assert execution.meta.native_failure_kind is None
    assert execution.meta.provider_chain == ["public:baidu"]
    assert "https://example.com" in execution.output
    public_search.assert_awaited_once()
    assert (
        public_search.await_args.kwargs["strategy"] == WEB_SEARCH_POLICY_BUILTIN_PUBLIC
    )


@pytest.mark.asyncio
async def test_orchestrator_returns_public_failure_without_native_retry() -> None:
    """
    Test type: behavioral
    """

    orchestrator = WebSearchOrchestrator()
    public_run = _make_public_run(
        status=STATUS_UPSTREAM_ERROR,
        failure_reason="public:baidu returned unreadable page",
    )

    with patch.object(
        PublicHtmlSearchProvider,
        "search",
        AsyncMock(return_value=public_run),
    ) as public_search:
        execution = await orchestrator.search(
            query="OpenAI",
            max_results=5,
            context=_make_context(),
        )

    assert execution.meta.status == STATUS_UPSTREAM_ERROR
    assert execution.meta.used_fallback is False
    assert execution.meta.fallback_reason is None
    assert execution.meta.native_failure_kind is None
    assert execution.meta.attempted_backends == ["public:baidu"]
    assert "Search source unavailable" in execution.output
    public_search.assert_awaited_once()


@pytest.mark.asyncio
async def test_public_html_filters_baidu_image_wrapper_result_as_no_results() -> None:
    """
    Test type: behavioral
    中文: 回归保护 BUG-2026-05-05-2295，百度图片包装页不能成为可抓取证据。
    EN: Regression for BUG-2026-05-05-2295; Baidu Images wrappers are not fetchable evidence.
    """

    html = """
    <html>
      <body>
        <div class="result c-container">
          <h3>
            <a href="https://image.baidu.com/search/index?tn=baiduimage&word=2026%E5%A5%B3%E6%80%A7%E8%A3%99%E5%AD%90">
              查一下 2026年最热门的 女性裙子款式排行! - 百度图片
            </a>
          </h3>
          <div>9 变清晰 4 变清晰 查看全部4341张图片 免费AI生图 百度图片</div>
        </div>
      </body>
    </html>
    """

    async def fake_fetch_public_html(
        url: str,
        *,
        params: dict[str, str],
        timeout_seconds: int | float,
    ):
        assert url == "https://www.baidu.com/s"
        assert params["wd"] == "查一下 2026年最热门的 女性裙子款式排行！"
        assert timeout_seconds > 0
        return public_html._transport.PublicHtmlResponse(
            status_code=200,
            text=html,
        )

    provider = PublicHtmlSearchProvider(providers=["baidu"])

    with patch.object(
        public_html._transport,
        "fetch_public_html",
        side_effect=fake_fetch_public_html,
    ):
        run = await provider.search(
            query="查一下 2026年最热门的 女性裙子款式排行！",
            max_results=5,
            locale="zh_CN",
            timeout_seconds=15,
            context=_make_context(conversation_id=2295),
            strategy=WEB_SEARCH_POLICY_BUILTIN_PUBLIC,
            runtime_provider_label="OpenAI",
            runtime_model_code="gpt-5.4",
        )

    assert run.status == STATUS_NO_RESULTS
    assert run.items == []
    assert run.failure_reason == "public:baidu returned only low-confidence results"
    assert run.attempted_backends == ["public:baidu"]


def test_public_html_policy_keeps_baidu_redirect_link_candidates() -> None:
    """
    Test type: behavioral
    中文: 百度 /link 跳转仍可由 fetch_url 跟随，不应被包装页策略误杀。
    EN: Baidu /link redirects can still be followed by fetch_url and must remain candidates.
    """

    from app.ai.web_search.public_html_policy import result_passes_relevance

    assert result_passes_relevance(
        "2026 女性裙子款式排行",
        {
            "title": "2026 女性裙子款式流行趋势排行",
            "url": "https://www.baidu.com/link?url=redirect-token",
            "snippet": "整理 2026 年女性裙子款式趋势、热门廓形与搭配。",
        },
    )


@pytest.mark.asyncio
async def test_orchestrator_clamps_public_timeout_to_remaining_tool_budget() -> None:
    """
    Test type: behavioral
    """

    orchestrator = WebSearchOrchestrator()
    public_run = _make_public_run(status=STATUS_SUCCESS, items=[_make_item()])
    context = _make_context()
    context.tool_deadline_monotonic = time.perf_counter() + 7.4

    with patch.object(
        PublicHtmlSearchProvider,
        "search",
        AsyncMock(return_value=public_run),
    ) as public_search:
        execution = await orchestrator.search(
            query="OpenAI",
            max_results=5,
            context=context,
        )

    assert execution.meta.status == STATUS_SUCCESS
    assert public_search.await_args.kwargs["timeout_seconds"] < 15
    assert public_search.await_args.kwargs["timeout_seconds"] <= 7


@pytest.mark.asyncio
async def test_orchestrator_marks_duplicate_queries_with_fetch_guidance() -> None:
    """
    Test type: behavioral
    """

    orchestrator = WebSearchOrchestrator()
    public_run = _make_public_run(status=STATUS_SUCCESS, items=[_make_item()])

    with patch.object(
        PublicHtmlSearchProvider,
        "search",
        AsyncMock(return_value=public_run),
    ):
        first = await orchestrator.search(
            query="OpenAI",
            max_results=5,
            context=_make_context(conversation_id=99),
        )
        second = await orchestrator.search(
            query="OpenAI",
            max_results=5,
            context=_make_context(conversation_id=99),
        )

    assert "[Note: This exact query was already searched" not in first.output
    assert "[Note: This exact query was already searched" in second.output


@pytest.mark.asyncio
async def test_orchestrator_disables_invalid_provider_web_search_config() -> None:
    """
    Test type: behavioral
    """

    provider = SimpleNamespace(
        id=1,
        is_active=True,
        code="openai",
        type="openai_compatible",
        config={"web_search": {"max_results_cap": 0}},
    )
    model = SimpleNamespace(id=2, code="gpt-5.4")
    context = SimpleNamespace(
        db=object(),
        runtime_provider_id=provider.id,
        runtime_model_id=model.id,
        runtime_model_code=model.code,
        runtime_provider_name="OpenAI",
        conversation_id=5,
        variables={},
    )
    provider_repo = AsyncMock()
    provider_repo.get_by_id.return_value = provider
    model_repo = AsyncMock()
    model_repo.get_active_with_provider.return_value = model
    orchestrator = WebSearchOrchestrator()

    with (
        patch.object(
            ws_orchestrator,
            "AIProviderRepository",
            return_value=provider_repo,
        ),
        patch.object(
            ws_orchestrator,
            "AIModelRepository",
            return_value=model_repo,
        ),
        patch.object(
            PublicHtmlSearchProvider,
            "search",
            AsyncMock(),
        ) as public_search,
    ):
        execution = await orchestrator.search(
            query="OpenAI",
            max_results=5,
            context=context,
        )

    assert execution.meta.status == STATUS_UNSUPPORTED
    assert "invalid provider config.web_search" in (execution.meta.failure_reason or "")
    public_search.assert_not_called()


@pytest.mark.asyncio
async def test_builtin_web_research_provider_diagnostics_stay_builtin_public() -> None:
    """
    Test type: structural
    """

    async def search_runner(query: str, max_results: int, context: object) -> object:
        return await WebSearchOrchestrator().search(
            query=query,
            max_results=max_results,
            context=context,
        )

    public_run = _make_public_run(status=STATUS_SUCCESS, items=[_make_item()])
    provider = BuiltinWebSearchProvider(search_runner=search_runner)

    with patch.object(
        PublicHtmlSearchProvider,
        "search",
        AsyncMock(return_value=public_run),
    ):
        results = await provider.search("OpenAI", SearchOptions(max_results=5))

    assert results.status == "completed"
    assert results.provider == "builtin:web_search"
    assert results.items[0].provider == "builtin:web_search"
    assert results.diagnostics["builtin_tool"] == "web_search"
    assert results.diagnostics["selected_backend"] == "public:baidu"
    assert results.diagnostics["provider_mode"] == PROVIDER_MODE_PUBLIC
    assert "used_fallback" not in results.diagnostics
    assert "fallback_reason" not in results.diagnostics
    assert "native_failure_kind" not in results.diagnostics


@pytest.mark.asyncio
async def test_public_html_cache_key_isolated_by_locale_runtime_and_strategy() -> None:
    """
    Test type: behavioral
    """

    calls: list[tuple[str, str | None, str | None, str | None, str | None]] = []

    async def fake_baidu(query: str, max_results: int, *, timeout_seconds: int):  # noqa: ARG001
        calls.append(
            (query, current_strategy, current_provider, current_model, current_locale)
        )
        return public_html._HtmlSearchAttempt(
            backend_key="public:baidu",
            status=STATUS_SUCCESS,
            items=[_make_item()],
        )

    provider = PublicHtmlSearchProvider(providers=["baidu"])
    context = SimpleNamespace(conversation_id=77)
    current_strategy: str | None = None
    current_provider: str | None = None
    current_model: str | None = None
    current_locale: str | None = None

    with patch.object(public_html, "_search_with_baidu_public", side_effect=fake_baidu):
        current_strategy = WEB_SEARCH_POLICY_BUILTIN_PUBLIC
        current_provider = "openai"
        current_model = "gpt-5.4"
        current_locale = "zh_CN"
        first = await provider.search(
            query="OpenAI",
            max_results=5,
            locale=current_locale,
            timeout_seconds=15,
            context=context,
            strategy=current_strategy,
            runtime_provider_label=current_provider,
            runtime_model_code=current_model,
        )
        second = await provider.search(
            query="OpenAI",
            max_results=5,
            locale=current_locale,
            timeout_seconds=15,
            context=context,
            strategy=current_strategy,
            runtime_provider_label=current_provider,
            runtime_model_code=current_model,
        )
        current_locale = "en"
        third = await provider.search(
            query="OpenAI",
            max_results=5,
            locale=current_locale,
            timeout_seconds=15,
            context=context,
            strategy=current_strategy,
            runtime_provider_label=current_provider,
            runtime_model_code=current_model,
        )
        current_model = "gpt-4o"
        current_locale = "zh_CN"
        fourth = await provider.search(
            query="OpenAI",
            max_results=5,
            locale=current_locale,
            timeout_seconds=15,
            context=context,
            strategy=current_strategy,
            runtime_provider_label=current_provider,
            runtime_model_code=current_model,
        )
        current_provider = "azure_openai"
        fifth = await provider.search(
            query="OpenAI",
            max_results=5,
            locale=current_locale,
            timeout_seconds=15,
            context=context,
            strategy=current_strategy,
            runtime_provider_label=current_provider,
            runtime_model_code=current_model,
        )
        current_strategy = "public_only_test"
        sixth = await provider.search(
            query="OpenAI",
            max_results=5,
            locale=current_locale,
            timeout_seconds=15,
            context=context,
            strategy=current_strategy,
            runtime_provider_label=current_provider,
            runtime_model_code=current_model,
        )

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert third.cache_hit is False
    assert fourth.cache_hit is False
    assert fifth.cache_hit is False
    assert sixth.cache_hit is False
    assert len(calls) == 5


@pytest.mark.asyncio
async def test_public_html_cooldown_does_not_block_other_backends() -> None:
    """
    Test type: behavioral
    """

    baidu_calls = 0

    async def fake_baidu(query: str, max_results: int, *, timeout_seconds: int):  # noqa: ARG001
        nonlocal baidu_calls
        baidu_calls += 1
        return public_html._HtmlSearchAttempt(
            backend_key="public:baidu",
            status=STATUS_UPSTREAM_ERROR,
            items=[],
            error="boom",
        )

    provider = PublicHtmlSearchProvider(providers=["legacy_public"])
    context = SimpleNamespace(conversation_id=88)

    with patch.object(public_html, "_search_with_baidu_public", side_effect=fake_baidu):
        third = await provider.search(
            query="OpenAI 3",
            max_results=5,
            locale="zh_CN",
            timeout_seconds=15,
            context=context,
        )

    assert provider.providers == ["baidu"]
    assert baidu_calls == 1
    assert third.status == STATUS_UPSTREAM_ERROR
    assert third.attempted_backends == ["public:baidu"]


@pytest.mark.asyncio
async def test_public_html_search_applies_timeout_budget_to_baidu_only_backend() -> (
    None
):
    """
    Test type: behavioral
    """

    observed_timeouts: list[tuple[str, float]] = []

    async def fake_baidu(
        query: str,
        max_results: int,
        *,
        timeout_seconds: int,
    ):  # noqa: ARG001
        observed_timeouts.append(("baidu", float(timeout_seconds)))
        await asyncio.sleep(0.15)
        return public_html._HtmlSearchAttempt(
            backend_key="public:baidu",
            status=STATUS_UPSTREAM_ERROR,
            items=[],
            error="timeout",
        )

    provider = PublicHtmlSearchProvider(providers=["baidu", "legacy_public"])

    with patch.object(public_html, "_search_with_baidu_public", side_effect=fake_baidu):
        result = await provider.search(
            query="OpenAI",
            max_results=5,
            locale="zh_CN",
            timeout_seconds=0.25,
            context=SimpleNamespace(conversation_id=90),
            strategy=WEB_SEARCH_POLICY_BUILTIN_PUBLIC,
            runtime_provider_label="openai",
            runtime_model_code="gpt-5.4",
        )

    assert provider.providers == ["baidu"]
    assert result.status == STATUS_UPSTREAM_ERROR
    assert result.attempted_backends == ["public:baidu"]
    assert len(observed_timeouts) == 1
    assert observed_timeouts[0][0] == "baidu"
    assert 0 < observed_timeouts[0][1] <= 0.25
