"""Quota diagnostics service tests / AI 配额诊断服务测试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.common.query import QuerySpec


class TestSummary:
    @pytest.mark.asyncio
    async def test_get_summary_counts_active_warning_and_exceeded_rules(self, mock_db):
        from app.enums.ai import QuotaTypeEnum
        from app.services.ai.quota_diagnostics_service import AIQuotaDiagnosticsService

        service = AIQuotaDiagnosticsService.__new__(AIQuotaDiagnosticsService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.list_all_quota_rules = AsyncMock(
            return_value=[
                SimpleNamespace(
                    tenant_id=1, is_active=True, quota_type=QuotaTypeEnum.HARD.value
                ),
                SimpleNamespace(
                    tenant_id=2, is_active=False, quota_type=QuotaTypeEnum.SOFT.value
                ),
                SimpleNamespace(
                    tenant_id=3, is_active=True, quota_type=QuotaTypeEnum.SOFT.value
                ),
            ]
        )
        service.repo.list_all_rate_limit_rules = AsyncMock(
            return_value=[
                SimpleNamespace(tenant_id=1, is_active=True),
                SimpleNamespace(tenant_id=2, is_active=False),
            ]
        )
        service.repo.get_tenant_name_map = AsyncMock(return_value={1: "Tenant A"})
        service._build_quota_diagnostic = AsyncMock(
            side_effect=[
                SimpleNamespace(is_warning=True, is_exceeded=False),
                SimpleNamespace(is_warning=False, is_exceeded=True),
            ]
        )
        service._build_rate_limit_diagnostic = AsyncMock(
            return_value=SimpleNamespace(is_warning=False, is_exceeded=True)
        )

        summary = await service.get_summary()

        assert summary.total_quota_rules == 3
        assert summary.active_quota_rules == 2
        assert summary.hard_quota_rules == 1
        assert summary.soft_quota_rules == 1
        assert summary.quota_warning_rules == 1
        assert summary.quota_exceeded_rules == 1
        assert summary.total_rate_limit_rules == 2
        assert summary.active_rate_limit_rules == 1
        assert summary.rate_limit_warning_rules == 0
        assert summary.rate_limit_exceeded_rules == 1

    @pytest.mark.asyncio
    async def test_get_summary_returns_zeroed_counts_when_repo_is_empty(self, mock_db):
        from app.services.ai.quota_diagnostics_service import AIQuotaDiagnosticsService

        service = AIQuotaDiagnosticsService.__new__(AIQuotaDiagnosticsService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.list_all_quota_rules = AsyncMock(return_value=[])
        service.repo.list_all_rate_limit_rules = AsyncMock(return_value=[])
        service.repo.get_tenant_name_map = AsyncMock(return_value={})
        service._build_quota_diagnostic = AsyncMock()
        service._build_rate_limit_diagnostic = AsyncMock()

        summary = await service.get_summary()

        assert summary.total_quota_rules == 0
        assert summary.total_rate_limit_rules == 0
        assert summary.quota_warning_rules == 0
        assert summary.rate_limit_exceeded_rules == 0
        service._build_quota_diagnostic.assert_not_called()
        service._build_rate_limit_diagnostic.assert_not_called()


class TestQuotaDiagnosticsList:
    @pytest.mark.asyncio
    async def test_list_quota_diagnostics_returns_paginated_items(self, mock_db):
        from app.services.ai.quota_diagnostics_service import AIQuotaDiagnosticsService

        spec = QuerySpec(page=2, size=2)
        service = AIQuotaDiagnosticsService.__new__(AIQuotaDiagnosticsService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.list_quota_rules = AsyncMock(
            return_value=([SimpleNamespace(id=11)], 3)
        )
        service._build_quota_diagnostic = AsyncMock(
            return_value=SimpleNamespace(id=11, runtime_status="healthy")
        )

        page = await service.list_quota_diagnostics(spec)

        assert page.total == 3
        assert page.page == 2
        assert page.page_size == 2
        assert page.pages == 2
        assert page.items[0].id == 11

    @pytest.mark.asyncio
    async def test_list_quota_diagnostics_returns_empty_page_when_no_items(
        self, mock_db
    ):
        from app.services.ai.quota_diagnostics_service import AIQuotaDiagnosticsService

        spec = QuerySpec()
        service = AIQuotaDiagnosticsService.__new__(AIQuotaDiagnosticsService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.list_quota_rules = AsyncMock(return_value=([], 0))
        service._build_quota_diagnostic = AsyncMock()

        page = await service.list_quota_diagnostics(spec)

        assert page.total == 0
        assert page.items == []
        service._build_quota_diagnostic.assert_not_called()


class TestRateLimitDiagnosticsList:
    @pytest.mark.asyncio
    async def test_list_rate_limit_diagnostics_returns_paginated_items(self, mock_db):
        from app.services.ai.quota_diagnostics_service import AIQuotaDiagnosticsService

        item = SimpleNamespace(id=21, tenant_id=8)
        spec = QuerySpec(page=1, size=5)
        service = AIQuotaDiagnosticsService.__new__(AIQuotaDiagnosticsService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.list_rate_limit_rules = AsyncMock(return_value=([item], 1))
        service.repo.get_tenant_name_map = AsyncMock(return_value={8: "Tenant B"})
        service._build_rate_limit_diagnostic = AsyncMock(
            return_value=SimpleNamespace(id=21, runtime_status="warning")
        )

        page = await service.list_rate_limit_diagnostics(spec)

        assert page.total == 1
        assert page.items[0].id == 21
        service.repo.get_tenant_name_map.assert_awaited_once_with({8})

    @pytest.mark.asyncio
    async def test_list_rate_limit_diagnostics_returns_empty_page_when_no_items(
        self, mock_db
    ):
        from app.services.ai.quota_diagnostics_service import AIQuotaDiagnosticsService

        spec = QuerySpec()
        service = AIQuotaDiagnosticsService.__new__(AIQuotaDiagnosticsService)
        service.db = mock_db
        service.repo = AsyncMock()
        service.repo.list_rate_limit_rules = AsyncMock(return_value=([], 0))
        service.repo.get_tenant_name_map = AsyncMock(return_value={})
        service._build_rate_limit_diagnostic = AsyncMock()

        page = await service.list_rate_limit_diagnostics(spec)

        assert page.total == 0
        assert page.items == []
        service._build_rate_limit_diagnostic.assert_not_called()
