from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.ai.web_search.orchestrator_support.diagnostics import (
    conv_id as _support_conv_id,
)
from app.ai.web_search.orchestrator_support.diagnostics import (
    native_backend_disabled as _support_native_backend_disabled,
)
from app.ai.web_search.orchestrator_support.diagnostics import (
    record_native_backend_outcome as _support_record_native_backend_outcome,
)
from app.ai.web_search.public_html import BaseSearchProvider, _normalize_text
from app.ai.web_search.types import (
    PROVIDER_MODE_NATIVE,
    STATUS_NO_RESULTS,
    STATUS_SUCCESS,
    STATUS_UNSUPPORTED,
    STATUS_UPSTREAM_ERROR,
    SearchProviderRun,
)
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext

logger = LogManager.get_logger("ai.web_search")

_NATIVE_BACKEND_FAIL_STREAK: dict[tuple[int, str], int] = {}
_NATIVE_BACKEND_DISABLED: dict[int, set[str]] = {}
_NATIVE_BACKEND_CACHE: dict[tuple[int, str, str, str, str, int], SearchProviderRun] = {}


def _conv_id(context: ExecutionContext | None) -> int:
    return _support_conv_id(context)


def _record_native_backend_outcome(conv_id: int, backend_key: str, status: str) -> None:
    disabled_now, streak = _support_record_native_backend_outcome(
        conv_id_value=conv_id,
        backend_key=backend_key,
        status=status,
        fail_streak=_NATIVE_BACKEND_FAIL_STREAK,
        disabled=_NATIVE_BACKEND_DISABLED,
    )
    if disabled_now:
        logger.info(
            "web_search native backend cooling down: backend={} conv_id={} streak={}",
            backend_key,
            conv_id,
            streak,
        )


def _native_backend_disabled(conv_id: int, backend_key: str) -> bool:
    return _support_native_backend_disabled(
        conv_id_value=conv_id,
        backend_key=backend_key,
        disabled=_NATIVE_BACKEND_DISABLED,
    )


