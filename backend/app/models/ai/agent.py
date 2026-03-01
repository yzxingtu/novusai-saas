"""
智能体模型

定义智能体的基本信息、模型配置、工具绑定等
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, Float, ForeignKey, Index, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.deletion import DeletionDep, DeletionStrategy
from app.core.i18n import _
from app.enums.agent import AgentStatusEnum, AgentExecutionModeEnum, AgentVisibilityEnum
from app.enums.common import ResourceScopeEnum


class Agent(TenantModel):
    """
    智能体模型

    存储智能体配置，包括系统提示词、关联 AI 模型、参数设置、工具绑定等
    属于租户级资源，通过 tenant_id 隔离
    """

    __tablename__ = "agents"

    __delete_deps__ = [
        DeletionDep("AgentSkillBinding", "agent_id", DeletionStrategy.CASCADE_DELETE,
                    label_field="id", i18n_key="agent_skill_binding"),
        DeletionDep("AgentConversation", "agent_id", DeletionStrategy.CASCADE_SOFT,
                    label_field="id", i18n_key="agent_conversation"),
        DeletionDep("BatchRun", "agent_id", DeletionStrategy.CASCADE_SOFT,
                    label_field="id", i18n_key="batch_run"),
        DeletionDep("SystemAgentAssignment", "agent_id", DeletionStrategy.NULLIFY,
                    label_field="id", i18n_key="system_agent_assignment"),
    ]

    # 覆盖 TenantModel 的 tenant_id，改为可选（scope=global/admin 时为 NULL）
    tenant_id = Column(
        Integer,
        nullable=True,
        index=True,
        comment="租户ID（scope=tenant 时必填，global/admin 时为 NULL）"
    )

    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "name": "name",
        "status": "status",
        "scope": "scope",
        "visibility": "visibility",
        "execution_mode": "execution_mode",
        "model_id": "model_id",
        "tenant_id": "tenant_id",
        "is_system": "is_system",
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

    # ==================== 作用域 ====================

    scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ResourceScopeEnum.ALL_TENANTS.value,
        index=True,
        comment=_("enum.agent_model.scope"),
    )

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

    # ==================== 多模型路由配置 ====================

    routing_config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("enum.agent_model.routing_config"),
    )

    # ==================== 变量 ====================

    input_variables: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment=_("enum.agent_model.input_variables"),
    )

    # ==================== 知识库（RAG）配置 [DEPRECATED] ====================
    # 已废弃：知识库绑定已迁移到技能包机制（SkillPackage → Skill[knowledge_base]）
    # 运行时 knowledge_base_ids 来自 SkillResolver + 用户 @ 选择，不再读取此字段
    # 保留列以兼容旧数据，后续可通过迁移删除

    knowledge_base_ids: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="[DEPRECATED] " + _("enum.agent_model.knowledge_base_ids"),
    )
    rag_config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="[DEPRECATED] " + _("enum.agent_model.rag_config"),
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

    # ==================== 系统标记 ====================

    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment=_("enum.agent_model.is_system"),
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

    # 技能绑定（新 Skill 架构）
    skill_bindings = relationship(
        "AgentSkillBinding",
        lazy="noload",
        cascade="all, delete-orphan",
        order_by="AgentSkillBinding.sort_order",
    )

    def __repr__(self) -> str:
        return f"<Agent(id={self.id}, name={self.name}, tenant_id={self.tenant_id})>"


if TYPE_CHECKING:
    from app.models.ai.model import AIModel
    from app.models.ai.agent_conversation import AgentConversation
    from app.models.ai.agent_skill_binding import AgentSkillBinding


__all__ = ["Agent"]
