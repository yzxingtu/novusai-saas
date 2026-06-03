"""
Long-term memory record model / 长期记忆记录模型
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel
from app.enums.memory import (
    MemoryScopeTypeEnum,
    MemorySourceKindEnum,
    MemoryStatusEnum,
    MemoryTypeEnum,
)


class MemoryRecord(TenantModel):
    """
    Long-term memory record / 长期记忆记录。

    Stores durable memory candidates and verified records scoped by tenant/user/agent.
    存储按 tenant/user/agent 作用域划分的长期记忆候选和已验证记录。
    """

    __tablename__ = "memory_records"

    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "agent_id": "agent_id",
        "user_id": "user_id",
        "scope_type": "scope_type",
        "scope_key": "scope_key",
        "memory_type": "memory_type",
        "status": "status",
        "created_at": "created_at",
        "updated_at": "updated_at",
        "expires_at": "expires_at",
    }

    __sortable__ = {
        "id": "id",
        "created_at": "created_at",
        "updated_at": "updated_at",
        "importance": "importance",
        "last_recalled_at": "last_recalled_at",
    }

    agent_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Associated agent ID / 关联智能体 ID",
    )

    user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Associated user ID / 关联用户 ID",
    )

    scope_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=MemoryScopeTypeEnum.USER_AGENT.value,
        index=True,
        comment="Memory scope type / 记忆作用域类型",
    )

    scope_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Scope key / 作用域键",
    )

    memory_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=MemoryTypeEnum.FACT.value,
        index=True,
        comment="Memory type / 记忆类型",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Canonical durable memory text / 规范长期记忆文本",
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Compact summary for injection / 注入用紧凑摘要",
    )

    keywords: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Keyword hints / 关键词提示",
    )

    content_hash: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
        comment="MD5 hash of content / 内容 MD5 哈希",
    )

    embedding_model_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="Embedding model ID used for this memory / 本条记忆使用的 embedding 模型 ID",
    )

    embedding_dimensions: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Embedding vector dimensions / 向量维度",
    )

    embedding = mapped_column(
        Vector(),
        nullable=True,
        comment="Durable memory embedding / 长期记忆向量",
    )

    confidence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=70,
        comment="Confidence 0-100 / 置信度 0-100",
    )

    importance: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
        comment="Importance 0-100 / 重要度 0-100",
    )

    source_kind: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=MemorySourceKindEnum.CONVERSATION_TURN.value,
        comment="Memory source kind / 记忆来源类型",
    )

    source_ref: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Source reference / 来源引用",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=MemoryStatusEnum.CANDIDATE.value,
        index=True,
        comment="Memory status / 记忆状态",
    )

    last_recalled_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="Last recalled timestamp / 最近召回时间",
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="Expiration timestamp / 过期时间",
    )

    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        comment="Additional metadata / 扩展元数据",
    )

    __table_args__ = (
        Index(
            "idx_memory_records_scope_lookup",
            "tenant_id",
            "scope_type",
            "scope_key",
            "status",
        ),
        Index(
            "idx_memory_records_scope_type_hash",
            "tenant_id",
            "scope_type",
            "scope_key",
            "memory_type",
            "content_hash",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<MemoryRecord(id={self.id}, tenant_id={self.tenant_id}, "
            f"scope_type={self.scope_type}, scope_key={self.scope_key})>"
        )


__all__ = ["MemoryRecord"]
