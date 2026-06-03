"""Shared execution preflight helpers for dispatcher and stream paths."""

from __future__ import annotations

from typing import Any

from app.ai.agent_quota_concurrency import AgentConcurrencyLimiter
from app.ai.agent_quota_config import AgentQuotaConfig
from app.ai.agent_quota_manager import AgentQuotaManager
from app.ai.events.hooks import HookPoint, get_hook_registry
from app.ai.utils.token_estimator import estimate_tokens
from app.core.i18n import _
from app.enums.agent import AgentExecutionModeEnum
from app.exceptions import BusinessException

from .types import ExecutionRequest


def apply_execution_mode_runtime_flags(request: ExecutionRequest) -> None:
    """Apply entrypoint-independent runtime flags before preflight checks."""
    if request.execution_mode != AgentExecutionModeEnum.API.value:
        return
    request.skip_quota = True
    request.skip_persistence = True
    request.skip_logging = True


def estimate_preflight_tokens(messages: list[Any] | None) -> int:
    """Estimate prompt cost for preflight quota enforcement."""
    if not messages:
        return 100
    return max(sum(estimate_tokens(message.content or "") for message in messages), 100)


async def acquire_preflight_lock(
    *,
    tenant_id: int,
    agent_id: int,
    quota_config: AgentQuotaConfig,
) -> str:
    """Acquire a concurrency slot when the quota config requires it."""
    if quota_config.max_concurrent <= 0 and quota_config.tenant_max_concurrent <= 0:
        return ""
    return await AgentConcurrencyLimiter.acquire(
        tenant_id=tenant_id,
        agent_id=agent_id,
        max_concurrent=quota_config.max_concurrent,
        tenant_max_concurrent=quota_config.tenant_max_concurrent,
    )


async def check_preflight_quota(
    *,
    db: Any,
    request: ExecutionRequest,
    agent_id: int,
    quota_config: AgentQuotaConfig,
    estimated_tokens: int,
) -> None:
    """Run the shared live-turn quota checks for sync and stream entrypoints."""
    if request.skip_quota:
        return
    await AgentQuotaManager.check_quota(
        tenant_id=request.tenant_id,
        agent_id=agent_id,
        config=quota_config,
        estimated_tokens=estimated_tokens,
    )
    if request.user_id:
        await AgentQuotaManager.check_user_quota(
            tenant_id=request.tenant_id,
            agent_id=agent_id,
            user_id=request.user_id,
            config=quota_config,
        )
    if not request.tenant_id:
        return
    from app.enums import ErrorCode
    from app.services.tenant.quota_service import QuotaService

    api_check = await QuotaService.check_api_quota_for_tenant_id(
        db,
        request.tenant_id,
    )
    if not api_check.allowed:
        raise BusinessException(
            message=api_check.message or _("quota.api_calls_exceeded"),
            code=ErrorCode.CONFLICT,
        )


async def trigger_before_execute_preflight(
    *,
    request: ExecutionRequest,
    agent_id: int,
) -> tuple[Any, dict[str, Any]]:
    """Trigger the shared BEFORE_EXECUTE hook and return its raw context."""
    hook_registry = get_hook_registry()
    hook_context = await hook_registry.trigger(
        HookPoint.BEFORE_EXECUTE,
        tenant_id=request.tenant_id,
        agent_id=agent_id,
        execution_mode=request.execution_mode,
        request=request,
    )
    return hook_registry, hook_context


__all__ = [
    "acquire_preflight_lock",
    "apply_execution_mode_runtime_flags",
    "check_preflight_quota",
    "estimate_preflight_tokens",
    "trigger_before_execute_preflight",
]
