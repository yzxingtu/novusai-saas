"""RAG 知识库绑定按企业过滤 / RAG KB binding tenant filter tests."""

from __future__ import annotations

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
