"""Runtime memory orchestration helpers for AgentChatService."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from app.ai.memory_policy import (
    attach_memory_runtime_policy,
    normalize_thread_memory_state,
    prime_memory_runtime_policy,
)
from app.enums.agent import MemoryChannelEnum, MemorySceneEnum

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.ai.engine.types import ExecutionRequest


def _can_use_conversation_metadata_store(db: Any) -> bool:
    if "conversation" in getattr(db, "__dict__", {}):
        return True
    try:
        from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession

        return isinstance(db, SQLAlchemyAsyncSession)
    except Exception:
        return False


@dataclass(frozen=True)
class PreparedRequestMemoryStartup:
    """Normalized startup snapshot used to prime request memory ownership."""

    thread_memory_state: dict[str, Any]
    request_memory_runtime_policy: dict[str, Any]
    memory_context_source_metadata: dict[str, Any]


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


def resolve_thread_memory_state(
    *,
    conversation: Any | None = None,
    thread_memory_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_thread_memory_state = thread_memory_state
    if raw_thread_memory_state is None and conversation is not None:
        conversation_metadata = getattr(conversation, "metadata_", None)
        if isinstance(conversation_metadata, dict):
            raw_thread_memory_state = conversation_metadata.get("thread_memory_state")
    return normalize_thread_memory_state(raw_thread_memory_state)


def prepare_request_memory_startup(
    *,
    request: ExecutionRequest,
    conversation: Any | None = None,
    thread_memory_state: dict[str, Any] | None = None,
) -> PreparedRequestMemoryStartup:
    normalized_thread_memory_state = resolve_thread_memory_state(
        conversation=conversation,
        thread_memory_state=thread_memory_state,
    )
    request_memory_runtime_policy = prime_memory_runtime_policy(
        request,
        thread_memory_state=normalized_thread_memory_state,
    )
    return PreparedRequestMemoryStartup(
        thread_memory_state=normalized_thread_memory_state,
        request_memory_runtime_policy=dict(request_memory_runtime_policy),
        memory_context_source_metadata=dict(
            getattr(request, "memory_context_source_metadata", {}) or {}
        ),
    )


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


def message_requests_memory_save(message: str) -> bool:
    from app.services.ai.memory_extraction_service import MemoryExtractionService

    return MemoryExtractionService.message_requests_memory_save(message)


async def load_session_memory_context(
    *,
    db: AsyncSession | None = None,
    tenant_id: int,
    request: ExecutionRequest,
    logger: Any,
    session_memory_service_cls: type,
) -> str:
    memory_policy = attach_memory_runtime_policy(request=request)
    if memory_policy.session_memory_state != "enabled":
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
        state = {}
    else:
        state = dict(state or {})

    persisted_state: dict[str, Any] | None = None
    if (
        db is not None
        and request.conversation_id
        and _can_use_conversation_metadata_store(db)
    ):
        try:
            from app.repositories.ai.agent_conversation_repository import (
                AgentConversationRepository,
            )
            from app.services.ai.conversation_memory_state_service import (
                extract_persisted_conversation_memory_state,
            )

            conversation = await AgentConversationRepository(
                db,
                tenant_id,
            ).get_by_id(request.conversation_id)
            if conversation is not None:
                persisted_state = extract_persisted_conversation_memory_state(
                    conversation
                )
        except Exception as exc:
            logger.warning(
                "Persisted session memory load degraded: tenant={} agent={} user={} conversation={} err={}",
                tenant_id,
                request.agent_id,
                request.user_id,
                request.conversation_id,
                str(exc),
            )

    if persisted_state:
        from app.services.ai.conversation_memory_state_service import (
            merge_conversation_memory_states,
        )

        state = merge_conversation_memory_states(state, persisted_state)

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


async def persist_conversation_memory_state(
    *,
    db: AsyncSession,
    tenant_id: int,
    request: ExecutionRequest,
    event_id: str,
    delta: dict[str, list[str]],
    metadata: dict[str, Any] | None = None,
) -> bool:
    from app.repositories.ai.agent_conversation_repository import (
        AgentConversationRepository,
    )
    from app.services.ai.conversation_memory_state_service import (
        CONVERSATION_MEMORY_STATE_METADATA_KEY,
        apply_conversation_memory_delta,
    )

    if not request.conversation_id or not request.user_id:
        return False
    if not _can_use_conversation_metadata_store(db):
        return False

    repo = AgentConversationRepository(db, tenant_id)
    conversation = await repo.get_by_id(request.conversation_id)
    if conversation is None:
        return False

    conversation_metadata = dict(getattr(conversation, "metadata_", None) or {})
    changed, state = apply_conversation_memory_delta(
        conversation_metadata.get(CONVERSATION_MEMORY_STATE_METADATA_KEY),
        tenant_id=tenant_id,
        channel=request.memory_channel,
        source=request.memory_source,
        agent_id=request.agent_id,
        user_id=request.user_id,
        conversation_id=request.conversation_id,
        event_id=event_id,
        delta=delta,
        metadata=metadata,
    )
    if not changed:
        return False

    conversation_metadata[CONVERSATION_MEMORY_STATE_METADATA_KEY] = state
    await repo.update(
        request.conversation_id,
        {"metadata_": conversation_metadata},
    )
    return True


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
    memory_policy = attach_memory_runtime_policy(request=request)
    explicit_memory_save = message_requests_memory_save(message)
    if not request.conversation_id or not request.user_id:
        return None
    if memory_policy.external_context_polluted:
        logger.info(
            "Skip memory capture for polluted turn: tenant={} agent={} user={} conversation={} reason={}",
            tenant_id,
            request.agent_id,
            request.user_id,
            request.conversation_id,
            memory_policy.external_context_reason or "external_context_polluted",
        )
        return None
    if (
        memory_policy.session_memory_state != "enabled"
        and memory_policy.long_term_memory_capture_state != "enabled"
        and not explicit_memory_save
    ):
        return None

    delta = await extract_delta(
        message=message,
        response=response,
        agent_id=request.agent_id,
    )
    if not any(delta.values()):
        return None

    if memory_policy.session_memory_state == "enabled":
        memory_svc = session_memory_service_cls(tenant_id)
        try:
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
        except Exception as exc:
            logger.warning(
                "Session memory Redis write degraded: tenant={} agent={} user={} conversation={} err={}",
                tenant_id,
                request.agent_id,
                request.user_id,
                request.conversation_id,
                str(exc),
            )

        try:
            await persist_conversation_memory_state(
                db=db,
                tenant_id=tenant_id,
                request=request,
                event_id=event_id,
                delta=delta,
                metadata={"scene": request.memory_scene},
            )
        except Exception as exc:
            logger.warning(
                "Conversation memory metadata write degraded: tenant={} agent={} user={} conversation={} err={}",
                tenant_id,
                request.agent_id,
                request.user_id,
                request.conversation_id,
                str(exc),
            )
    elif explicit_memory_save:
        try:
            await persist_conversation_memory_state(
                db=db,
                tenant_id=tenant_id,
                request=request,
                event_id=event_id,
                delta=delta,
                metadata={"scene": request.memory_scene},
            )
        except Exception as exc:
            logger.warning(
                "Conversation memory metadata write degraded: tenant={} agent={} user={} conversation={} err={}",
                tenant_id,
                request.agent_id,
                request.user_id,
                request.conversation_id,
                str(exc),
            )

    if memory_policy.long_term_memory_capture_state == "enabled" and request.user_id:
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
