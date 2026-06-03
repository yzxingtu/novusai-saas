"""Gateway failover collaborator."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.ai.failover import FailoverService
from app.ai.routing.routing_capabilities import (
    detect_audio_video_attachments,
    detect_image_attachments,
)
from app.ai.types import ChatMessage
from app.ai.usage_mode import estimate_input_tokens
from app.models.ai import AIModel

_FAILOVER_RETIRED_RUNTIME_PROTOCOL_KEYS = frozenset(
    {
        "_runtime_force_protocol_path",
        "_runtime_force_wire_api",
    }
)


class GatewayFailoverOrchestrator:
    """Thin failover collaborator for gateway composition."""

    def __init__(self, failover_service: FailoverService) -> None:
        self._failover_service = failover_service

    async def is_provider_healthy(self, provider_id: int) -> bool:
        return await self._failover_service.is_provider_healthy(provider_id)

    async def get_fallback_model(
        self,
        model_id: int,
        *,
        max_depth: int = 3,
        needs_vision: bool = False,
        needs_audio: bool = False,
        needs_video: bool = False,
        needs_fc: bool = False,
        min_context_window: int | None = None,
    ) -> AIModel | None:
        return await self._failover_service.get_fallback_model(
            model_id,
            max_depth=max_depth,
            needs_vision=needs_vision,
            needs_audio=needs_audio,
            needs_video=needs_video,
            needs_fc=needs_fc,
            min_context_window=min_context_window,
        )

    @staticmethod
    async def get_all_provider_health() -> list[dict]:
        return await FailoverService.get_all_provider_health()

    @staticmethod
    async def get_provider_health_history(
        provider_id: int,
        *,
        limit: int = 100,
    ) -> list[dict]:
        return await FailoverService.get_provider_health_history(
            provider_id,
            limit=limit,
        )


def build_gateway_fallback_requirements(
    *,
    messages: Iterable[ChatMessage] | None,
    tools: list[dict] | None,
    estimated_input: int = 0,
) -> dict[str, Any]:
    message_list = list(messages or [])
    needs_vision = detect_image_attachments(None, message_list)
    needs_audio, needs_video = detect_audio_video_attachments(None, message_list)
    min_context_window = estimate_input_tokens(
        message_list,
        estimated_input=estimated_input,
    )
    return {
        "needs_vision": needs_vision,
        "needs_audio": needs_audio,
        "needs_video": needs_video,
        "needs_fc": bool(tools),
        "min_context_window": min_context_window or None,
    }


def scrub_gateway_failover_runtime_kwargs(
    extra_kwargs: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        key: value
        for key, value in dict(extra_kwargs or {}).items()
        if key not in _FAILOVER_RETIRED_RUNTIME_PROTOCOL_KEYS
    }
