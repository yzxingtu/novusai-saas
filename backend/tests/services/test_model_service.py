"""Model service unit tests / AI 模型服务单元测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.ai.model import AIModelCreate, AIModelUpdate


class _FakeModel:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def update_from_dict(self, data):
        self.__dict__.update(data)


class TestModelQueries:

    @pytest.mark.asyncio
    async def test_get_by_code_returns_model_from_repo(self, mock_db):
        from app.services.ai.model_service import AIModelService

        service = AIModelService.__new__(AIModelService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_code = AsyncMock(return_value=SimpleNamespace(code="gpt-4o"))

        result = await service.get_by_code("gpt-4o")

        assert result.code == "gpt-4o"

    @pytest.mark.asyncio
    async def test_get_by_code_returns_none_when_repo_misses(self, mock_db):
        from app.services.ai.model_service import AIModelService

        service = AIModelService.__new__(AIModelService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_code = AsyncMock(return_value=None)

        assert await service.get_by_code("missing") is None

    @pytest.mark.asyncio
    async def test_get_by_provider_passes_include_deleted_flag(self, mock_db):
        from app.services.ai.model_service import AIModelService

        service = AIModelService.__new__(AIModelService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_provider = AsyncMock(return_value=[SimpleNamespace(id=1)])

        result = await service.get_by_provider(3, include_deleted=True)

        assert len(result) == 1
        service.repo.get_by_provider.assert_awaited_once_with(3, include_deleted=True)

    @pytest.mark.asyncio
    async def test_get_by_provider_returns_empty_list_when_repo_has_no_items(self, mock_db):
        from app.services.ai.model_service import AIModelService

        service = AIModelService.__new__(AIModelService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.get_by_provider = AsyncMock(return_value=[])

        assert await service.get_by_provider(99) == []


class TestCreateModel:

    @pytest.mark.asyncio
    async def test_create_model_adds_new_model_when_code_is_unique(self, mock_db):
        from app.services.ai import model_service as module
        from app.services.ai.model_service import AIModelService

        service = AIModelService.__new__(AIModelService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.code_exists = AsyncMock(return_value=False)

        with patch.object(module, "AIModel", _FakeModel):
            model_obj = await service.create_model(
                AIModelCreate(
                    provider_id=1,
                    name="GPT-4o",
                    code="gpt-4o",
                    type="chat",
                )
            )

        assert model_obj.code == "gpt-4o"
        mock_db.add.assert_called_once_with(model_obj)
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_model_raises_when_code_already_exists(self, mock_db):
        from app.exceptions import ConflictException
        from app.services.ai.model_service import AIModelService

        service = AIModelService.__new__(AIModelService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.code_exists = AsyncMock(return_value=True)

        with pytest.raises(ConflictException):
            await service.create_model(
                AIModelCreate(
                    provider_id=1,
                    name="GPT-4o",
                    code="gpt-4o",
                    type="chat",
                )
            )


class TestUpdateModel:

    @pytest.mark.asyncio
    async def test_update_model_updates_fields_when_model_exists(self, mock_db):
        from app.services.ai.model_service import AIModelService

        existing = _FakeModel(id=7, code="gpt-4o", name="Old Name")
        service = AIModelService.__new__(AIModelService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.get_by_id = AsyncMock(return_value=existing)
        service.repo.code_exists = AsyncMock(return_value=False)

        result = await service.update_model(7, AIModelUpdate(name="New Name"))

        assert result.name == "New Name"
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_model_raises_when_model_is_missing(self, mock_db):
        from app.exceptions import NotFoundException
        from app.services.ai.model_service import AIModelService

        service = AIModelService.__new__(AIModelService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await service.update_model(7, AIModelUpdate(name="New Name"))


class TestDeleteModel:

    @pytest.mark.asyncio
    async def test_delete_model_calls_soft_delete_path(self, mock_db):
        from app.services.ai.model_service import AIModelService

        service = AIModelService.__new__(AIModelService)
        service.db = mock_db
        service.delete = AsyncMock(return_value=True)

        await service.delete_model(5)

        service.delete.assert_awaited_once_with(5, soft=True)

    @pytest.mark.asyncio
    async def test_delete_model_raises_when_delete_returns_false(self, mock_db):
        from app.exceptions import NotFoundException
        from app.services.ai.model_service import AIModelService

        service = AIModelService.__new__(AIModelService)
        service.db = mock_db
        service.delete = AsyncMock(return_value=False)

        with pytest.raises(NotFoundException):
            await service.delete_model(5)


class TestFetchRemoteModels:

    @pytest.mark.asyncio
    async def test_fetch_remote_models_merges_extra_models_and_enriches_capabilities(
        self, mock_db
    ):
        from app.services.ai.model_service import AIModelService

        provider = SimpleNamespace(
            id=1,
            is_active=True,
            type="openai",
            code="openai",
            base_url="https://api.example.com",
            config={"extra_models": [{"id": "embedding-model"}]},
        )
        api_key = SimpleNamespace(
            is_available=lambda: True,
            decrypt_key=lambda: "secret-key",
        )
        adapter = MagicMock()
        adapter.list_models = AsyncMock(return_value=[{"id": "chat-model"}])
        provider_repo = MagicMock()
        provider_repo.get_by_id = AsyncMock(return_value=provider)
        api_key_repo = MagicMock()
        api_key_repo.get_available_key = AsyncMock(return_value=api_key)

        service = AIModelService.__new__(AIModelService)
        service.db = mock_db

        with patch(
            "app.repositories.ai.AIProviderRepository",
            return_value=provider_repo,
        ), patch(
            "app.repositories.ai.ProviderApiKeyRepository",
            return_value=api_key_repo,
        ), patch(
            "app.ai.adapters.AdapterRegistry.create_adapter",
            return_value=adapter,
        ), patch(
            "app.services.ai.model_capability_lookup.enrich_remote_models",
            new=AsyncMock(return_value=[{"id": "chat-model"}, {"id": "embedding-model"}]),
        ) as enrich_remote_models:
            result = await service.fetch_remote_models(1)

        assert result == [{"id": "chat-model"}, {"id": "embedding-model"}]
        enriched_input = enrich_remote_models.await_args.args[0]
        assert {item["id"] for item in enriched_input} == {"chat-model", "embedding-model"}

    @pytest.mark.asyncio
    async def test_fetch_remote_models_raises_when_remote_adapter_fails(self, mock_db):
        from app.exceptions import ExternalServiceException
        from app.services.ai.model_service import AIModelService

        provider = SimpleNamespace(
            id=1,
            is_active=True,
            type="openai",
            code="openai",
            base_url="https://api.example.com",
            config={},
        )
        api_key = SimpleNamespace(
            is_available=lambda: True,
            decrypt_key=lambda: "secret-key",
        )
        adapter = MagicMock()
        adapter.list_models = AsyncMock(side_effect=RuntimeError("boom"))
        provider_repo = MagicMock()
        provider_repo.get_by_id = AsyncMock(return_value=provider)
        api_key_repo = MagicMock()
        api_key_repo.get_available_key = AsyncMock(return_value=api_key)

        service = AIModelService.__new__(AIModelService)
        service.db = mock_db

        with patch(
            "app.repositories.ai.AIProviderRepository",
            return_value=provider_repo,
        ), patch(
            "app.repositories.ai.ProviderApiKeyRepository",
            return_value=api_key_repo,
        ), patch(
            "app.ai.adapters.AdapterRegistry.create_adapter",
            return_value=adapter,
        ), pytest.raises(ExternalServiceException, match="boom"):
            await service.fetch_remote_models(1)
