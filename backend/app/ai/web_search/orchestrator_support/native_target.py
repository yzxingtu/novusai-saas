from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from redis.exceptions import RedisError

from app.ai.failover import HEALTH_KEY_PREFIX
from app.ai.web_search.orchestrator_support.provider_selector import (
    is_verified_native_runtime_candidate as _support_is_verified_native_runtime_candidate,
)
from app.repositories.ai import AIModelRepository, AIProviderRepository
from app.schemas.ai.provider import (
    AIProviderWebSearchConfig,
    AIProviderWebSearchVerifiedTarget,
)

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


async def is_health_verified_native_candidate(
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


async def verify_native_runtime_candidate(
    provider: AIProvider | None,
    *,
    model_code: str,
    allow_unverified_runtime_target: bool,
) -> tuple[bool, str]:
    is_verified, verify_reason = _support_is_verified_native_runtime_candidate(
        provider,
        allow_unverified_runtime_target=allow_unverified_runtime_target,
        trusted_hosts=_TRUSTED_OPENAI_COMPATIBLE_HOSTS,
    )
    if is_verified:
        return True, verify_reason
    if provider is None or allow_unverified_runtime_target:
        return is_verified, verify_reason

    provider_type = str(getattr(provider, "type", "") or "").strip().lower()
    if provider_type != "openai_compatible":
        return False, verify_reason

    health_verified, health_reason = await is_health_verified_native_candidate(
        provider,
        model_code=model_code,
    )
    if health_verified:
        return True, health_reason
    return False, f"{verify_reason}:{health_reason}"


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


async def resolve_verified_target_from_config(
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


async def resolve_default_verified_native_target(
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
        is_verified, verify_reason = await verify_native_runtime_candidate(
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

        is_verified, verify_reason = await verify_native_runtime_candidate(
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


async def resolve_verified_native_target(
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
        provider, model, reason = await resolve_verified_target_from_config(
            target=explicit_target,
            provider_repo=provider_repo,
            model_repo=model_repo,
            runtime_model=runtime_model,
        )
        if provider is not None and model is not None:
            is_verified, verify_reason = await verify_native_runtime_candidate(
                provider,
                model_code=str(getattr(model, "code", "") or "").strip(),
                allow_unverified_runtime_target=bool(
                    normalized_config.allow_unverified_runtime_target
                ),
            )
            if not is_verified:
                return None, None, None, f"verified_target_rejected:{verify_reason}"
            return provider, model, "verified_native_target", verify_reason
        return None, None, None, reason

    (
        default_provider,
        default_model,
        default_source,
        default_reason,
    ) = await resolve_default_verified_native_target(
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
        _, runtime_verify_reason = await verify_native_runtime_candidate(
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


__all__ = [
    "load_runtime_provider_and_model",
    "resolve_verified_native_target",
    "verify_native_runtime_candidate",
]
