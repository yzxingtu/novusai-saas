"""
Test type: behavioral
Scope: web-search orchestration across native, fallback, cache, and readiness decisions.
Mock strategy: orchestrator logic runs real while provider/network boundaries are faked.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.ai.skills.resolver import SkillResolver, SkillResolveResult
from app.ai.web_search import orchestrator as ws_orchestrator
from app.ai.web_search import public_html as public_html
from app.ai.web_search.orchestrator import (
    NativeModelSearchProvider,
    WebSearchOrchestrator,
)
from app.ai.web_search.orchestrator_support.native_target import (
    check_native_runtime_readiness,
    resolve_native_readiness_target,
)
from app.ai.web_search.public_html import PublicHtmlSearchProvider
from app.ai.web_search.types import (
    PROVIDER_MODE_NATIVE,
    PROVIDER_MODE_PUBLIC,
    STATUS_NO_RESULTS,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    STATUS_UNSUPPORTED,
    STATUS_UPSTREAM_ERROR,
    WEB_SEARCH_POLICY_NATIVE_FIRST_BAIDU_FALLBACK,
    SearchProviderRun,
    SearchResultItem,
)
from app.schemas.ai.provider import AIProviderWebSearchConfig


@pytest.fixture(autouse=True)
def _clear_orchestrator_state() -> None:
    ws_orchestrator._DUPLICATE_QUERY_SIGNATURES.clear()
    ws_orchestrator._NATIVE_BACKEND_FAIL_STREAK.clear()
    ws_orchestrator._NATIVE_BACKEND_DISABLED.clear()
    ws_orchestrator._NATIVE_BACKEND_CACHE.clear()
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
    source: str = "native:openai:gpt-5.4",
    provider: str = "openai",
    provider_mode: str = PROVIDER_MODE_NATIVE,
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


def _make_run(
    *,
    status: str,
    provider: str | None,
    provider_mode: str | None,
    backend_key: str | None,
    items: list[SearchResultItem] | None = None,
    failure_reason: str | None = None,
    attempted_backends: list[str] | None = None,
    cache_hit: bool = False,
    native_attempted: bool = True,
) -> SearchProviderRun:
    return SearchProviderRun(
        provider=provider,
        provider_mode=provider_mode,
        backend_key=backend_key,
        status=status,
        items=list(items or []),
        failure_reason=failure_reason,
        attempted_backends=list(attempted_backends or ([backend_key] if backend_key else [])),
        cache_hit=cache_hit,
        native_attempted=native_attempted,
    )


def test_skill_resolver_injects_baseline_web_research_tools() -> None:
    result = SkillResolveResult()
    SkillResolver()._inject_baseline_runtime_builtins(result)

    tool_names = [tool.name for tool in result.tools]
    assert tool_names == ["get_current_time", "web_search", "fetch_url"]
    assert result.tool_consent_modes["get_current_time"] == "auto"
    assert result.tool_consent_modes["web_search"] == "auto"
    assert result.tool_consent_modes["fetch_url"] == "auto"
    assert any(tool.semantic_family == "web_research" for tool in result.tools)


@pytest.mark.asyncio
async def test_skill_resolver_does_not_resolve_runtime_builtins_from_db_skills() -> None:
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

    assert [tool.name for tool in result.tools] == ["custom_builtin_tool"]


@pytest.mark.asyncio
async def test_native_model_search_provider_routes_through_gateway() -> None:
    provider = SimpleNamespace(
        id=7,
        is_active=True,
        code="openai",
        type="openai_compatible",
    )
    model = SimpleNamespace(id=9, code="gpt-5.4", config={})
    context = SimpleNamespace(
        db=object(),
        tenant_id=101,
        user_id=88,
        agent_id=33,
        conversation_id=22,
        runtime_provider_id=provider.id,
        runtime_model_id=model.id,
        runtime_model_code=model.code,
    )
    provider_repo = AsyncMock()
    provider_repo.get_by_id.return_value = provider
    model_repo = AsyncMock()
    model_repo.get_active_with_provider.return_value = model
    gateway = AsyncMock()
    gateway.native_web_search.return_value = _make_run(
        status=STATUS_SUCCESS,
        provider="openai",
        provider_mode=PROVIDER_MODE_NATIVE,
        backend_key="native:openai:gpt-5.4",
        items=[_make_item()],
    )

    with patch.object(
        ws_orchestrator,
        "AIProviderRepository",
        return_value=provider_repo,
    ), patch.object(
        ws_orchestrator,
        "AIModelRepository",
        return_value=model_repo,
    ), patch.object(
        ws_orchestrator,
        "AIGateway",
        return_value=gateway,
    ):
        run = await NativeModelSearchProvider().search(
            query="OpenAI",
            max_results=5,
            locale="zh_CN",
            timeout_seconds=20,
            context=context,
            strategy=WEB_SEARCH_POLICY_NATIVE_FIRST_BAIDU_FALLBACK,
        )

    assert run.status == STATUS_SUCCESS
    gateway.native_web_search.assert_awaited_once()
    kwargs = gateway.native_web_search.await_args.kwargs
    assert kwargs["provider_code"] == "openai"
    assert kwargs["model"] == "gpt-5.4"
    assert kwargs["tenant_id"] == 101
    assert kwargs["user_id"] == 88
    assert kwargs["agent_id"] == 33
    assert kwargs["conversation_id"] == 22
    assert kwargs["backend_key"] == "native:openai:gpt-5.4"


@pytest.mark.asyncio
async def test_orchestrator_prefers_native_success_without_public_fallback() -> None:
    orchestrator = WebSearchOrchestrator()
    native_run = _make_run(
        status=STATUS_SUCCESS,
        provider="openai",
        provider_mode=PROVIDER_MODE_NATIVE,
        backend_key="native:openai:gpt-5.4",
        items=[_make_item()],
    )

    with patch.object(
        NativeModelSearchProvider,
        "search",
        AsyncMock(return_value=native_run),
    ), patch.object(
        PublicHtmlSearchProvider,
        "search",
        AsyncMock(),
    ) as public_search:
        execution = await orchestrator.search(
            query="OpenAI",
            max_results=5,
            context=_make_context(),
        )

    assert execution.meta.status == STATUS_SUCCESS
    assert execution.meta.provider == "openai"
    assert execution.meta.provider_mode == PROVIDER_MODE_NATIVE
    assert execution.meta.selected_backend == "native:openai:gpt-5.4"
    assert execution.meta.used_fallback is False
    assert execution.meta.provider_chain == ["native:openai:gpt-5.4"]
    assert "https://example.com" in execution.output
    public_search.assert_not_called()


@pytest.mark.asyncio
async def test_orchestrator_falls_back_from_unsupported_native_to_public_success() -> None:
    orchestrator = WebSearchOrchestrator()
    native_run = _make_run(
        status=STATUS_UNSUPPORTED,
        provider="openai",
        provider_mode=PROVIDER_MODE_NATIVE,
        backend_key="native:openai:gpt-5.4",
        failure_reason="native web search unavailable",
    )
    public_run = _make_run(
        status=STATUS_SUCCESS,
        provider="baidu_public",
        provider_mode=PROVIDER_MODE_PUBLIC,
        backend_key="public:baidu",
        items=[
            _make_item(
                provider="baidu_public",
                provider_mode=PROVIDER_MODE_PUBLIC,
                source="public:baidu",
            )
        ],
        attempted_backends=["public:baidu"],
    )

    with patch.object(
        NativeModelSearchProvider,
        "search",
        AsyncMock(return_value=native_run),
    ), patch.object(
        PublicHtmlSearchProvider,
        "search",
        AsyncMock(return_value=public_run),
    ):
        execution = await orchestrator.search(
            query="OpenAI",
            max_results=5,
            context=_make_context(),
        )

    assert execution.meta.status == STATUS_SUCCESS
    assert execution.meta.provider == "baidu_public"
    assert execution.meta.provider_mode == PROVIDER_MODE_PUBLIC
    assert execution.meta.selected_backend == "public:baidu"
    assert execution.meta.used_fallback is True
    assert execution.meta.fallback_reason == "native_unsupported"
    assert execution.meta.native_failure_kind == STATUS_UNSUPPORTED
    assert execution.meta.provider_chain == [
        "native:openai:gpt-5.4",
        "public:baidu",
    ]


@pytest.mark.asyncio
async def test_orchestrator_returns_public_no_results_after_native_timeout() -> None:
    orchestrator = WebSearchOrchestrator()
    native_run = _make_run(
        status=STATUS_TIMEOUT,
        provider="openai",
        provider_mode=PROVIDER_MODE_NATIVE,
        backend_key="native:openai:gpt-5.4",
        failure_reason="provider timed out",
    )
    public_run = _make_run(
        status=STATUS_NO_RESULTS,
        provider="baidu_public",
        provider_mode=PROVIDER_MODE_PUBLIC,
        backend_key="public:baidu",
        failure_reason="public:baidu returned no results",
    )

    with patch.object(
        NativeModelSearchProvider,
        "search",
        AsyncMock(return_value=native_run),
    ), patch.object(
        PublicHtmlSearchProvider,
        "search",
        AsyncMock(return_value=public_run),
    ):
        execution = await orchestrator.search(
            query="OpenAI",
            max_results=5,
            context=_make_context(),
        )

    assert execution.meta.status == STATUS_NO_RESULTS
    assert execution.meta.used_fallback is True
    assert execution.meta.fallback_reason == "native_timeout"
    assert execution.meta.native_failure_kind == STATUS_TIMEOUT
    assert execution.output == "No results found for: OpenAI"


@pytest.mark.asyncio
async def test_orchestrator_clamps_public_timeout_to_remaining_tool_budget() -> None:
    orchestrator = WebSearchOrchestrator()
    native_run = _make_run(
        status=STATUS_TIMEOUT,
        provider="openai",
        provider_mode=PROVIDER_MODE_NATIVE,
        backend_key="native:openai:gpt-5.4",
        failure_reason="provider timed out",
    )
    public_run = _make_run(
        status=STATUS_SUCCESS,
        provider="baidu_public",
        provider_mode=PROVIDER_MODE_PUBLIC,
        backend_key="public:baidu",
        items=[
            _make_item(
                provider="baidu_public",
                provider_mode=PROVIDER_MODE_PUBLIC,
                source="public:baidu",
            )
        ],
    )
    context = _make_context()
    context.tool_deadline_monotonic = time.perf_counter() + 7.4

    with patch.object(
        NativeModelSearchProvider,
        "search",
        AsyncMock(return_value=native_run),
    ), patch.object(
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
async def test_orchestrator_surfaces_public_failure_when_all_backends_fail() -> None:
    orchestrator = WebSearchOrchestrator()
    native_run = _make_run(
        status=STATUS_TIMEOUT,
        provider="openai",
        provider_mode=PROVIDER_MODE_NATIVE,
        backend_key="native:openai:gpt-5.4",
        failure_reason="provider timed out",
    )
    public_run = _make_run(
        status=STATUS_UPSTREAM_ERROR,
        provider=None,
        provider_mode=PROVIDER_MODE_PUBLIC,
        backend_key="public:baidu",
        failure_reason="public:baidu returned unreadable page",
        attempted_backends=["public:baidu"],
    )

    with patch.object(
        NativeModelSearchProvider,
        "search",
        AsyncMock(return_value=native_run),
    ), patch.object(
        PublicHtmlSearchProvider,
        "search",
        AsyncMock(return_value=public_run),
    ):
        execution = await orchestrator.search(
            query="OpenAI",
            max_results=5,
            context=_make_context(),
        )

    assert execution.meta.status == STATUS_UPSTREAM_ERROR
    assert execution.meta.used_fallback is True
    assert execution.meta.fallback_reason == "native_timeout"
    assert execution.meta.native_failure_kind == STATUS_TIMEOUT
    assert execution.meta.attempted_backends == [
        "native:openai:gpt-5.4",
        "public:baidu",
    ]
    assert "Search source unavailable" in execution.output


@pytest.mark.asyncio
async def test_orchestrator_falls_back_to_public_when_native_not_attempted() -> None:
    orchestrator = WebSearchOrchestrator()
    native_run = _make_run(
        status=STATUS_UNSUPPORTED,
        provider="openai",
        provider_mode=PROVIDER_MODE_NATIVE,
        backend_key="native:openai:gpt-5.4",
        failure_reason="native readiness target unavailable",
        attempted_backends=[],
        native_attempted=False,
    )
    public_run = _make_run(
        status=STATUS_SUCCESS,
        provider="baidu_public",
        provider_mode=PROVIDER_MODE_PUBLIC,
        backend_key="public:baidu",
        items=[
            _make_item(
                provider="baidu_public",
                provider_mode=PROVIDER_MODE_PUBLIC,
                source="public:baidu",
            )
        ],
    )

    with patch.object(
        NativeModelSearchProvider,
        "search",
        AsyncMock(return_value=native_run),
    ), patch.object(
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
    assert execution.meta.used_fallback is True
    assert (
        execution.meta.fallback_reason
        == "native_not_attempted:native readiness target unavailable"
    )
    assert execution.meta.native_failure_kind == STATUS_UNSUPPORTED
    public_search.assert_awaited_once()


@pytest.mark.asyncio
async def test_orchestrator_ignores_legacy_explicit_verified_native_target_config() -> None:
    orchestrator = WebSearchOrchestrator()
    runtime_provider = SimpleNamespace(
        id=11,
        is_active=True,
        code="provider_1",
        type="openai_compatible",
        base_url="https://api.asxs.top/v1",
        config={
            "web_search": {
                "enabled": True,
                "strategy": "native_first_fallback_public",
                "verified_native_target": {
                    "provider_code": "ignored-provider",
                    "model_code": "ignored-model",
                },
            }
        },
    )
    runtime_model = SimpleNamespace(id=111, provider_id=11, code="gpt-5.4")
    ready_provider = SimpleNamespace(
        id=12,
        is_active=True,
        code="openai",
        type="openai_compatible",
        base_url="https://api.openai.com/v1",
        config={},
    )
    ready_model = SimpleNamespace(id=222, provider_id=12, code="gpt-5.4")
    context = SimpleNamespace(
        db=object(),
        runtime_provider_id=11,
        runtime_model_id=111,
        runtime_model_code="gpt-5.4",
        runtime_provider_name="provider_1",
        conversation_id=42,
        variables={},
    )
    provider_repo = AsyncMock()
    provider_repo.get_by_id.return_value = runtime_provider
    provider_repo.get_active_providers.return_value = [runtime_provider, ready_provider]
    model_repo = AsyncMock()
    model_repo.get_active_with_provider.return_value = runtime_model
    model_repo.get_active_by_code_and_provider.return_value = ready_model
    native_run = _make_run(
        status=STATUS_SUCCESS,
        provider="openai",
        provider_mode=PROVIDER_MODE_NATIVE,
        backend_key="native:openai:gpt-5.4",
        items=[_make_item()],
        native_attempted=True,
    )

    with patch.object(
        ws_orchestrator,
        "AIProviderRepository",
        return_value=provider_repo,
    ), patch.object(
        ws_orchestrator,
        "AIModelRepository",
        return_value=model_repo,
    ), patch.object(
        NativeModelSearchProvider,
        "search",
        AsyncMock(return_value=native_run),
    ) as native_search:
        execution = await orchestrator.search(
            query="OpenAI",
            max_results=5,
            context=context,
        )

    assert execution.meta.status == STATUS_SUCCESS
    assert execution.meta.selected_backend == "native:openai:gpt-5.4"
    provider_repo.get_by_code.assert_not_awaited()
    kwargs = native_search.await_args.kwargs
    assert kwargs["provider_id_override"] == 12
    assert kwargs["model_id_override"] == 222
    assert kwargs["model_code_override"] == "gpt-5.4"


@pytest.mark.asyncio
async def test_orchestrator_uses_default_native_readiness_target_when_runtime_provider_is_untrusted() -> None:
    orchestrator = WebSearchOrchestrator()
    runtime_provider = SimpleNamespace(
        id=11,
        is_active=True,
        code="provider_1",
        type="openai_compatible",
        base_url="https://api.asxs.top/v1",
        config={
            "web_search": {
                "enabled": True,
            }
        },
    )
    runtime_model = SimpleNamespace(id=111, provider_id=11, code="gpt-5.4")
    ready_provider = SimpleNamespace(
        id=12,
        is_active=True,
        code="openai",
        type="openai_compatible",
        base_url="https://api.openai.com/v1",
        config={},
    )
    ready_model = SimpleNamespace(id=222, provider_id=12, code="gpt-5.4")
    context = SimpleNamespace(
        db=object(),
        runtime_provider_id=11,
        runtime_model_id=111,
        runtime_model_code="gpt-5.4",
        runtime_provider_name="provider_1",
        conversation_id=43,
        variables={},
    )
    provider_repo = AsyncMock()
    provider_repo.get_by_id.return_value = runtime_provider
    provider_repo.get_active_providers.return_value = [runtime_provider, ready_provider]
    model_repo = AsyncMock()
    model_repo.get_active_with_provider.return_value = runtime_model

    async def get_active_by_code_and_provider(code: str, provider_id: int):
        if code == "gpt-5.4" and provider_id == ready_provider.id:
            return ready_model
        return None

    model_repo.get_active_by_code_and_provider.side_effect = get_active_by_code_and_provider
    native_run = _make_run(
        status=STATUS_SUCCESS,
        provider="openai",
        provider_mode=PROVIDER_MODE_NATIVE,
        backend_key="native:openai:gpt-5.4",
        items=[_make_item()],
        native_attempted=True,
    )

    with patch.object(
        ws_orchestrator,
        "AIProviderRepository",
        return_value=provider_repo,
    ), patch.object(
        ws_orchestrator,
        "AIModelRepository",
        return_value=model_repo,
    ), patch.object(
        NativeModelSearchProvider,
        "search",
        AsyncMock(return_value=native_run),
    ) as native_search:
        execution = await orchestrator.search(
            query="OpenAI",
            max_results=5,
            context=context,
        )

    assert execution.meta.status == STATUS_SUCCESS
    kwargs = native_search.await_args.kwargs
    assert kwargs["provider_id_override"] == 12
    assert kwargs["model_id_override"] == 222
    assert kwargs["model_code_override"] == "gpt-5.4"


@pytest.mark.asyncio
async def test_orchestrator_falls_back_public_when_only_untrusted_runtime_candidate_exists() -> None:
    orchestrator = WebSearchOrchestrator()
    runtime_provider = SimpleNamespace(
        id=11,
        is_active=True,
        code="provider_1",
        type="openai_compatible",
        base_url="https://api.asxs.top/v1",
        config={
            "web_search": {
                "enabled": True,
            }
        },
    )
    runtime_model = SimpleNamespace(id=111, provider_id=11, code="gpt-5.4")
    context = SimpleNamespace(
        db=object(),
        runtime_provider_id=11,
        runtime_model_id=111,
        runtime_model_code="gpt-5.4",
        runtime_provider_name="provider_1",
        conversation_id=43,
        variables={},
    )
    provider_repo = AsyncMock()
    provider_repo.get_by_id.return_value = runtime_provider
    provider_repo.get_active_providers.return_value = [runtime_provider]
    model_repo = AsyncMock()
    model_repo.get_active_with_provider.return_value = runtime_model
    model_repo.get_active_by_code_and_provider.return_value = runtime_model
    public_run = _make_run(
        status=STATUS_SUCCESS,
        provider="baidu_public",
        provider_mode=PROVIDER_MODE_PUBLIC,
        backend_key="public:baidu",
        items=[
            _make_item(
                provider="baidu_public",
                provider_mode=PROVIDER_MODE_PUBLIC,
                source="public:baidu",
            )
        ],
    )

    with patch.object(
        ws_orchestrator,
        "AIProviderRepository",
        return_value=provider_repo,
    ), patch.object(
        ws_orchestrator,
        "AIModelRepository",
        return_value=model_repo,
    ), patch.object(
        NativeModelSearchProvider,
        "search",
        AsyncMock(),
    ) as native_search, patch.object(
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
    assert execution.meta.used_fallback is True
    assert execution.meta.native_failure_kind == STATUS_UNSUPPORTED
    assert "native_not_attempted:default_native_readiness_target_unavailable" in (
        execution.meta.fallback_reason or ""
    )
    assert "untrusted_openai_compatible_runtime_candidate" in (
        execution.meta.fallback_reason or ""
    )
    native_search.assert_not_called()
    public_search.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_native_readiness_target_rejects_untrusted_runtime_without_override() -> None:
    runtime_provider = SimpleNamespace(
        id=11,
        is_active=True,
        code="provider_1",
        type="openai_compatible",
        base_url="https://api.asxs.top/v1",
        config={},
    )
    runtime_model = SimpleNamespace(id=111, provider_id=11, code="gpt-5.4")
    provider_repo = AsyncMock()
    provider_repo.get_active_providers.return_value = [runtime_provider]
    model_repo = AsyncMock()

    provider, model, source, reason = await resolve_native_readiness_target(
        normalized_config=AIProviderWebSearchConfig(
            enabled=True,
            fallback_provider="baidu",
        ),
        runtime_provider=runtime_provider,
        runtime_model=runtime_model,
        runtime_model_code="gpt-5.4",
        provider_repo=provider_repo,
        model_repo=model_repo,
    )

    assert provider is None
    assert model is None
    assert source is None
    assert "untrusted_openai_compatible_runtime_candidate:api.asxs.top" in reason


@pytest.mark.asyncio
async def test_native_readiness_rejects_non_openai_compatible_provider() -> None:
    provider = SimpleNamespace(
        id=21,
        is_active=True,
        code="anthropic",
        type="anthropic",
        base_url="https://api.anthropic.com",
        config={"wire_api": "responses"},
    )

    is_ready, reason = await check_native_runtime_readiness(
        provider,
        model_code="claude-3-5-sonnet",
    )

    assert is_ready is False
    assert reason == "provider_type_native_denied:anthropic"


@pytest.mark.asyncio
async def test_orchestrator_uses_health_ready_untrusted_runtime_candidate() -> None:
    orchestrator = WebSearchOrchestrator()
    runtime_provider = SimpleNamespace(
        id=11,
        is_active=True,
        code="provider_1",
        type="openai_compatible",
        base_url="https://api.asxs.top/v1",
        config={
            "wire_api": "responses",
            "web_search": {
                "enabled": True,
            },
        },
    )
    runtime_model = SimpleNamespace(id=111, provider_id=11, code="gpt-5.4")
    context = SimpleNamespace(
        db=object(),
        runtime_provider_id=11,
        runtime_model_id=111,
        runtime_model_code="gpt-5.4",
        runtime_provider_name="provider_1",
        conversation_id=44,
        variables={},
    )
    provider_repo = AsyncMock()
    provider_repo.get_by_id.return_value = runtime_provider
    provider_repo.get_active_providers.return_value = [runtime_provider]
    model_repo = AsyncMock()
    model_repo.get_active_with_provider.return_value = runtime_model
    model_repo.get_active_by_code_and_provider.return_value = runtime_model
    redis_client = AsyncMock()
    redis_client.get.return_value = json.dumps(
        {
            "is_healthy": True,
            "tool_calling_healthy": True,
            "tool_probe_model": "gpt-5.4",
            "wire_api": "responses",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    native_run = _make_run(
        status=STATUS_SUCCESS,
        provider="provider_1",
        provider_mode=PROVIDER_MODE_NATIVE,
        backend_key="native:provider_1:gpt-5.4",
        items=[_make_item(provider="provider_1", source="native:provider_1:gpt-5.4")],
        native_attempted=True,
    )

    with patch.object(
        ws_orchestrator,
        "AIProviderRepository",
        return_value=provider_repo,
    ), patch.object(
        ws_orchestrator,
        "AIModelRepository",
        return_value=model_repo,
    ), patch.object(
        ws_orchestrator,
        "get_redis",
        AsyncMock(return_value=redis_client),
    ), patch.object(
        NativeModelSearchProvider,
        "search",
        AsyncMock(return_value=native_run),
    ) as native_search, patch.object(
        PublicHtmlSearchProvider,
        "search",
        AsyncMock(),
    ) as public_search:
        execution = await orchestrator.search(
            query="OpenAI",
            max_results=5,
            context=context,
        )

    assert execution.meta.status == STATUS_SUCCESS
    assert execution.meta.selected_backend == "native:provider_1:gpt-5.4"
    assert execution.meta.used_fallback is False
    native_search.assert_awaited_once()
    public_search.assert_not_called()


@pytest.mark.asyncio
async def test_orchestrator_marks_duplicate_queries_with_fetch_guidance() -> None:
    ws_orchestrator._DUPLICATE_QUERY_SIGNATURES.clear()
    orchestrator = WebSearchOrchestrator()
    native_run = _make_run(
        status=STATUS_SUCCESS,
        provider="openai",
        provider_mode=PROVIDER_MODE_NATIVE,
        backend_key="native:openai:gpt-5.4",
        items=[_make_item()],
    )

    with patch.object(
        NativeModelSearchProvider,
        "search",
        AsyncMock(return_value=native_run),
    ), patch.object(
        PublicHtmlSearchProvider,
        "search",
        AsyncMock(),
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

    with patch.object(
        ws_orchestrator,
        "AIProviderRepository",
        return_value=provider_repo,
    ), patch.object(
        ws_orchestrator,
        "AIModelRepository",
        return_value=model_repo,
    ), patch.object(
        NativeModelSearchProvider,
        "search",
        AsyncMock(),
    ) as native_search, patch.object(
        PublicHtmlSearchProvider,
        "search",
        AsyncMock(),
    ) as public_search:
        execution = await orchestrator.search(
            query="OpenAI",
            max_results=5,
            context=context,
        )

    assert execution.meta.status == STATUS_UNSUPPORTED
    assert "invalid provider config.web_search" in (execution.meta.failure_reason or "")
    native_search.assert_not_called()
    public_search.assert_not_called()


@pytest.mark.asyncio
async def test_public_html_cache_key_isolated_by_locale_runtime_and_strategy() -> None:
    calls: list[tuple[str, str | None, str | None, str | None, str | None]] = []

    async def fake_baidu(query: str, max_results: int, *, timeout_seconds: int):  # noqa: ARG001
        calls.append((query, current_strategy, current_provider, current_model, current_locale))
        return public_html._HtmlSearchAttempt(
            backend_key="public:baidu",
            status=STATUS_SUCCESS,
            items=[
                _make_item(
                    provider="baidu_public",
                    provider_mode=PROVIDER_MODE_PUBLIC,
                    source="public:baidu",
                )
            ],
        )

    provider = PublicHtmlSearchProvider(providers=["baidu"])
    context = SimpleNamespace(conversation_id=77)
    current_strategy: str | None = None
    current_provider: str | None = None
    current_model: str | None = None
    current_locale: str | None = None

    with patch.object(public_html, "_search_with_baidu_public", side_effect=fake_baidu):
        current_strategy = WEB_SEARCH_POLICY_NATIVE_FIRST_BAIDU_FALLBACK
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
        current_strategy = WEB_SEARCH_POLICY_NATIVE_FIRST_BAIDU_FALLBACK
        current_provider = "openai"
        current_model = "gpt-5.4"
        current_locale = "zh_CN"
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
        current_strategy = WEB_SEARCH_POLICY_NATIVE_FIRST_BAIDU_FALLBACK
        current_provider = "openai"
        current_model = "gpt-5.4"
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
        current_strategy = WEB_SEARCH_POLICY_NATIVE_FIRST_BAIDU_FALLBACK
        current_provider = "openai"
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
        current_strategy = WEB_SEARCH_POLICY_NATIVE_FIRST_BAIDU_FALLBACK
        current_provider = "azure_openai"
        current_model = "gpt-4o"
        current_locale = "zh_CN"
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
        current_provider = "azure_openai"
        current_model = "gpt-4o"
        current_locale = "zh_CN"
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
async def test_public_html_search_applies_timeout_budget_to_baidu_only_backend() -> None:
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
    result = None

    with patch.object(public_html, "_search_with_baidu_public", side_effect=fake_baidu):
        result = await provider.search(
            query="OpenAI",
            max_results=5,
            locale="zh_CN",
            timeout_seconds=0.25,
            context=SimpleNamespace(conversation_id=90),
            strategy=WEB_SEARCH_POLICY_NATIVE_FIRST_BAIDU_FALLBACK,
            runtime_provider_label="openai",
            runtime_model_code="gpt-5.4",
        )

    assert provider.providers == ["baidu"]
    assert result.status == STATUS_UPSTREAM_ERROR
    assert result.attempted_backends == ["public:baidu"]
    assert len(observed_timeouts) == 1
    assert observed_timeouts[0][0] == "baidu"
    assert 0 < observed_timeouts[0][1] <= 0.25
