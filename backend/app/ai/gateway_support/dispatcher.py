"""Provider/model/API-key dispatcher helpers for AIGateway."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import _
from app.exceptions import BusinessException, NotFoundException
from app.models.ai import AIModel, AIProvider, ProviderApiKey
from app.repositories.ai import (
    AIModelRepository,
    AIProviderRepository,
    ProviderApiKeyRepository,
)


class GatewayDispatcher:
    """Read-only dispatch collaborator for provider/model/key lookup."""

    def __init__(self, db: AsyncSession):
        self._provider_repo = AIProviderRepository(db)
        self._api_key_repo = ProviderApiKeyRepository(db)
        self._model_repo = AIModelRepository(db)

    async def resolve_provider_and_key(
        self,
        *,
        provider_code: str,
        tenant_id: int | None,
    ) -> tuple[AIProvider, ProviderApiKey]:
        provider = await self._provider_repo.get_by_code(provider_code)
        if not provider or not provider.is_active:
            raise NotFoundException(message=_("ai.provider_not_found"))

        api_key = await self._api_key_repo.get_available_key(
            provider_id=provider.id,
            tenant_id=tenant_id,
        )
        if not api_key:
            raise BusinessException(message=_("ai.no_api_key"))
        if not api_key.is_available():
            raise BusinessException(message=_("ai.api_key_unavailable"))
        return provider, api_key

    async def resolve_model(
        self,
        *,
        model_name: str,
        provider_id: int,
    ) -> AIModel | None:
        model = await self._model_repo.get_active_by_code_and_provider(
            model_name,
            provider_id,
        )
        if model is not None:
            return model
        return await self._model_repo.get_active_by_name_and_provider(
            model_name,
            provider_id,
        )
