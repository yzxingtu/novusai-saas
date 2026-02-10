"""
智能体模型

定义智能体的基本信息、模型配置、工具绑定等
"""

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.i18n import _
from app.enums.agent import AgentStatusEnum, AgentExecutionModeEnum, AgentVisibilityEnum


class Agent(TenantModel):
    """
    智能体模型

    存储智能体配置，包括系统提示词、关联 AI 模型、参数设置、工具绑定等
    属于租户级资源，通过 tenant_id 隔离
    """

    __tablename__ = "agents"

    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "name": "name",
        "status": "status",
        "visibility": "visibility",
        "execution_mode": "execution_mode",
        "model_id": "model_id",
        "tenant_id": "tenant_id",
        "created_at": "created_at",
    }

    # 允许排序的字段
    __sortable__ = {
        "id": "id",
        "name": "name",
        "status": "status",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    # ==================== 基本信息 ====================

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment=_("enum.agent_model.name"),
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("enum.agent_model.description"),
    )
    avatar: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment=_("enum.agent_model.avatar"),
    )

    # ==================== 模型配置 ====================

    # 关联 AI 模型
    model_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_models.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment=_("enum.agent_model.model_id"),
    )
    system_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment=_("enum.agent_model.system_prompt"),
    )
    temperature: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.7,
        comment=_("enum.agent_model.temperature"),
    )
    max_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("enum.agent_model.max_tokens"),
    )
    top_p: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment=_("enum.agent_model.top_p"),
    )

    # ==================== 状态与模式 ====================

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AgentStatusEnum.DRAFT.value,
        index=True,
        comment=_("enum.agent_model.status"),
    )
    execution_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AgentExecutionModeEnum.CONVERSATION.value,
        comment=_("enum.agent_model.execution_mode"),
    )
    published_version: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("enum.agent_model.published_version"),
    )
    visibility: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AgentVisibilityEnum.PUBLIC.value,
        index=True,
        comment=_("enum.agent_model.visibility"),
    )

    # ==================== 配额配置 ====================

    quota_config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("enum.agent_model.quota_config"),
    )

    # ==================== 工具与变量 ====================

    tool_bindings: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment=_("enum.agent_model.tool_bindings"),
    )
    input_variables: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment=_("enum.agent_model.input_variables"),
    )

    # ==================== 上下文配置 ====================

    context_config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("enum.agent_model.context_config"),
    )
    output_schema: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("enum.agent_model.output_schema"),
    )

    # ==================== 交互配置 ====================

    welcome_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("enum.agent_model.welcome_message"),
    )
    suggested_questions: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment=_("enum.agent_model.suggested_questions"),
    )

    # ==================== 复合索引 ====================

    __table_args__ = (
        Index("ix_agents_tenant_status", "tenant_id", "status"),
    )

    # ==================== 关系 ====================

    # 关联的 AI 模型
    model = relationship(
        "AIModel",
        lazy="selectin",
    )

    # 关联的对话列表
    conversations = relationship(
        "AgentConversation",
        back_populates="agent",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Agent(id={self.id}, name={self.name}, tenant_id={self.tenant_id})>"


if TYPE_CHECKING:
    from app.models.ai.model import AIModel
    from app.models.ai.agent_conversation import AgentConversation


__all__ = ["Agent"]
