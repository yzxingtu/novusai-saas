"""中文: AI 测试模块分类标记。

EN: AI test module classification marker.

Test type: structural / behavioral
Scope: Existing AI tests in this module; no real-dialogue smoke acceptance is claimed.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai.engine.execution_preflight_support import (
    apply_execution_mode_runtime_flags,
    check_preflight_quota,
    estimate_preflight_tokens,
)
from app.ai.engine.types import ExecutionRequest
from app.ai.types import ChatMessage
from app.enums.agent import AgentExecutionModeEnum


def test_apply_execution_mode_runtime_flags_marks_api_mode_requests() -> None:
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        execution_mode=AgentExecutionModeEnum.API.value,
    )

    apply_execution_mode_runtime_flags(request)

    assert request.skip_quota is True
    assert request.skip_persistence is True
    assert request.skip_logging is True


def test_estimate_preflight_tokens_enforces_minimum_budget() -> None:
    assert estimate_preflight_tokens([]) == 100
    assert estimate_preflight_tokens([ChatMessage(role="user", content="hi")]) >= 100


@pytest.mark.asyncio
async def test_check_preflight_quota_skips_when_request_marks_skip_quota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = ExecutionRequest(
        agent_id=1,
        tenant_id=1,
        user_id=2,
        skip_quota=True,
    )
    check_quota = AsyncMock()
    check_user_quota = AsyncMock()
    check_api_quota = AsyncMock(
        return_value=SimpleNamespace(allowed=True, message=None)
    )

    monkeypatch.setattr(
        "app.ai.engine.execution_preflight_support.AgentQuotaManager.check_quota",
        check_quota,
    )
    monkeypatch.setattr(
        "app.ai.engine.execution_preflight_support.AgentQuotaManager.check_user_quota",
        check_user_quota,
    )
    monkeypatch.setattr(
        "app.services.tenant.quota_service.QuotaService.check_api_quota_for_tenant_id",
        check_api_quota,
    )

    await check_preflight_quota(
        db=object(),
        request=request,
        agent_id=1,
        quota_config=SimpleNamespace(),
        estimated_tokens=123,
    )

    check_quota.assert_not_awaited()
    check_user_quota.assert_not_awaited()
    check_api_quota.assert_not_awaited()
