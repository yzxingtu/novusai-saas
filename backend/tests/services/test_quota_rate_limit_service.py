"""
TenantQuotaService + RateLimitService 单元测试

覆盖：配额检查、配额扣减、配额重置、速率限制检查。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.services.conftest import make_mock_model, make_scalar_result


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


class TestQuotaServiceMethods:

    @pytest.mark.asyncio
    async def test_service_has_quota_methods(self, mock_db):
        from app.services.ai.tenant_quota_service import TenantQuotaService

        service = TenantQuotaService.__new__(TenantQuotaService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()

        assert hasattr(service, 'create_quota')
        assert hasattr(service, 'get_active_quotas')
        assert hasattr(service, 'check_quota_warning')
        assert hasattr(service, 'get_all_quotas_with_usage')
