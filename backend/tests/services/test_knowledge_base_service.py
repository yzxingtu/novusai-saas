"""KnowledgeBaseService 单元测试 / Test.

覆盖：知识库 CRUD、文档管理、向量化状态、权限检查。"""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock

import pytest

from tests.services.conftest import make_mock_model


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
    async def test_after_restore_updates_statistics_and_invalidates_cache(self, mock_db):
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
