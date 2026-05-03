"""
Web search orchestrator and native search provider.
联网搜索编排器与原生搜索提供器。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.ai.gateway import AIGateway  # noqa: F401
from app.ai.page_locale import resolve_page_locale
from app.ai.web_search.orchestration import native_provider as _native_provider
from app.ai.web_search.orchestration.native_provider import NativeModelSearchProvider
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
    PROVIDER_MODE_NATIVE,
    STATUS_NO_RESULTS,
    STATUS_PARSE_ERROR,
    STATUS_POLICY_FILTERED,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    STATUS_UNSUPPORTED,
    STATUS_UPSTREAM_ERROR,
    WEB_SEARCH_POLICY_NATIVE_FIRST_BAIDU_FALLBACK,
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
_NATIVE_BACKEND_FAIL_STREAK = _native_provider._NATIVE_BACKEND_FAIL_STREAK
_NATIVE_BACKEND_DISABLED = _native_provider._NATIVE_BACKEND_DISABLED
_NATIVE_BACKEND_CACHE = _native_provider._NATIVE_BACKEND_CACHE

_NATIVE_RETRYABLE_FAILURES = {
    STATUS_TIMEOUT,
    STATUS_UPSTREAM_ERROR,
    STATUS_PARSE_ERROR,
    STATUS_NO_RESULTS,
    STATUS_POLICY_FILTERED,
    STATUS_UNSUPPORTED,
}

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

        if resolved_config.policy != WEB_SEARCH_POLICY_NATIVE_FIRST_BAIDU_FALLBACK:
            return _support_build_execution(
                query=rewritten_query,
                items=[],
                meta=WebSearchExecutionMeta(
                    status=STATUS_UNSUPPORTED,
                    attempted_backends=[],
                    selected_backend=None,
                    used_fallback=False,
                    failure_reason=f"unsupported web search policy: {resolved_config.policy}",
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

        attempted_backends: list[str] = []
        provider_chain: list[str] = []
        selected_run: SearchProviderRun | None = None
        native_run: SearchProviderRun | None = None
        public_run: SearchProviderRun | None = None
        used_fallback = False
        fallback_reason: str | None = None
        native_failure_kind: str | None = None

        skip_runtime_native_after_hosted_failure = bool(
            getattr(context, "web_search_skip_native_provider", False)
        )
        skip_runtime_native_reason = str(
            getattr(context, "web_search_skip_native_reason", "") or ""
        ).strip()
        should_attempt_runtime_native_without_db = (
            resolved_config.provider is None
            and resolved_config.model is None
            and resolved_config.native_readiness_reason
            == "runtime_db_unavailable_for_native_readiness_resolution"
        )

        if skip_runtime_native_after_hosted_failure:
            native_run = SearchProviderRun(
                provider=provider_label,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=None,
                status=STATUS_UNSUPPORTED,
                items=[],
                failure_reason=(
                    skip_runtime_native_reason
                    or "native provider skipped after hosted web search failure"
                ),
                attempted_backends=[],
                native_attempted=False,
            )
        elif (
            resolved_config.provider is None or resolved_config.model is None
        ) and not should_attempt_runtime_native_without_db:
            native_run = SearchProviderRun(
                provider=provider_label,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=None,
                status=STATUS_UNSUPPORTED,
                items=[],
                failure_reason=(
                    resolved_config.native_readiness_reason
                    or "native readiness target unavailable"
                ),
                attempted_backends=[],
                native_attempted=False,
            )
        else:
            native_provider = NativeModelSearchProvider()
            native_timeout_seconds = _clamp_stage_timeout_seconds(
                resolved_config.native_timeout_seconds,
                context=context,
            )
            native_run = await native_provider.search(
                query=rewritten_query,
                max_results=effective_max_results,
                locale=locale,
                timeout_seconds=native_timeout_seconds,
                context=context,
                strategy=resolved_config.policy,
                runtime_provider_label=provider_label,
                runtime_model_code=model_code,
                provider_id_override=(
                    int(resolved_config.provider.id)
                    if resolved_config.provider is not None
                    else None
                ),
                model_id_override=(
                    int(resolved_config.model.id)
                    if resolved_config.model is not None
                    else None
                ),
                model_code_override=(
                    str(getattr(resolved_config.model, "code", "") or "")
                    if resolved_config.model is not None
                    else None
                ),
            )
        attempted_backends.extend(native_run.attempted_backends)
        provider_chain.extend(native_run.attempted_backends)
        if native_run.status == STATUS_SUCCESS and native_run.items:
            selected_run = native_run
        else:
            native_failure_kind = native_run.status
            should_fallback = native_run.status in _NATIVE_RETRYABLE_FAILURES and (
                bool(native_run.native_attempted)
                or (
                    native_run.status == STATUS_UNSUPPORTED
                    and not bool(native_run.native_attempted)
                )
            )
            if should_fallback:
                used_fallback = True
                fallback_reason = (
                    f"native_{native_run.status}"
                    if native_run.native_attempted
                    else (
                        "native_not_attempted:"
                        f"{native_run.failure_reason or native_run.status}"
                    )
                )
                logger.info(
                    "web_search orchestrator fallback: native_status={} native_backend={} native_attempted={} reason={}",
                    native_run.status,
                    native_run.backend_key or "",
                    bool(native_run.native_attempted),
                    native_run.failure_reason or "",
                )
                fallback_timeout_seconds = _clamp_stage_timeout_seconds(
                    resolved_config.fallback_timeout_seconds,
                    context=context,
                )
                public_provider = PublicHtmlSearchProvider(
                    providers=[resolved_config.fallback_provider],
                )
                public_run = await public_provider.search(
                    query=rewritten_query,
                    max_results=effective_max_results,
                    locale=locale,
                    timeout_seconds=fallback_timeout_seconds,
                    context=context,
                    strategy=resolved_config.policy,
                    runtime_provider_label=provider_label,
                    runtime_model_code=model_code,
                )
                attempted_backends.extend(public_run.attempted_backends)
                provider_chain.extend(public_run.attempted_backends)
                selected_run = public_run
            else:
                selected_run = native_run

        if selected_run is None:
            selected_run = native_run or SearchProviderRun(
                provider=None,
                provider_mode=None,
                backend_key=None,
                status=STATUS_UPSTREAM_ERROR,
                items=[],
                failure_reason="web_search did not select a backend",
            )

        failure_reason = selected_run.failure_reason
        if (
            failure_reason is None
            and selected_run.status != STATUS_SUCCESS
            and native_run is not None
            and public_run is not None
        ):
            reasons = [
                reason
                for reason in (
                    native_run.failure_reason,
                    public_run.failure_reason,
                )
                if reason
            ]
            failure_reason = "; ".join(reasons) or None

        meta = WebSearchExecutionMeta(
            status=selected_run.status,
            attempted_backends=list(attempted_backends),
            selected_backend=selected_run.backend_key,
            used_fallback=used_fallback,
            failure_reason=failure_reason,
            latency_ms=int((time.perf_counter() - start) * 1000),
            provider=selected_run.provider,
            provider_mode=selected_run.provider_mode,
            provider_chain=list(provider_chain),
            fallback_reason=fallback_reason,
            native_failure_kind=native_failure_kind,
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
    "NativeModelSearchProvider",
    "WebSearchOrchestrator",
    "run_web_search",
]
