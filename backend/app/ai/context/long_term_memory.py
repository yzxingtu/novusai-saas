"""
Long-term memory provider / 长期记忆 provider
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai.memory_record import MemoryRecord
from app.services.ai.long_term_memory_service import LongTermMemoryService


class LongTermMemoryProvider(ABC):
    @abstractmethod
    async def capture(
        self,
        *,
        agent_id: int,
        user_id: int,
        source_kind: str,
        source_ref: str | None,
        items_by_type: dict[str, list[str]],
    ) -> list[MemoryRecord]: ...

    @abstractmethod
    async def recall(
        self,
        *,
        agent_id: int,
        user_id: int,
        query_text: str,
        limit: int = 5,
    ) -> list[MemoryRecord]: ...

    @abstractmethod
    async def profile(
        self,
        *,
        agent_id: int,
        user_id: int,
        limit: int = 10,
    ) -> dict[str, Any] | None: ...

    @abstractmethod
    async def search(
        self,
        *,
        agent_id: int,
        user_id: int,
        query_text: str,
        limit: int = 10,
    ) -> list[MemoryRecord]: ...


class DatabaseLongTermMemoryProvider(LongTermMemoryProvider):
    def __init__(self, db: AsyncSession, tenant_id: int):
        self.service = LongTermMemoryService(db, tenant_id)

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
    "LongTermMemoryProvider",
    "DatabaseLongTermMemoryProvider",
    "get_long_term_memory_provider",
]
