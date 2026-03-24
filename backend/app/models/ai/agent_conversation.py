"""
智能体对话模型 / Agent Conversation Model

定义智能体对话记录，存储对话元信息和消息
Defines agent conversation records, stores conversation metadata and messages.
"""

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.deletion import DeletionDep, DeletionStrategy
from app.core.i18n import _
from app.enums.agent import (
    ConversationOwnerTypeEnum,
    ConversationStatusEnum,
)


class AgentConversation(TenantModel):
    """
    智能体对话模型 / Agent conversation model.

    存储对话的元信息（标题、状态、消耗统计）和消息内容
    初版消息以 JSON 数组存储，后续 M14-T18 将拆分为独立 ConversationMessage 模型
    """

    __tablename__ = "agent_conversations"

    __ai_policy__ = {
        "label": "对话记录",
        "keywords": ["对话", "conversation", "chat", "聊天"],
        "allow_read": True,
    }

    __delete_deps__ = [
        DeletionDep("ConversationMessage", "conversation_id", DeletionStrategy.CASCADE_DELETE,
                    label_field="id", i18n_key="conversation_message"),
    ]

    # 允许前端筛选的字段 / Fields exposed for list filtering
    __filterable__ = {
        "id": "id",
        "agent_id": "agent_id",
        "user_id": "user_id",
        "owner_type": "owner_type",
        "status": "status",
        "tenant_id": "tenant_id",
        "created_at": "created_at",
    }

    # 允许排序的字段 / Sortable columns for UI
    __sortable__ = {
        "id": "id",
        "created_at": "created_at",
        "updated_at": "updated_at",
        "token_count": "token_count",
    }

    # ==================== 关联 ==================== / Associations

    agent_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("enum.agent_conversation.agent_id"),
    )
    # 业务用户 ID，nullable 兼容匿名/API 调用 / Business user id (nullable for anon/API)
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment=_("enum.agent_conversation.user_id"),
    )
    owner_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ConversationOwnerTypeEnum.UNKNOWN.value,
        server_default=ConversationOwnerTypeEnum.UNKNOWN.value,
        index=True,
        comment="会话归属类型 / Conversation owner type",
    )

    # ==================== 基本信息 ==================== / Basic info

    title: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment=_("enum.agent_conversation.title"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ConversationStatusEnum.ACTIVE.value,
        index=True,
        comment=_("enum.agent_conversation.status"),
    )

    # ==================== 消息存储 ==================== / Message storage

    # [已废弃] 初版 JSON 存储，已迁移至 ConversationMessage 独立模型 /
    # Deprecated JSON blob; use ConversationMessage rows
    # 保留字段兼容旧数据，新消息通过 message_list relationship 访问 /
    # Legacy column; new code uses message_list
    messages: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment=_("enum.agent_conversation.messages"),
    )

    # 消息数量冗余计数（同步自 ConversationMessage 条数） / Denormalized message count
    message_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("enum.agent_conversation.message_count"),
    )

    # ==================== 消耗统计 ==================== / Usage totals

    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("enum.agent_conversation.token_count"),
    )
    # 冗余 Token 总计（累加每次执行的 total_tokens，与 token_count 一致更新） /
    # Denormalized token sum
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("enum.agent_conversation.total_tokens"),
    )
    cost: Mapped[float] = mapped_column(
        Numeric(12, 6),
        nullable=False,
        default=0,
        comment=_("enum.agent_conversation.cost"),
    )

    # ==================== 扩展 ==================== / Extensions

    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        comment=_("enum.agent_conversation.metadata"),
    )

    # ==================== 复合索引 ==================== / Composite indexes

    __table_args__ = (
        Index("ix_agent_conv_tenant_agent_user", "tenant_id", "agent_id", "user_id"),
        Index("ix_agent_conv_tenant_owner_user", "tenant_id", "owner_type", "user_id"),
    )

    # ==================== 关系 ==================== / Relationships

    agent = relationship(
        "Agent",
        back_populates="conversations",
        lazy="selectin",
    )

    # 独立消息列表（M14-T18） / ConversationMessage rows (M14-T18)
    message_list = relationship(
        "ConversationMessage",
        back_populates="conversation",
        lazy="noload",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.sequence",
    )

    def __repr__(self) -> str:
        return (
            f"<AgentConversation(id={self.id}, agent_id={self.agent_id}, "
            f"tenant_id={self.tenant_id}, owner_type={self.owner_type})>"
        )


if TYPE_CHECKING:
    pass


__all__ = ["AgentConversation"]
