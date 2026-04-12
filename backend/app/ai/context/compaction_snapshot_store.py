"""
Context compaction snapshot store.

Keeps context-engine sidecar snapshot persistence out of services.ai so the
runtime layer can read/write its own compaction metadata without reversing the
service dependency direction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.ai.agent_conversation_repository import (
    AgentConversationRepository,
)

_CONTEXT_COMPACTION_METADATA_KEY = "context_compaction"


class ContextCompactionSnapshotStore:
    """Read/write conversation-level compaction snapshots."""

    def __init__(self, db: AsyncSession, tenant_id: int) -> None:
        self.repo = AgentConversationRepository(db, tenant_id)

    @staticmethod
    def _format_generated_at() -> str:
        return datetime.now(timezone.utc).isoformat()

    async def get_snapshot(
        self,
        conversation_id: int,
    ) -> dict[str, Any] | None:
        conversation = await self.repo.get_by_id(conversation_id)
        if not conversation:
            return None
        metadata = (
            conversation.metadata_ if isinstance(conversation.metadata_, dict) else {}
        )
        snapshot = metadata.get(_CONTEXT_COMPACTION_METADATA_KEY)
        return dict(snapshot) if isinstance(snapshot, dict) else None

    async def upsert_snapshot(
        self,
        conversation_id: int,
        *,
        summary: str,
        source_message_count: int,
        source_token_estimate: int,
    ) -> dict[str, Any] | None:
        conversation = await self.repo.get_by_id(conversation_id)
        if not conversation:
            return None

        metadata = dict(conversation.metadata_ or {})
        snapshot = {
            "summary": summary,
            "source_message_count": source_message_count,
            "source_token_estimate": source_token_estimate,
            "generated_at": self._format_generated_at(),
        }
        metadata[_CONTEXT_COMPACTION_METADATA_KEY] = snapshot
        await self.repo.update(conversation_id, {"metadata_": metadata})
        return snapshot


__all__ = ["ContextCompactionSnapshotStore"]
