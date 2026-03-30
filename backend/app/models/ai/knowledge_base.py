"""
知识库模型 / Knowledge Base Model

定义知识库的基本信息、Embedding 配置、分块配置、检索配置等
Defines knowledge base basic info, embedding config, chunking config, retrieval config, etc.
"""

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.core.base_model import BaseModel
from app.core.deletion import DeletionDep, DeletionStrategy
from app.core.i18n import _
from app.enums.common import ResourceScopeEnum
from app.enums.knowledge_base import (
    ChunkStrategyEnum,
    KBStatusEnum,
    SearchModeEnum,
)


class KnowledgeBase(BaseModel):
    """
    知识库模型 / Knowledge base model.

    投放范围由 ResourceScopeEnum + owner_tenant_id + resource_tenant_assignments 表达；
    TenantRepository 仍通过 tenant_id 键注入/过滤，映射到 owner_tenant_id 列。
    """

    __tablename__ = "knowledge_bases"

    __ai_policy__ = {
        "label": "知识库",
        "keywords": ["知识库", "knowledge", "知识"],
        "allow_read": True,
    }

    __delete_deps__ = [
        DeletionDep("AgentKnowledgeBaseBinding", "knowledge_base_id", DeletionStrategy.CASCADE_DELETE,
                    label_field="id", i18n_key="agent_kb_binding"),
        DeletionDep("KnowledgeDocument", "knowledge_base_id", DeletionStrategy.CASCADE_SOFT,
                    label_field="name", i18n_key="knowledge_document"),
    ]

    owner_tenant_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
        comment="归属企业ID（平台级知识库为 NULL）",
    )
    tenant_id = synonym("owner_tenant_id")

    __filterable__ = {
        "id": "id",
        "name": "name",
        "status": "status",
        "scope": "scope",
        "embedding_model_id": "embedding_model_id",
        "vision_model_id": "vision_model_id",
        "audio_model_id": "audio_model_id",
        "video_model_id": "video_model_id",
        "owner_tenant_id": "owner_tenant_id",
        "tenant_id": "owner_tenant_id",
        "created_at": "created_at",
    }

    __sortable__ = {
        "id": "id",
        "name": "name",
        "status": "status",
        "document_count": "document_count",
        "total_chunks": "total_chunks",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    scope: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default=ResourceScopeEnum.ALL_TENANTS.value,
        index=True,
        comment=_("knowledge_base.model.scope"),
    )

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

    vision_model_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("ai_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment=_("knowledge_base.model.vision_model_id"),
    )
    extract_images: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment=_("knowledge_base.model.extract_images"),
    )

    audio_model_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("ai_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment=_("knowledge_base.model.audio_model_id"),
    )
    video_model_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("ai_models.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment=_("knowledge_base.model.video_model_id"),
    )

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

    search_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SearchModeEnum.HYBRID.value,
        comment="KB-level default; Agent.rag_config.search_mode overrides at runtime",
    )
    top_k: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
        comment="KB-level default; Agent.rag_config.top_k overrides at runtime",
    )
    score_threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
        comment="KB-level default; Agent.rag_config.score_threshold overrides at runtime",
    )

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

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=KBStatusEnum.ACTIVE.value,
        index=True,
        comment=_("knowledge_base.model.status"),
    )

    __table_args__ = (
        Index("ix_kb_owner_status", "owner_tenant_id", "status"),
    )

    embedding_model = relationship(
        "AIModel",
        foreign_keys=[embedding_model_id],
        lazy="selectin",
    )

    vision_model = relationship(
        "AIModel",
        foreign_keys=[vision_model_id],
        lazy="selectin",
    )

    audio_model = relationship(
        "AIModel",
        foreign_keys=[audio_model_id],
        lazy="selectin",
    )
    video_model = relationship(
        "AIModel",
        foreign_keys=[video_model_id],
        lazy="selectin",
    )

    documents = relationship(
        "KnowledgeDocument",
        back_populates="knowledge_base",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBase(id={self.id}, name={self.name}, owner_tenant_id={self.owner_tenant_id})>"


if TYPE_CHECKING:
    pass


__all__ = ["KnowledgeBase"]
