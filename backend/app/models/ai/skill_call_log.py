"""
技能调用日志模型

记录每次工具/技能调用的详情，用于统计分析和审计。
"""

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel
from app.core.i18n import _


class SkillCallLog(TenantModel):
    """
    技能调用日志

    每次 ToolSandbox 执行工具调用后自动写入一条记录。
    """

    __tablename__ = "skill_call_logs"

    __filterable__ = {
        "skill_id": "skill_id",
        "agent_id": "agent_id",
        "tool_name": "tool_name",
        "status": "status",
        "created_at": "created_at",
    }

    __sortable__ = {
        "created_at": "created_at",
        "duration_ms": "duration_ms",
    }

    # ==================== 关联信息 ====================

    skill_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment=_("skill_call_log.field.skill_id"),
    )
    agent_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment=_("skill_call_log.field.agent_id"),
    )

    # ==================== 调用信息 ====================

    tool_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        comment=_("skill_call_log.field.tool_name"),
    )
    tool_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment=_("skill_call_log.field.tool_type"),
    )

    # ==================== 结果 ====================

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="success",
        index=True,
        comment=_("skill_call_log.field.status"),
    )
    duration_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("skill_call_log.field.duration_ms"),
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("skill_call_log.field.error_message"),
    )

    # ==================== 复合索引 ====================

    __table_args__ = (
        Index("ix_skill_call_logs_tenant_skill", "tenant_id", "skill_id"),
        Index("ix_skill_call_logs_tenant_agent", "tenant_id", "agent_id"),
        Index("ix_skill_call_logs_tenant_created", "tenant_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<SkillCallLog(id={self.id}, tool={self.tool_name}, "
            f"status={self.status}, duration={self.duration_ms}ms)>"
        )


__all__ = ["SkillCallLog"]
