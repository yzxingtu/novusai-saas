"""API key service unit tests / AI API Key 服务单元测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.enums.common import ResourceScopeEnum
from app.schemas.ai.api_key import ProviderApiKeyCreate, ProviderApiKeyUpdate


class _FakeProviderApiKey:
    def __init__(self, **kwargs):
        self.id = kwargs.pop("id", 101)
        self.encrypted_value = None
        self.__dict__.update(kwargs)

    def encrypt_key(self, raw_key: str) -> None:
        self.encrypted_value = raw_key

    def update_from_dict(self, data: dict) -> None:
        self.__dict__.update(data)


class TestCreateKey:
    @pytest.mark.asyncio
    async def test_create_key_normalizes_scope_and_syncs_assignments(self, mock_db):
        from app.services.ai.api_key_service import ProviderApiKeyService

        rta_repo = MagicMock()
        rta_repo.sync_assignments = AsyncMock()

        service = ProviderApiKeyService.__new__(ProviderApiKeyService)
        service.db = mock_db
        service.repo = AsyncMock()

        with (
            patch(
                "app.services.ai.api_key_service.ProviderApiKey",
                _FakeProviderApiKey,
            ),
            patch(
                "app.services.ai.api_key_service.ResourceTenantAssignmentRepository",
                return_value=rta_repo,
            ),
        ):
            key = await service.create_key(
                ProviderApiKeyCreate(
                    provider_id=1,
                    scope=ResourceScopeEnum.ALL_TENANTS.value,
                    tenant_id=5,
                    name="Primary",
                    api_key="secret",
                )
            )

        assert key.scope == ResourceScopeEnum.SELECTED_TENANTS.value
        assert key.owner_tenant_id == 5
        assert key.encrypted_value == "secret"
        mock_db.add.assert_called_once_with(key)
        mock_db.flush.assert_awaited_once()
        rta_repo.sync_assignments.assert_awaited_once_with("ai_api_key", 101, [5])

    @pytest.mark.asyncio
    async def test_create_key_raises_when_selected_scope_has_no_owner(self, mock_db):
        from app.exceptions import ValidationException
        from app.services.ai.api_key_service import ProviderApiKeyService

        service = ProviderApiKeyService.__new__(ProviderApiKeyService)
        service.db = mock_db
        service.repo = AsyncMock()

        with pytest.raises(ValidationException):
            await service.create_key(
                ProviderApiKeyCreate(
                    provider_id=1,
                    scope=ResourceScopeEnum.SELECTED_TENANTS.value,
                    name="Broken",
                    api_key="secret",
                )
            )


class TestUpdateKey:
    @pytest.mark.asyncio
    async def test_update_key_updates_metadata_with_real_schema(self, mock_db):
        from app.services.ai.api_key_service import ProviderApiKeyService

        key = _FakeProviderApiKey(id=7, name="Old", is_active=True)
        service = ProviderApiKeyService.__new__(ProviderApiKeyService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.get_by_id = AsyncMock(return_value=key)

        result = await service.update_key(
            7,
            ProviderApiKeyUpdate(name="Updated", is_active=False),
        )

        assert result.name == "Updated"
        assert result.is_active is False
        assert result.encrypted_value is None
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_key_raises_when_key_is_missing(self, mock_db):
        from app.exceptions import NotFoundException
        from app.services.ai.api_key_service import ProviderApiKeyService

        service = ProviderApiKeyService.__new__(ProviderApiKeyService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await service.update_key(7, ProviderApiKeyUpdate(name="Updated"))


class TestToggleStatus:
    @pytest.mark.asyncio
    async def test_toggle_status_flips_active_flag(self, mock_db):
        from app.services.ai.api_key_service import ProviderApiKeyService

        key = _FakeProviderApiKey(id=9, is_active=True)
        service = ProviderApiKeyService.__new__(ProviderApiKeyService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.get_by_id = AsyncMock(return_value=key)

        result = await service.toggle_status(9)

        assert result.is_active is False
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_toggle_status_raises_when_key_is_missing(self, mock_db):
        from app.exceptions import NotFoundException
        from app.services.ai.api_key_service import ProviderApiKeyService

        service = ProviderApiKeyService.__new__(ProviderApiKeyService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await service.toggle_status(9)


class TestDelegatingMethods:
    @pytest.mark.asyncio
    async def test_increment_usage_delegates_with_default_increment(self, mock_db):
        from app.services.ai.api_key_service import ProviderApiKeyService

        service = ProviderApiKeyService.__new__(ProviderApiKeyService)
        service.db = mock_db
        service.repo = AsyncMock()

        await service.increment_usage(12)

        service.repo.update_usage_count.assert_awaited_once_with(12, 1)

    @pytest.mark.asyncio
    async def test_increment_usage_delegates_custom_increment(self, mock_db):
        from app.services.ai.api_key_service import ProviderApiKeyService

        service = ProviderApiKeyService.__new__(ProviderApiKeyService)
        service.db = mock_db
        service.repo = AsyncMock()

        await service.increment_usage(12, increment=5)

        service.repo.update_usage_count.assert_awaited_once_with(12, 5)

    @pytest.mark.asyncio
    async def test_get_keys_by_provider_returns_repo_values(self, mock_db):
        from app.services.ai.api_key_service import ProviderApiKeyService

        service = ProviderApiKeyService.__new__(ProviderApiKeyService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_keys_by_provider = AsyncMock(
            return_value=[SimpleNamespace(id=1)]
        )

        result = await service.get_keys_by_provider(provider_id=3, tenant_id=8)

        assert len(result) == 1
        service.repo.get_keys_by_provider.assert_awaited_once_with(
            provider_id=3,
            tenant_id=8,
        )

    @pytest.mark.asyncio
    async def test_get_keys_by_provider_returns_empty_list_for_default_filters(
        self, mock_db
    ):
        from app.services.ai.api_key_service import ProviderApiKeyService

        service = ProviderApiKeyService.__new__(ProviderApiKeyService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_keys_by_provider = AsyncMock(return_value=[])

        assert await service.get_keys_by_provider() == []

    @pytest.mark.asyncio
    async def test_get_available_key_returns_repo_match(self, mock_db):
        from app.services.ai.api_key_service import ProviderApiKeyService

        service = ProviderApiKeyService.__new__(ProviderApiKeyService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_available_key = AsyncMock(return_value=SimpleNamespace(id=2))

        result = await service.get_available_key(provider_id=5, tenant_id=9)

        assert result.id == 2
        service.repo.get_available_key.assert_awaited_once_with(
            provider_id=5,
            tenant_id=9,
        )

    @pytest.mark.asyncio
    async def test_get_available_key_returns_none_when_repo_has_no_match(self, mock_db):
        from app.services.ai.api_key_service import ProviderApiKeyService

        service = ProviderApiKeyService.__new__(ProviderApiKeyService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_available_key = AsyncMock(return_value=None)

        assert await service.get_available_key(provider_id=5) is None
