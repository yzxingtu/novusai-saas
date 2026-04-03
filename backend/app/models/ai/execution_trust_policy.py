"""
Execution trust policy model / 执行信任策略模型
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel


class ExecutionTrustPolicy(TenantModel):
    """
    Execution trust policy / 执行信任策略。

    Stores server-side trust grants for conversation/operator/tool-family scoped
    auto-approval semantics. / 存储 conversation/operator/tool-family 级服务端信任授权。
    """

    __tablename__ = "execution_trust_policies"

    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "conversation_id": "conversation_id",
        "agent_id": "agent_id",
        "operator_id": "operator_id",
        "operator_type": "operator_type",
        "tool_family": "tool_family",
        "is_active": "is_active",
        "expires_at": "expires_at",
        "created_at": "created_at",
    }

    __sortable__ = {
        "id": "id",
        "created_at": "created_at",
        "updated_at": "updated_at",
        "expires_at": "expires_at",
    }

    conversation_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Conversation scope / 对话作用域",
    )

    agent_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Agent scope / 智能体作用域",
    )

    operator_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Operator ID / 操作者 ID",
    )

    operator_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Operator type / 操作者类型",
    )

    tool_family: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Tool family / 工具族",
    )

    allowed_tool_names: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Allowed tool names / 允许的工具名列表",
    )

    risk_level_cap: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Highest auto-approved action level / 自动批准的最高风险级别",
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
        comment="Expiration timestamp / 过期时间",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether the trust policy is active / 策略是否生效",
    )

    granted_by: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Grantor user ID / 授权人用户 ID",
    )

    grant_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Grant reason / 授权原因",
    )

    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        comment="Additional trust metadata / 扩展信任元数据",
    )

    __table_args__ = (
        Index(
            "idx_exec_trust_scope",
            "tenant_id",
            "conversation_id",
            "agent_id",
            "operator_id",
            "is_active",
        ),
        Index(
            "idx_exec_trust_operator_family",
            "tenant_id",
            "operator_type",
            "operator_id",
            "tool_family",
            "is_active",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ExecutionTrustPolicy(id={self.id}, tenant_id={self.tenant_id}, "
            f"conversation_id={self.conversation_id}, agent_id={self.agent_id})>"
        )


__all__ = ["ExecutionTrustPolicy"]
