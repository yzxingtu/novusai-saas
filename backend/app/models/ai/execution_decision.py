"""
Execution decision model / 执行决策模型
"""

from sqlalchemy import Boolean, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel


class ExecutionDecision(TenantModel):
    __tablename__ = "execution_decisions"

    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "conversation_id": "conversation_id",
        "agent_id": "agent_id",
        "operator_id": "operator_id",
        "operator_type": "operator_type",
        "decision_type": "decision_type",
        "subject_type": "subject_type",
        "status": "status",
        "decision_scope": "decision_scope",
        "tool_name": "tool_name",
        "action_name": "action_name",
        "created_at": "created_at",
    }

    __sortable__ = {
        "id": "id",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    conversation_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    agent_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    operator_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    operator_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    decision_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    subject_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    decision_scope: Mapped[str] = mapped_column(String(30), nullable=False, default="once")
    risk_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    auto_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tool_call_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    action_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    table_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    correlation_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index(
            "uq_execution_decisions_tenant_correlation",
            "tenant_id",
            "correlation_key",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ExecutionDecision(id={self.id}, tenant_id={self.tenant_id}, "
            f"decision_type={self.decision_type}, status={self.status})>"
        )


__all__ = ["ExecutionDecision"]
