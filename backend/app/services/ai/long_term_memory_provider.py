"""
Long-term memory provider implementation owned by the service layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context.long_term_memory import LongTermMemoryProvider
from app.models.ai.memory_record import MemoryRecord

if TYPE_CHECKING:
    from app.services.ai.long_term_memory_service import LongTermMemoryService


def _create_long_term_memory_service(
    db: AsyncSession,
    tenant_id: int,
) -> LongTermMemoryService:
    from app.services.ai.long_term_memory_service import LongTermMemoryService

    return LongTermMemoryService(db, tenant_id)


class DatabaseLongTermMemoryProvider(LongTermMemoryProvider):
    def __init__(self, db: AsyncSession, tenant_id: int):
        self.service: LongTermMemoryService = _create_long_term_memory_service(
            db,
            tenant_id,
        )

    async def capture(
        self,
        *,
        agent_id: int,
        user_id: int,
        source_kind: str,
        source_ref: str | None,
        items_by_type: dict[str, list[str]],
    ) -> list[MemoryRecord]:
        return await self.service.capture_records(
            agent_id=agent_id,
            user_id=user_id,
            source_kind=source_kind,
            source_ref=source_ref,
            items_by_type=items_by_type,
        )

    async def recall(
        self,
        *,
        agent_id: int,
        user_id: int,
        query_text: str,
        limit: int = 5,
    ) -> list[MemoryRecord]:
        return await self.service.recall(
            agent_id=agent_id,
            user_id=user_id,
            query_text=query_text,
            limit=limit,
        )

    async def profile(
        self,
        *,
        agent_id: int,
        user_id: int,
        limit: int = 10,
    ) -> dict[str, Any] | None:
        return await self.service.profile(
            agent_id=agent_id,
            user_id=user_id,
            limit=limit,
        )

    async def search(
        self,
        *,
        agent_id: int,
        user_id: int,
        query_text: str,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        return await self.service.search(
            agent_id=agent_id,
            user_id=user_id,
            query_text=query_text,
            limit=limit,
        )


def get_long_term_memory_provider(
    *,
    db: AsyncSession,
    tenant_id: int,
) -> LongTermMemoryProvider:
    return DatabaseLongTermMemoryProvider(db, tenant_id)


__all__ = [
    "DatabaseLongTermMemoryProvider",
    "get_long_term_memory_provider",
]
