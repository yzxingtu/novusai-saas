"""AI quota runtime diagnostics tests / AI 配额运行时诊断测试。"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from tests.services.conftest import make_mock_model


@pytest.mark.asyncio
async def test_quota_manager_uses_model_specific_and_global_buckets(mock_db):
    from app.ai.quota import QuotaManager

    manager = QuotaManager(mock_db)
    request_date = date(2026, 3, 23)
    model_specific = SimpleNamespace(
        id=11,
        model_id=5,
        period='daily',
        quota_type='hard',
        limit=1000,
        is_active=True,
    )
    global_rule = SimpleNamespace(
        id=12,
        model_id=None,
        period='monthly',
        quota_type='soft',
        limit=2000,
        is_active=True,
    )

    with patch.object(
        manager,
        '_get_effective_quotas',
        new=AsyncMock(return_value=[model_specific, global_rule]),
    ), patch(
        'app.ai.quota.UsageTracker.check_and_record_usage',
        new=AsyncMock(return_value=-1),
    ) as check_usage, patch(
        'app.ai.quota.UsageTracker.get_usage',
        new=AsyncMock(return_value=1950),
    ) as get_usage, patch.object(
        manager,
        '_notify_soft_quota_exceeded',
        new=AsyncMock(),
    ) as notify_soft:
        result = await manager.check_quota(
            tenant_id=9,
            model_id=5,
            estimated_tokens=100,
            request_stat_date=request_date,
        )

    check_usage.assert_awaited_once_with(
        tenant_id=9,
        model_id=5,
        estimated_tokens=100,
        limit=1000,
        period='daily',
        stat_date=request_date,
    )
    get_usage.assert_awaited_once_with(
        tenant_id=9,
        model_id=0,
        period='monthly',
        stat_date=request_date,
    )
    notify_soft.assert_awaited_once()
    assert [item.tracking_model_id for item in result.items] == [5, 0]
    assert [item.period for item in result.items] == ['daily', 'monthly']


@pytest.mark.asyncio
async def test_quota_manager_finalize_usage_updates_hard_and_soft_periods(mock_db):
    from app.ai.quota import QuotaCheckResult, QuotaManager, QuotaMeteringItem

    manager = QuotaManager(mock_db)
    quota_result = QuotaCheckResult(
        items=(
            QuotaMeteringItem(
                quota_id=1,
                period='daily',
                quota_type='hard',
                tracking_model_id=7,
            ),
            QuotaMeteringItem(
                quota_id=2,
                period='monthly',
                quota_type='soft',
                tracking_model_id=0,
            ),
        )
    )

    with patch(
        'app.ai.quota.UsageTracker.adjust_usage_for_period',
        new=AsyncMock(),
    ) as adjust_period, patch(
        'app.ai.quota.UsageTracker.record_usage_for_period',
        new=AsyncMock(),
    ) as record_period:
        await manager.adjust_usage(
            tenant_id=3,
            model_id=7,
            estimated_tokens=80,
            actual_tokens=120,
            quota_result=quota_result,
            stat_date=date(2026, 3, 23),
        )

    adjust_period.assert_awaited_once_with(
        tenant_id=3,
        model_id=7,
        estimated_tokens=80,
        actual_tokens=120,
        period='daily',
        stat_date=date(2026, 3, 23),
    )
    record_period.assert_awaited_once_with(
        tenant_id=3,
        model_id=0,
        tokens=120,
        period='monthly',
        stat_date=date(2026, 3, 23),
    )


@pytest.mark.asyncio
async def test_quota_manager_rolls_back_previous_hard_precharge_on_later_failure(mock_db):
    from app.ai.quota import QuotaExceeded, QuotaManager

    manager = QuotaManager(mock_db)
    daily_rule = SimpleNamespace(
        id=101,
        model_id=9,
        period='daily',
        quota_type='hard',
        limit=500,
        is_active=True,
    )
    monthly_rule = SimpleNamespace(
        id=102,
        model_id=None,
        period='monthly',
        quota_type='hard',
        limit=1000,
        is_active=True,
    )

    with patch.object(
        manager,
        '_get_effective_quotas',
        new=AsyncMock(return_value=[daily_rule, monthly_rule]),
    ), patch(
        'app.ai.quota.UsageTracker.check_and_record_usage',
        new=AsyncMock(side_effect=[-1, 900]),
    ), patch(
        'app.ai.quota.UsageTracker.adjust_usage_for_period',
        new=AsyncMock(),
    ) as rollback_usage:
        with pytest.raises(QuotaExceeded):
            await manager.check_quota(
                tenant_id=4,
                model_id=9,
                estimated_tokens=120,
                request_stat_date=date(2026, 3, 23),
            )

    rollback_usage.assert_awaited_once_with(
        tenant_id=4,
        model_id=9,
        estimated_tokens=120,
        actual_tokens=0,
        period='daily',
        stat_date=date(2026, 3, 23),
    )


@pytest.mark.asyncio
async def test_rate_limit_service_merges_blank_fields_with_model_defaults(mock_db):
    from app.services.ai.tenant_rate_limit_service import TenantRateLimitService

    service = TenantRateLimitService.__new__(TenantRateLimitService)
    service.db = mock_db
    service.tenant_id = 5
    service.repo = AsyncMock()
    service.repo.get_latest_active_limit = AsyncMock(
        return_value=make_mock_model(
            id=21,
            tenant_id=5,
            model_id=8,
            is_active=True,
            rpm_limit=None,
            tpm_limit=3200,
        )
    )

    model = make_mock_model(id=8, rpm_limit=60, tpm_limit=9000)

    with patch(
        'app.services.ai.tenant_rate_limit_service.AIModelRepository.get_by_id',
        new=AsyncMock(return_value=model),
    ):
        result = await service.get_effective_rate_limits(8)

    assert result['rpm_limit'] == 60
    assert result['tpm_limit'] == 3200
    assert result['rpm_source'] == 'model'
    assert result['tpm_source'] == 'tenant'
    assert result['source'] == 'tenant'
