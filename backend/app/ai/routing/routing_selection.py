"""
Routing selection seams for multimodal and long-context paths.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from app.ai.routing.routing_capabilities import model_satisfies_requirements
from app.ai.routing.routing_contracts import RouteResult
from app.ai.routing.routing_helpers import build_multimodal_reason, filter_tiers_by_max
from app.enums.ai import ModelTierEnum

if TYPE_CHECKING:
    from app.models.ai.agent import Agent
    from app.models.ai.model import AIModel
    from app.repositories.ai.model_repository import AIModelRepository

RouteFallback = Callable[["Agent", str], RouteResult]
ProviderHealthCheck = Callable[[int | None], Awaitable[bool]]


async def route_for_multimodal(
    *,
    routing_config: dict,
    agent: Agent,
    agent_provider_id: int | None,
    model_repo: AIModelRepository,
    has_image: bool,
    has_audio: bool,
    has_video: bool,
    needs_fc: bool,
    fallback: RouteFallback,
    is_provider_healthy: ProviderHealthCheck,
) -> RouteResult | None:
    """Route requests that require one or more multimodal capabilities."""
    agent_model: AIModel | None = getattr(agent, "model", None)
    if model_satisfies_requirements(
        agent_model,
        needs_vision=has_image,
        needs_audio=has_audio,
        needs_video=has_video,
        needs_fc=needs_fc,
    ) and await is_provider_healthy(getattr(agent_model, "provider_id", None)):
        return fallback(
            agent,
            reason=build_multimodal_reason(
                has_image=has_image,
                has_audio=has_audio,
                has_video=has_video,
                suffix="agent_model",
            ),
        )

    explicit_ids: list[int] = []
    vision_model_id: int | None = routing_config.get("vision_model_id")
    audio_model_id: int | None = routing_config.get("audio_model_id")
    video_model_id: int | None = routing_config.get("video_model_id")
    if has_video and video_model_id:
        explicit_ids.append(video_model_id)
    if has_audio and audio_model_id and audio_model_id not in explicit_ids:
        explicit_ids.append(audio_model_id)
    if has_image and vision_model_id and vision_model_id not in explicit_ids:
        explicit_ids.append(vision_model_id)

    for model_id_to_try in explicit_ids:
        model = await model_repo.get_active_with_provider(model_id_to_try)
        if (
            model
            and model_satisfies_requirements(
                model,
                needs_vision=has_image,
                needs_audio=has_audio,
                needs_video=has_video,
                needs_fc=needs_fc,
            )
            and await is_provider_healthy(model.provider_id)
        ):
            return RouteResult(
                provider_code=model.provider.code,
                model_code=model.code,
                model_id=model.id,
                tier=model.tier,
                reason=build_multimodal_reason(
                    has_image=has_image,
                    has_audio=has_audio,
                    has_video=has_video,
                    suffix="explicit_config",
                ),
                is_overridden=True,
            )

    fallback_tiers = [
        ModelTierEnum.STANDARD.value,
        ModelTierEnum.PREMIUM.value,
        ModelTierEnum.FAST.value,
    ]
    max_tier = routing_config.get("max_tier")
    if max_tier:
        fallback_tiers = filter_tiers_by_max(fallback_tiers, max_tier)

    for tier in fallback_tiers:
        model = await model_repo.get_by_tier(
            tier=tier,
            preferred_provider_id=agent_provider_id,
            supports_vision=has_image,
            supports_audio=has_audio,
            supports_video=has_video,
            supports_function_calling=needs_fc,
        )
        if model and await is_provider_healthy(model.provider_id):
            return RouteResult(
                provider_code=model.provider.code,
                model_code=model.code,
                model_id=model.id,
                tier=model.tier,
                reason=build_multimodal_reason(
                    has_image=has_image,
                    has_audio=has_audio,
                    has_video=has_video,
                    suffix="tier_fallback",
                ),
                is_overridden=True,
            )

    return None


async def route_for_long_context(
    *,
    routing_config: dict,
    agent: Agent,
    agent_provider_id: int | None,
    estimated_tokens: int,
    model_repo: AIModelRepository,
    needs_fc: bool,
    fallback: RouteFallback,
    is_provider_healthy: ProviderHealthCheck,
) -> RouteResult | None:
    """Long context routing: prioritize explicitly configured long_context_model_id."""
    agent_model: AIModel | None = getattr(agent, "model", None)
    if model_satisfies_requirements(
        agent_model,
        min_context_window=estimated_tokens,
        needs_fc=needs_fc,
    ) and await is_provider_healthy(getattr(agent_model, "provider_id", None)):
        return fallback(agent, reason="long_context:agent_model")

    lc_model_id: int | None = routing_config.get("long_context_model_id")
    if lc_model_id:
        model = await model_repo.get_active_with_provider(lc_model_id)
        if (
            model
            and model_satisfies_requirements(
                model,
                min_context_window=estimated_tokens,
                needs_fc=needs_fc,
            )
            and await is_provider_healthy(model.provider_id)
        ):
            return RouteResult(
                provider_code=model.provider.code,
                model_code=model.code,
                model_id=model.id,
                tier=model.tier,
                reason="long_context:explicit_config",
                is_overridden=True,
            )

    fallback_tiers = [
        ModelTierEnum.PREMIUM.value,
        ModelTierEnum.STANDARD.value,
        ModelTierEnum.FAST.value,
    ]
    max_tier = routing_config.get("max_tier")
    if max_tier:
        fallback_tiers = filter_tiers_by_max(fallback_tiers, max_tier)

    for tier in fallback_tiers:
        model = await model_repo.get_by_tier(
            tier=tier,
            preferred_provider_id=agent_provider_id,
            supports_function_calling=needs_fc,
            min_context_window=estimated_tokens,
        )
        if model and await is_provider_healthy(model.provider_id):
            return RouteResult(
                provider_code=model.provider.code,
                model_code=model.code,
                model_id=model.id,
                tier=model.tier,
                reason="long_context:tier_fallback",
                is_overridden=True,
            )

    return None


__all__ = ["route_for_long_context", "route_for_multimodal"]
