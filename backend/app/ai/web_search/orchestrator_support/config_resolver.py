from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.ai.web_search.orchestrator_support.provider_selector import (
    default_web_search_config,
    normalize_provider_web_search_settings,
)
from app.ai.web_search.types import (
    DEFAULT_PUBLIC_PROVIDER,
    WEB_SEARCH_POLICY_BUILTIN_PUBLIC,
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
    public_provider: str
    public_timeout_seconds: int
    provider: AIProvider | None = None
    model: AIModel | None = None
    runtime_provider: AIProvider | None = None
    runtime_model: AIModel | None = None
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
        runtime_provider_id = getattr(context, "runtime_provider_id", None)
        runtime_model_id = getattr(context, "runtime_model_id", None)
        runtime_model_code = str(
            getattr(context, "runtime_model_code", "") or ""
        ).strip()
        if runtime_provider_id is not None:
            runtime_provider = await provider_repo.get_by_id(int(runtime_provider_id))
        if runtime_model_id is not None:
            runtime_model = await model_repo.get_active_with_provider(
                int(runtime_model_id)
            )
        if (
            runtime_model is None
            and runtime_provider is not None
            and runtime_model_code
        ):
            runtime_model = await model_repo.get_active_by_code_and_provider(
                runtime_model_code,
                runtime_provider.id,
            )

    if (
        runtime_provider is not None
        and getattr(runtime_provider, "config", None) is not None
    ):
        if isinstance(runtime_provider.config, dict):
            raw_provider_config = dict(runtime_provider.config)
        else:
            reason = (
                "invalid provider config.web_search: provider config must be an object"
            )
            logger.warning(
                "web_search config normalization failed, disabling runtime web_search: {}",
                reason,
            )
            return _ResolvedWebSearchConfig(
                enabled=False,
                policy=WEB_SEARCH_POLICY_BUILTIN_PUBLIC,
                max_results_cap=int(defaults.max_results_cap),
                public_provider=str(defaults.fallback_provider),
                public_timeout_seconds=int(defaults.fallback_timeout_seconds),
                provider=runtime_provider,
                model=runtime_model,
                runtime_provider=runtime_provider,
                runtime_model=runtime_model,
                config_error=reason,
            )

    if (
        runtime_provider is not None
        and isinstance(raw_provider_config, dict)
        and "web_search" in raw_provider_config
    ):
        try:
            normalized: AIProviderWebSearchConfig = (
                normalize_provider_web_search_settings(
                    raw_provider_config,
                )
            )
        except Exception as exc:  # noqa: BLE001
            reason = f"invalid provider config.web_search: {exc}"
            logger.warning(
                "web_search config normalization failed, disabling runtime web_search: {}",
                exc,
            )
            return _ResolvedWebSearchConfig(
                enabled=False,
                policy=WEB_SEARCH_POLICY_BUILTIN_PUBLIC,
                max_results_cap=int(defaults.max_results_cap),
                public_provider=str(defaults.fallback_provider),
                public_timeout_seconds=int(defaults.fallback_timeout_seconds),
                provider=runtime_provider,
                model=runtime_model,
                runtime_provider=runtime_provider,
                runtime_model=runtime_model,
                config_error=reason,
            )
    else:
        normalized = defaults

    return _ResolvedWebSearchConfig(
        enabled=bool(normalized.enabled),
        policy=WEB_SEARCH_POLICY_BUILTIN_PUBLIC,
        max_results_cap=int(normalized.max_results_cap),
        public_provider=str(normalized.fallback_provider or DEFAULT_PUBLIC_PROVIDER),
        public_timeout_seconds=int(normalized.fallback_timeout_seconds),
        provider=runtime_provider,
        model=runtime_model,
        runtime_provider=runtime_provider,
        runtime_model=runtime_model,
        config_error=None,
    )


__all__ = ["_ResolvedWebSearchConfig", "resolve_web_search_config"]
