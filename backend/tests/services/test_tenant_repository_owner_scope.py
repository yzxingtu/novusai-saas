"""TenantRepository owner scope compatibility tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.services.conftest import make_scalar_result


class TestOwnerTenantScopeCompatibility:
    @pytest.mark.asyncio
    async def test_count_deleted_uses_owner_tenant_id_for_agent_repository(
        self, mock_db
    ):
        from app.repositories.ai.agent_repository import AgentRepository

        repo = AgentRepository(mock_db, tenant_id=1)
        mock_db.execute.return_value = make_scalar_result(0)

        await repo.count_deleted(delete_level="tenant")

        stmt = mock_db.execute.await_args.args[0]
        stmt_text = str(stmt)
        assert "agents.owner_tenant_id" in stmt_text
        assert "agents.tenant_id" not in stmt_text

    @pytest.mark.asyncio
    async def test_query_deleted_injects_owner_tenant_id_filter_for_agent_repository(
        self, mock_db
    ):
        from app.core.base_repository import BaseRepository
        from app.repositories.ai.agent_repository import AgentRepository
        from app.schemas.common.query import QuerySpec

        repo = AgentRepository(mock_db, tenant_id=1)

        with patch.object(
            BaseRepository,
            "query_deleted",
            new=AsyncMock(return_value=([], 0)),
        ) as mock_query_deleted:
            await repo.query_deleted(
                spec=QuerySpec(),
                delete_level="tenant",
            )

        forced_filters = mock_query_deleted.await_args.kwargs["forced_filters"]
        assert forced_filters[0].field == "owner_tenant_id"
        assert forced_filters[0].value == 1
