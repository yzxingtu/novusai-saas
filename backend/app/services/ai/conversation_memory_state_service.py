"""
Conversation memory state helpers.
"""

from __future__ import annotations

import time
from typing import Any

from app.services.ai.session_memory_service import SessionMemoryService

CONVERSATION_MEMORY_STATE_METADATA_KEY = "conversation_memory_state"
MEMORY_STATE_LIST_FIELDS = (
    "preferences",
    "constraints",
    "task_states",
    "verified_facts",
)


def empty_conversation_memory_state() -> dict[str, Any]:
    return {
        "preferences": [],
        "constraints": [],
        "task_states": [],
        "verified_facts": [],
        "version": 0,
        "updated_at": 0,
    }


def _normalize_string_list(value: Any, *, limit: int = 20) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    if not isinstance(value, (list, tuple)):
        return items
    for raw_item in value:
        text = str(raw_item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        items.append(text)
        if len(items) >= limit:
            break
    return items


def _merge_list(
    original: list[str],
    incoming: list[str],
    *,
    limit: int = 20,
) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for item in [*incoming, *original]:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        merged.append(text)
        if len(merged) >= limit:
            break
    return merged


def normalize_conversation_memory_state(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return empty_conversation_memory_state()

    state = empty_conversation_memory_state()
    for field in MEMORY_STATE_LIST_FIELDS:
        state[field] = _normalize_string_list(payload.get(field))
    try:
        state["version"] = max(0, int(payload.get("version", 0) or 0))
    except (TypeError, ValueError):
        state["version"] = 0
    try:
        state["updated_at"] = max(0, int(payload.get("updated_at", 0) or 0))
    except (TypeError, ValueError):
        state["updated_at"] = 0

    last_event_id = str(payload.get("last_event_id") or "").strip()
    if last_event_id:
        state["last_event_id"] = last_event_id

    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        state["metadata"] = dict(metadata)
    return state


def merge_conversation_memory_states(
    *states: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge states with earlier arguments taking list-order precedence."""

    merged = empty_conversation_memory_state()
    for raw_state in reversed(states):
        state = normalize_conversation_memory_state(raw_state)
        for field in MEMORY_STATE_LIST_FIELDS:
            merged[field] = _merge_list(merged[field], state.get(field, []))
        merged["version"] = max(merged["version"], int(state.get("version", 0) or 0))
        merged["updated_at"] = max(
            merged["updated_at"],
            int(state.get("updated_at", 0) or 0),
        )
    return merged


def apply_conversation_memory_delta(
    state: dict[str, Any] | None,
    *,
    tenant_id: int,
    channel: str,
    source: str,
    agent_id: int,
    user_id: int,
    conversation_id: int,
    event_id: str,
    delta: dict[str, list[str]],
    metadata: dict[str, Any] | None = None,
) -> tuple[bool, dict[str, Any]]:
    current = normalize_conversation_memory_state(state)
    if event_id and current.get("last_event_id") == event_id:
        return False, current

    updated = {
        **current,
        "tenant_id": tenant_id,
        "channel": channel,
        "source": source,
        "agent_id": agent_id,
        "user_id": user_id,
        "conversation_id": conversation_id,
        "version": int(current.get("version", 0) or 0) + 1,
        "updated_at": int(time.time()),
        "last_event_id": event_id,
    }
    for field in MEMORY_STATE_LIST_FIELDS:
        updated[field] = _merge_list(
            current.get(field, []),
            list(delta.get(field) or []),
        )
    if metadata:
        updated["metadata"] = {**dict(current.get("metadata") or {}), **metadata}
    return True, updated


def extract_persisted_conversation_memory_state(
    conversation_or_metadata: Any,
) -> dict[str, Any]:
    metadata = conversation_or_metadata
    if not isinstance(metadata, dict):
        metadata = getattr(conversation_or_metadata, "metadata_", None)
    if not isinstance(metadata, dict):
        return empty_conversation_memory_state()
    return normalize_conversation_memory_state(
        metadata.get(CONVERSATION_MEMORY_STATE_METADATA_KEY)
    )


class ConversationMemoryStateService:
    """Command helpers for conversation memory state."""

    def __init__(self, *, memory_tenant_id: int) -> None:
        self._memory_tenant_id = memory_tenant_id

    def _memory_service(self) -> SessionMemoryService:
        if not hasattr(self, "_memory_service_instance"):
            self._memory_service_instance = SessionMemoryService(self._memory_tenant_id)
        return self._memory_service_instance

    async def get_state(self, conversation_id: int) -> dict[str, Any]:
        return await self._memory_service().get_conversation_memory_state(
            conversation_id
        )

    async def clear_state(self, conversation_id: int) -> int:
        return await self._memory_service().clear_conversation_memory(conversation_id)

    async def clear_state_safe(
        self,
        *,
        conversation_id: int,
        tenant_id: int | None,
        logger: Any,
        log_message: str,
    ) -> None:
        try:
            await self.clear_state(conversation_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                log_message,
                conversation_id,
                tenant_id,
                str(exc),
            )


__all__ = [
    "CONVERSATION_MEMORY_STATE_METADATA_KEY",
    "ConversationMemoryStateService",
    "MEMORY_STATE_LIST_FIELDS",
    "apply_conversation_memory_delta",
    "empty_conversation_memory_state",
    "extract_persisted_conversation_memory_state",
    "merge_conversation_memory_states",
    "normalize_conversation_memory_state",
]
