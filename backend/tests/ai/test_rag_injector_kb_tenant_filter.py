"""RAG 知识库绑定按企业过滤 / RAG KB binding tenant filter tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.rag_injector import load_agent_kb_bindings


@pytest.mark.asyncio
async def test_load_agent_kb_bindings_includes_global_and_current_tenant_rows():
    """查询条件应包含 tenant_id IS NULL 或等于当前企业 / SQL scopes platform + tenant overlay."""
    from sqlalchemy.sql.visitors import Visitable

    captured: list[Visitable] = []

    async def capture_execute(stmt, *args, **kwargs):
        captured.append(stmt)
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        return result

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=capture_execute)

    await load_agent_kb_bindings(db, agent_id=42, tenant_id=7)

    assert len(captured) == 1
    compiled = str(captured[0]).lower()
    assert "tenant_id" in compiled
    assert "agent_id" in compiled


@pytest.mark.asyncio
async def test_load_agent_kb_bindings_filters_inaccessible_kbs_for_tenant():
    bindings = [
        SimpleNamespace(knowledge_base_id=101, tenant_id=None, weight=1.0),
        SimpleNamespace(knowledge_base_id=202, tenant_id=7, weight=0.6),
    ]

    result = MagicMock()
    result.scalars.return_value.all.return_value = bindings

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    class DummyRepo:
        def __init__(self, db, tenant_id):
            self.db = db
            self.tenant_id = tenant_id

        async def filter_accessible_ids(self, kb_ids):
            assert kb_ids == [101, 202]
            return {202}

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.services.ai.tenant_platform_kb_suppression_service.load_suppressed_platform_kb_ids",
            AsyncMock(return_value=set()),
        )
        mp.setattr(
            "app.repositories.ai.knowledge_base_repository.KnowledgeBaseRepository",
            DummyRepo,
        )
        kb_ids, kb_weights = await load_agent_kb_bindings(
            db,
            agent_id=42,
            tenant_id=7,
        )

    assert kb_ids == [202]
    assert kb_weights == {202: 0.6}
