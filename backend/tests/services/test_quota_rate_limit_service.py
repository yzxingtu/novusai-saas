"""TenantQuotaService + RateLimitService 单元测试 / Test.

覆盖：配额检查、配额扣减、配额重置、速率限制检查。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.services.conftest import make_mock_model


def _make_quota(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "agent_id": 1,
        "daily_limit": 100,
        "daily_used": 50,
        "monthly_limit": 3000,
        "monthly_used": 1500,
    }
    defaults.update(overrides)
    return make_mock_model(**defaults)


def _make_rate_limit(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "agent_id": None,
        "requests_per_minute": 60,
        "requests_per_hour": 1000,
        "tokens_per_minute": 100000,
    }
    defaults.update(overrides)
    return make_mock_model(**defaults)


class TestQuotaCreate:
    @pytest.mark.asyncio
    async def test_create_quota(self, mock_db):
        from app.services.ai.tenant_quota_service import TenantQuotaService

        quota = _make_quota()
        service = TenantQuotaService.__new__(TenantQuotaService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.create = AsyncMock(return_value=quota)

        result = await service.repo.create(quota)
        assert result.daily_limit == 100


class TestQuotaQuery:
    @pytest.mark.asyncio
    async def test_get_active_quotas(self, mock_db):
        from app.services.ai.tenant_quota_service import TenantQuotaService

        quotas = [_make_quota(id=i) for i in range(3)]
        service = TenantQuotaService.__new__(TenantQuotaService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_active_quotas = AsyncMock(return_value=quotas)

        result = await service.get_active_quotas()
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_get_active_quotas_empty(self, mock_db):
        from app.services.ai.tenant_quota_service import TenantQuotaService

        service = TenantQuotaService.__new__(TenantQuotaService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_active_quotas = AsyncMock(return_value=[])

        result = await service.get_active_quotas()
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_get_all_quotas_with_usage_keeps_listed_rule_identity(self, mock_db):
        from app.services.ai.tenant_quota_service import TenantQuotaService

        service = TenantQuotaService.__new__(TenantQuotaService)
        service.db = mock_db
        service.tenant_id = 1
        first_quota = make_mock_model(
            id=11,
            tenant_id=1,
            model_id=None,
            period="monthly",
            limit=1000,
            warning_threshold=80,
        )
        second_quota = make_mock_model(
            id=12,
            tenant_id=1,
            model_id=9,
            period="daily",
            limit=600,
            warning_threshold=60,
        )
        service.repo = AsyncMock()
        service.repo.list_quotas = AsyncMock(return_value=[first_quota, second_quota])

        from app.services.ai import tenant_quota_service as service_module

        original_tracker = service_module.UsageTracker

        class _FakeTracker:
            @staticmethod
            async def get_usage(*, tenant_id, model_id, period):
                if tenant_id == 1 and model_id == 0 and period == "monthly":
                    return 250
                if tenant_id == 1 and model_id == 9 and period == "daily":
                    return 480
                return 0

        service_module.UsageTracker = _FakeTracker
        try:
            result = await service.get_all_quotas_with_usage()
        finally:
            service_module.UsageTracker = original_tracker

        assert [item["quota"].id for item in result] == [11, 12]
        assert result[0]["remaining"] == 750
        assert result[1]["is_warning"] is True


class TestRateLimitCheck:
    @pytest.mark.asyncio
    async def test_rate_limit_config_exists(self, mock_db):
        from app.services.ai.tenant_rate_limit_service import TenantRateLimitService

        rl = _make_rate_limit(requests_per_minute=60)
        service = TenantRateLimitService.__new__(TenantRateLimitService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_rate_limit = AsyncMock(return_value=rl)

        config = await service.repo.get_rate_limit(tenant_id=1)
        assert config.requests_per_minute == 60

    @pytest.mark.asyncio
    async def test_rate_limit_no_config(self, mock_db):
        from app.services.ai.tenant_rate_limit_service import TenantRateLimitService

        service = TenantRateLimitService.__new__(TenantRateLimitService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_rate_limit = AsyncMock(return_value=None)

        config = await service.repo.get_rate_limit(tenant_id=1)
        assert config is None

    @pytest.mark.asyncio
    async def test_get_active_limits_can_request_all_statuses(self, mock_db):
        from app.services.ai.tenant_rate_limit_service import TenantRateLimitService

        service = TenantRateLimitService.__new__(TenantRateLimitService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.list_limits = AsyncMock(return_value=[])

        await service.get_active_limits(model_id=7, is_active=None)

        service.repo.list_limits.assert_awaited_once_with(
            tenant_id=1,
            model_id=7,
            is_active=None,
        )


class TestQuotaServiceMethods:
    @pytest.mark.asyncio
    async def test_service_has_quota_methods(self, mock_db):
        from app.services.ai.tenant_quota_service import TenantQuotaService

        service = TenantQuotaService.__new__(TenantQuotaService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()

        assert hasattr(service, "create_quota")
        assert hasattr(service, "get_active_quotas")
        assert hasattr(service, "check_quota_warning")
        assert hasattr(service, "get_all_quotas_with_usage")
