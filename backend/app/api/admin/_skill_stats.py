"""
Skill 使用统计查询辅助模块

供 admin 和 tenant 端 Skill stats API 共用
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai.action_log import AIActionLog


async def get_skill_stats_by_id(
    db: AsyncSession,
    skill_id: int,
) -> dict[str, Any]:
    """
    查询单个 Skill 的调用统计

    Returns:
        {
            "skill_id": 1,
            "total_calls": 100,
            "success_count": 95,
            "failure_count": 5,
            "success_rate": 0.95,
            "avg_duration_ms": 1200,
            "last_called_at": "2026-02-13T12:00:00",
        }
    """
    stmt = select(
        func.count().label("total_calls"),
        func.sum(
            case((AIActionLog.status == "success", 1), else_=0)
        ).label("success_count"),
        func.sum(
            case((AIActionLog.status != "success", 1), else_=0)
        ).label("failure_count"),
        func.avg(AIActionLog.duration_ms).label("avg_duration_ms"),
        func.max(AIActionLog.created_at).label("last_called_at"),
    ).where(
        AIActionLog.skill_id == skill_id,
        AIActionLog.is_deleted == False,  # noqa: E712
    )

    result = await db.execute(stmt)
    row = result.one()

    total = row.total_calls or 0
    success_count = row.success_count or 0
    failure_count = row.failure_count or 0

    return {
        "skill_id": skill_id,
        "total_calls": total,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": round(success_count / total, 4) if total > 0 else 0,
        "avg_duration_ms": round(float(row.avg_duration_ms or 0), 1),
        "last_called_at": row.last_called_at.isoformat() if row.last_called_at else None,
    }


async def get_all_skills_stats(
    db: AsyncSession,
    tenant_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    查询所有 Skill 的汇总统计

    Args:
        db: 数据库会话
        tenant_id: 可选租户 ID 过滤

    Returns:
        按调用次数降序排列的统计列表
    """
    from app.models.ai.skill import Skill

    stmt = (
        select(
            AIActionLog.skill_id,
            Skill.name.label("skill_name"),
            Skill.type.label("skill_type"),
            func.count().label("total_calls"),
            func.sum(
                case((AIActionLog.status == "success", 1), else_=0)
            ).label("success_count"),
            func.avg(AIActionLog.duration_ms).label("avg_duration_ms"),
            func.max(AIActionLog.created_at).label("last_called_at"),
        )
        .join(Skill, AIActionLog.skill_id == Skill.id, isouter=True)
        .where(
            AIActionLog.skill_id.isnot(None),
            AIActionLog.is_deleted == False,  # noqa: E712
        )
        .group_by(AIActionLog.skill_id, Skill.name, Skill.type)
        .order_by(func.count().desc())
    )

    if tenant_id is not None:
        stmt = stmt.where(AIActionLog.tenant_id == tenant_id)

    result = await db.execute(stmt)
    rows = result.all()

    stats = []
    for row in rows:
        total = row.total_calls or 0
        sc = row.success_count or 0
        stats.append({
            "skill_id": row.skill_id,
            "skill_name": row.skill_name,
            "skill_type": row.skill_type,
            "total_calls": total,
            "success_count": sc,
            "failure_count": total - sc,
            "success_rate": round(sc / total, 4) if total > 0 else 0,
            "avg_duration_ms": round(float(row.avg_duration_ms or 0), 1),
            "last_called_at": row.last_called_at.isoformat() if row.last_called_at else None,
        })

    return stats


__all__ = ["get_skill_stats_by_id", "get_all_skills_stats"]
