"""
文档分块模型 / Document Chunk Model

定义分块文本内容、向量、元数据等，包含 pgvector 向量字段和 HNSW 索引
Defines chunk text content, vectors, metadata, with pgvector vector fields and HNSW indexes.
"""

from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSON, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import TenantModel
from app.core.i18n import _


class DocumentChunk(TenantModel):
    """
    文档分块模型 / Document chunk model.

    存储分块文本内容、Embedding 向量、元数据等
    属于企业级资源，通过 tenant_id 隔离

    向量索引使用 HNSW（在 Alembic 迁移中手动创建）：
    - 适合增量写入场景
    - 写入后立即可查
    - 查询性能 O(log n)
    """

    __tablename__ = "document_chunks"

    # 覆盖 TenantModel 的 tenant_id：允许 NULL（全局/管理端 KB 分块无企业归属）
    tenant_id = Column(Integer, nullable=True, index=True, comment="企业ID")

    # 允许前端筛选的字段 / Fields exposed for list filtering
    __filterable__ = {
        "id": "id",
        "document_id": "document_id",
        "knowledge_base_id": "knowledge_base_id",
        "chunk_index": "chunk_index",
        "tenant_id": "tenant_id",
    }

    # 允许排序的字段 / Sortable columns for UI
    __sortable__ = {
        "id": "id",
        "chunk_index": "chunk_index",
        "char_count": "char_count",
        "token_count": "token_count",
        "created_at": "created_at",
    }

    # ==================== 关联 ==================== / Associations

    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("knowledge_base.chunk_model.document_id"),
    )
    knowledge_base_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment=_("knowledge_base.chunk_model.knowledge_base_id"),
    )

    # ==================== 分块内容 ==================== / Chunk payload

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment=_("knowledge_base.chunk_model.chunk_index"),
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment=_("knowledge_base.chunk_model.content"),
    )
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment=_("knowledge_base.chunk_model.content_hash"),
    )
    char_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("knowledge_base.chunk_model.char_count"),
    )
    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment=_("knowledge_base.chunk_model.token_count"),
    )

    # ==================== 向量 ==================== / Embeddings

    # pgvector 向量字段，不固定维度以支持不同 embedding 模型 /
    # pgvector column; dimension from KB embedding settings
    # 实际维度由知识库 embedding_dimensions 决定
    embedding = mapped_column(
        Vector(),
        nullable=True,
        comment=_("knowledge_base.chunk_model.embedding"),
    )

    # ==================== 全文检索 ==================== / Full-text search

    # tsvector 列，由 DB trigger trg_document_chunks_tsv 自动维护 /
    # tsvector maintained by trigger
    # 用于 KeywordSearcher 全文检索 / Used by KeywordSearcher
    content_tsv = mapped_column(
        TSVECTOR,
        nullable=True,
    )

    # ==================== 元数据 ==================== / Chunk metadata

    # 结构化存储来源信息: page, heading, source, paragraph, row_index 等 /
    # Structured provenance (page, heading, ...)
    metadata_ = mapped_column(
        "metadata",
        JSON,
        nullable=True,
        default=dict,
        comment=_("knowledge_base.chunk_model.metadata"),
    )

    # ==================== 复合索引 ==================== / Composite indexes

    __table_args__ = (
        UniqueConstraint(
            "document_id", "chunk_index",
            name="uq_doc_chunk_index",
        ),
        Index("ix_chunk_kb", "knowledge_base_id"),
        # HNSW 向量索引和 tsvector GIN 索引在 Alembic 迁移中通过 raw SQL 创建 /
        # HNSW/GIN indexes created in Alembic migrations
    )

    # ==================== 关系 ==================== / Relationships

    document = relationship(
        "KnowledgeDocument",
        back_populates="chunks",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk(id={self.id}, document_id={self.document_id}, "
            f"chunk_index={self.chunk_index}, tenant_id={self.tenant_id})>"
        )


if TYPE_CHECKING:
    pass


__all__ = ["DocumentChunk"]
