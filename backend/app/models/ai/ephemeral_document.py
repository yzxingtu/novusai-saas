"""
Ephemeral document model / 临时资料文档模型
"""

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel
from app.enums.knowledge_base import EphemeralDocScopeEnum, EphemeralDocStatusEnum


class EphemeralDocument(TenantModel):
    __tablename__ = "ephemeral_documents"

    conversation_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Conversation ID / 会话 ID",
    )
    agent_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Agent ID / 智能体 ID",
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Operator user ID / 操作用户 ID",
    )
    scope_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=EphemeralDocScopeEnum.CONVERSATION_SCOPED.value,
        index=True,
        comment="Ephemeral scope type / 临时资料作用域类型",
    )
    scope_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Ephemeral scope key / 临时资料作用域键",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Ephemeral Document",
        comment="Display title / 展示标题",
    )
    content_kind: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="text",
        comment="Content kind / 内容类型",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Ephemeral raw content / 临时资料原始内容",
    )
    content_hash: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment="Content hash / 内容哈希",
    )
    source_ref: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Source reference / 来源引用",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=EphemeralDocStatusEnum.ACTIVE.value,
        index=True,
        comment="Document status / 文档状态",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
        comment="Expiration time / 过期时间",
    )
    promoted_knowledge_base_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Promoted knowledge base ID / 提升后的知识库 ID",
    )
    promoted_document_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Promoted formal document ID / 提升后的正式文档 ID",
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="Last used at / 最近使用时间",
    )
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        comment="Additional metadata / 扩展元数据",
    )

    __table_args__ = (
        Index(
            "idx_ephemeral_documents_scope_hash",
            "tenant_id",
            "scope_type",
            "scope_key",
            "content_hash",
            unique=True,
        ),
    )


__all__ = ["EphemeralDocument"]
