"""Companion helpers for AgentChatCommandService ephemeral stream setup."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi.responses import StreamingResponse

from app.services.ai.agent_chat_command_preflight_support import (
    build_ephemeral_stream_completion_handler,
)

if TYPE_CHECKING:
    from app.services.ai.agent_chat_service import AgentChatService


async def prepare_ephemeral_stream_runtime(
    *,
    service: AgentChatService,
    agent: Any,
    agent_id: int,
    message: str,
    variables: dict[str, Any] | None,
    user_id: int | None,
    knowledge_base_ids: list[int] | None,
    dropped_knowledge_base_ids: list[int] | None,
    user_role: str,
    user_role_id: int | None,
    permissions: set[str] | None,
    agent_concurrency_limiter: Any,
    agent_quota_manager: Any,
    agent_stats_manager: Any,
) -> tuple[Any, Any]:
    request_bundle = await service.stream_bootstrap.build_ephemeral_stream_request(
        agent=agent,
        agent_id=agent_id,
        message=message,
        variables=variables,
        user_id=user_id,
        knowledge_base_ids=knowledge_base_ids,
        dropped_knowledge_base_ids=dropped_knowledge_base_ids,
        user_role=user_role,
        user_role_id=user_role_id,
        permissions=permissions,
        billing_context=await service._build_billing_context(
            agent=agent,
            user_id=user_id,
            user_role=user_role,
            user_role_id=user_role_id,
        ),
    )
    preflight = await service.stream_bootstrap.run_stream_preflight(
        agent=agent,
        agent_id=agent_id,
        request=request_bundle.request,
        quota_config=request_bundle.quota_config,
        estimated_tokens=request_bundle.estimated_tokens,
        user_id=user_id,
        persist_new_conversation=False,
        persist_user_messages=None,
    )
    on_stream_complete = build_ephemeral_stream_completion_handler(
        tenant_id=service.tenant_id,
        agent_id=agent_id,
        estimated_tokens=request_bundle.estimated_tokens,
        quota_config=request_bundle.quota_config,
        user_id=user_id,
        lock_token=preflight.lock_token,
        agent_concurrency_limiter=agent_concurrency_limiter,
        agent_quota_manager=agent_quota_manager,
        agent_stats_manager=agent_stats_manager,
    )
    return request_bundle, on_stream_complete


async def execute_ephemeral_stream_chat(
    *,
    service: AgentChatService,
    agent_id: int,
    message: str,
    variables: dict[str, Any] | None,
    user_id: int | None,
    knowledge_base_ids: list[int] | None,
    user_role: str,
    user_role_id: int | None,
    permissions: set[str] | None,
    agent_concurrency_limiter: Any,
    agent_quota_manager: Any,
    agent_stats_manager: Any,
) -> StreamingResponse:
    agent = await service._validate_agent(agent_id)
    (
        knowledge_base_ids,
        dropped_knowledge_base_ids,
    ) = await service.query_service.sanitize_client_knowledge_base_ids(
        agent_id,
        knowledge_base_ids,
    )
    request_bundle, on_stream_complete = await prepare_ephemeral_stream_runtime(
        service=service,
        agent=agent,
        agent_id=agent_id,
        message=message,
        variables=variables,
        user_id=user_id,
        knowledge_base_ids=knowledge_base_ids,
        dropped_knowledge_base_ids=dropped_knowledge_base_ids,
        user_role=user_role,
        user_role_id=user_role_id,
        permissions=permissions,
        agent_concurrency_limiter=agent_concurrency_limiter,
        agent_quota_manager=agent_quota_manager,
        agent_stats_manager=agent_stats_manager,
    )
    engine_bundle = await service.stream_bootstrap.build_stream_engine_bundle(
        agent=agent,
        agent_id=agent_id,
        request=request_bundle.request,
        user_id=user_id,
        user_role=user_role,
        permissions=permissions,
        variables=variables,
        page_session_id=None,
        trust_policy_ref=None,
        enable_tool_runtime=False,
    )
    return await engine_bundle.engine.stream_execute(
        agent=agent,
        request=request_bundle.request,
        on_complete=on_stream_complete,
    )


__all__ = [
    "execute_ephemeral_stream_chat",
    "prepare_ephemeral_stream_runtime",
]
