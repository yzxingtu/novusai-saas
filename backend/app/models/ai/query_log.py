"""
AI 数据查询审计日志模型 / AI Data Query Audit Log Model

历史上用于记录 AI 查询链路的审计信息，现主要作为兼容性与审计留存模型。
Historically used for AI query-chain auditing and now retained mainly for compatibility and audit records.
"""

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel
from app.core.i18n import _


class AIQueryLog(TenantModel):
    """
    AI 数据查询审计日志 / AI Data Query Audit Log.

    记录 AI 查询链路的详细审计信息：
    - 用户原始问题
    - 生成或执行过的查询语句
    - 执行者身份（user_id, user_role）
    - 执行状态、耗时、返回行数
    - 失败原因
    """

    __tablename__ = "ai_query_logs"

    # 允许前端筛选的字段 / Fields exposed for list filtering
    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "user_id": "user_id",
        "user_role": "user_role",
        "agent_id": "agent_id",
        "status": "status",
        "created_at": "created_at",
    }

    # 允许排序的字段 / Sortable columns for UI
    __sortable__ = {
        "id": "id",
        "created_at": "created_at",
        "duration_ms": "duration_ms",
        "row_count": "row_count",
    }

    # 智能体 ID
    agent_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment=_("ai_query_log.field.agent_id"),
    )

    # 操作者 ID（关联 admins / tenant_admins）
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment=_("ai_query_log.field.user_id"),
    )

    # 操作者角色（platform_admin / tenant_admin / tenant_user） / Actor role
    user_role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="tenant_admin",
        comment=_("ai_query_log.field.user_role"),
    )

    # 用户原始问题 / Natural language question
    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment=_("ai_query_log.field.question"),
    )

    # LLM 生成的原始 SQL / LLM-generated SQL
    generated_sql: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("ai_query_log.field.generated_sql"),
    )

    # 隔离注入后的最终 SQL / Final SQL after tenant isolation
    final_sql: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("ai_query_log.field.final_sql"),
    )

    # 返回行数 / Returned row count
    row_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("ai_query_log.field.row_count"),
    )

    # 执行状态（success / failed / rejected） / Execution status
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="success",
        index=True,
        comment=_("ai_query_log.field.status"),
    )

    # 错误信息 / Error message
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("ai_query_log.field.error_message"),
    )

    # 执行耗时（毫秒） / Duration in ms
    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("ai_query_log.field.duration_ms"),
    )

    # LLM 置信度 / LLM confidence label
    confidence: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment=_("ai_query_log.field.confidence"),
    )

    # ==================== 索引 ==================== / Indexes

    __table_args__ = (
        # 企业 + 创建时间复合索引 / tenant + created_at
        Index("idx_ai_query_logs_tenant_created", "tenant_id", "created_at"),
        # 操作者 + 创建时间复合索引 / user + created_at
        Index("idx_ai_query_logs_user_created", "user_id", "created_at"),
        # 状态 + 创建时间复合索引 / status + created_at
        Index("idx_ai_query_logs_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AIQueryLog(id={self.id}, tenant_id={self.tenant_id}, "
            f"user_id={self.user_id}, status={self.status})>"
        )


__all__ = ["AIQueryLog"]
