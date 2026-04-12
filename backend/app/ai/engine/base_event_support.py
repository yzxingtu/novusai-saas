"""Execution lifecycle event helpers extracted from BaseEngine."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.ai.events.bus import get_event_bus
from app.ai.events.types import (
    ExecutionCompleted,
    ExecutionFailed,
    ExecutionStarted,
)

if TYPE_CHECKING:
    from app.models.ai.agent import Agent

    from .types import ExecutionRequest, ExecutionResult


class BaseEventSupportMixin:
    """Mixin for publishing execution lifecycle events."""

    @staticmethod
    async def _publish_execution_started(
        request: ExecutionRequest,
        agent: Agent,
    ) -> None:
        """Publish execution started event / 发布执行开始事件"""
        await get_event_bus().publish(
            ExecutionStarted(
                tenant_id=request.tenant_id,
                agent_id=agent.id,
                execution_mode=request.execution_mode,
            )
        )

    @staticmethod
    async def _publish_execution_completed(
        request: ExecutionRequest,
        agent: Agent,
        result: ExecutionResult,
    ) -> None:
        """Publish execution completed event / 发布执行完成事件"""
        await get_event_bus().publish(
            ExecutionCompleted(
                tenant_id=request.tenant_id,
                agent_id=agent.id,
                total_tokens=result.total_tokens,
                duration_ms=result.duration_ms,
            )
        )

    @staticmethod
    async def _publish_execution_failed(
        request: ExecutionRequest,
        agent: Agent,
        error: str,
        error_type: str = "",
    ) -> None:
        """Publish execution failed event / 发布执行失败事件"""
        await get_event_bus().publish(
            ExecutionFailed(
                tenant_id=request.tenant_id,
                agent_id=agent.id,
                error=error,
                error_type=error_type,
            )
        )


__all__ = ["BaseEventSupportMixin"]
