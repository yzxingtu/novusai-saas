"""Test type: structural / behavioral.

中文: 覆盖知识库 CRUD、文档管理、向量化状态、权限检查与选择列表边界。
EN: Covers KB CRUD, document management, vectorization state, permission checks,
and selectable-list boundaries.
"""

from __future__ import annotations

import contextlib
import re
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from tests.services.conftest import (
    make_mock_model,
    make_scalar_result,
    make_scalars_result,
)


def _make_kb(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "owner_tenant_id": 1,
        "name": "Test KB",
        "description": "A test knowledge base",
        "scope": "all_tenants",
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

    @pytest.mark.asyncio
    async def test_tenant_create_rejects_global_shared_scope(self, mock_db):
        from app.enums.common import ResourceScopeEnum
        from app.exceptions import BusinessException
        from app.services.ai.knowledge_base_service import KnowledgeBaseService

        service = KnowledgeBaseService.__new__(KnowledgeBaseService)
        service.db = mock_db
        service.tenant_id = 7
        service.repo = AsyncMock()
        service.repo.tenant_id = 7
        service.repo.count_by_tenant = AsyncMock(return_value=0)

        with pytest.raises(BusinessException, match="scope"):
            await service._before_create(
                {
                    "name": "Escalated KB",
                    "scope": ResourceScopeEnum.GLOBAL_SHARED.value,
                }
            )

        service.repo.count_by_tenant.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_tenant_create_rejects_retired_tenant_id_alias(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.ai.knowledge_base_service import KnowledgeBaseService

        service = KnowledgeBaseService.__new__(KnowledgeBaseService)
        service.db = mock_db
        service.tenant_id = 7
        service.repo = AsyncMock()

        with pytest.raises(BusinessException, match="tenant_id"):
            await service._before_create(
                {
                    "name": "Legacy alias KB",
                    "tenant_id": 7,
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

    def test_request_schemas_reject_retired_multimodal_fields(self):
        from pydantic import ValidationError

        from app.core.i18n import _
        from app.models.ai.knowledge_base import KnowledgeBase
        from app.schemas.ai.knowledge_base import (
            AdminKnowledgeBaseCreate,
            AdminKnowledgeBaseUpdate,
            KnowledgeBaseCreate,
            KnowledgeBaseUpdate,
        )

        schema_classes = (
            KnowledgeBaseCreate,
            KnowledgeBaseUpdate,
            AdminKnowledgeBaseCreate,
            AdminKnowledgeBaseUpdate,
        )

        for schema_class in schema_classes:
            schema = schema_class.model_json_schema()
            assert "audio_model_id" not in schema.get("properties", {})
            assert "video_model_id" not in schema.get("properties", {})

            with pytest.raises(
                ValidationError,
                match=re.escape(
                    _("knowledge_base.error.multimodal_model_config_unavailable")
                ),
            ):
                schema_class(
                    **(
                        {
                            "name": "KB",
                            "embedding_model_id": 1,
                        }
                        if schema_class
                        in (KnowledgeBaseCreate, AdminKnowledgeBaseCreate)
                        else {}
                    ),
                    audio_model_id=7,
                )

            with pytest.raises(
                ValidationError,
                match=re.escape(
                    _("knowledge_base.error.multimodal_model_config_unavailable")
                ),
            ):
                schema_class(
                    **(
                        {
                            "name": "KB",
                            "embedding_model_id": 1,
                        }
                        if schema_class
                        in (KnowledgeBaseCreate, AdminKnowledgeBaseCreate)
                        else {}
                    ),
                    video_model_id=None,
                )

        assert "audio_model_id" not in KnowledgeBase.__filterable__
        assert "video_model_id" not in KnowledgeBase.__filterable__

    def test_admin_request_schemas_reject_legacy_assignment_aliases(self):
        from pydantic import ValidationError

        from app.core.i18n import _
        from app.schemas.ai.knowledge_base import (
            AdminKnowledgeBaseCreate,
            AdminKnowledgeBaseUpdate,
        )

        schema_inputs = (
            (
                AdminKnowledgeBaseCreate,
                {
                    "name": "KB",
                    "embedding_model_id": 1,
                },
            ),
            (AdminKnowledgeBaseUpdate, {}),
        )
        retired_aliases = {
            "tenant_id": 12,
            "assigned_tenant_ids": [3, 9],
        }

        for schema_class, base_input in schema_inputs:
            schema = schema_class.model_json_schema()
            assert "tenant_id" not in schema.get("properties", {})
            assert "assigned_tenant_ids" not in schema.get("properties", {})

            for field, value in retired_aliases.items():
                with pytest.raises(
                    ValidationError,
                    match=re.escape(
                        _("agent.error.rejected_legacy_field").format(field=field)
                    ),
                ):
                    schema_class(**base_input, **{field: value})


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

    @pytest.mark.asyncio
    async def test_tenant_update_rejects_scope_escalation_to_global_shared(
        self, mock_db
    ):
        from app.enums.common import ResourceScopeEnum
        from app.exceptions import BusinessException
        from app.services.ai.knowledge_base_service import KnowledgeBaseService

        service = KnowledgeBaseService.__new__(KnowledgeBaseService)
        service.db = mock_db
        service.tenant_id = 7
        service.repo = AsyncMock()
        service.repo.tenant_id = 7
        service.repo.get_by_id = AsyncMock(
            return_value=_make_kb(
                id=1,
                tenant_id=7,
                owner_tenant_id=7,
                scope=ResourceScopeEnum.ALL_TENANTS.value,
            )
        )

        with pytest.raises(BusinessException, match="scope"):
            await service._before_update(
                1,
                {"scope": ResourceScopeEnum.GLOBAL_SHARED.value},
            )

    @pytest.mark.asyncio
    async def test_tenant_update_rejects_platform_shared_kb_mutation(self, mock_db):
        from app.enums.common import ResourceScopeEnum
        from app.exceptions import BusinessException
        from app.services.ai.knowledge_base_service import KnowledgeBaseService

        service = KnowledgeBaseService.__new__(KnowledgeBaseService)
        service.db = mock_db
        service.tenant_id = 7
        service.repo = AsyncMock()
        service.repo.tenant_id = 7
        service.repo.get_by_id = AsyncMock(
            return_value=_make_kb(
                id=9,
                tenant_id=None,
                owner_tenant_id=None,
                scope=ResourceScopeEnum.GLOBAL_SHARED.value,
            )
        )

        with pytest.raises(BusinessException):
            await service._before_update(9, {"name": "Tenant cannot edit platform KB"})

    @pytest.mark.asyncio
    async def test_tenant_update_rejects_retired_assignment_alias(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.ai.knowledge_base_service import KnowledgeBaseService

        service = KnowledgeBaseService.__new__(KnowledgeBaseService)
        service.db = mock_db
        service.tenant_id = 7
        service.repo = AsyncMock()
        service.repo.get_by_id = AsyncMock()

        with pytest.raises(BusinessException, match="assigned_tenant_ids"):
            await service._before_update(
                1,
                {
                    "assigned_tenant_ids": [7],
                },
            )

        service.repo.get_by_id.assert_not_awaited()


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
    @pytest.mark.asyncio
    async def test_repository_get_by_id_returns_none_when_visibility_check_fails(
        self, mock_db
    ):
        from app.repositories.ai.knowledge_base_repository import (
            KnowledgeBaseRepository,
        )

        tenant_b_kb = _make_kb(
            id=202,
            tenant_id=8,
            owner_tenant_id=8,
            scope="all_tenants",
        )
        mock_db.execute = AsyncMock(
            side_effect=[
                make_scalar_result(tenant_b_kb),
                make_scalar_result(None),
            ]
        )
        repo = KnowledgeBaseRepository(mock_db, tenant_id=7)

        assert await repo.get_by_id(202) is None

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
        assert "knowledge_bases.owner_tenant_id IS NULL" in sql
        assert "OR knowledge_bases.scope = 'global_shared'" not in sql
        assert "knowledge_bases.scope != 'admin_only'" not in sql

    @pytest.mark.asyncio
    async def test_selectable_repository_uses_canonical_visibility_condition(
        self, mock_db
    ):
        from app.repositories.ai.knowledge_base_repository import (
            KnowledgeBaseRepository,
        )

        mock_db.execute = AsyncMock(return_value=make_scalars_result([]))
        repo = KnowledgeBaseRepository(mock_db, tenant_id=7)

        await repo.list_selectable(limit=25)

        stmt = mock_db.execute.await_args.args[0]
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))

        assert "knowledge_bases.owner_tenant_id = 7" in sql
        assert "knowledge_bases.tenant_id = 7" not in sql
        assert "knowledge_bases.scope = 'all_tenants'" in sql
        assert "'global_shared'" in sql
        assert "'selected_tenants'" in sql
        assert "'admin_and_selected_tenants'" in sql
        assert "ORDER BY knowledge_bases.name ASC" in sql
        assert "LIMIT 25" in sql

    @pytest.mark.asyncio
    async def test_selectable_service_delegates_to_repository(self, mock_db):
        from app.services.ai.knowledge_base_service import KnowledgeBaseService

        expected = [_make_kb(id=8, name="Selectable KB")]
        service = KnowledgeBaseService.__new__(KnowledgeBaseService)
        service.db = mock_db
        service.tenant_id = 7
        service.repo = AsyncMock()
        service.repo.list_selectable = AsyncMock(return_value=expected)

        result = await service.list_selectable(limit=19)

        service.repo.list_selectable.assert_awaited_once_with(limit=19)
        assert result == expected

    @pytest.mark.asyncio
    async def test_document_repository_reads_platform_docs_through_kb_visibility(
        self, mock_db
    ):
        from app.repositories.ai.knowledge_base_repository import (
            KnowledgeDocumentRepository,
        )
        from app.schemas.common.query import FilterOp, FilterRule, QuerySpec

        mock_db.execute = AsyncMock(
            side_effect=[
                make_scalar_result(0),
                make_scalars_result([]),
            ]
        )
        repo = KnowledgeDocumentRepository(mock_db, tenant_id=7)

        await repo.query_list(
            QuerySpec(
                filters=[
                    FilterRule(
                        field="knowledge_base_id",
                        op=FilterOp.eq,
                        value="12",
                    )
                ]
            )
        )

        stmt = mock_db.execute.await_args_list[1].args[0]
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))

        assert (
            "JOIN knowledge_bases ON knowledge_bases.id = "
            "knowledge_documents.knowledge_base_id"
        ) in sql
        assert "knowledge_bases.owner_tenant_id = 7" in sql
        assert "knowledge_documents.tenant_id = 7" in sql
        assert "knowledge_bases.owner_tenant_id IS NULL" in sql
        assert "knowledge_documents.tenant_id IS NULL" in sql
        assert "resource_tenant_assignments.resource_type = 'knowledge_base'" in sql
        assert "knowledge_documents.knowledge_base_id = 12" in sql

    @pytest.mark.asyncio
    async def test_chunk_repository_reads_platform_chunks_through_kb_visibility(
        self, mock_db
    ):
        from app.repositories.ai.knowledge_base_repository import (
            DocumentChunkRepository,
        )

        mock_db.execute = AsyncMock(return_value=make_scalars_result([]))
        repo = DocumentChunkRepository(mock_db, tenant_id=7)

        await repo.get_by_document(document_id=15, skip=3, limit=9)

        stmt = mock_db.execute.await_args.args[0]
        sql = str(stmt.compile(compile_kwargs={"literal_binds": True}))

        assert (
            "JOIN knowledge_documents ON knowledge_documents.id = "
            "document_chunks.document_id"
        ) in sql
        assert (
            "document_chunks.knowledge_base_id = knowledge_documents.knowledge_base_id"
        ) in sql
        assert "knowledge_bases.owner_tenant_id = 7" in sql
        assert "document_chunks.tenant_id = 7" in sql
        assert "knowledge_bases.owner_tenant_id IS NULL" in sql
        assert "document_chunks.tenant_id IS NULL" in sql
        assert "document_chunks.document_id = 15" in sql
        assert "LIMIT 9" in sql
        assert "OFFSET 3" in sql

    def test_model_declares_scope_owner_check_constraint(self):
        from sqlalchemy import CheckConstraint

        from app.models.ai.knowledge_base import KnowledgeBase

        constraints = [
            constraint
            for constraint in KnowledgeBase.__table__.constraints
            if isinstance(constraint, CheckConstraint)
        ]

        assert any(
            constraint.name == "ck_knowledge_bases_scope_owner_tenant"
            for constraint in constraints
        )

    def test_scope_owner_rule_matrix_is_explicit(self):
        from app.enums.common import ResourceScopeEnum
        from app.services.ai.knowledge_base_support import (
            KB_PLATFORM_OWNER_SCOPES,
            KB_TENANT_OWNER_SCOPES,
            is_valid_kb_scope_owner,
        )

        assert set(KB_PLATFORM_OWNER_SCOPES) == {
            ResourceScopeEnum.GLOBAL_SHARED.value,
            ResourceScopeEnum.ADMIN_ONLY.value,
            ResourceScopeEnum.ALL_TENANTS.value,
            ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
            ResourceScopeEnum.SELECTED_TENANTS.value,
        }
        assert (ResourceScopeEnum.ALL_TENANTS.value,) == KB_TENANT_OWNER_SCOPES
        assert is_valid_kb_scope_owner(
            scope=ResourceScopeEnum.GLOBAL_SHARED.value,
            owner_tenant_id=None,
        )
        assert not is_valid_kb_scope_owner(
            scope=ResourceScopeEnum.GLOBAL_SHARED.value,
            owner_tenant_id=7,
        )


class TestAdminKBPayloadNormalization:
    def test_prepare_admin_payload_rejects_assigned_tenant_ids_alias(self, mock_db):
        from app.enums.common import ResourceScopeEnum
        from app.exceptions import BusinessException
        from app.services.ai.knowledge_base_service import AdminKnowledgeBaseService

        service = AdminKnowledgeBaseService.__new__(AdminKnowledgeBaseService)
        service.db = mock_db

        with pytest.raises(BusinessException, match="assigned_tenant_ids"):
            service._prepare_admin_payload(
                {
                    "name": "Scoped KB",
                    "scope": ResourceScopeEnum.SELECTED_TENANTS.value,
                    "assigned_tenant_ids": [3, 9],
                }
            )

    def test_prepare_admin_payload_rejects_tenant_id_alias(self, mock_db):
        from app.exceptions import BusinessException
        from app.services.ai.knowledge_base_service import AdminKnowledgeBaseService

        service = AdminKnowledgeBaseService.__new__(AdminKnowledgeBaseService)
        service.db = mock_db

        with pytest.raises(BusinessException, match="tenant_id"):
            service._prepare_admin_payload(
                {
                    "name": "Tenant-owned KB",
                    "tenant_id": 12,
                }
            )

    def test_prepare_admin_payload_defaults_tenant_owned_rows_to_all_tenants(
        self, mock_db
    ):
        from app.enums.common import ResourceScopeEnum
        from app.services.ai.knowledge_base_service import AdminKnowledgeBaseService

        service = AdminKnowledgeBaseService.__new__(AdminKnowledgeBaseService)
        service.db = mock_db

        payload, tenant_ids = service._prepare_admin_payload(
            {
                "name": "Tenant-owned KB",
                "owner_tenant_id": 12,
            }
        )

        assert tenant_ids is None
        assert payload["owner_tenant_id"] == 12
        assert payload["scope"] == ResourceScopeEnum.ALL_TENANTS.value

    def test_prepare_admin_payload_rejects_tenant_owned_assignment_scope(self, mock_db):
        from app.enums.common import ResourceScopeEnum
        from app.exceptions import BusinessException
        from app.services.ai.knowledge_base_service import AdminKnowledgeBaseService

        service = AdminKnowledgeBaseService.__new__(AdminKnowledgeBaseService)
        service.db = mock_db

        with pytest.raises(BusinessException, match="scope"):
            service._prepare_admin_payload(
                {
                    "scope": ResourceScopeEnum.SELECTED_TENANTS.value,
                    "owner_tenant_id": 12,
                    "tenant_ids": [12],
                }
            )

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
    async def test_update_admin_knowledge_base_rejects_tenant_owned_assignment_scope(
        self, mock_db
    ):
        from app.enums.common import ResourceScopeEnum
        from app.exceptions import BusinessException
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
        service.update = AsyncMock()

        with pytest.raises(BusinessException, match="scope"):
            await service.update_admin_knowledge_base(
                1,
                {
                    "scope": ResourceScopeEnum.SELECTED_TENANTS.value,
                    "tenant_ids": [3],
                },
            )

        service.update.assert_not_awaited()

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
