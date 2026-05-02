from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from redis.exceptions import RedisError

from app.ai.adapters.openai_compatible.capabilities import OpenAIProtocolCapabilities
from app.ai.exceptions import ProviderError
from app.ai.failover import HEALTH_KEY_PREFIX
from app.ai.web_search.orchestrator_support.provider_selector import (
    is_native_runtime_readiness_candidate as _support_is_native_runtime_readiness_candidate,
)
from app.repositories.ai import AIModelRepository, AIProviderRepository
from app.schemas.ai.provider import AIProviderWebSearchConfig

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext
    from app.models.ai import AIModel, AIProvider

_TRUSTED_OPENAI_COMPATIBLE_HOSTS = frozenset(
    {
        "api.openai.com",
    }
)
_HEALTH_VERIFIED_NATIVE_SEARCH_MAX_AGE = timedelta(hours=24)


def normalize_wire_api(wire_api: object) -> str:
    normalized = str(wire_api or "").strip().lower().replace("-", "_")
    if normalized in {"responses", "response", "responses_api"}:
        return "responses"
    return normalized


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


def _provider_config(provider: AIProvider | None) -> dict:
    raw_config = getattr(provider, "config", None) if provider is not None else None
    return dict(raw_config or {}) if isinstance(raw_config, dict) else {}


def _check_native_protocol_config(provider: AIProvider | None) -> tuple[bool, str]:
    provider_config = _provider_config(provider)
    web_search_config = provider_config.get("web_search")
    if (
        isinstance(web_search_config, dict)
        and web_search_config.get("enabled") is False
    ):
        return False, "provider_web_search_disabled"
    try:
        capabilities = OpenAIProtocolCapabilities.from_provider_config(
            provider_config=provider_config,
            configured_wire_api=provider_config.get("wire_api"),
        )
    except ProviderError as exc:
        return False, f"provider_protocol_capabilities_invalid:{exc.error_code}"
    if not capabilities.supports_wire_api("responses"):
        allowed = (
            ",".join(capabilities.allowed_wire_apis) or capabilities.primary_wire_api
        )
        return False, f"provider_responses_wire_api_unsupported:{allowed}"
    return True, "provider_responses_wire_api_supported"


async def is_health_ready_native_candidate(
    provider: AIProvider | None,
    *,
    model_code: str,
) -> tuple[bool, str]:
    if provider is None:
        return False, "provider_health_missing"

    provider_id = int(getattr(provider, "id", 0) or 0)
    if provider_id <= 0:
        return False, "provider_health_missing"

    provider_config = _provider_config(provider)
    wire_api = normalize_wire_api(provider_config.get("wire_api"))
    if wire_api != "responses":
        return False, f"provider_health_wire_api_mismatch:{wire_api or 'unknown'}"

    try:
        from app.ai.web_search import orchestrator as ws_orchestrator

        redis = await ws_orchestrator.get_redis()
        raw_payload = await redis.get(HEALTH_KEY_PREFIX.format(provider_id=provider_id))
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

    checked_at = _parse_health_checked_at(payload.get("checked_at"))
    if checked_at is None:
        return False, "provider_health_missing_checked_at"
    if datetime.now(timezone.utc) - checked_at > _HEALTH_VERIFIED_NATIVE_SEARCH_MAX_AGE:
        return False, "provider_health_stale"

    probe_model = str(payload.get("tool_probe_model") or "").strip()
    normalized_model_code = str(model_code or "").strip()
    if probe_model and normalized_model_code and probe_model != normalized_model_code:
        return False, f"provider_health_model_mismatch:{probe_model}"

    return (
        True,
        f"responses_tool_probe_verified:{provider_id}:{probe_model or normalized_model_code or 'unknown'}",
    )


async def check_native_runtime_readiness(
    provider: AIProvider | None,
    *,
    model_code: str,
) -> tuple[bool, str]:
    if provider is None:
        return False, "runtime_provider_missing"

    provider_type = str(getattr(provider, "type", "") or "").strip().lower()
    if provider_type != "openai_compatible":
        return False, f"provider_type_native_denied:{provider_type or 'unknown'}"

    config_ready, config_reason = _check_native_protocol_config(provider)
    if not config_ready:
        return False, config_reason

    is_ready, readiness_reason = _support_is_native_runtime_readiness_candidate(
        provider,
        trusted_hosts=_TRUSTED_OPENAI_COMPATIBLE_HOSTS,
    )
    if is_ready:
        return True, readiness_reason

    health_ready, health_reason = await is_health_ready_native_candidate(
        provider,
        model_code=model_code,
    )
    if health_ready:
        return True, health_reason
    return False, f"{readiness_reason}:{health_reason}"


async def load_runtime_provider_and_model(
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
    if model is None and provider is not None and runtime_model_code:
        model = await model_repo.get_active_by_code_and_provider(
            runtime_model_code,
            provider.id,
        )
    return provider, model


async def resolve_default_native_readiness_target(
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
        is_ready, readiness_reason = await check_native_runtime_readiness(
            runtime_provider,
            model_code=preferred_model_code,
        )
        if is_ready:
            return (
                runtime_provider,
                runtime_model,
                "default_native_readiness_target",
                readiness_reason,
            )
        runtime_provider_id = int(getattr(runtime_provider, "id", 0) or 0)
    else:
        runtime_provider_id = 0

    if not preferred_model_code:
        return None, None, None, "default_native_readiness_target_model_code_missing"

    active_providers = await provider_repo.get_active_providers()
    for provider in active_providers:
        provider_id = int(getattr(provider, "id", 0) or 0)
        if provider_id and provider_id == runtime_provider_id:
            continue

        is_ready, readiness_reason = await check_native_runtime_readiness(
            provider,
            model_code=preferred_model_code,
        )
        if not is_ready:
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
            "default_native_readiness_target",
            readiness_reason,
        )

    return None, None, None, "default_native_readiness_target_unavailable"


async def resolve_native_readiness_target(
    *,
    normalized_config: AIProviderWebSearchConfig,
    runtime_provider: AIProvider | None,
    runtime_model: AIModel | None,
    runtime_model_code: str,
    provider_repo: AIProviderRepository,
    model_repo: AIModelRepository,
) -> tuple[AIProvider | None, AIModel | None, str | None, str]:
    _ = normalized_config
    (
        default_provider,
        default_model,
        default_source,
        default_reason,
    ) = await resolve_default_native_readiness_target(
        runtime_provider=runtime_provider,
        runtime_model=runtime_model,
        runtime_model_code=runtime_model_code,
        provider_repo=provider_repo,
        model_repo=model_repo,
    )
    if default_provider is not None and default_model is not None:
        return default_provider, default_model, default_source, default_reason

    runtime_readiness_reason = None
    if runtime_provider is not None and runtime_model is not None:
        _, runtime_readiness_reason = await check_native_runtime_readiness(
            runtime_provider,
            model_code=str(getattr(runtime_model, "code", "") or runtime_model_code),
        )

    if runtime_provider is None or runtime_model is None:
        reason = default_reason or "runtime_readiness_candidate_missing"
        return None, None, None, reason

    if runtime_readiness_reason:
        reason = f"{default_reason or 'default_native_readiness_target_unavailable'}:{runtime_readiness_reason}"
        return (
            None,
            None,
            None,
            reason,
        )

    return (
        None,
        None,
        None,
        default_reason or "default_native_readiness_target_unavailable",
    )


__all__ = [
    "check_native_runtime_readiness",
    "load_runtime_provider_and_model",
    "resolve_native_readiness_target",
]
