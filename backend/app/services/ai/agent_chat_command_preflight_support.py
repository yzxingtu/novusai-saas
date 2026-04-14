"""
Helper utilities for the AgentChatCommandService pre-dispatch work.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.ai.engine.types import ExecutionResult
from app.ai.events.hooks import HookPoint, get_hook_registry
from app.ai.types import ChatMessage
from app.core.i18n import _
from app.exceptions import BusinessException

if TYPE_CHECKING:
    from app.ai.agent_quota import AgentQuotaConfig


def _normalize_attachments(
    attachments: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    if not attachments:
        return None
    return [
        a if isinstance(a, dict) else a.model_dump()
        for a in attachments
    ]


def build_user_messages(
    *,
    batch: list[str] | None = None,
    message: str = "",
    attachments: list[dict[str, Any]] | None = None,
) -> list[ChatMessage]:
    attach_list = _normalize_attachments(attachments)
    if batch:
        return [
            ChatMessage(
                role="user",
                content=item,
                attachments=attach_list if index == 0 else None,
            )
            for index, item in enumerate(batch)
        ]
    if message.strip() or attach_list:
        return [
            ChatMessage(
                role="user",
                content=message,
                attachments=attach_list,
            )
        ]
    return []


def merge_history_with_user_messages(
    history_messages: list[ChatMessage],
    user_messages: list[ChatMessage],
) -> list[ChatMessage]:
    if not user_messages:
        return list(history_messages)
    return [*history_messages, *user_messages]


async def run_before_agent_chat_hook(
    *,
    tenant_id: int,
    agent_id: int,
    messages: list[ChatMessage],
    variables: dict[str, Any] | None,
    knowledge_base_ids: list[int] | None,
) -> tuple[Any, list[ChatMessage]]:
    hook_registry = get_hook_registry()
    if hook_registry.has_hooks(HookPoint.BEFORE_AGENT_CHAT):
        hook_ctx = await hook_registry.trigger(
            HookPoint.BEFORE_AGENT_CHAT,
            tenant_id=tenant_id,
            agent_id=agent_id,
            messages=messages,
            config={
                "variables": variables,
                "knowledge_base_ids": knowledge_base_ids,
            },
        )
        if hook_ctx.get("blocked"):
            raise BusinessException(
                message=hook_ctx.get(
                    "block_reason", _("agent_chat.error.blocked_by_hook")
                )
            )
        messages = hook_ctx.get("messages", messages)
    return hook_registry, messages


def build_ephemeral_stream_completion_handler(
    *,
    tenant_id: int,
    agent_id: int,
    estimated_tokens: int,
    quota_config: AgentQuotaConfig,
    user_id: int | None,
    lock_token: str | None,
    agent_concurrency_limiter: Any,
    agent_quota_manager: Any,
    agent_stats_manager: Any,
):
    async def on_stream_complete(result: ExecutionResult) -> dict[str, Any] | None:
        try:
            actual_tokens = result.total_tokens or 0
            await agent_quota_manager.adjust_usage(
                tenant_id=tenant_id,
                agent_id=agent_id,
                estimated_tokens=estimated_tokens,
                actual_tokens=actual_tokens,
                config=quota_config,
            )
            if user_id and actual_tokens > 0:
                await agent_quota_manager.record_user_usage(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    user_id=user_id,
                    tokens=actual_tokens,
                )
            await agent_stats_manager.record_chat(
                tenant_id=tenant_id,
                agent_id=agent_id,
                tokens=result.total_tokens,
            )
        finally:
            if lock_token:
                await agent_concurrency_limiter.release(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    lock_token=lock_token,
                )
        return None

    return on_stream_complete


__all__ = [
    "build_ephemeral_stream_completion_handler",
    "build_user_messages",
    "merge_history_with_user_messages",
    "run_before_agent_chat_hook",
]
