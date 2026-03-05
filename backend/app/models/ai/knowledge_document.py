"""
知识文档模型

定义文档的文件信息、处理状态、统计数据等
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.deletion import DeletionDep, DeletionStrategy
from app.core.i18n import _
from app.enums.knowledge_base import DocumentStatusEnum, DocumentTypeEnum


class KnowledgeDocument(TenantModel):
    """
    知识文档模型

    存储文档的文件信息、处理状态机、统计数据等
    属于租户级资源，通过 tenant_id 隔离（全局/管理端 KB 的文档 tenant_id 为 NULL）

    状态机流转：
    pending → parsing → chunking → embedding → completed
                 ↓         ↓           ↓
               error     error       error
    """

    __tablename__ = "knowledge_documents"

    __delete_deps__ = [
        DeletionDep("DocumentChunk", "document_id", DeletionStrategy.CASCADE_DELETE,
                    label_field="id", i18n_key="document_chunk"),
    ]

    # 覆盖 TenantModel 的 tenant_id：允许 NULL（全局/管理端 KB 文档无租户归属）
    tenant_id = Column(Integer, nullable=True, index=True, comment="租户ID")

    # 允许前端筛选的字段
    __filterable__ = {
        "id": "id",
        "knowledge_base_id": "knowledge_base_id",
        "file_name": "file_name",
        "file_type": "file_type",
        "status": "status",
        "tenant_id": "tenant_id",
        "created_at": "created_at",
    }

    # 允许排序的字段
    __sortable__ = {
        "id": "id",
        "file_name": "file_name",
        "file_size": "file_size",
        "chunk_count": "chunk_count",
        "status": "status",
        "created_at": "created_at",
        "updated_at": "updated_at",
    }

    # ==================== 关联 ====================

    knowledge_base_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("knowledge_base.document_model.knowledge_base_id"),
    )
    attachment_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("attachments.id", ondelete="SET NULL"),
        nullable=True,
        comment=_("knowledge_base.document_model.attachment_id"),
    )

    # ==================== 文件信息 ====================

    file_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment=_("knowledge_base.document_model.file_name"),
    )
    file_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DocumentTypeEnum.TXT.value,
        comment=_("knowledge_base.document_model.file_type"),
    )
    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("knowledge_base.document_model.file_size"),
    )
    file_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment=_("knowledge_base.document_model.file_hash"),
    )

    # ==================== 文档来源元数据 ====================

    source_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("knowledge_base.document_model.source_url"),
    )
    metadata_extra: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("knowledge_base.document_model.metadata_extra"),
    )

    # ==================== 处理状态 ====================

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=DocumentStatusEnum.PENDING.value,
        index=True,
        comment=_("knowledge_base.document_model.status"),
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=_("knowledge_base.document_model.error_message"),
    )
    error_stage: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment=_("knowledge_base.document_model.error_stage"),
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("knowledge_base.document_model.retry_count"),
    )

    # ==================== 统计 ====================

    chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("knowledge_base.document_model.chunk_count"),
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("knowledge_base.document_model.token_count"),
    )
    char_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("knowledge_base.document_model.char_count"),
    )

    # ==================== 处理时间 ====================

    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment=_("knowledge_base.document_model.processing_started_at"),
    )
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment=_("knowledge_base.document_model.processing_completed_at"),
    )

    # ==================== 复合索引 ====================

    __table_args__ = (
        Index("ix_doc_kb_status", "knowledge_base_id", "status"),
        UniqueConstraint(
            "knowledge_base_id", "file_hash",
            name="uq_doc_kb_hash",
        ),
    )

    # ==================== 关系 ====================

    knowledge_base = relationship(
        "KnowledgeBase",
        back_populates="documents",
        lazy="selectin",
    )

    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<KnowledgeDocument(id={self.id}, file_name={self.file_name}, "
            f"status={self.status}, tenant_id={self.tenant_id})>"
        )


if TYPE_CHECKING:
    pass


__all__ = ["KnowledgeDocument"]
