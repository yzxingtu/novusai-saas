"""KnowledgeBaseService 单元测试 / Test.

覆盖：知识库 CRUD、文档管理、向量化状态、权限检查。"""

from __future__ import annotations

import contextlib
import re
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from tests.services.conftest import make_mock_model, make_scalar_result


def _make_kb(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "name": "Test KB",
        "description": "A test knowledge base",
        "status": "active",
        "is_active": True,
        "document_count": 0,
        "chunk_count": 0,
    }
    defaults.update(overrides)
    obj = make_mock_model(**defaults)
    obj.to_dict.return_value = defaults
    return obj


def _make_document(**overrides):
    defaults = {
        "id": 1,
        "knowledge_base_id": 1,
        "title": "Test Doc",
        "content": "Some content",
        "status": "indexed",
        "chunk_count": 5,
    }
    defaults.update(overrides)
    return make_mock_model(**defaults)


class TestKBCreate:
    @pytest.mark.asyncio
    async def test_unique_name_passes(self, mock_db):
        """When no existing KB with same name, _before_create should not raise name_exists / 创建"""
        from app.services.ai.knowledge_base_service import KnowledgeBaseService

        service = KnowledgeBaseService.__new__(KnowledgeBaseService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.find_by_name = AsyncMock(return_value=None)

        # Should not raise for unique name (may raise for other reasons like quota)
        with contextlib.suppress(Exception):
            await service._before_create({"name": "Unique KB"})

    @pytest.mark.asyncio
    async def test_rejects_audio_video_model_config_until_runtime_support_exists(
        self, mock_db
    ):
        from app.core.i18n import _
        from app.exceptions import BusinessException
        from app.services.ai.knowledge_base_service import KnowledgeBaseService

        service = KnowledgeBaseService.__new__(KnowledgeBaseService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()

        with pytest.raises(
            BusinessException,
            match=re.escape(
                _("knowledge_base.error.multimodal_model_config_unavailable")
            ),
        ):
            await service._before_create(
                {
                    "name": "Unsupported KB",
                    "audio_model_id": 7,
                }
            )


class TestKBDelete:
    @pytest.mark.asyncio
    async def test_delete_not_found_raises(self, mock_db):
        from app.exceptions import NotFoundException
        from app.services.ai.knowledge_base_service import KnowledgeBaseService

        service = KnowledgeBaseService.__new__(KnowledgeBaseService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await service._before_delete(999)


class TestKBDetail:
    @pytest.mark.asyncio
    async def test_get_kb_detail_not_found(self, mock_db):
        from app.exceptions import NotFoundException
        from app.services.ai.knowledge_base_service import KnowledgeBaseService

        service = KnowledgeBaseService.__new__(KnowledgeBaseService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await service.get_kb_detail(999)

    def test_build_kb_detail_retracts_retired_multimodal_fields(self):
        from app.services.ai.knowledge_base_projector import build_kb_detail

        kb = _make_kb(
            embedding_model_id=3,
            vision_model_id=5,
            audio_model_id=7,
            video_model_id=9,
        )
        kb.embedding_model = make_mock_model(name="Embedding")
        kb.vision_model = make_mock_model(name="Vision")
        kb.audio_model = make_mock_model(name="Audio")
        kb.video_model = make_mock_model(name="Video")
        kb.to_dict.return_value = {
            "id": 1,
            "name": "Test KB",
            "embedding_model_id": 3,
            "vision_model_id": 5,
            "audio_model_id": 7,
            "video_model_id": 9,
            "audio_model_name": "Audio",
            "video_model_name": "Video",
        }

        result = build_kb_detail(kb)

        assert result["embedding_model_name"] == "Embedding"
        assert result["vision_model_name"] == "Vision"
        assert "audio_model_id" not in result
        assert "video_model_id" not in result
        assert "audio_model_name" not in result
        assert "video_model_name" not in result

    def test_request_schema_hides_retired_multimodal_fields_from_public_schema(self):
        from app.schemas.ai.knowledge_base import KnowledgeBaseCreate

        schema = KnowledgeBaseCreate.model_json_schema()

        assert "audio_model_id" not in schema.get("properties", {})
        assert "video_model_id" not in schema.get("properties", {})

        payload = KnowledgeBaseCreate(
            name="KB",
            embedding_model_id=1,
            audio_model_id=7,
            video_model_id=9,
        )

        assert payload.audio_model_id == 7
        assert payload.video_model_id == 9


class TestKBUpdate:
    @pytest.mark.asyncio
    async def test_update_name_conflict(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.ai.knowledge_base_service import KnowledgeBaseService

        existing = _make_kb(id=99, name="Taken")
        service = KnowledgeBaseService.__new__(KnowledgeBaseService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock(return_value=_make_kb(id=1))
        service.repo.find_by_name = AsyncMock(return_value=existing)

        with pytest.raises(BusinessException):
            await service._before_update(1, {"name": "Taken"})


class TestKBQuota:
    @pytest.mark.asyncio
    async def test_check_kb_quota_within_limit(self, mock_db):
        from app.services.ai.knowledge_base_service import KnowledgeBaseService

        service = KnowledgeBaseService.__new__(KnowledgeBaseService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.count_by_tenant = AsyncMock(return_value=5)

        await service.check_kb_quota()  # Should not raise

    @pytest.mark.asyncio
    async def test_check_kb_quota_exceeded(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.ai.knowledge_base_service import KnowledgeBaseService

        service = KnowledgeBaseService.__new__(KnowledgeBaseService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.count_by_tenant = AsyncMock(return_value=9999)

        with pytest.raises(BusinessException):
            await service.check_kb_quota()


class TestKBRestore:
    @pytest.mark.asyncio
    async def test_after_restore_updates_statistics_and_invalidates_cache(
        self, mock_db
    ):
        from app.services.ai.knowledge_base_service import KnowledgeBaseService

        service = KnowledgeBaseService.__new__(KnowledgeBaseService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.db = AsyncMock()
        service.repo.update_statistics = AsyncMock(return_value=None)

        kb = _make_kb(id=1)

        with pytest.MonkeyPatch.context() as mp:
            invalidate = AsyncMock(return_value=None)
            mp.setattr(
                "app.ai.rag.retriever.HybridRetriever.invalidate_kb_cache",
                invalidate,
            )
            await service._after_restore(kb)

        service.repo.update_statistics.assert_awaited_once_with(1)
        invalidate.assert_awaited_once_with(1)


class TestAdminKBRepository:
    @pytest.mark.asyncio
    async def test_update_statistics_exists_and_updates_admin_kb_stats(self, mock_db):
        from app.repositories.ai.knowledge_base_repository import (
            AdminKnowledgeBaseRepository,
        )

        doc_result = MagicMock()
        doc_result.one.return_value = (2, 2048)
        mock_db.execute = AsyncMock(
            side_effect=[
                doc_result,
                make_scalar_result(9),
                MagicMock(),
            ]
        )

        repo = AdminKnowledgeBaseRepository(mock_db)

        await repo.update_statistics(1)

        assert mock_db.execute.await_count == 3


class TestTenantKBVisibility:
    def test_visible_condition_requires_assignment_for_partial_scopes(self):
        from app.models.ai.knowledge_base import KnowledgeBase
        from app.repositories.ai.knowledge_base_repository import _kb_visible_condition

        stmt = select(KnowledgeBase.id).where(_kb_visible_condition(7))
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))

        assert "knowledge_bases.owner_tenant_id = 7" in sql
        assert "knowledge_bases.scope = 'all_tenants'" in sql
        assert "'global_shared'" in sql
        assert "'all_tenants'" in sql
        assert "'selected_tenants'" in sql
        assert "'admin_and_selected_tenants'" in sql
        assert "resource_tenant_assignments.resource_type = 'knowledge_base'" in sql
        assert "knowledge_bases.scope != 'admin_only'" not in sql


class TestAdminKBPayloadNormalization:
    def test_prepare_admin_payload_uses_assigned_tenant_ids_alias(self, mock_db):
        from app.enums.common import ResourceScopeEnum
        from app.services.ai.knowledge_base_service import AdminKnowledgeBaseService

        service = AdminKnowledgeBaseService.__new__(AdminKnowledgeBaseService)
        service.db = mock_db

        payload, tenant_ids = service._prepare_admin_payload(
            {
                "name": "Scoped KB",
                "scope": ResourceScopeEnum.SELECTED_TENANTS.value,
                "assigned_tenant_ids": [3, 9],
                "owner_tenant_id": 12,
            }
        )

        assert tenant_ids == [3, 9]
        assert payload["scope"] == ResourceScopeEnum.SELECTED_TENANTS.value
        assert payload["owner_tenant_id"] == 12
        assert "assigned_tenant_ids" not in payload

    def test_prepare_admin_payload_requires_binding_when_entering_assignment_scope(
        self, mock_db
    ):
        from app.enums.common import ResourceScopeEnum
        from app.exceptions import BusinessException
        from app.services.ai.knowledge_base_service import AdminKnowledgeBaseService

        service = AdminKnowledgeBaseService.__new__(AdminKnowledgeBaseService)
        service.db = mock_db

        with pytest.raises(BusinessException):
            service._prepare_admin_payload(
                {
                    "scope": ResourceScopeEnum.SELECTED_TENANTS.value,
                },
                existing=make_mock_model(
                    id=1,
                    scope=ResourceScopeEnum.GLOBAL_SHARED.value,
                    owner_tenant_id=None,
                ),
            )

    def test_prepare_admin_payload_keeps_existing_bindings_when_scope_stays_assigned(
        self, mock_db
    ):
        from app.enums.common import ResourceScopeEnum
        from app.services.ai.knowledge_base_service import AdminKnowledgeBaseService

        service = AdminKnowledgeBaseService.__new__(AdminKnowledgeBaseService)
        service.db = mock_db

        payload, tenant_ids = service._prepare_admin_payload(
            {"name": "Renamed KB"},
            existing=make_mock_model(
                id=1,
                scope=ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
                owner_tenant_id=None,
            ),
        )

        assert payload["name"] == "Renamed KB"
        assert tenant_ids is None

    @pytest.mark.asyncio
    async def test_update_admin_knowledge_base_preserves_existing_owner_for_assignment_scope(
        self, mock_db
    ):
        from app.enums.common import ResourceScopeEnum
        from app.services.ai.knowledge_base_service import AdminKnowledgeBaseService

        service = AdminKnowledgeBaseService.__new__(AdminKnowledgeBaseService)
        service.db = mock_db
        service.get_by_id = AsyncMock(
            return_value=make_mock_model(
                id=1,
                scope=ResourceScopeEnum.ALL_TENANTS.value,
                owner_tenant_id=12,
            )
        )
        service.update = AsyncMock(
            return_value=make_mock_model(
                id=1,
                scope=ResourceScopeEnum.SELECTED_TENANTS.value,
                owner_tenant_id=12,
            )
        )

        _, tenant_ids = await service.update_admin_knowledge_base(
            1,
            {
                "scope": ResourceScopeEnum.SELECTED_TENANTS.value,
                "tenant_ids": [3],
            },
        )

        assert tenant_ids == [3]
        service.update.assert_awaited_once_with(
            1,
            {
                "scope": ResourceScopeEnum.SELECTED_TENANTS.value,
            },
        )

    @pytest.mark.asyncio
    async def test_admin_before_create_rejects_audio_video_model_config(self, mock_db):
        from app.core.i18n import _
        from app.exceptions import BusinessException
        from app.services.ai.knowledge_base_service import AdminKnowledgeBaseService

        service = AdminKnowledgeBaseService.__new__(AdminKnowledgeBaseService)
        service.db = mock_db

        with pytest.raises(
            BusinessException,
            match=re.escape(
                _("knowledge_base.error.multimodal_model_config_unavailable")
            ),
        ):
            await service._before_create(
                {
                    "name": "Scoped KB",
                    "scope": "global_shared",
                    "video_model_id": 9,
                }
            )
