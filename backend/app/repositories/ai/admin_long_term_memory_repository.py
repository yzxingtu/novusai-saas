"""
Admin long-term memory repositories / 管理端长期记忆仓储
"""

from app.core.base_repository import BaseRepository
from app.models.ai.memory_record import MemoryRecord
from app.models.ai.profile_snapshot import ProfileSnapshot


class AdminMemoryRecordRepository(BaseRepository[MemoryRecord]):
    model = MemoryRecord


class AdminProfileSnapshotRepository(BaseRepository[ProfileSnapshot]):
    model = ProfileSnapshot


__all__ = [
    "AdminMemoryRecordRepository",
    "AdminProfileSnapshotRepository",
]
