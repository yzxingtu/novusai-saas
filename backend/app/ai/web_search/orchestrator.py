"""
Builtin public web_search orchestrator.
内置公共联网搜索编排器。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.ai.gateway import AIGateway  # noqa: F401
from app.ai.page_locale import resolve_page_locale
from app.ai.web_search.orchestrator_support.config_resolver import (
    _ResolvedWebSearchConfig,
    resolve_web_search_config,
)
from app.ai.web_search.orchestrator_support.diagnostics import (
    clamp_stage_timeout_seconds as _support_clamp_stage_timeout_seconds,
)
from app.ai.web_search.orchestrator_support.diagnostics import (
    duplicate_query_signature as _support_duplicate_query_signature,
)
from app.ai.web_search.orchestrator_support.execution_builder import (
    build_execution as _support_build_execution,
)
from app.ai.web_search.public_html import (
    PublicHtmlSearchProvider,
    _correct_query_year,
    _normalize_text,
)
from app.ai.web_search.types import (
    STATUS_UNSUPPORTED,
    STATUS_UPSTREAM_ERROR,
    SearchProviderRun,
    WebSearchExecution,
    WebSearchExecutionMeta,
)
from app.core.logging import LogManager
from app.core.redis import get_redis  # noqa: F401
from app.repositories.ai import AIModelRepository, AIProviderRepository  # noqa: F401

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.web_search")

_DUPLICATE_QUERY_SIGNATURES: set[tuple[int, str, str, str, str, str, int]] = set()

_SEARCH_ENGINE_HOSTS = frozenset({"www.baidu.com", "baidu.com"})
_MIN_STAGE_TIMEOUT_SECONDS = 1
_SEARCH_TIMEOUT_SAFETY_MARGIN_SECONDS = 0.25


def _duplicate_query_signature(
    *,
    query: str,
    policy: str,
    provider_label: str,
    model_code: str,
    locale: str | None,
    max_results: int,
    context: ExecutionContext | None,
) -> tuple[int, str, str, str, str, str, int]:
    return _support_duplicate_query_signature(
        query=query,
        strategy=policy,
        provider_label=provider_label,
        model_code=model_code,
        locale=locale,
        max_results=max_results,
        context=context,
    )


def _clamp_stage_timeout_seconds(
    requested_seconds: int,
    *,
    context: ExecutionContext | None,
) -> int:
    return _support_clamp_stage_timeout_seconds(
        requested_seconds,
        context=context,
        min_stage_timeout_seconds=_MIN_STAGE_TIMEOUT_SECONDS,
        timeout_safety_margin_seconds=_SEARCH_TIMEOUT_SAFETY_MARGIN_SECONDS,
    )


class WebSearchOrchestrator:
    async def _resolve_config(
        self,
        context: ExecutionContext | None,
    ) -> _ResolvedWebSearchConfig:
        return await resolve_web_search_config(context)

    async def search(
        self,
        *,
        query: str,
        max_results: int,
        context: ExecutionContext | None = None,
    ) -> WebSearchExecution:
        start = time.perf_counter()
        rewritten_query = _normalize_text(_correct_query_year(query))
        resolved_config = await self._resolve_config(context)
        locale = resolve_page_locale(getattr(context, "variables", None))
        effective_max_results = min(
            max(1, int(max_results)),
            int(resolved_config.max_results_cap),
        )

        provider_label = str(
            getattr(resolved_config.provider, "code", "")
            or getattr(context, "runtime_provider_name", "")
            or "provider"
        )
        model_code = str(
            getattr(resolved_config.model, "code", "")
            or getattr(context, "runtime_model_code", "")
            or ""
        )
        duplicate_signature = _duplicate_query_signature(
            query=rewritten_query,
            policy=resolved_config.policy,
            provider_label=provider_label,
            model_code=model_code,
            locale=locale,
            max_results=effective_max_results,
            context=context,
        )

        if not resolved_config.enabled:
            return _support_build_execution(
                query=rewritten_query,
                items=[],
                meta=WebSearchExecutionMeta(
                    status=STATUS_UNSUPPORTED,
                    attempted_backends=[],
                    selected_backend=None,
                    used_fallback=False,
                    failure_reason=(
                        resolved_config.config_error
                        or "web_search disabled in provider config"
                    ),
                    latency_ms=int((time.perf_counter() - start) * 1000),
                    provider=None,
                    provider_mode=None,
                    provider_chain=[],
                    cache_hit=False,
                ),
                duplicate_signature=duplicate_signature,
                search_engine_hosts=_SEARCH_ENGINE_HOSTS,
                seen_signatures=_DUPLICATE_QUERY_SIGNATURES,
            )

        public_provider = PublicHtmlSearchProvider(
            providers=[resolved_config.public_provider],
        )
        timeout_seconds = _clamp_stage_timeout_seconds(
            resolved_config.public_timeout_seconds,
            context=context,
        )
        selected_run = await public_provider.search(
            query=rewritten_query,
            max_results=effective_max_results,
            locale=locale,
            timeout_seconds=timeout_seconds,
            context=context,
            strategy=resolved_config.policy,
            runtime_provider_label=provider_label,
            runtime_model_code=model_code,
        )
        if selected_run is None:
            selected_run = SearchProviderRun(
                provider=None,
                provider_mode=None,
                backend_key=None,
                status=STATUS_UPSTREAM_ERROR,
                items=[],
                failure_reason="web_search did not select a backend",
            )

        meta = WebSearchExecutionMeta(
            status=selected_run.status,
            attempted_backends=list(selected_run.attempted_backends),
            selected_backend=selected_run.backend_key,
            used_fallback=False,
            failure_reason=selected_run.failure_reason,
            latency_ms=int((time.perf_counter() - start) * 1000),
            provider=selected_run.provider,
            provider_mode=selected_run.provider_mode,
            provider_chain=list(selected_run.attempted_backends),
            fallback_reason=None,
            native_failure_kind=None,
            cache_hit=bool(selected_run.cache_hit),
        )
        return _support_build_execution(
            query=rewritten_query,
            items=list(selected_run.items),
            meta=meta,
            duplicate_signature=duplicate_signature,
            search_engine_hosts=_SEARCH_ENGINE_HOSTS,
            seen_signatures=_DUPLICATE_QUERY_SIGNATURES,
        )


async def run_web_search(
    query: str,
    max_results: int,
    *,
    context: ExecutionContext | None = None,
) -> WebSearchExecution:
    orchestrator = WebSearchOrchestrator()
    return await orchestrator.search(
        query=query,
        max_results=max_results,
        context=context,
    )


__all__ = [
    "WebSearchOrchestrator",
    "run_web_search",
]
