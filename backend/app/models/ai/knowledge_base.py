"""
知识库模型

定义知识库的基本信息、Embedding 配置、分块配置、检索配置等
"""

from typing import TYPE_CHECKING

from sqlalchemy import Column, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.deletion import DeletionDep, DeletionStrategy
from app.core.i18n import _
from app.enums.common import ResourceScopeEnum
from app.enums.knowledge_base import (
    ChunkStrategyEnum,
    KBStatusEnum,
    SearchModeEnum,
)


class KnowledgeBase(TenantModel):
    """
    知识库模型

    存储知识库配置，包括 Embedding 模型、分块策略、检索模式等
    属于租户级资源，通过 tenant_id 隔离
    """

    __tablename__ = "knowledge_bases"

    __delete_deps__ = [
        DeletionDep("KnowledgeDocument", "knowledge_base_id", DeletionStrategy.CASCADE_SOFT,
                    label_field="name", i18n_key="knowledge_document"),
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
        "embedding_model_id": "embedding_model_id",
        "tenant_id": "tenant_id",
        "created_at": "created_at",
    }

    # 允许排序的字段
    __sortable__ = {
        "id": "id",
        "name": "name",
        "status": "status",
        "document_count": "document_count",
        "total_chunks": "total_chunks",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    # ==================== 作用域 ====================

    scope: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ResourceScopeEnum.TENANT.value,
        index=True,
        comment=_("knowledge_base.model.scope"),
    )

    # ==================== 基本信息 ====================

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        comment=_("knowledge_base.model.name"),
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("knowledge_base.model.description"),
    )
    avatar: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment=_("knowledge_base.model.avatar"),
    )

    # ==================== Embedding 配置 ====================

    embedding_model_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("ai_models.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment=_("knowledge_base.model.embedding_model_id"),
    )
    embedding_dimensions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1536,
        comment=_("knowledge_base.model.embedding_dimensions"),
    )

    # ==================== 分块配置 ====================

    chunk_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=512,
        comment=_("knowledge_base.model.chunk_size"),
    )
    chunk_overlap: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
        comment=_("knowledge_base.model.chunk_overlap"),
    )
    chunk_strategy: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ChunkStrategyEnum.RECURSIVE.value,
        comment=_("knowledge_base.model.chunk_strategy"),
    )

    # ==================== 检索配置 ====================

    search_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SearchModeEnum.HYBRID.value,
        comment=_("knowledge_base.model.search_mode"),
    )
    top_k: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        comment=_("knowledge_base.model.top_k"),
    )
    score_threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
        comment=_("knowledge_base.model.score_threshold"),
    )

    # ==================== 统计 ====================

    document_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("knowledge_base.model.document_count"),
    )
    total_chunks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("knowledge_base.model.total_chunks"),
    )
    total_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("knowledge_base.model.total_size_bytes"),
    )

    # ==================== 状态 ====================

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=KBStatusEnum.ACTIVE.value,
        index=True,
        comment=_("knowledge_base.model.status"),
    )

    # ==================== 复合索引 ====================

    __table_args__ = (
        Index("ix_kb_tenant_status", "tenant_id", "status"),
    )

    # ==================== 关系 ====================

    # 关联的 Embedding 模型
    embedding_model = relationship(
        "AIModel",
        lazy="selectin",
    )

    # 关联的文档列表
    documents = relationship(
        "KnowledgeDocument",
        back_populates="knowledge_base",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBase(id={self.id}, name={self.name}, tenant_id={self.tenant_id})>"


if TYPE_CHECKING:
    from app.models.ai.model import AIModel
    from app.models.ai.knowledge_document import KnowledgeDocument


__all__ = ["KnowledgeBase"]
