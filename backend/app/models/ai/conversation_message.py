"""
对话消息模型

独立存储每条对话消息，支持结构化查询、索引和 function calling
"""

from typing import TYPE_CHECKING

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.i18n import _
from app.enums.agent import MessageRoleEnum


class ConversationMessage(TenantModel):
    """
    对话消息模型

    每条消息独立存储，属于某个 AgentConversation
    支持 system/user/assistant/tool 四种角色
    支持 function calling（tool_calls / tool_call_id）
    """

    __tablename__ = "conversation_messages"

    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "conversation_id": "conversation_id",
        "role": "role",
        "tenant_id": "tenant_id",
        "created_at": "created_at",
    }

    # 允许排序的字段
    __sortable__ = {
        "id": "id",
        "sequence": "sequence",
        "created_at": "created_at",
    }

    # ==================== 关联 ====================

    conversation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("agent_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("enum.conversation_message.conversation_id"),
    )

    # ==================== 消息内容 ====================

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=MessageRoleEnum.USER.value,
        index=True,
        comment=_("enum.conversation_message.role"),
    )
    content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("enum.conversation_message.content"),
    )
    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("enum.conversation_message.sequence"),
    )

    # ==================== Token 统计 ====================

    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("enum.conversation_message.token_count"),
    )

    # ==================== Function Calling ====================

    # assistant 发起的 tool_calls 请求（JSON 数组）
    tool_calls: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment=_("enum.conversation_message.tool_calls"),
    )
    # tool 角色的消息关联的 tool_call_id
    tool_call_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment=_("enum.conversation_message.tool_call_id"),
    )
    # 工具名称（tool 角色消息使用）
    tool_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment=_("enum.conversation_message.tool_name"),
    )

    # ==================== 性能指标 ====================

    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=_("enum.conversation_message.latency_ms"),
    )

    # ==================== 关联模型 ====================

    # 生成此消息使用的 AI 模型（仅 assistant 角色）
    model_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("ai_models.id", ondelete="SET NULL"),
        nullable=True,
        comment=_("enum.conversation_message.model_id"),
    )

    # ==================== 扩展 ====================

    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        comment=_("enum.conversation_message.metadata"),
    )

    # ==================== 复合索引 ====================

    __table_args__ = (
        Index("ix_conv_msg_conv_seq", "conversation_id", "sequence"),
        Index("ix_conv_msg_tenant_conv", "tenant_id", "conversation_id"),
    )

    # ==================== 关系 ====================

    conversation = relationship(
        "AgentConversation",
        back_populates="message_list",
        lazy="noload",
    )

    model = relationship(
        "AIModel",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ConversationMessage(id={self.id}, role={self.role}, conv={self.conversation_id})>"


if TYPE_CHECKING:
    pass


__all__ = ["ConversationMessage"]