class NativeModelSearchProvider(BaseSearchProvider):
    async def search(
        self,
        *,
        query: str,
        max_results: int,
        locale: str | None,
        timeout_seconds: int,
        context: ExecutionContext | None = None,
        strategy: str | None = None,
        runtime_provider_label: str | None = None,
        runtime_model_code: str | None = None,
        provider_id_override: int | None = None,
        model_id_override: int | None = None,
        model_code_override: str | None = None,
    ) -> SearchProviderRun:
        start = time.perf_counter()
        _ = (runtime_provider_label, runtime_model_code, strategy)
        if context is None or context.db is None:
            return SearchProviderRun(
                provider=None,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=None,
                status=STATUS_UNSUPPORTED,
                items=[],
                failure_reason="runtime db session unavailable for native web search",
                latency_ms=int((time.perf_counter() - start) * 1000),
                native_attempted=False,
            )

        runtime_provider_id = (
            int(provider_id_override)
            if provider_id_override is not None
            else getattr(context, "runtime_provider_id", None)
        )
        runtime_model_id = (
            int(model_id_override)
            if model_id_override is not None
            else getattr(context, "runtime_model_id", None)
        )
        runtime_model_code = str(
            model_code_override
            or getattr(context, "runtime_model_code", "")
            or ""
        ).strip()
        if runtime_provider_id is None or not runtime_model_code:
            return SearchProviderRun(
                provider=None,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=None,
                status=STATUS_UNSUPPORTED,
                items=[],
                failure_reason="runtime provider/model metadata unavailable",
                latency_ms=int((time.perf_counter() - start) * 1000),
                native_attempted=False,
            )

        from app.ai.web_search import orchestrator as ws_orchestrator

        provider_repo = ws_orchestrator.AIProviderRepository(context.db)
        provider = await provider_repo.get_by_id(int(runtime_provider_id))
        if provider is None or not provider.is_active:
            return SearchProviderRun(
                provider=None,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=None,
                status=STATUS_UNSUPPORTED,
                items=[],
                failure_reason="runtime provider unavailable",
                latency_ms=int((time.perf_counter() - start) * 1000),
                native_attempted=False,
            )

        model = None
        model_repo = ws_orchestrator.AIModelRepository(context.db)
        if runtime_model_id is not None:
            model = await model_repo.get_active_with_provider(int(runtime_model_id))
        if model is None:
            model = await model_repo.get_active_by_code_and_provider(
                runtime_model_code,
                provider.id,
            )

        provider_label = str(getattr(provider, "code", "") or provider.type or "provider")
        model_code = str(getattr(model, "code", None) or runtime_model_code)
        backend_key = f"native:{provider_label}:{model_code}"
        conv_id = _conv_id(context)
        cache_key = (
            conv_id,
            backend_key,
            _normalize_text(query).lower(),
            str(strategy or "").strip().lower(),
            str(locale or ""),
            int(max_results),
        )

        if cache_key in _NATIVE_BACKEND_CACHE:
            cached = _NATIVE_BACKEND_CACHE[cache_key]
            return SearchProviderRun(
                provider=cached.provider,
                provider_mode=cached.provider_mode,
                backend_key=cached.backend_key,
                status=cached.status,
                items=list(cached.items),
                failure_reason=cached.failure_reason,
                latency_ms=int((time.perf_counter() - start) * 1000),
                attempted_backends=[backend_key],
                cache_hit=True,
                native_attempted=True,
            )

        if _native_backend_disabled(conv_id, backend_key):
            return SearchProviderRun(
                provider=provider_label,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=backend_key,
                status=STATUS_UPSTREAM_ERROR,
                items=[],
                failure_reason="native backend temporarily cooling down",
                latency_ms=int((time.perf_counter() - start) * 1000),
                attempted_backends=[],
                native_attempted=False,
            )

        from app.ai.web_search import orchestrator as ws_orchestrator

        gateway = ws_orchestrator.AIGateway(context.db)
        native_run = await gateway.native_web_search(
            provider_code=str(getattr(provider, "code", "") or provider.type or "").strip(),
            model=model_code,
            query=query,
            max_results=max_results,
            locale=locale,
            timeout_seconds=timeout_seconds,
            tenant_id=context.tenant_id,
            user_id=getattr(context, "user_id", None),
            agent_id=getattr(context, "agent_id", None),
            conversation_id=getattr(context, "conversation_id", None),
            provider_label=provider_label,
            backend_key=backend_key,
        )
        if not native_run.backend_key:
            native_run.backend_key = backend_key
        if not native_run.provider:
            native_run.provider = provider_label
        if native_run.provider_mode is None:
            native_run.provider_mode = PROVIDER_MODE_NATIVE
        if not native_run.attempted_backends:
            native_run.attempted_backends = [backend_key]
        native_run.latency_ms = int((time.perf_counter() - start) * 1000)
        native_run.native_attempted = True
        _record_native_backend_outcome(conv_id, backend_key, native_run.status)
        logger.info(
            "web_search native attempt: backend={} status={} result_count={} cache_hit={}",
            backend_key,
            native_run.status,
            len(native_run.items),
            native_run.cache_hit,
        )
        if native_run.status in {STATUS_SUCCESS, STATUS_NO_RESULTS}:
            _NATIVE_BACKEND_CACHE[cache_key] = SearchProviderRun(
                provider=native_run.provider,
                provider_mode=native_run.provider_mode,
                backend_key=native_run.backend_key,
                status=native_run.status,
                items=list(native_run.items),
                failure_reason=native_run.failure_reason,
                attempted_backends=list(native_run.attempted_backends),
                input_tokens=native_run.input_tokens,
                output_tokens=native_run.output_tokens,
                total_tokens=native_run.total_tokens,
            )
        return native_run


__all__ = ["NativeModelSearchProvider"]
