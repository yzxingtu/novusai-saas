"""
CRUD 代码生成记录服务

提供生成记录的业务逻辑层
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_service import BaseService
from app.models.system.crud_generation_record import CrudGenerationRecord
from app.repositories.system.crud_generation_record_repository import (
    CrudGenerationRecordRepository,
)


class CrudGenerationRecordService(
    BaseService[CrudGenerationRecord, CrudGenerationRecordRepository]
):
    """CRUD 代码生成记录服务"""

    model = CrudGenerationRecord
    repository_class = CrudGenerationRecordRepository

    async def create_record(self, data: dict[str, Any]) -> CrudGenerationRecord:
        """创建生成记录"""
        return await self.create(data)

    async def get_record_detail(self, record_id: int) -> CrudGenerationRecord | None:
        """获取记录详情"""
        return await self.get_by_id(record_id)

    async def get_config_from_record(
        self, record_id: int
    ) -> dict[str, Any] | None:
        """从记录中提取配置快照"""
        record = await self.get_by_id(record_id)
        if record is None:
            return None
        return record.config_snapshot

    async def get_statistics(self) -> dict[str, Any]:
        """获取生成记录统计信息"""
        db = self.db

        # 按操作类型统计
        type_stmt = (
            select(
                CrudGenerationRecord.operation_type,
                func.count(CrudGenerationRecord.id).label("count"),
            )
            .where(CrudGenerationRecord.is_deleted.is_(False))
            .group_by(CrudGenerationRecord.operation_type)
        )
        type_result = await db.execute(type_stmt)
        by_type = {row.operation_type: row.count for row in type_result}

        # 按状态统计
        status_stmt = (
            select(
                CrudGenerationRecord.status,
                func.count(CrudGenerationRecord.id).label("count"),
            )
            .where(CrudGenerationRecord.is_deleted.is_(False))
            .group_by(CrudGenerationRecord.status)
        )
        status_result = await db.execute(status_stmt)
        by_status = {row.status: row.count for row in status_result}

        # 总数
        total = sum(by_type.values())

        # 平均耗时
        avg_stmt = (
            select(func.avg(CrudGenerationRecord.duration_ms))
            .where(CrudGenerationRecord.is_deleted.is_(False))
            .where(CrudGenerationRecord.duration_ms.isnot(None))
        )
        avg_result = await db.execute(avg_stmt)
        avg_duration = avg_result.scalar()

        return {
            "total": total,
            "by_type": by_type,
            "by_status": by_status,
            "avg_duration_ms": round(avg_duration, 2) if avg_duration else 0,
        }


__all__ = ["CrudGenerationRecordService"]
