"""
CRUD 代码生成记录仓储

提供生成记录的数据访问层
"""

from app.core.base_repository import BaseRepository
from app.plugins.crud_generator.models.crud_generation_record import CrudGenerationRecord


class CrudGenerationRecordRepository(BaseRepository[CrudGenerationRecord]):
    """CRUD 代码生成记录仓储"""

    model = CrudGenerationRecord


__all__ = ["CrudGenerationRecordRepository"]
