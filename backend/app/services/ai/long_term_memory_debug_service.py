"""
Admin long-term memory debug service / 管理端长期记忆调试服务
"""

from __future__ import annotations

from app.core.base_service import GlobalService
from app.models.ai.memory_record import MemoryRecord
from app.models.ai.profile_snapshot import ProfileSnapshot
from app.repositories.ai.admin_long_term_memory_repository import (
    AdminMemoryRecordRepository,
    AdminProfileSnapshotRepository,
)


class AdminMemoryRecordDebugService(
    GlobalService[MemoryRecord, AdminMemoryRecordRepository]
):
    model = MemoryRecord
    repository_class = AdminMemoryRecordRepository

    async def serialize_record(self, item: MemoryRecord) -> dict:
        return item.to_dict()

    async def serialize_records(self, items: list[MemoryRecord]) -> list[dict]:
        return [item.to_dict() for item in items]


class AdminProfileSnapshotDebugService(
    GlobalService[ProfileSnapshot, AdminProfileSnapshotRepository]
):
    model = ProfileSnapshot
    repository_class = AdminProfileSnapshotRepository

    async def serialize_snapshot(self, item: ProfileSnapshot) -> dict:
        return item.to_dict()

    async def serialize_snapshots(self, items: list[ProfileSnapshot]) -> list[dict]:
        return [item.to_dict() for item in items]


__all__ = [
    "AdminMemoryRecordDebugService",
    "AdminProfileSnapshotDebugService",
]
