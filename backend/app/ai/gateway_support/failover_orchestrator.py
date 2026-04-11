"""Gateway failover collaborator."""

from __future__ import annotations

from app.ai.failover import FailoverService
from app.models.ai import AIModel


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
    ) -> AIModel | None:
        return await self._failover_service.get_fallback_model(
            model_id,
            max_depth=max_depth,
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
