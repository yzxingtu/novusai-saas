"""Runtime support facade for agent chat orchestration helpers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.constants import DEFAULT_MEMORY_SCENE, MEMORY_CHANNEL_SYSTEM
from app.core.logging import LogManager
from app.services.ai.agent_chat_billing_support import (
    build_billing_context as _build_billing_context_impl,
)
from app.services.ai.agent_chat_interaction_support import (
    build_trust_policy_ref_from_interaction_updates as _build_trust_policy_ref_from_interaction_updates_impl,
)
from app.services.ai.agent_chat_interaction_support import (
    build_trusted_auto_bootstrap_policy_ref as _build_trusted_auto_bootstrap_policy_ref_impl,
)
from app.services.ai.agent_chat_interaction_support import (
    grant_trusted_auto_policies as _grant_trusted_auto_policies_impl,
)
from app.services.ai.agent_chat_interaction_support import (
    resolve_interaction_mode as _resolve_interaction_mode_impl,
)
from app.services.ai.agent_chat_interaction_support import (
    resolve_runtime_trust_policy_ref as _resolve_runtime_trust_policy_ref_impl,
)
from app.services.ai.agent_chat_memory_support import (
    PreparedRequestMemoryStartup,
)
from app.services.ai.agent_chat_memory_support import (
    build_memory_event_id as _build_memory_event_id_impl,
)
from app.services.ai.agent_chat_memory_support import (
    extract_memory_delta as _extract_memory_delta_impl,
)
from app.services.ai.agent_chat_memory_support import (
    load_session_memory_context as _load_session_memory_context_impl,
)
from app.services.ai.agent_chat_memory_support import (
    persist_session_memory as _persist_session_memory_impl,
)
from app.services.ai.agent_chat_memory_support import (
    prepare_request_memory_startup as _prepare_request_memory_startup_impl,
)
from app.services.ai.agent_chat_memory_support import (
    resolve_effective_memory_enabled as _resolve_effective_memory_enabled_impl,
)
from app.services.ai.agent_chat_memory_support import (
    resolve_memory_context as _resolve_memory_context_impl,
)

logger = LogManager.get_logger("ai.agent_chat_service")


class AgentChatRuntimeSupport:
    """Facade that delegates runtime concerns to focused helper modules."""

    def __init__(self, db: AsyncSession, tenant_id: int) -> None:
        self.db = db
        self.tenant_id = tenant_id

    async def build_billing_context(
        self,
        *,
        agent: Any,
        user_id: int | None,
        user_role: str,
        user_role_id: int | None = None,
    ) -> dict[str, Any]:
        return await _build_billing_context_impl(
            db=self.db,
            tenant_id=self.tenant_id,
            agent=agent,
            user_id=user_id,
            user_role=user_role,
            user_role_id=user_role_id,
        )

    async def extract_memory_delta(
        self,
        *,
        message: str,
        response: str,
        agent_id: int,
    ) -> dict[str, list[str]]:
        return await _extract_memory_delta_impl(
            tenant_id=self.tenant_id,
            message=message,
            response=response,
            agent_id=agent_id,
        )

    async def load_session_memory_context(
        self,
        *,
        request: Any,
        session_memory_service_cls: type | None = None,
    ) -> str:
        if session_memory_service_cls is None:
            from app.services.ai.session_memory_service import SessionMemoryService

            session_memory_service_cls = SessionMemoryService
        return await _load_session_memory_context_impl(
            tenant_id=self.tenant_id,
            request=request,
            logger=logger,
            session_memory_service_cls=session_memory_service_cls,
        )

    async def persist_session_memory(
        self,
        *,
        request: Any,
        message: str,
        response: str,
        event_id: str,
        extract_delta: Callable[..., Any] | None = None,
        extract_memory_delta_fn: Callable[..., Any] | None = None,
        build_capture_payload: Callable[[dict[str, list[str]]], dict[str, list[str]]]
        | None = None,
        long_term_provider_factory: Callable[..., Any] | None = None,
        long_term_memory_provider_factory: Callable[..., Any] | None = None,
        session_memory_service_cls: type | None = None,
    ) -> dict[str, list[str]] | None:
        if extract_delta is None:
            extract_delta = extract_memory_delta_fn or self.extract_memory_delta
        if build_capture_payload is None:
            from app.services.ai.long_term_memory_service import (
                build_memory_capture_payload_from_session_delta,
            )

            build_capture_payload = build_memory_capture_payload_from_session_delta
        if long_term_provider_factory is None:
            long_term_provider_factory = long_term_memory_provider_factory
        if long_term_provider_factory is None:
            from app.services.ai.long_term_memory_provider import (
                get_long_term_memory_provider,
            )

            long_term_provider_factory = get_long_term_memory_provider
        if session_memory_service_cls is None:
            from app.services.ai.session_memory_service import SessionMemoryService

            session_memory_service_cls = SessionMemoryService

        return await _persist_session_memory_impl(
            db=self.db,
            tenant_id=self.tenant_id,
            request=request,
            message=message,
            response=response,
            event_id=event_id,
            logger=logger,
            extract_delta=extract_delta,
            build_capture_payload=build_capture_payload,
            long_term_provider_factory=long_term_provider_factory,
            session_memory_service_cls=session_memory_service_cls,
        )

    @staticmethod
    def build_memory_event_id(conversation_id: int) -> str:
        return _build_memory_event_id_impl(conversation_id)

    @staticmethod
    def prepare_request_memory_startup(
        *,
        request: Any,
        conversation: Any | None = None,
        thread_memory_state: dict[str, Any] | None = None,
    ) -> PreparedRequestMemoryStartup:
        return _prepare_request_memory_startup_impl(
            request=request,
            conversation=conversation,
            thread_memory_state=thread_memory_state,
        )

    @staticmethod
    def resolve_memory_context(
        *,
        memory_scene: str = DEFAULT_MEMORY_SCENE,
        memory_channel: str = MEMORY_CHANNEL_SYSTEM,
        memory_source: str = "",
    ) -> tuple[str, str, str, bool]:
        return _resolve_memory_context_impl(
            memory_scene=memory_scene,
            memory_channel=memory_channel,
            memory_source=memory_source,
        )

    async def resolve_effective_memory_enabled(
        self,
        *,
        agent_id: int,
        scene: str,
        scene_enabled: bool,
    ) -> bool:
        return await _resolve_effective_memory_enabled_impl(
            db=self.db,
            tenant_id=self.tenant_id,
            agent_id=agent_id,
            scene=scene,
            scene_enabled=scene_enabled,
            logger=logger,
        )

    async def resolve_runtime_trust_policy_ref(
        self,
        *,
        conversation_id: int | None,
        agent_id: int,
        operator_id: int | None,
        operator_type: str | None,
        explicit_ref: dict[str, Any] | None = None,
        trust_policy_service_cls: type | None = None,
    ) -> dict[str, Any] | None:
        return await _resolve_runtime_trust_policy_ref_impl(
            db=self.db,
            tenant_id=self.tenant_id,
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=operator_id,
            operator_type=operator_type,
            explicit_ref=explicit_ref,
            logger=logger,
            trust_policy_service_cls=trust_policy_service_cls,
        )

    async def resolve_interaction_mode(
        self,
        *,
        requested_mode: str | None,
        conversation_id: int | None,
        agent_id: int,
        operator_id: int | None,
        operator_type: str | None,
        explicit_trust_policy_ref: dict[str, Any] | None = None,
        interaction_updates: list[dict[str, Any]] | None = None,
        trust_policy_service_cls: type | None = None,
    ) -> tuple[str, dict[str, Any] | None, str | None]:
        return await _resolve_interaction_mode_impl(
            db=self.db,
            tenant_id=self.tenant_id,
            requested_mode=requested_mode,
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=operator_id,
            operator_type=operator_type,
            explicit_trust_policy_ref=explicit_trust_policy_ref,
            interaction_updates=interaction_updates,
            logger=logger,
            trust_policy_service_cls=trust_policy_service_cls,
        )

    @staticmethod
    def build_trust_policy_ref_from_interaction_updates(
        interaction_updates: list[dict[str, Any]] | None,
        trust_policy_service_cls: type | None = None,
    ) -> dict[str, Any] | None:
        return _build_trust_policy_ref_from_interaction_updates_impl(
            interaction_updates,
            trust_policy_service_cls=trust_policy_service_cls,
        )

    @staticmethod
    def build_trusted_auto_bootstrap_policy_ref() -> dict[str, Any]:
        return _build_trusted_auto_bootstrap_policy_ref_impl()

    async def grant_trusted_auto_policies(
        self,
        *,
        conversation_id: int,
        agent_id: int,
        operator_id: int | None,
        operator_type: str | None,
        interaction_updates: list[dict[str, Any]] | None,
        interaction_mode: str,
        trust_policy_service_cls: type | None = None,
    ) -> None:
        await _grant_trusted_auto_policies_impl(
            db=self.db,
            tenant_id=self.tenant_id,
            conversation_id=conversation_id,
            agent_id=agent_id,
            operator_id=operator_id,
            operator_type=operator_type,
            interaction_updates=interaction_updates,
            interaction_mode=interaction_mode,
            trust_policy_service_cls=trust_policy_service_cls,
        )


__all__ = ["AgentChatRuntimeSupport"]
