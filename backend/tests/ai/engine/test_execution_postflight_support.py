"""中文: AI 测试模块分类标记。

EN: AI test module classification marker.

Test type: structural / behavioral
Scope: Existing AI tests in this module; no real-dialogue smoke acceptance is claimed.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.ai.engine.execution_postflight_support import (
    ExecutionPostflightDependencies,
    apply_execution_result_postflight,
    publish_failed_execution_postflight,
    release_execution_postflight_lock,
    rollback_execution_postflight_usage,
)
from app.ai.engine.types import ExecutionRequest, ExecutionResult


def _build_dependencies() -> ExecutionPostflightDependencies:
    return ExecutionPostflightDependencies(
        adjust_usage=AsyncMock(),
        record_user_usage=AsyncMock(),
        release_concurrency=AsyncMock(),
        publish_execution_completed=AsyncMock(),
        publish_execution_failed=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_apply_execution_result_postflight_records_usage_and_publishes_completion() -> (
    None
):
    request = ExecutionRequest(
        agent_id=3,
        tenant_id=11,
        user_id=13,
    )
    quota_config = SimpleNamespace()
    result = ExecutionResult(success=True, total_tokens=321)
    agent = SimpleNamespace(id=3)
    hook_registry = SimpleNamespace(trigger=AsyncMock(return_value={}))
    dependencies = _build_dependencies()

    await apply_execution_result_postflight(
        request=request,
        agent=agent,
        agent_id=3,
        result=result,
        hook_registry=hook_registry,
        estimated_tokens=200,
        quota_config=quota_config,
        user_id=request.user_id,
        dependencies=dependencies,
    )

    hook_registry.trigger.assert_awaited_once()
    dependencies.adjust_usage.assert_awaited_once_with(
        tenant_id=11,
        agent_id=3,
        estimated_tokens=200,
        actual_tokens=321,
        config=quota_config,
    )
    dependencies.record_user_usage.assert_awaited_once_with(
        tenant_id=11,
        agent_id=3,
        user_id=13,
        tokens=321,
    )
    dependencies.publish_execution_completed.assert_awaited_once()
    dependencies.publish_execution_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_execution_result_postflight_skips_quota_for_flagged_requests() -> (
    None
):
    request = ExecutionRequest(
        agent_id=5,
        tenant_id=17,
        user_id=19,
        skip_quota=True,
    )
    quota_config = SimpleNamespace()
    result = ExecutionResult(success=False, error="execution failed")
    agent = SimpleNamespace(id=5)
    hook_registry = SimpleNamespace(trigger=AsyncMock(return_value={}))
    dependencies = _build_dependencies()

    await apply_execution_result_postflight(
        request=request,
        agent=agent,
        agent_id=5,
        result=result,
        hook_registry=hook_registry,
        estimated_tokens=150,
        quota_config=quota_config,
        user_id=request.user_id,
        dependencies=dependencies,
    )

    hook_registry.trigger.assert_awaited_once()
    dependencies.adjust_usage.assert_not_awaited()
    dependencies.record_user_usage.assert_not_awaited()
    dependencies.publish_execution_completed.assert_not_awaited()
    dependencies.publish_execution_failed.assert_awaited_once_with(
        request,
        agent,
        "execution failed",
    )


@pytest.mark.asyncio
async def test_rollback_execution_postflight_usage_releases_estimated_tokens() -> None:
    request = ExecutionRequest(
        agent_id=7,
        tenant_id=23,
    )
    quota_config = SimpleNamespace()
    dependencies = _build_dependencies()

    await rollback_execution_postflight_usage(
        request=request,
        agent_id=7,
        estimated_tokens=144,
        quota_config=quota_config,
        dependencies=dependencies,
    )

    dependencies.adjust_usage.assert_awaited_once_with(
        tenant_id=23,
        agent_id=7,
        estimated_tokens=144,
        actual_tokens=0,
        config=quota_config,
    )


@pytest.mark.asyncio
async def test_publish_failed_and_release_helpers_delegate_to_shared_dependencies() -> (
    None
):
    request = ExecutionRequest(
        agent_id=9,
        tenant_id=29,
    )
    dependencies = _build_dependencies()
    agent = SimpleNamespace(id=9)

    await publish_failed_execution_postflight(
        request=request,
        agent=agent,
        error="public error",
        error_type="RuntimeError",
        dependencies=dependencies,
    )
    await release_execution_postflight_lock(
        request=request,
        agent_id=9,
        lock_token="lock-9",
        dependencies=dependencies,
    )

    dependencies.publish_execution_failed.assert_awaited_once_with(
        request,
        agent,
        "public error",
        "RuntimeError",
    )
    dependencies.release_concurrency.assert_awaited_once_with(
        tenant_id=29,
        agent_id=9,
        lock_token="lock-9",
    )
