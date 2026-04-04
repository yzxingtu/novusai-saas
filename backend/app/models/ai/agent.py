"""
智能体模型 / Agent Model

定义智能体的基本信息、模型配置、工具绑定等
Defines agent basic info, model configuration, tool bindings, etc.
"""

from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel
from app.core.deletion import DeletionDep, DeletionStrategy
from app.core.i18n import _
from app.enums.agent import (
    AgentExecutionModeEnum,
    AgentStatusEnum,
    AgentVisibilityEnum,
)
from app.enums.common import ResourceScopeEnum


class Agent(BaseModel):
    """
    智能体模型 / Agent model.

    存储智能体配置，包括系统提示词、关联 AI 模型、参数设置、工具绑定等
    平台级与企业级资源通过 owner_tenant_id + scope 表达归属与投放范围
    """

    __tablename__ = "agents"

    __ai_policy__ = {
        "label": "智能体",
        "keywords": ["智能体", "agent", "机器人", "bot", "助手"],
        "allow_read": True,
    }

    __delete_deps__ = [
        DeletionDep(
            "AgentAccess",
            "agent_id",
            DeletionStrategy.CASCADE_DELETE,
            label_field="id",
            i18n_key="agent_access",
        ),
        DeletionDep(
            "TenantAgentPublication",
            "agent_id",
            DeletionStrategy.CASCADE_DELETE,
            label_field="id",
            i18n_key="agent_access",
        ),
        DeletionDep(
            "AgentVersion",
            "agent_id",
            DeletionStrategy.CASCADE_DELETE,
            label_field="id",
            i18n_key="agent_version",
        ),
        DeletionDep(
            "AgentSkillGrant",
            "agent_id",
            DeletionStrategy.CASCADE_DELETE,
            label_field="id",
            i18n_key="agent_skill_grant",
        ),
        DeletionDep(
            "AgentKnowledgeBaseBinding",
            "agent_id",
            DeletionStrategy.CASCADE_DELETE,
            label_field="id",
            i18n_key="agent_kb_binding",
        ),
        DeletionDep(
            "AgentConversation",
            "agent_id",
            DeletionStrategy.CASCADE_SOFT,
            label_field="id",
            i18n_key="agent_conversation",
        ),
        DeletionDep(
            "BatchRun",
            "agent_id",
            DeletionStrategy.CASCADE_SOFT,
            label_field="id",
            i18n_key="batch_run",
        ),
        DeletionDep(
            "SystemAgentAssignment",
            "agent_id",
            DeletionStrategy.NULLIFY,
            label_field="id",
            i18n_key="system_agent_assignment",
        ),
    ]

    # 覆盖 TenantModel.tenant_id：使用 owner_tenant_id 表示资源归属企业（平台级为 NULL）
    owner_tenant_id = Column(
        Integer,
        nullable=True,
        index=True,
        comment="归属企业ID（平台级智能体为 NULL，企业自有智能体为所属企业）",
    )

    # 允许前端筛选的字段 / Fields exposed for list filtering
    __filterable__ = {
        "id": "id",
        "name": "name",
        "status": "status",
        "scope": "scope",
        "source_plugin": "source_plugin",
        "visibility": "visibility",
        "execution_mode": "execution_mode",
        "model_id": "model_id",
        "owner_tenant_id": "owner_tenant_id",
        "is_system": "is_system",
        "created_at": "created_at",
    }

    __selectable__ = {
        "label": "name",
        "value": "id",
        "search": ["name", "description"],
        "extra": ["avatar", "scope"],
    }

    # 允许排序的字段 / Sortable columns for UI
    __sortable__ = {
        "id": "id",
        "name": "name",
        "status": "status",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    scope: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=ResourceScopeEnum.ALL_TENANTS.value,
        index=True,
        comment="资源作用域 ResourceScopeEnum（五类）/ Resource scope",
    )
    source_plugin: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="来源插件 slug（插件托管智能体）/ Source plugin slug",
    )

    # ==================== 基本信息 ==================== / Basic info

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

    # ==================== 模型配置 ==================== / Model parameters

    # 关联 AI 模型 / Linked AI model
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

    # ==================== 状态与模式 ==================== / Status and mode

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

    # ==================== 配额配置 ==================== / Quota config

    quota_config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("enum.agent_model.quota_config"),
    )

    # ==================== 多模型路由配置 ==================== / Multi-model routing

    routing_config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("enum.agent_model.routing_config"),
    )

    # ==================== 会话记忆配置 ==================== / Session memory

    memory_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment=_("enum.agent_model.memory_enabled"),
    )

    # ==================== 变量 ==================== / Variables

    input_variables: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment=_("enum.agent_model.input_variables"),
    )

    # ==================== 知识库（RAG）配置 ==================== / Knowledge (RAG)
    # 知识库绑定通过 AgentKnowledgeBaseBinding 中间表管理 / Bindings via join table
    # rag_config 为 Agent 级统一 RAG 配置 / Agent-level RAG JSON

    rag_config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment=_("enum.agent_model.rag_config"),
    )

    # ==================== 上下文配置 ==================== / Context config

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

    # ==================== 系统标记 ==================== / System flags

    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment=_("enum.agent_model.is_system"),
    )

    # ==================== 交互配置 ==================== / Interaction defaults

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

    # ==================== 复合索引 ==================== / Composite indexes

    __table_args__ = (
        Index("ix_agents_owner_tenant_status", "owner_tenant_id", "status"),
    )

    # ==================== 关系 ==================== / Relationships

    # 关联的 AI 模型 / Linked AIModel row
    model = relationship(
        "AIModel",
        lazy="selectin",
    )

    # 关联的对话列表 / Conversations for this agent
    conversations = relationship(
        "AgentConversation",
        back_populates="agent",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    # 技能授权（Direct Skill Grants） / Direct skill grants
    skill_grants = relationship(
        "AgentSkillGrant",
        back_populates="agent",
        lazy="noload",
        cascade="all, delete-orphan",
        order_by="AgentSkillGrant.sort_order",
    )

    # 知识库绑定 / Knowledge base bindings
    kb_bindings = relationship(
        "AgentKnowledgeBaseBinding",
        lazy="noload",
        cascade="all, delete-orphan",
        order_by="AgentKnowledgeBaseBinding.sort_order",
    )

    def __repr__(self) -> str:
        return f"<Agent(id={self.id}, name={self.name}, owner_tenant_id={self.owner_tenant_id})>"


if TYPE_CHECKING:
    pass


__all__ = ["Agent"]
