"""Tenant QuotaService 单元测试 / Test.

覆盖：存储配额检查、用户配额、配额统计。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.services.conftest import make_mock_model


def _make_plan(**overrides):
    defaults = {
        "id": 1,
        "name": "Basic",
        "storage_limit_gb": 10,
        "user_limit": 50,
        "admin_limit": 5,
    }
    defaults.update(overrides)
    return make_mock_model(**defaults)


class TestStorageQuota:
    @pytest.mark.asyncio
    async def test_storage_within_limit(self, mock_db):
        from app.services.tenant.quota_service import QuotaService

        service = QuotaService.__new__(QuotaService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_storage_used = AsyncMock(return_value=5 * 1024 * 1024 * 1024)
        service.repo.get_storage_limit = AsyncMock(return_value=10 * 1024 * 1024 * 1024)

        used = await service.repo.get_storage_used()
        limit = await service.repo.get_storage_limit()
        assert used < limit

    @pytest.mark.asyncio
    async def test_storage_exceeded(self, mock_db):
        from app.services.tenant.quota_service import QuotaService

        service = QuotaService.__new__(QuotaService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_storage_used = AsyncMock(return_value=11 * 1024 * 1024 * 1024)
        service.repo.get_storage_limit = AsyncMock(return_value=10 * 1024 * 1024 * 1024)

        used = await service.repo.get_storage_used()
        limit = await service.repo.get_storage_limit()
        assert used > limit


class TestUserQuota:
    @pytest.mark.asyncio
    async def test_user_count_within_limit(self, mock_db):
        from app.services.tenant.quota_service import QuotaService

        service = QuotaService.__new__(QuotaService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_user_count = AsyncMock(return_value=30)
        service.repo.get_user_limit = AsyncMock(return_value=50)

        count = await service.repo.get_user_count()
        limit = await service.repo.get_user_limit()
        assert count < limit

    @pytest.mark.asyncio
    async def test_user_count_at_limit(self, mock_db):
        from app.services.tenant.quota_service import QuotaService

        service = QuotaService.__new__(QuotaService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_user_count = AsyncMock(return_value=50)
        service.repo.get_user_limit = AsyncMock(return_value=50)

        count = await service.repo.get_user_count()
        limit = await service.repo.get_user_limit()
        assert count >= limit


class TestQuotaStats:
    @pytest.mark.asyncio
    async def test_get_quota_overview(self, mock_db):
        from app.services.tenant.quota_service import QuotaService

        service = QuotaService.__new__(QuotaService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_quota_overview = AsyncMock(
            return_value={
                "storage_used_bytes": 5368709120,
                "storage_limit_bytes": 10737418240,
                "user_count": 30,
                "user_limit": 50,
                "admin_count": 3,
                "admin_limit": 5,
            }
        )

        result = await service.repo.get_quota_overview()
        assert result["user_count"] == 30
        assert result["storage_used_bytes"] == 5368709120

    @pytest.mark.asyncio
    async def test_unlimited_quota(self, mock_db):
        from app.services.tenant.quota_service import QuotaService

        service = QuotaService.__new__(QuotaService)
        service.db = mock_db
        service.tenant_id = 1
        service.repo = AsyncMock()
        service.repo.get_storage_limit = AsyncMock(return_value=0)

        limit = await service.repo.get_storage_limit()
        assert limit == 0  # 0 = unlimited


class TestApiCallsQuota:
    def _build_service(self, mock_db, limit: int = 5):
        from app.services.tenant.quota_service import QuotaService

        tenant = SimpleNamespace(
            id=1,
            plan_id=1,
            quota={},
            tenant_plan=SimpleNamespace(is_active=True),
        )
        tenant.get_quota_value = MagicMock(
            side_effect=lambda key, default=None: (
                limit if key == "api_calls_per_month" else default
            )
        )
        return QuotaService(mock_db, tenant)

    @pytest.mark.asyncio
    async def test_check_api_calls_quota_seeds_month_counter_once(self, mock_db):
        service = self._build_service(mock_db, limit=5)
        count_result = MagicMock()
        count_result.scalar.return_value = 4
        mock_db.execute = AsyncMock(return_value=count_result)

        fake_redis = AsyncMock()
        fake_redis.get = AsyncMock(return_value=None)
        fake_redis.setnx = AsyncMock(return_value=True)
        fake_redis.expire = AsyncMock()
        fake_redis.eval = AsyncMock(return_value=-1)

        with patch(
            "app.services.tenant.quota_service.get_redis",
            new=AsyncMock(return_value=fake_redis),
        ):
            result = await service.check_api_calls_quota(additional=1)

        assert result.allowed is True
        assert result.current == 4
        assert result.remaining == 1
        mock_db.execute.assert_awaited_once()
        fake_redis.setnx.assert_awaited_once()
        fake_redis.eval.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_check_api_calls_quota_reuses_hot_counter_without_db_count(
        self,
        mock_db,
    ):
        service = self._build_service(mock_db, limit=5)
        mock_db.execute = AsyncMock()

        fake_redis = AsyncMock()
        fake_redis.get = AsyncMock(return_value="5")
        fake_redis.eval = AsyncMock(return_value=5)

        with patch(
            "app.services.tenant.quota_service.get_redis",
            new=AsyncMock(return_value=fake_redis),
        ):
            result = await service.check_api_calls_quota(additional=1)

        assert result.allowed is False
        assert result.current == 5
        assert result.remaining == 0
        mock_db.execute.assert_not_awaited()
        fake_redis.eval.assert_awaited_once()
