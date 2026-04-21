from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.engine.dispatcher import ExecutionDispatcher
from app.ai.engine.types import ExecutionRequest, ExecutionResult
from app.enums.agent import AgentExecutionModeEnum, AgentStatusEnum


@pytest.mark.asyncio
async def test_dispatcher_marks_api_mode_requests_before_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatcher = ExecutionDispatcher(db=MagicMock())
    agent = SimpleNamespace(
        id=7,
        status=AgentStatusEnum.PUBLISHED.value,
        quota_config={},
    )
    request = ExecutionRequest(
        agent_id=7,
        tenant_id=11,
        user_id=13,
        execution_mode=AgentExecutionModeEnum.API.value,
    )

    check_quota = AsyncMock()
    check_user_quota = AsyncMock()
    adjust_usage = AsyncMock()
    record_user_usage = AsyncMock()
    publish_started = AsyncMock()
    publish_completed = AsyncMock()
    hook_registry = SimpleNamespace(trigger=AsyncMock(return_value={}))
    engine = SimpleNamespace(
        execute=AsyncMock(return_value=ExecutionResult(success=True, total_tokens=0))
    )
    captured_requests: list[ExecutionRequest] = []

    async def _fake_build_engine_bootstrap_bundle(**kwargs):
        captured_requests.append(kwargs["request"])
        return SimpleNamespace(
            engine=engine,
            skill_result=None,
            gateway=None,
            sandbox=None,
            is_image_model=False,
        )

    monkeypatch.setattr(
        "app.ai.engine.dispatcher.build_engine_bootstrap_bundle",
        _fake_build_engine_bootstrap_bundle,
    )

    async def _fake_trigger_before_execute_preflight(**kwargs):
        _ = kwargs
        return hook_registry, {}

    monkeypatch.setattr(
        "app.ai.engine.dispatcher.trigger_before_execute_preflight",
        _fake_trigger_before_execute_preflight,
    )
    monkeypatch.setattr(
        "app.ai.engine.dispatcher.AgentQuotaManager.check_quota",
        check_quota,
    )
    monkeypatch.setattr(
        "app.ai.engine.dispatcher.AgentQuotaManager.check_user_quota",
        check_user_quota,
    )
    monkeypatch.setattr(
        "app.ai.engine.dispatcher.AgentQuotaManager.adjust_usage",
        adjust_usage,
    )
    monkeypatch.setattr(
        "app.ai.engine.dispatcher.AgentQuotaManager.record_user_usage",
        record_user_usage,
    )
    monkeypatch.setattr(
        "app.ai.engine.base.BaseEngine._publish_execution_started",
        publish_started,
    )
    monkeypatch.setattr(
        "app.ai.engine.base.BaseEngine._publish_execution_completed",
        publish_completed,
    )
    monkeypatch.setattr(
        "app.ai.agent_quota.AgentConcurrencyLimiter.acquire",
        AsyncMock(return_value="lock-1"),
    )
    monkeypatch.setattr(
        "app.ai.agent_quota.AgentConcurrencyLimiter.release",
        AsyncMock(),
    )

    result = await dispatcher.dispatch(request, pre_loaded_agent=agent)

    assert result.success is True
    assert request.skip_quota is True
    assert request.skip_persistence is True
    assert request.skip_logging is True
    assert captured_requests == [request]
    check_quota.assert_not_awaited()
    check_user_quota.assert_not_awaited()
    adjust_usage.assert_not_awaited()
    record_user_usage.assert_not_awaited()
    publish_started.assert_awaited_once()
    publish_completed.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatcher_rolls_back_preflight_usage_when_engine_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatcher = ExecutionDispatcher(db=MagicMock())
    agent = SimpleNamespace(
        id=9,
        status=AgentStatusEnum.PUBLISHED.value,
        quota_config={},
    )
    request = ExecutionRequest(
        agent_id=9,
        tenant_id=21,
        user_id=34,
        messages=[],
        execution_mode=AgentExecutionModeEnum.CONVERSATION.value,
    )

    engine = SimpleNamespace(execute=AsyncMock(side_effect=RuntimeError("boom")))
    hook_registry = SimpleNamespace(trigger=AsyncMock(return_value={}))
    publish_started = AsyncMock()
    publish_failed = AsyncMock()
    adjust_usage = AsyncMock()
    release_concurrency = AsyncMock()

    async def _fake_build_engine_bootstrap_bundle(**kwargs):
        _ = kwargs
        return SimpleNamespace(
            engine=engine,
            skill_result=None,
            gateway=None,
            sandbox=None,
            is_image_model=False,
        )

    async def _fake_trigger_before_execute_preflight(**kwargs):
        _ = kwargs
        return hook_registry, {}

    monkeypatch.setattr(
        "app.ai.engine.dispatcher.build_engine_bootstrap_bundle",
        _fake_build_engine_bootstrap_bundle,
    )
    monkeypatch.setattr(
        "app.ai.engine.dispatcher.check_preflight_quota",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.ai.engine.dispatcher.trigger_before_execute_preflight",
        _fake_trigger_before_execute_preflight,
    )
    monkeypatch.setattr(
        "app.ai.engine.base.BaseEngine._publish_execution_started",
        publish_started,
    )
    monkeypatch.setattr(
        "app.ai.engine.execution_postflight_support.BaseEngine._publish_execution_failed",
        publish_failed,
    )
    monkeypatch.setattr(
        "app.ai.engine.execution_postflight_support.AgentQuotaManager.adjust_usage",
        adjust_usage,
    )
    monkeypatch.setattr(
        "app.ai.engine.execution_postflight_support.AgentConcurrencyLimiter.release",
        release_concurrency,
    )
    monkeypatch.setattr(
        "app.ai.agent_quota.AgentConcurrencyLimiter.acquire",
        AsyncMock(return_value="lock-9"),
    )

    result = await dispatcher.dispatch(request, pre_loaded_agent=agent)

    assert result.success is False
    publish_started.assert_awaited_once()
    publish_failed.assert_awaited_once()
    adjust_kwargs = adjust_usage.await_args.kwargs
    assert adjust_kwargs["tenant_id"] == 21
    assert adjust_kwargs["agent_id"] == 9
    assert adjust_kwargs["estimated_tokens"] == 100
    assert adjust_kwargs["actual_tokens"] == 0
    release_concurrency.assert_awaited_once_with(
        tenant_id=21,
        agent_id=9,
        lock_token="lock-9",
    )
