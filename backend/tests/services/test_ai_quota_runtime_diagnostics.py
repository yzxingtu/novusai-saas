"""AI quota runtime diagnostics tests / AI 配额运行时诊断测试。"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from tests.services.conftest import make_mock_model


@pytest.mark.asyncio
async def test_quota_manager_uses_model_specific_and_global_buckets(mock_db):
    from app.ai.quota_manager import QuotaManager

    manager = QuotaManager(mock_db)
    request_date = date(2026, 3, 23)
    model_specific = SimpleNamespace(
        id=11,
        model_id=5,
        period="daily",
        quota_type="hard",
        limit=1000,
        is_active=True,
    )
    global_rule = SimpleNamespace(
        id=12,
        model_id=None,
        period="monthly",
        quota_type="soft",
        limit=2000,
        is_active=True,
    )

    with (
        patch.object(
            manager,
            "_get_effective_quotas",
            new=AsyncMock(return_value=[model_specific, global_rule]),
        ),
        patch(
            "app.ai.quota_manager.UsageTracker.check_and_record_usage",
            new=AsyncMock(return_value=-1),
        ) as check_usage,
        patch(
            "app.ai.quota_manager.UsageTracker.get_usage",
            new=AsyncMock(return_value=1950),
        ) as get_usage,
        patch.object(
            manager,
            "_notify_soft_quota_exceeded",
            new=AsyncMock(),
        ) as notify_soft,
    ):
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
        period="daily",
        stat_date=request_date,
    )
    get_usage.assert_awaited_once_with(
        tenant_id=9,
        model_id=0,
        period="monthly",
        stat_date=request_date,
    )
    notify_soft.assert_awaited_once()
    assert [item.tracking_model_id for item in result.items] == [5, 0]
    assert [item.period for item in result.items] == ["daily", "monthly"]


@pytest.mark.asyncio
async def test_quota_manager_finalize_usage_updates_hard_and_soft_periods(mock_db):
    from app.ai.quota_manager import QuotaManager
    from app.ai.quota_models import QuotaCheckResult, QuotaMeteringItem

    manager = QuotaManager(mock_db)
    quota_result = QuotaCheckResult(
        items=(
            QuotaMeteringItem(
                quota_id=1,
                period="daily",
                quota_type="hard",
                tracking_model_id=7,
            ),
            QuotaMeteringItem(
                quota_id=2,
                period="monthly",
                quota_type="soft",
                tracking_model_id=0,
            ),
        )
    )

    with (
        patch(
            "app.ai.quota_manager.UsageTracker.adjust_usage_for_period",
            new=AsyncMock(),
        ) as adjust_period,
        patch(
            "app.ai.quota_manager.UsageTracker.record_usage_for_period",
            new=AsyncMock(),
        ) as record_period,
    ):
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
        period="daily",
        stat_date=date(2026, 3, 23),
    )
    record_period.assert_awaited_once_with(
        tenant_id=3,
        model_id=0,
        tokens=120,
        period="monthly",
        stat_date=date(2026, 3, 23),
    )


@pytest.mark.asyncio
async def test_quota_manager_rolls_back_previous_hard_precharge_on_later_failure(
    mock_db,
):
    from app.ai.quota_exceptions import QuotaExceeded
    from app.ai.quota_manager import QuotaManager

    manager = QuotaManager(mock_db)
    daily_rule = SimpleNamespace(
        id=101,
        model_id=9,
        period="daily",
        quota_type="hard",
        limit=500,
        is_active=True,
    )
    monthly_rule = SimpleNamespace(
        id=102,
        model_id=None,
        period="monthly",
        quota_type="hard",
        limit=1000,
        is_active=True,
    )

    with (
        patch.object(
            manager,
            "_get_effective_quotas",
            new=AsyncMock(return_value=[daily_rule, monthly_rule]),
        ),
        patch(
            "app.ai.quota_manager.UsageTracker.check_and_record_usage",
            new=AsyncMock(side_effect=[-1, 900]),
        ),
        patch(
            "app.ai.quota_manager.UsageTracker.adjust_usage_for_period",
            new=AsyncMock(),
        ) as rollback_usage,
        pytest.raises(QuotaExceeded),
    ):
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
        period="daily",
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
        "app.services.ai.tenant_rate_limit_service.AIModelRepository.get_by_id",
        new=AsyncMock(return_value=model),
    ):
        result = await service.get_effective_rate_limits(8)

    assert result["rpm_limit"] == 60
    assert result["tpm_limit"] == 3200
    assert result["rpm_source"] == "model"
    assert result["tpm_source"] == "tenant"
    assert result["source"] == "tenant"


@pytest.mark.asyncio
async def test_usage_tracker_adjust_usage_for_period_preserves_or_reseeds_ttl() -> None:
    from app.ai.quota_usage_tracker import UsageTracker

    fake_redis = AsyncMock()

    with patch(
        "app.ai.quota_usage_tracker.get_redis",
        new=AsyncMock(return_value=fake_redis),
    ):
        await UsageTracker.adjust_usage_for_period(
            tenant_id=3,
            model_id=9,
            estimated_tokens=120,
            actual_tokens=80,
            period="daily",
            stat_date=date(2026, 3, 23),
        )

    fake_redis.eval.assert_awaited_once_with(
        UsageTracker._USAGE_ADJUST_LUA,
        1,
        "ai:usage:daily:3:9:2026-03-23",
        "-40",
        str(86400 * 2),
    )


@pytest.mark.asyncio
async def test_usage_recorder_rolls_back_rate_limit_precharge_when_quota_fails(
    mock_db,
):
    from app.ai.quota_exceptions import QuotaExceeded
    from app.ai.usage_recorder_core import UsageRecorder

    recorder = UsageRecorder(mock_db)
    recorder.quota_manager.check_quota = AsyncMock(
        side_effect=QuotaExceeded("quota blocked")
    )
    reservation = SimpleNamespace(rpm_key="rpm", rpm_member="member", tpm_key="tpm")
    ai_model = make_mock_model(id=6, rpm_limit=60, tpm_limit=6000)

    with (
        patch(
            "app.ai.usage_recorder_core.RateLimiter.check_and_record",
            new=AsyncMock(return_value=reservation),
        ) as check_and_record,
        patch(
            "app.ai.usage_recorder_core.RateLimiter.rollback_precharge",
            new=AsyncMock(),
        ) as rollback,
        pytest.raises(QuotaExceeded),
    ):
        await recorder.check_rate_and_quota(
            tenant_id=0,
            model_id=6,
            ai_model=ai_model,
            estimated_tokens=300,
        )

    check_and_record.assert_awaited_once()
    rollback.assert_awaited_once_with(
        reservation=reservation,
        estimated_tokens=300,
    )


@pytest.mark.asyncio
async def test_usage_recorder_adjusts_tpm_when_estimate_is_zero(mock_db):
    from app.ai.quota_models import QuotaCheckResult
    from app.ai.usage_recorder_context import UsageMeteringContext
    from app.ai.usage_recorder_core import UsageRecorder

    recorder = UsageRecorder(mock_db)
    recorder.quota_manager.adjust_usage = AsyncMock()

    with patch(
        "app.ai.usage_recorder_core.RateLimiter.adjust_tpm_after_response",
        new=AsyncMock(),
    ) as adjust_tpm:
        await recorder.record_usage_and_adjust(
            tenant_id=5,
            model_id=12,
            request_type="chat",
            input_tokens=0,
            output_tokens=42,
            total_tokens=42,
            cost=0.0,
            estimated_input=0,
            latency_ms=10,
            metering_context=UsageMeteringContext(
                request_minute_key=123,
                request_stat_date=date(2026, 3, 23),
                quota_check=QuotaCheckResult(),
            ),
        )

    adjust_tpm.assert_awaited_once_with(
        tenant_id=5,
        model_id=12,
        estimated_tokens=0,
        actual_tokens=42,
        request_minute_key=123,
    )


@pytest.mark.asyncio
async def test_agent_quota_adjust_usage_reseeds_ttl_for_daily_and_monthly_keys() -> (
    None
):
    from app.ai.agent_quota_config import AgentQuotaConfig
    from app.ai.agent_quota_manager import AgentQuotaManager

    fake_redis = AsyncMock()
    fake_redis.eval = AsyncMock(return_value=10)

    with patch(
        "app.ai.agent_quota_manager.get_redis",
        new=AsyncMock(return_value=fake_redis),
    ):
        await AgentQuotaManager.adjust_usage(
            tenant_id=6,
            agent_id=18,
            estimated_tokens=120,
            actual_tokens=80,
            config=AgentQuotaConfig(daily_token_limit=1000, monthly_token_limit=3000),
        )

    assert fake_redis.eval.await_count == 2
    first_call = fake_redis.eval.await_args_list[0].args
    second_call = fake_redis.eval.await_args_list[1].args
    assert first_call[0] == AgentQuotaManager._ADJUST_LUA
    assert first_call[2].startswith("ai:agent_quota:daily:6:18:")
    assert first_call[4] == str(86400 * 2)
    assert second_call[0] == AgentQuotaManager._ADJUST_LUA
    assert second_call[2].startswith("ai:agent_quota:monthly:6:18:")
    assert second_call[4] == str(86400 * 35)
