"""Shared execution postflight helpers for dispatcher and stream paths."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.ai.agent_quota import (
    AgentConcurrencyLimiter,
    AgentQuotaConfig,
    AgentQuotaManager,
)
from app.ai.events.hooks import HookPoint

from .base import BaseEngine
from .types import ExecutionRequest, ExecutionResult


@dataclass(frozen=True)
class ExecutionPostflightDependencies:
    """Shared runtime collaborators for execution postflight handling."""

    adjust_usage: Callable[..., Awaitable[None]]
    record_user_usage: Callable[..., Awaitable[None]]
    release_concurrency: Callable[..., Awaitable[None]]
    publish_execution_completed: Callable[
        [ExecutionRequest, Any, ExecutionResult],
        Awaitable[None],
    ]
    publish_execution_failed: Callable[..., Awaitable[None]]


def default_execution_postflight_dependencies() -> ExecutionPostflightDependencies:
    """Build the default postflight dependency bundle."""
    return ExecutionPostflightDependencies(
        adjust_usage=AgentQuotaManager.adjust_usage,
        record_user_usage=AgentQuotaManager.record_user_usage,
        release_concurrency=AgentConcurrencyLimiter.release,
        publish_execution_completed=BaseEngine._publish_execution_completed,
        publish_execution_failed=BaseEngine._publish_execution_failed,
    )


async def trigger_after_execute_postflight(
    *,
    request: ExecutionRequest,
    agent_id: int,
    result: ExecutionResult,
    hook_registry: Any,
) -> None:
    """Trigger the shared AFTER_EXECUTE hook for a completed turn."""
    await hook_registry.trigger(
        HookPoint.AFTER_EXECUTE,
        tenant_id=request.tenant_id,
        agent_id=agent_id,
        result=result,
    )


async def adjust_execution_postflight_usage(
    *,
    request: ExecutionRequest,
    agent_id: int,
    result: ExecutionResult,
    estimated_tokens: int,
    quota_config: AgentQuotaConfig,
    user_id: int | None,
    dependencies: ExecutionPostflightDependencies,
) -> None:
    """Adjust preflight quota estimates to actual usage and record user usage."""
    if request.skip_quota:
        return

    actual_tokens = result.total_tokens or 0
    await dependencies.adjust_usage(
        tenant_id=request.tenant_id,
        agent_id=agent_id,
        estimated_tokens=estimated_tokens,
        actual_tokens=actual_tokens,
        config=quota_config,
    )
    if user_id and actual_tokens > 0:
        await dependencies.record_user_usage(
            tenant_id=request.tenant_id,
            agent_id=agent_id,
            user_id=user_id,
            tokens=actual_tokens,
        )


async def publish_execution_result_postflight(
    *,
    request: ExecutionRequest,
    agent: Any,
    result: ExecutionResult,
    dependencies: ExecutionPostflightDependencies,
) -> None:
    """Publish execution outcome events after the result is finalized."""
    if result.success:
        await dependencies.publish_execution_completed(
            request,
            agent,
            result,
        )
        return

    await dependencies.publish_execution_failed(
        request,
        agent,
        result.error or "",
    )


async def apply_execution_result_postflight(
    *,
    request: ExecutionRequest,
    agent: Any,
    agent_id: int,
    result: ExecutionResult,
    hook_registry: Any,
    estimated_tokens: int,
    quota_config: AgentQuotaConfig,
    user_id: int | None,
    dependencies: ExecutionPostflightDependencies,
) -> None:
    """Run the shared live-turn postflight contract after engine execution."""
    await trigger_after_execute_postflight(
        request=request,
        agent_id=agent_id,
        result=result,
        hook_registry=hook_registry,
    )
    await adjust_execution_postflight_usage(
        request=request,
        agent_id=agent_id,
        result=result,
        estimated_tokens=estimated_tokens,
        quota_config=quota_config,
        user_id=user_id,
        dependencies=dependencies,
    )
    await publish_execution_result_postflight(
        request=request,
        agent=agent,
        result=result,
        dependencies=dependencies,
    )


async def rollback_execution_postflight_usage(
    *,
    request: ExecutionRequest,
    agent_id: int,
    estimated_tokens: int,
    quota_config: AgentQuotaConfig,
    dependencies: ExecutionPostflightDependencies,
) -> None:
    """Release preflight-estimated quota when execution fails before finalize."""
    if request.skip_quota or estimated_tokens <= 0:
        return

    await dependencies.adjust_usage(
        tenant_id=request.tenant_id,
        agent_id=agent_id,
        estimated_tokens=estimated_tokens,
        actual_tokens=0,
        config=quota_config,
    )


async def publish_failed_execution_postflight(
    *,
    request: ExecutionRequest,
    agent: Any,
    error: str,
    error_type: str = "",
    dependencies: ExecutionPostflightDependencies,
) -> None:
    """Publish an execution-failed event for errors outside result finalization."""
    await dependencies.publish_execution_failed(
        request,
        agent,
        error,
        error_type,
    )


async def release_execution_postflight_lock(
    *,
    request: ExecutionRequest,
    agent_id: int,
    lock_token: str,
    dependencies: ExecutionPostflightDependencies,
) -> None:
    """Release the shared execution concurrency slot if one was acquired."""
    if not lock_token:
        return

    await dependencies.release_concurrency(
        tenant_id=request.tenant_id,
        agent_id=agent_id,
        lock_token=lock_token,
    )


__all__ = [
    "ExecutionPostflightDependencies",
    "adjust_execution_postflight_usage",
    "apply_execution_result_postflight",
    "default_execution_postflight_dependencies",
    "publish_failed_execution_postflight",
    "publish_execution_result_postflight",
    "release_execution_postflight_lock",
    "rollback_execution_postflight_usage",
    "trigger_after_execute_postflight",
]
