"""
Web search orchestrator and native search provider.
联网搜索编排器与原生搜索提供器。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from redis.exceptions import RedisError

from app.ai.failover import HEALTH_KEY_PREFIX
from app.ai.gateway import AIGateway
from app.ai.page_locale import resolve_page_locale
from app.ai.web_search.orchestrator_support.diagnostics import (
    clamp_stage_timeout_seconds as _support_clamp_stage_timeout_seconds,
)
from app.ai.web_search.orchestrator_support.diagnostics import (
    conv_id as _support_conv_id,
)
from app.ai.web_search.orchestrator_support.diagnostics import (
    decorate_duplicate_query_output as _support_decorate_duplicate_query_output,
)
from app.ai.web_search.orchestrator_support.diagnostics import (
    duplicate_query_signature as _support_duplicate_query_signature,
)
from app.ai.web_search.orchestrator_support.diagnostics import (
    native_backend_disabled as _support_native_backend_disabled,
)
from app.ai.web_search.orchestrator_support.diagnostics import (
    record_native_backend_outcome as _support_record_native_backend_outcome,
)
from app.ai.web_search.orchestrator_support.diagnostics import (
    remaining_tool_budget_seconds as _support_remaining_tool_budget_seconds,
)
from app.ai.web_search.orchestrator_support.provider_selector import (
    default_web_search_config as _support_default_web_search_config,
)
from app.ai.web_search.orchestrator_support.provider_selector import (
    is_verified_native_runtime_candidate as _support_is_verified_native_runtime_candidate,
)
from app.ai.web_search.orchestrator_support.provider_selector import (
    normalize_provider_web_search_settings as _support_normalize_provider_web_search_settings,
)
from app.ai.web_search.orchestrator_support.provider_selector import (
    normalized_hostname as _support_normalized_hostname,
)
from app.ai.web_search.orchestrator_support.summary_builder import (
    build_search_output_text as _support_build_search_output_text,
)
from app.ai.web_search.public_html import (
    BaseSearchProvider,
    PublicHtmlSearchProvider,
    _correct_query_year,
    _normalize_text,
)
from app.ai.web_search.types import (
    DEFAULT_PUBLIC_PROVIDERS,
    PROVIDER_MODE_NATIVE,
    STATUS_NO_RESULTS,
    STATUS_PARSE_ERROR,
    STATUS_POLICY_FILTERED,
    STATUS_SUCCESS,
    STATUS_TIMEOUT,
    STATUS_UNSUPPORTED,
    STATUS_UPSTREAM_ERROR,
    STRATEGY_NATIVE_FIRST_FALLBACK_PUBLIC,
    SearchProviderRun,
    SearchResultItem,
    WebSearchExecution,
    WebSearchExecutionMeta,
)
from app.core.logging import LogManager
from app.core.redis import get_redis
from app.repositories.ai import (
    AIModelRepository,
    AIProviderRepository,
)
from app.schemas.ai.provider import (
    AIProviderWebSearchConfig,
    AIProviderWebSearchVerifiedTarget,
)

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext
    from app.models.ai import AIModel, AIProvider

logger = LogManager.get_logger("ai.web_search")

_DUPLICATE_QUERY_SIGNATURES: set[
    tuple[int, str, str, str, str, str, int]
] = set()
_NATIVE_BACKEND_FAIL_STREAK: dict[tuple[int, str], int] = {}
_NATIVE_BACKEND_DISABLED: dict[int, set[str]] = {}
_NATIVE_BACKEND_CACHE: dict[tuple[int, str, str, str, str, int], SearchProviderRun] = {}

_NATIVE_RETRYABLE_FAILURES = {
    STATUS_TIMEOUT,
    STATUS_UPSTREAM_ERROR,
    STATUS_PARSE_ERROR,
    STATUS_NO_RESULTS,
    STATUS_POLICY_FILTERED,
    STATUS_UNSUPPORTED,
}

_SEARCH_ENGINE_HOSTS = frozenset({"www.baidu.com", "baidu.com", "www.so.com", "so.com"})
_TRUSTED_OPENAI_COMPATIBLE_HOSTS = frozenset(
    {
        "api.openai.com",
    }
)
_HEALTH_VERIFIED_NATIVE_SEARCH_MAX_AGE = timedelta(hours=24)
_MIN_STAGE_TIMEOUT_SECONDS = 1
_SEARCH_TIMEOUT_SAFETY_MARGIN_SECONDS = 0.25


@dataclass
class _ResolvedWebSearchConfig:
    enabled: bool
    strategy: str
    max_results_cap: int
    native_timeout_seconds: int
    public_timeout_seconds: int
    public_providers: list[str]
    provider: AIProvider | None = None
    model: AIModel | None = None
    runtime_provider: AIProvider | None = None
    runtime_model: AIModel | None = None
    native_target_source: str | None = None
    native_target_reason: str | None = None
    config_error: str | None = None


def _normalized_hostname(raw_url: str | None) -> str:
    return _support_normalized_hostname(raw_url)


def _is_trusted_openai_compatible_host(hostname: str) -> bool:
    if not hostname:
        return False
    return hostname in _TRUSTED_OPENAI_COMPATIBLE_HOSTS or hostname.endswith(
        ".openai.azure.com"
    )


def _is_verified_native_runtime_candidate(
    provider: AIProvider | None,
    *,
    allow_unverified_runtime_target: bool,
) -> tuple[bool, str]:
    return _support_is_verified_native_runtime_candidate(
        provider,
        allow_unverified_runtime_target=allow_unverified_runtime_target,
        trusted_hosts=_TRUSTED_OPENAI_COMPATIBLE_HOSTS,
    )


def _default_web_search_config() -> AIProviderWebSearchConfig:
    return _support_default_web_search_config(list(DEFAULT_PUBLIC_PROVIDERS))


def _normalize_provider_web_search_settings(
    provider_config: dict | None,
) -> AIProviderWebSearchConfig:
    return _support_normalize_provider_web_search_settings(
        provider_config,
        default_public_providers=list(DEFAULT_PUBLIC_PROVIDERS),
    )


def _conv_id(context: ExecutionContext | None) -> int:
    return _support_conv_id(context)


def _build_search_output_text(query: str, items: list[SearchResultItem]) -> str:
    return _support_build_search_output_text(
        query,
        items,
        search_engine_hosts=_SEARCH_ENGINE_HOSTS,
    )


def _duplicate_query_signature(
    *,
    query: str,
    strategy: str,
    provider_label: str,
    model_code: str,
    locale: str | None,
    max_results: int,
    context: ExecutionContext | None,
) -> tuple[int, str, str, str, str, str, int]:
    return _support_duplicate_query_signature(
        query=query,
        strategy=strategy,
        provider_label=provider_label,
        model_code=model_code,
        locale=locale,
        max_results=max_results,
        context=context,
    )


def _decorate_duplicate_query_output(
    *,
    output: str,
    signature: tuple[int, str, str, str, str, str, int],
    status: str,
) -> str:
    return _support_decorate_duplicate_query_output(
        output=output,
        signature=signature,
        status=status,
        seen_signatures=_DUPLICATE_QUERY_SIGNATURES,
    )


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


def _remaining_tool_budget_seconds(context: ExecutionContext | None) -> float | None:
    return _support_remaining_tool_budget_seconds(context)


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
        _ = (runtime_provider_label, runtime_model_code)
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

        provider_repo = AIProviderRepository(context.db)
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
        model_repo = AIModelRepository(context.db)
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

        gateway = AIGateway(context.db)
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


class WebSearchOrchestrator:
    @staticmethod
    def _normalize_wire_api(wire_api: object) -> str:
        normalized = str(wire_api or "").strip().lower().replace("-", "_")
        if normalized in {"responses", "response", "responses_api"}:
            return "responses"
        return normalized

    @staticmethod
    def _parse_health_checked_at(value: object) -> datetime | None:
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    async def _is_health_verified_native_candidate(
        provider: AIProvider | None,
        *,
        model_code: str,
    ) -> tuple[bool, str]:
        if provider is None:
            return False, "provider_health_missing"

        provider_id = int(getattr(provider, "id", 0) or 0)
        if provider_id <= 0:
            return False, "provider_health_missing"

        provider_config = (
            dict(getattr(provider, "config", {}) or {})
            if isinstance(getattr(provider, "config", None), dict)
            else {}
        )
        wire_api = WebSearchOrchestrator._normalize_wire_api(
            provider_config.get("wire_api")
        )
        if wire_api != "responses":
            return False, f"provider_health_wire_api_mismatch:{wire_api or 'unknown'}"

        try:
            redis = await get_redis()
            raw_payload = await redis.get(
                HEALTH_KEY_PREFIX.format(provider_id=provider_id)
            )
        except (RedisError, RuntimeError, TypeError, ValueError) as exc:
            return False, f"provider_health_unavailable:{type(exc).__name__}"

        if not raw_payload:
            return False, "provider_health_missing"

        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            return False, "provider_health_invalid_json"

        if not isinstance(payload, dict):
            return False, "provider_health_invalid_payload"
        if not bool(payload.get("is_healthy", payload.get("is_available", True))):
            return False, "provider_health_unhealthy"
        if payload.get("tool_calling_healthy") is not True:
            return False, "provider_health_tool_calling_unverified"

        checked_at = WebSearchOrchestrator._parse_health_checked_at(
            payload.get("checked_at")
        )
        if checked_at is None:
            return False, "provider_health_missing_checked_at"
        if (
            datetime.now(timezone.utc) - checked_at
            > _HEALTH_VERIFIED_NATIVE_SEARCH_MAX_AGE
        ):
            return False, "provider_health_stale"

        probe_model = str(payload.get("tool_probe_model") or "").strip()
        normalized_model_code = str(model_code or "").strip()
        if probe_model and normalized_model_code and probe_model != normalized_model_code:
            return False, f"provider_health_model_mismatch:{probe_model}"

        return (
            True,
            f"responses_tool_probe_verified:{provider_id}:{probe_model or normalized_model_code or 'unknown'}",
        )

    @staticmethod
    async def _verify_native_runtime_candidate(
        provider: AIProvider | None,
        *,
        model_code: str,
        allow_unverified_runtime_target: bool,
    ) -> tuple[bool, str]:
        is_verified, verify_reason = _is_verified_native_runtime_candidate(
            provider,
            allow_unverified_runtime_target=allow_unverified_runtime_target,
        )
        if is_verified:
            return True, verify_reason
        if provider is None or allow_unverified_runtime_target:
            return is_verified, verify_reason

        provider_type = str(getattr(provider, "type", "") or "").strip().lower()
        if provider_type != "openai_compatible":
            return False, verify_reason

        health_verified, health_reason = (
            await WebSearchOrchestrator._is_health_verified_native_candidate(
                provider,
                model_code=model_code,
            )
        )
        if health_verified:
            return True, health_reason
        return False, f"{verify_reason}:{health_reason}"

    @staticmethod
    async def _load_runtime_provider_and_model(
        *,
        context: ExecutionContext | None,
        provider_repo: AIProviderRepository,
        model_repo: AIModelRepository,
    ) -> tuple[AIProvider | None, AIModel | None]:
        runtime_provider_id = getattr(context, "runtime_provider_id", None)
        runtime_model_id = getattr(context, "runtime_model_id", None)
        runtime_model_code = str(getattr(context, "runtime_model_code", "") or "").strip()

        provider = None
        model = None
        if runtime_provider_id is not None:
            provider = await provider_repo.get_by_id(int(runtime_provider_id))
        if runtime_model_id is not None:
            model = await model_repo.get_active_with_provider(int(runtime_model_id))
        if (
            model is None
            and provider is not None
            and runtime_model_code
        ):
            model = await model_repo.get_active_by_code_and_provider(
                runtime_model_code,
                provider.id,
            )
        return provider, model

    @staticmethod
    async def _resolve_verified_target_from_config(
        *,
        target: AIProviderWebSearchVerifiedTarget,
        provider_repo: AIProviderRepository,
        model_repo: AIModelRepository,
        runtime_model: AIModel | None,
    ) -> tuple[AIProvider | None, AIModel | None, str]:
        provider = None
        if target.provider_id is not None:
            provider = await provider_repo.get_by_id(int(target.provider_id))
        elif target.provider_code:
            provider = await provider_repo.get_by_code(str(target.provider_code).strip())
        if provider is None or not provider.is_active:
            return None, None, "verified_target_provider_unavailable"

        model = None
        if target.model_id is not None:
            model = await model_repo.get_active_with_provider(int(target.model_id))
            if model is not None and int(getattr(model, "provider_id", 0) or 0) != int(
                provider.id
            ):
                model = None
        if model is None and target.model_code:
            model = await model_repo.get_active_by_code_and_provider(
                str(target.model_code).strip(),
                provider.id,
            )
        if (
            model is None
            and runtime_model is not None
            and int(getattr(runtime_model, "provider_id", 0) or 0) == int(provider.id)
        ):
            model = runtime_model
        if model is None:
            return provider, None, "verified_target_model_unavailable"
        return provider, model, "verified_native_target"

    @staticmethod
    async def _resolve_default_verified_native_target(
        *,
        runtime_provider: AIProvider | None,
        runtime_model: AIModel | None,
        runtime_model_code: str,
        provider_repo: AIProviderRepository,
        model_repo: AIModelRepository,
    ) -> tuple[AIProvider | None, AIModel | None, str | None, str]:
        preferred_model_code = str(
            getattr(runtime_model, "code", "") or runtime_model_code or ""
        ).strip()

        if runtime_provider is not None and runtime_model is not None:
            is_verified, verify_reason = await WebSearchOrchestrator._verify_native_runtime_candidate(
                runtime_provider,
                model_code=preferred_model_code,
                allow_unverified_runtime_target=False,
            )
            if is_verified:
                return (
                    runtime_provider,
                    runtime_model,
                    "default_verified_native_target",
                    verify_reason,
                )
            runtime_provider_id = int(getattr(runtime_provider, "id", 0) or 0)
        else:
            runtime_provider_id = 0

        if not preferred_model_code:
            return None, None, None, "default_verified_target_model_code_missing"

        active_providers = await provider_repo.get_active_providers()
        for provider in active_providers:
            provider_id = int(getattr(provider, "id", 0) or 0)
            if provider_id and provider_id == runtime_provider_id:
                continue

            is_verified, verify_reason = await WebSearchOrchestrator._verify_native_runtime_candidate(
                provider,
                model_code=preferred_model_code,
                allow_unverified_runtime_target=False,
            )
            if not is_verified:
                continue

            model = await model_repo.get_active_by_code_and_provider(
                preferred_model_code,
                provider_id,
            )
            if model is None:
                continue

            return (
                provider,
                model,
                "default_verified_native_target",
                verify_reason,
            )

        return None, None, None, "default_verified_target_unavailable"

    @staticmethod
    async def _resolve_verified_native_target(
        *,
        normalized_config: AIProviderWebSearchConfig,
        runtime_provider: AIProvider | None,
        runtime_model: AIModel | None,
        runtime_model_code: str,
        provider_repo: AIProviderRepository,
        model_repo: AIModelRepository,
    ) -> tuple[AIProvider | None, AIModel | None, str | None, str]:
        explicit_target = normalized_config.verified_native_target
        if explicit_target is not None:
            provider, model, reason = await WebSearchOrchestrator._resolve_verified_target_from_config(
                target=explicit_target,
                provider_repo=provider_repo,
                model_repo=model_repo,
                runtime_model=runtime_model,
            )
            if provider is not None and model is not None:
                is_verified, verify_reason = await WebSearchOrchestrator._verify_native_runtime_candidate(
                    provider,
                    model_code=str(getattr(model, "code", "") or "").strip(),
                    allow_unverified_runtime_target=bool(
                        normalized_config.allow_unverified_runtime_target
                    ),
                )
                if not is_verified:
                    return (
                        None,
                        None,
                        None,
                        f"verified_target_rejected:{verify_reason}",
                    )
                return provider, model, "verified_native_target", verify_reason
            return None, None, None, reason

        (
            default_provider,
            default_model,
            default_source,
            default_reason,
        ) = await WebSearchOrchestrator._resolve_default_verified_native_target(
            runtime_provider=runtime_provider,
            runtime_model=runtime_model,
            runtime_model_code=runtime_model_code,
            provider_repo=provider_repo,
            model_repo=model_repo,
        )
        if default_provider is not None and default_model is not None:
            return default_provider, default_model, default_source, default_reason

        if (
            bool(normalized_config.allow_unverified_runtime_target)
            and runtime_provider is not None
            and runtime_model is not None
        ):
            return (
                runtime_provider,
                runtime_model,
                "runtime_unverified_override",
                "allow_unverified_runtime_target_override",
            )

        runtime_verify_reason = None
        if runtime_provider is not None and runtime_model is not None:
            _, runtime_verify_reason = await WebSearchOrchestrator._verify_native_runtime_candidate(
                runtime_provider,
                model_code=str(getattr(runtime_model, "code", "") or runtime_model_code),
                allow_unverified_runtime_target=False,
            )

        if runtime_provider is None or runtime_model is None:
            return None, None, None, default_reason or "runtime_target_missing"

        if runtime_verify_reason:
            return (
                None,
                None,
                None,
                f"{default_reason or 'default_verified_target_unavailable'}:{runtime_verify_reason}",
            )

        return None, None, None, default_reason or "default_verified_target_unavailable"

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
            strategy=resolved_config.strategy,
            provider_label=provider_label,
            model_code=model_code,
            locale=locale,
            max_results=effective_max_results,
            context=context,
        )

        if not resolved_config.enabled:
            return self._build_execution(
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
            )

        if resolved_config.strategy != STRATEGY_NATIVE_FIRST_FALLBACK_PUBLIC:
            return self._build_execution(
                query=rewritten_query,
                items=[],
                meta=WebSearchExecutionMeta(
                    status=STATUS_UNSUPPORTED,
                    attempted_backends=[],
                    selected_backend=None,
                    used_fallback=False,
                    failure_reason=f"unsupported web search strategy: {resolved_config.strategy}",
                    latency_ms=int((time.perf_counter() - start) * 1000),
                    provider=None,
                    provider_mode=None,
                    provider_chain=[],
                    cache_hit=False,
                ),
                duplicate_signature=duplicate_signature,
            )

        attempted_backends: list[str] = []
        provider_chain: list[str] = []
        selected_run: SearchProviderRun | None = None
        native_run: SearchProviderRun | None = None
        public_run: SearchProviderRun | None = None
        used_fallback = False
        fallback_reason: str | None = None
        native_failure_kind: str | None = None

        should_attempt_legacy_native = (
            resolved_config.provider is None
            and resolved_config.model is None
            and resolved_config.native_target_reason
            == "runtime_db_unavailable_for_verified_target_resolution"
        )

        if (
            (resolved_config.provider is None or resolved_config.model is None)
            and not should_attempt_legacy_native
        ):
            native_run = SearchProviderRun(
                provider=provider_label,
                provider_mode=PROVIDER_MODE_NATIVE,
                backend_key=None,
                status=STATUS_UNSUPPORTED,
                items=[],
                failure_reason=(
                    resolved_config.native_target_reason
                    or "verified native target unavailable"
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
                strategy=resolved_config.strategy,
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
                public_timeout_seconds = _clamp_stage_timeout_seconds(
                    resolved_config.public_timeout_seconds,
                    context=context,
                )
                public_provider = PublicHtmlSearchProvider(
                    providers=resolved_config.public_providers,
                )
                public_run = await public_provider.search(
                    query=rewritten_query,
                    max_results=effective_max_results,
                    locale=locale,
                    timeout_seconds=public_timeout_seconds,
                    context=context,
                    strategy=resolved_config.strategy,
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
        return self._build_execution(
            query=rewritten_query,
            items=list(selected_run.items),
            meta=meta,
            duplicate_signature=duplicate_signature,
        )

    async def _resolve_config(
        self,
        context: ExecutionContext | None,
    ) -> _ResolvedWebSearchConfig:
        defaults = _default_web_search_config()
        runtime_provider = None
        runtime_model = None
        raw_provider_config: dict | None = None
        context_db = getattr(context, "db", None) if context is not None else None
        provider_repo: AIProviderRepository | None = None
        model_repo: AIModelRepository | None = None
        if context_db is not None:
            provider_repo = AIProviderRepository(context_db)
            model_repo = AIModelRepository(context_db)
            runtime_provider, runtime_model = (
                await self._load_runtime_provider_and_model(
                    context=context,
                    provider_repo=provider_repo,
                    model_repo=model_repo,
                )
            )

        if (
            runtime_provider is not None
            and getattr(runtime_provider, "config", None) is not None
        ):
            if isinstance(runtime_provider.config, dict):
                raw_provider_config = dict(runtime_provider.config)
            else:
                reason = "invalid provider config.web_search: provider config must be an object"
                logger.warning(
                    "web_search config normalization failed, disabling runtime web_search: {}",
                    reason,
                )
                return _ResolvedWebSearchConfig(
                    enabled=False,
                    strategy=str(defaults.strategy),
                    max_results_cap=int(defaults.max_results_cap),
                    native_timeout_seconds=int(defaults.native_timeout_seconds),
                    public_timeout_seconds=int(defaults.public_timeout_seconds),
                    public_providers=list(defaults.public_providers),
                    provider=runtime_provider,
                    model=runtime_model,
                    runtime_provider=runtime_provider,
                    runtime_model=runtime_model,
                    native_target_reason=reason,
                    config_error=reason,
                )

        if (
            runtime_provider is not None
            and isinstance(raw_provider_config, dict)
            and "web_search" in raw_provider_config
        ):
            try:
                normalized = _normalize_provider_web_search_settings(raw_provider_config)
            except Exception as exc:  # noqa: BLE001
                reason = f"invalid provider config.web_search: {exc}"
                logger.warning(
                    "web_search config normalization failed, disabling runtime web_search: {}",
                    exc,
                )
                return _ResolvedWebSearchConfig(
                    enabled=False,
                    strategy=str(defaults.strategy),
                    max_results_cap=int(defaults.max_results_cap),
                    native_timeout_seconds=int(defaults.native_timeout_seconds),
                    public_timeout_seconds=int(defaults.public_timeout_seconds),
                    public_providers=list(defaults.public_providers),
                    provider=runtime_provider,
                    model=runtime_model,
                    runtime_provider=runtime_provider,
                    runtime_model=runtime_model,
                    native_target_reason=reason,
                    config_error=reason,
                )
        else:
            normalized = defaults

        resolved_provider = None
        resolved_model = None
        native_target_source = None
        native_target_reason = "verified_target_resolution_unavailable"
        if provider_repo is not None and model_repo is not None:
            (
                resolved_provider,
                resolved_model,
                native_target_source,
                native_target_reason,
            ) = await self._resolve_verified_native_target(
                normalized_config=normalized,
                runtime_provider=runtime_provider,
                runtime_model=runtime_model,
                runtime_model_code=str(
                    getattr(context, "runtime_model_code", "") or ""
                ).strip(),
                provider_repo=provider_repo,
                model_repo=model_repo,
            )
        elif (
            context_db is None
            and (
                context is not None
                and str(getattr(context, "runtime_model_code", "") or "").strip()
            )
        ):
            native_target_reason = "runtime_db_unavailable_for_verified_target_resolution"
        elif (
            context is not None
            and str(getattr(context, "runtime_model_code", "") or "").strip()
        ) or runtime_provider is None:
            native_target_reason = "runtime_target_missing"
        else:
            native_target_reason = "runtime_db_unavailable_for_verified_target_resolution"

        return _ResolvedWebSearchConfig(
            enabled=bool(normalized.enabled),
            strategy=str(normalized.strategy),
            max_results_cap=int(normalized.max_results_cap),
            native_timeout_seconds=int(normalized.native_timeout_seconds),
            public_timeout_seconds=int(normalized.public_timeout_seconds),
            public_providers=[
                str(provider_name)
                for provider_name in normalized.public_providers
                if str(provider_name or "").strip()
            ]
            or list(DEFAULT_PUBLIC_PROVIDERS),
            provider=resolved_provider,
            model=resolved_model,
            runtime_provider=runtime_provider,
            runtime_model=runtime_model,
            native_target_source=native_target_source,
            native_target_reason=native_target_reason,
            config_error=None,
        )

    @staticmethod
    def _build_execution(
        *,
        query: str,
        items: list[SearchResultItem],
        meta: WebSearchExecutionMeta,
        duplicate_signature: tuple[int, str, str, str, str, str, int],
    ) -> WebSearchExecution:
        if meta.status == STATUS_SUCCESS and items:
            output = _build_search_output_text(query, items)
        elif meta.status == STATUS_NO_RESULTS:
            output = f"No results found for: {query}"
        elif meta.status == STATUS_TIMEOUT:
            output = f"Search source timed out: {meta.failure_reason or 'timeout'}"
        elif meta.status == STATUS_PARSE_ERROR:
            output = (
                f"Search parser unavailable: {meta.failure_reason or 'search result parsing failed'}"
            )
        else:
            output = (
                f"Search source unavailable: {meta.failure_reason or 'search unavailable'}"
            )
        output = _decorate_duplicate_query_output(
            output=output,
            signature=duplicate_signature,
            status=meta.status,
        )
        return WebSearchExecution(output=output, items=items, meta=meta)


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
