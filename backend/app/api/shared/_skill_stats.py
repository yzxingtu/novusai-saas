"""
技能调用统计聚合查询

提供按技能包、按技能、按时间范围的调用统计数据。
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import utc_now
from app.models.ai.skill import Skill
from app.models.ai.skill_call_log import SkillCallLog


async def get_package_call_stats(
    db: AsyncSession,
    package_id: int,
    days: int = 7,
) -> dict[str, Any]:
    """
    获取技能包内所有技能的调用统计

    Args:
        db: 数据库会话
        package_id: 技能包 ID
        days: 统计天数（默认 7 天）

    Returns:
        统计数据字典
    """
    since = utc_now() - timedelta(days=days)

    # 查询包内技能 ID 列表
    skill_ids_result = await db.execute(
        select(Skill.id).where(
            Skill.package_id == package_id,
            Skill.is_deleted.is_(False),
        ),
    )
    skill_ids = [row[0] for row in skill_ids_result.all()]

    if not skill_ids:
        return {
            "days": days,
            "total_calls": 0,
            "success_count": 0,
            "failed_count": 0,
            "success_rate": 0,
            "avg_duration_ms": 0,
            "by_skill": [],
        }

    # 总体统计
    total_result = await db.execute(
        select(
            func.count(SkillCallLog.id).label("total"),
            func.sum(
                case((SkillCallLog.status == "success", 1), else_=0)
            ).label("success_count"),
            func.sum(
                case((SkillCallLog.status != "success", 1), else_=0)
            ).label("failed_count"),
            func.avg(SkillCallLog.duration_ms).label("avg_duration"),
        ).where(
            and_(
                SkillCallLog.skill_id.in_(skill_ids),
                SkillCallLog.created_at >= since,
                SkillCallLog.is_deleted.is_(False),
            ),
        ),
    )
    row = total_result.one()
    total = row.total or 0
    success_count = row.success_count or 0
    failed_count = row.failed_count or 0
    avg_duration = round(float(row.avg_duration or 0), 1)

    # 按技能分组统计
    by_skill_result = await db.execute(
        select(
            SkillCallLog.skill_id,
            SkillCallLog.tool_name,
            func.count(SkillCallLog.id).label("calls"),
            func.sum(
                case((SkillCallLog.status == "success", 1), else_=0)
            ).label("successes"),
            func.avg(SkillCallLog.duration_ms).label("avg_ms"),
        ).where(
            and_(
                SkillCallLog.skill_id.in_(skill_ids),
                SkillCallLog.created_at >= since,
                SkillCallLog.is_deleted.is_(False),
            ),
        ).group_by(
            SkillCallLog.skill_id,
            SkillCallLog.tool_name,
        ).order_by(
            func.count(SkillCallLog.id).desc(),
        ),
    )

    by_skill = []
    for r in by_skill_result.all():
        calls = r.calls or 0
        successes = r.successes or 0
        by_skill.append({
            "skill_id": r.skill_id,
            "tool_name": r.tool_name,
            "calls": calls,
            "success_rate": round(successes / calls * 100, 1) if calls > 0 else 0,
            "avg_duration_ms": round(float(r.avg_ms or 0), 1),
        })

    return {
        "days": days,
        "total_calls": total,
        "success_count": success_count,
        "failed_count": failed_count,
        "success_rate": round(success_count / total * 100, 1) if total > 0 else 0,
        "avg_duration_ms": avg_duration,
        "by_skill": by_skill,
    }
