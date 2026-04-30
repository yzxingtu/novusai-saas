from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.ai.web_search.orchestrator_support.native_target import (
    load_runtime_provider_and_model,
    resolve_native_readiness_target,
)
from app.ai.web_search.orchestrator_support.provider_selector import (
    default_web_search_config,
    normalize_provider_web_search_settings,
)
from app.ai.web_search.types import (
    DEFAULT_FALLBACK_PROVIDER,
    WEB_SEARCH_POLICY_NATIVE_FIRST_BAIDU_FALLBACK,
)
from app.core.logging import LogManager

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext
    from app.models.ai import AIModel, AIProvider
    from app.schemas.ai.provider import AIProviderWebSearchConfig

logger = LogManager.get_logger("ai.web_search")


@dataclass
class _ResolvedWebSearchConfig:
    enabled: bool
    policy: str
    max_results_cap: int
    native_timeout_seconds: int
    fallback_provider: str
    fallback_timeout_seconds: int
    provider: AIProvider | None = None
    model: AIModel | None = None
    runtime_provider: AIProvider | None = None
    runtime_model: AIModel | None = None
    native_readiness_source: str | None = None
    native_readiness_reason: str | None = None
    config_error: str | None = None


async def resolve_web_search_config(
    context: ExecutionContext | None,
) -> _ResolvedWebSearchConfig:
    defaults = default_web_search_config()
    runtime_provider = None
    runtime_model = None
    raw_provider_config: dict | None = None
    context_db = getattr(context, "db", None) if context is not None else None
    provider_repo = None
    model_repo = None
    if context_db is not None:
        from app.ai.web_search import orchestrator as ws_orchestrator

        provider_repo = ws_orchestrator.AIProviderRepository(context_db)
        model_repo = ws_orchestrator.AIModelRepository(context_db)
        runtime_provider, runtime_model = await load_runtime_provider_and_model(
            context=context,
            provider_repo=provider_repo,
            model_repo=model_repo,
        )

    if runtime_provider is not None and getattr(runtime_provider, "config", None) is not None:
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
                policy=WEB_SEARCH_POLICY_NATIVE_FIRST_BAIDU_FALLBACK,
                max_results_cap=int(defaults.max_results_cap),
                native_timeout_seconds=int(defaults.native_timeout_seconds),
                fallback_provider=str(defaults.fallback_provider),
                fallback_timeout_seconds=int(defaults.fallback_timeout_seconds),
                provider=runtime_provider,
                model=runtime_model,
                runtime_provider=runtime_provider,
                runtime_model=runtime_model,
                native_readiness_reason=reason,
                config_error=reason,
            )

    if (
        runtime_provider is not None
        and isinstance(raw_provider_config, dict)
        and "web_search" in raw_provider_config
    ):
        try:
            normalized: AIProviderWebSearchConfig = normalize_provider_web_search_settings(
                raw_provider_config,
            )
        except Exception as exc:  # noqa: BLE001
            reason = f"invalid provider config.web_search: {exc}"
            logger.warning(
                "web_search config normalization failed, disabling runtime web_search: {}",
                exc,
            )
            return _ResolvedWebSearchConfig(
                enabled=False,
                policy=WEB_SEARCH_POLICY_NATIVE_FIRST_BAIDU_FALLBACK,
                max_results_cap=int(defaults.max_results_cap),
                native_timeout_seconds=int(defaults.native_timeout_seconds),
                fallback_provider=str(defaults.fallback_provider),
                fallback_timeout_seconds=int(defaults.fallback_timeout_seconds),
                provider=runtime_provider,
                model=runtime_model,
                runtime_provider=runtime_provider,
                runtime_model=runtime_model,
                native_readiness_reason=reason,
                config_error=reason,
            )
    else:
        normalized = defaults

    resolved_provider = None
    resolved_model = None
    native_readiness_source = None
    native_readiness_reason = "native_readiness_resolution_unavailable"
    if provider_repo is not None and model_repo is not None:
        (
            resolved_provider,
            resolved_model,
            native_readiness_source,
            native_readiness_reason,
        ) = await resolve_native_readiness_target(
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
        native_readiness_reason = "runtime_db_unavailable_for_native_readiness_resolution"
    elif (
        context is not None
        and str(getattr(context, "runtime_model_code", "") or "").strip()
    ) or runtime_provider is None:
        native_readiness_reason = "runtime_readiness_candidate_missing"
    else:
        native_readiness_reason = "runtime_db_unavailable_for_native_readiness_resolution"

    return _ResolvedWebSearchConfig(
        enabled=bool(normalized.enabled),
        policy=WEB_SEARCH_POLICY_NATIVE_FIRST_BAIDU_FALLBACK,
        max_results_cap=int(normalized.max_results_cap),
        native_timeout_seconds=int(normalized.native_timeout_seconds),
        fallback_provider=str(normalized.fallback_provider or DEFAULT_FALLBACK_PROVIDER),
        fallback_timeout_seconds=int(normalized.fallback_timeout_seconds),
        provider=resolved_provider,
        model=resolved_model,
        runtime_provider=runtime_provider,
        runtime_model=runtime_model,
        native_readiness_source=native_readiness_source,
        native_readiness_reason=native_readiness_reason,
        config_error=None,
    )


__all__ = ["_ResolvedWebSearchConfig", "resolve_web_search_config"]
