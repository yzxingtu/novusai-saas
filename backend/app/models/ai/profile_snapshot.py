"""
Profile snapshot model / 画像快照模型
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import TenantModel
from app.enums.memory import MemoryScopeTypeEnum


class ProfileSnapshot(TenantModel):
    """
    Derived profile snapshot for long-term memory injection / 长期记忆注入用派生画像快照。

    This is not the source of truth. Source records remain in MemoryRecord.
    这不是记忆真源，真源仍然是 MemoryRecord。
    """

    __tablename__ = "profile_snapshots"

    __filterable__ = {
        "id": "id",
        "tenant_id": "tenant_id",
        "agent_id": "agent_id",
        "user_id": "user_id",
        "scope_type": "scope_type",
        "scope_key": "scope_key",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    __sortable__ = {
        "id": "id",
        "created_at": "created_at",
        "updated_at": "updated_at",
        "record_count": "record_count",
        "source_updated_at": "source_updated_at",
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
        comment="Snapshot scope type / 快照作用域类型",
    )

    scope_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Snapshot scope key / 快照作用域键",
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Compact profile summary / 紧凑画像摘要",
    )

    profile_json: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Structured profile payload / 结构化画像载荷",
    )

    record_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Source memory record count / 来源记忆记录数",
    )

    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="Latest source record update time / 最近来源记录更新时间",
    )

    metadata_: Mapped[dict | None] = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        comment="Additional metadata / 扩展元数据",
    )

    __table_args__ = (
        Index(
            "idx_profile_snapshots_scope_unique",
            "tenant_id",
            "scope_type",
            "scope_key",
            unique=True,
        ),
    )


__all__ = ["ProfileSnapshot"]
