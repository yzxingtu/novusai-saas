"""
Long-term memory provider / 长期记忆 provider
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.models.ai.memory_record import MemoryRecord


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


__all__ = [
    "LongTermMemoryProvider",
]
