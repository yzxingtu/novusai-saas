"""
智能体版本模型

存储智能体每次发布时的配置快照，支持历史查看和回滚
"""

from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.i18n import _


class AgentVersion(TenantModel):
    """
    智能体版本模型

    每次发布智能体时，将当前配置冻结为一条版本记录。
    支持版本历史查看、回滚、对比等操作。
    属于租户级资源，通过 tenant_id 隔离。
    """

    __tablename__ = "agent_versions"

    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "agent_id": "agent_id",
        "version": "version",
        "tenant_id": "tenant_id",
        "created_at": "created_at",
    }

    # 允许排序的字段
    __sortable__ = {
        "id": "id",
        "version": "version",
        "created_at": "created_at",
    }

    # ==================== 关联 ====================

    agent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("agent.version.field.agent_id"),
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment=_("agent.version.field.version"),
    )

    # ==================== 配置快照 ====================

    system_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment=_("agent.version.field.system_prompt"),
    )
    model_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_models.id", ondelete="RESTRICT"),
        nullable=False,
        comment=_("agent.version.field.model_id"),
    )
    temperature: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.7,
        comment=_("agent.version.field.temperature"),
    )
    max_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("agent.version.field.max_tokens"),
    )
    top_p: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment=_("agent.version.field.top_p"),
    )
    execution_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment=_("agent.version.field.execution_mode"),
    )
    tool_bindings: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment=_("agent.version.field.tool_bindings"),
    )
    input_variables: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment=_("agent.version.field.input_variables"),
    )
    welcome_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("agent.version.field.welcome_message"),
    )
    suggested_questions: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment=_("agent.version.field.suggested_questions"),
    )
    quota_config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("agent.version.field.quota_config"),
    )
    rag_config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("agent.version.field.rag_config"),
    )
    context_config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("agent.version.field.context_config"),
    )
    output_schema: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("agent.version.field.output_schema"),
    )

    # ==================== 版本元信息 ====================

    change_log: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("agent.version.field.change_log"),
    )
    created_by: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("agent.version.field.created_by"),
    )

    # ==================== 约束 ====================

    __table_args__ = (
        UniqueConstraint("agent_id", "version", name="uq_agent_version"),
        Index("ix_agent_versions_agent_version", "agent_id", "version"),
    )

    # ==================== 关系 ====================

    agent = relationship(
        "Agent",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<AgentVersion(id={self.id}, agent_id={self.agent_id}, version={self.version})>"


if TYPE_CHECKING:
    pass


__all__ = ["AgentVersion"]
