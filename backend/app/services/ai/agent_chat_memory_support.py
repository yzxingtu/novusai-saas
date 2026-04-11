"""Runtime memory orchestration helpers for AgentChatService."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from app.enums.agent import MemoryChannelEnum, MemorySceneEnum

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.ai.engine.types import ExecutionRequest


def build_memory_event_id(conversation_id: int) -> str:
    return f"memevt:{conversation_id}:{uuid4().hex}"


def resolve_memory_context(
    memory_scene: str,
    memory_channel: str,
    memory_source: str,
) -> tuple[str, str, str, bool]:
    scene = (
        memory_scene
        if MemorySceneEnum.has_value(memory_scene)
        else MemorySceneEnum.UNKNOWN.value
    )
    channel = (
        memory_channel
        if MemoryChannelEnum.has_value(memory_channel)
        else MemoryChannelEnum.SYSTEM.value
    )
    source = memory_source or scene
    enabled = scene in (
        MemorySceneEnum.AI_CHAT_PAGE.value,
        MemorySceneEnum.ADMIN_CHAT.value,
    )
    return scene, channel, source, enabled


async def extract_memory_delta(
    *,
    tenant_id: int,
    message: str,
    response: str,
    agent_id: int,
) -> dict[str, list[str]]:
    from app.services.ai.memory_extraction_service import MemoryExtractionService

    empty: dict[str, list[str]] = {
        "preferences": [],
        "constraints": [],
        "task_states": [],
        "verified_facts": [],
    }
    result = await MemoryExtractionService(
        tenant_id,
    ).extract_turn_memory(
        agent_id=agent_id,
        message=message,
        response=response,
    )
    return result or empty


async def load_session_memory_context(
    *,
    tenant_id: int,
    request: ExecutionRequest,
    logger: Any,
    session_memory_service_cls: type,
) -> str:
    if not request.memory_enabled:
        return ""
    if not request.conversation_id or not request.user_id:
        return ""

    try:
        memory_svc = session_memory_service_cls(tenant_id)
        _, state = await memory_svc.get_state(
            channel=request.memory_channel,
            source=request.memory_source,
            agent_id=request.agent_id,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
        )
    except Exception as exc:
        logger.warning(
            "Session memory load degraded: tenant={} agent={} user={} conversation={} err={}",
            tenant_id,
            request.agent_id,
            request.user_id,
            request.conversation_id,
            str(exc),
        )
        return ""

    memory_section_keys = (
        "constraints",
        "preferences",
        "task_states",
        "verified_facts",
    )
    parts: list[str] = []
    for key in memory_section_keys:
        items = state.get(key)
        if items:
            parts.append(f"{key}: " + " | ".join(items[:6]))

    if not parts:
        logger.info(
            "Session memory context empty: tenant={} agent={} user={} conversation={}",
            tenant_id,
            request.agent_id,
            request.user_id,
            request.conversation_id,
        )
        return ""
    logger.info(
        "Session memory context injected: tenant={} agent={} user={} conversation={}",
        tenant_id,
        request.agent_id,
        request.user_id,
        request.conversation_id,
    )
    return "[SESSION MEMORY CONTEXT]\n" + "\n".join(parts)


async def persist_session_memory(
    *,
    db: AsyncSession,
    tenant_id: int,
    request: ExecutionRequest,
    message: str,
    response: str,
    event_id: str,
    logger: Any,
    extract_delta: Callable[..., Any],
    build_capture_payload: Callable[[dict[str, list[str]]], dict[str, list[str]]],
    long_term_provider_factory: Callable[..., Any],
    session_memory_service_cls: type,
) -> dict[str, list[str]] | None:
    if not request.memory_enabled:
        return None
    if not request.conversation_id or not request.user_id:
        return None

    delta = await extract_delta(
        message=message,
        response=response,
        agent_id=request.agent_id,
    )
    if not any(delta.values()):
        return None

    memory_svc = session_memory_service_cls(tenant_id)
    await memory_svc.upsert_state(
        channel=request.memory_channel,
        source=request.memory_source,
        agent_id=request.agent_id,
        user_id=request.user_id,
        conversation_id=request.conversation_id,
        event_id=event_id,
        delta=delta,
        metadata={"scene": request.memory_scene},
    )

    if request.long_term_memory_enabled and request.user_id:
        try:
            payload = build_capture_payload(delta)
            if any(payload.values()):
                provider = long_term_provider_factory(
                    db=db,
                    tenant_id=tenant_id,
                )
                await provider.capture(
                    agent_id=request.agent_id,
                    user_id=request.user_id,
                    source_kind="conversation_turn",
                    source_ref=f"conversation:{request.conversation_id}:{event_id}",
                    items_by_type=payload,
                )
        except Exception as exc:
            logger.warning(
                "Long-term memory capture degraded: tenant={} agent={} user={} conversation={} err={}",
                tenant_id,
                request.agent_id,
                request.user_id,
                request.conversation_id,
                str(exc),
            )
    return delta


async def resolve_effective_memory_enabled(
    *,
    db: AsyncSession,
    tenant_id: int,
    agent_id: int,
    scene: str,
    scene_enabled: bool,
    logger: Any,
) -> bool:
    if not scene_enabled:
        return False

    try:
        from app.configs.service import PLATFORM_TENANT_ID

        if tenant_id == PLATFORM_TENANT_ID:
            from app.services.ai.agent_service import AdminAgentService

            config = await AdminAgentService(db).get_memory_config(agent_id)
        else:
            from app.services.ai.agent_service import AgentService

            config = await AgentService(db, tenant_id).get_memory_config(agent_id)

        enabled = bool(config.get("effective_memory_enabled", False))
        logger.info(
            "Session memory switch resolved: tenant={} agent={} scene={} enabled={}",
            tenant_id,
            agent_id,
            scene,
            enabled,
        )
        return enabled
    except Exception as exc:
        logger.warning(
            "Resolve session memory switch degraded: tenant={} agent={} scene={} err={}",
            tenant_id,
            agent_id,
            scene,
            str(exc),
        )
        return False
