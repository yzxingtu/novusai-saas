"""
智能体知识库绑定模型

定义 Agent 与 KnowledgeBase 的多对多关系，支持权重和启用/禁用控制
"""

from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.i18n import _


class AgentKnowledgeBaseBinding(TenantModel):
    """
    智能体知识库绑定模型

    记录 Agent 与 KnowledgeBase 的 M:N 关系。
    每条记录表示一个 Agent 绑定了一个 KnowledgeBase，支持：
      - weight: 检索结果排序权重（0.1~2.0，默认 1.0）
      - enabled: 是否启用该绑定（可临时关闭而不解绑）
      - sort_order: 前端显示排序
    """

    __tablename__ = "agent_knowledge_base_bindings"

    # 覆盖 TenantModel 的 tenant_id，跟随 Agent 的 tenant_id
    tenant_id = Column(
        Integer,
        nullable=True,
        index=True,
        comment="租户ID（跟随 Agent 的 tenant_id）"
    )

    # ==================== 关联 ====================

    agent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("agent_kb_binding.field.agent_id"),
    )
    knowledge_base_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("agent_kb_binding.field.knowledge_base_id"),
    )

    # ==================== 绑定配置 ====================

    weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        comment=_("agent_kb_binding.field.weight"),
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment=_("agent_kb_binding.field.enabled"),
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("agent_kb_binding.field.sort_order"),
    )

    # ==================== 约束与索引 ====================

    __table_args__ = (
        UniqueConstraint(
            "agent_id", "knowledge_base_id",
            name="uq_agent_knowledge_base_binding",
        ),
        Index(
            "ix_agent_kb_bindings_agent_enabled",
            "agent_id", "enabled",
        ),
    )

    # ==================== 关系 ====================

    agent = relationship(
        "Agent",
        lazy="noload",
        overlaps="kb_bindings",
    )
    knowledge_base = relationship(
        "KnowledgeBase",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<AgentKBBinding(id={self.id}, agent_id={self.agent_id}, "
            f"kb_id={self.knowledge_base_id}, weight={self.weight}, "
            f"enabled={self.enabled})>"
        )


if TYPE_CHECKING:
    pass


__all__ = ["AgentKnowledgeBaseBinding"]
