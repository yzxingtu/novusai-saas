"""Stream support helpers for AgentChatService."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from app.services.ai.agent_chat_stream_runtime_dependencies import (
    AgentChatStreamPersistenceDependencies,
    default_agent_chat_stream_persistence_dependencies,
)

DependencyFactory = Callable[
    [], AgentChatStreamPersistenceDependencies | Mapping[str, Any]
]


class AgentChatStreamSupport:
    """Builds stream persistence dependencies and lightweight stream helpers."""

    def __init__(
        self,
        *,
        dependency_factory: DependencyFactory = (
            default_agent_chat_stream_persistence_dependencies
        ),
    ) -> None:
        self._dependency_factory = dependency_factory

    def build_stream_runtime_dependencies(
        self,
    ) -> AgentChatStreamPersistenceDependencies:
        dependencies = self._dependency_factory()
        if isinstance(dependencies, AgentChatStreamPersistenceDependencies):
            return dependencies
        if isinstance(dependencies, Mapping):
            return AgentChatStreamPersistenceDependencies.from_mapping(dependencies)
        raise TypeError(
            "Stream persistence dependencies must be a mapping or AgentChatStreamPersistenceDependencies"
        )

    @staticmethod
    def assistant_message_has_visible_reply_payload(message: dict[str, Any]) -> bool:
        if not isinstance(message, dict):
            return False
        if str(message.get("role") or "").strip() != "assistant":
            return False
        if str(message.get("content") or "").strip():
            return True
        metadata = message.get("metadata")
        if not isinstance(metadata, dict):
            return False
        if metadata.get("error") is True:
            return True
        if isinstance(metadata.get("pending_confirmation"), dict) or isinstance(
            metadata.get("pending_consent"), dict
        ):
            return True
        action_buttons = metadata.get("action_buttons")
        return isinstance(action_buttons, list) and len(action_buttons) > 0


__all__ = ["AgentChatStreamSupport"]
