"""
知识库相关 Schema

定义知识库、文档、分块的请求和响应数据结构
"""

from datetime import datetime

from pydantic import Field

from app.core.base_schema import (
    BaseCreateSchema,
    BaseUpdateSchema,
    TenantResponseSchema,
)
from app.core.i18n import _

# ==================== 知识库 Schema ====================


class KnowledgeBaseCreate(BaseCreateSchema):
    """创建知识库请求"""

    name: str = Field(..., max_length=200, description=_("knowledge_base.model.name"))
    description: str | None = Field(None, description=_("knowledge_base.model.description"))
    avatar: str | None = Field(None, max_length=50, description=_("knowledge_base.model.avatar"))
    embedding_model_id: int = Field(..., description=_("knowledge_base.model.embedding_model_id"))
    vision_model_id: int | None = Field(None, description=_("knowledge_base.model.vision_model_id"))
    extract_images: bool = Field(False, description=_("knowledge_base.model.extract_images"))
    chunk_size: int = Field(512, ge=128, le=4096, description=_("knowledge_base.model.chunk_size"))
    chunk_overlap: int = Field(50, ge=0, description=_("knowledge_base.model.chunk_overlap"))
    chunk_strategy: str = Field("recursive", description=_("knowledge_base.model.chunk_strategy"))
    search_mode: str = Field("hybrid", description=_("knowledge_base.model.search_mode"))
    top_k: int = Field(5, ge=1, le=20, description=_("knowledge_base.model.top_k"))
    score_threshold: float = Field(0.5, ge=0.0, le=1.0, description=_("knowledge_base.model.score_threshold"))


class KnowledgeBaseUpdate(BaseUpdateSchema):
    """更新知识库请求"""

    name: str | None = Field(None, max_length=200, description=_("knowledge_base.model.name"))
    description: str | None = Field(None, description=_("knowledge_base.model.description"))
    avatar: str | None = Field(None, max_length=50, description=_("knowledge_base.model.avatar"))
    vision_model_id: int | None = Field(None, description=_("knowledge_base.model.vision_model_id"))
    extract_images: bool | None = Field(None, description=_("knowledge_base.model.extract_images"))
    chunk_size: int | None = Field(None, ge=128, le=4096, description=_("knowledge_base.model.chunk_size"))
    chunk_overlap: int | None = Field(None, ge=0, description=_("knowledge_base.model.chunk_overlap"))
    chunk_strategy: str | None = Field(None, description=_("knowledge_base.model.chunk_strategy"))
    search_mode: str | None = Field(None, description=_("knowledge_base.model.search_mode"))
    top_k: int | None = Field(None, ge=1, le=20, description=_("knowledge_base.model.top_k"))
    score_threshold: float | None = Field(None, ge=0.0, le=1.0, description=_("knowledge_base.model.score_threshold"))
    status: str | None = Field(None, description=_("knowledge_base.model.status"))


class AdminKnowledgeBaseCreate(BaseCreateSchema):
    """管理端创建知识库请求（支持 scope）"""

    name: str = Field(..., max_length=200, description=_("knowledge_base.model.name"))
    description: str | None = Field(None, description=_("knowledge_base.model.description"))
    avatar: str | None = Field(None, max_length=50, description=_("knowledge_base.model.avatar"))
    scope: str = Field("all_tenants", description=_("knowledge_base.model.scope"))
    visibility: str = Field("private", description=_("knowledge_base.model.visibility"))
    tenant_id: int | None = Field(None, description=_("knowledge_base.model.tenant_id"))
    assigned_tenant_ids: list[int] | None = Field(None, description=_("knowledge_base.model.assigned_tenant_ids"))
    tenant_ids: list[int] | None = Field(None, description=_("knowledge_base.model.tenant_ids"))
    embedding_model_id: int = Field(..., description=_("knowledge_base.model.embedding_model_id"))
    vision_model_id: int | None = Field(None, description=_("knowledge_base.model.vision_model_id"))
    extract_images: bool = Field(False, description=_("knowledge_base.model.extract_images"))
    chunk_size: int = Field(512, ge=128, le=4096, description=_("knowledge_base.model.chunk_size"))
    chunk_overlap: int = Field(50, ge=0, description=_("knowledge_base.model.chunk_overlap"))
    chunk_strategy: str = Field("recursive", description=_("knowledge_base.model.chunk_strategy"))
    search_mode: str = Field("hybrid", description=_("knowledge_base.model.search_mode"))
    top_k: int = Field(5, ge=1, le=20, description=_("knowledge_base.model.top_k"))
    score_threshold: float = Field(0.5, ge=0.0, le=1.0, description=_("knowledge_base.model.score_threshold"))


class AdminKnowledgeBaseUpdate(BaseUpdateSchema):
    """管理端更新知识库请求"""

    name: str | None = Field(None, max_length=200, description=_("knowledge_base.model.name"))
    description: str | None = Field(None, description=_("knowledge_base.model.description"))
    avatar: str | None = Field(None, max_length=50, description=_("knowledge_base.model.avatar"))
    scope: str | None = Field(None, description=_("knowledge_base.model.scope"))
    visibility: str | None = Field(None, description=_("knowledge_base.model.visibility"))
    tenant_id: int | None = Field(None, description=_("knowledge_base.model.tenant_id"))
    assigned_tenant_ids: list[int] | None = Field(None, description=_("knowledge_base.model.assigned_tenant_ids"))
    tenant_ids: list[int] | None = Field(None, description=_("knowledge_base.model.tenant_ids"))
    vision_model_id: int | None = Field(None, description=_("knowledge_base.model.vision_model_id"))
    extract_images: bool | None = Field(None, description=_("knowledge_base.model.extract_images"))
    chunk_size: int | None = Field(None, ge=128, le=4096, description=_("knowledge_base.model.chunk_size"))
    chunk_overlap: int | None = Field(None, ge=0, description=_("knowledge_base.model.chunk_overlap"))
    chunk_strategy: str | None = Field(None, description=_("knowledge_base.model.chunk_strategy"))
    search_mode: str | None = Field(None, description=_("knowledge_base.model.search_mode"))
    top_k: int | None = Field(None, ge=1, le=20, description=_("knowledge_base.model.top_k"))
    score_threshold: float | None = Field(None, ge=0.0, le=1.0, description=_("knowledge_base.model.score_threshold"))
    status: str | None = Field(None, description=_("knowledge_base.model.status"))


class KnowledgeBaseResponse(TenantResponseSchema):
    """知识库详情响应"""

    name: str = Field(..., description=_("knowledge_base.model.name"))
    description: str | None = Field(None, description=_("knowledge_base.model.description"))
    avatar: str | None = Field(None, description=_("knowledge_base.model.avatar"))
    embedding_model_id: int = Field(..., description=_("knowledge_base.model.embedding_model_id"))
    embedding_dimensions: int = Field(..., description=_("knowledge_base.model.embedding_dimensions"))
    chunk_size: int = Field(..., description=_("knowledge_base.model.chunk_size"))
    chunk_overlap: int = Field(..., description=_("knowledge_base.model.chunk_overlap"))
    chunk_strategy: str = Field(..., description=_("knowledge_base.model.chunk_strategy"))
    search_mode: str = Field(..., description=_("knowledge_base.model.search_mode"))
    top_k: int = Field(..., description=_("knowledge_base.model.top_k"))
    score_threshold: float = Field(..., description=_("knowledge_base.model.score_threshold"))
    vision_model_id: int | None = Field(None, description=_("knowledge_base.model.vision_model_id"))
    extract_images: bool = Field(False, description=_("knowledge_base.model.extract_images"))
    document_count: int = Field(..., description=_("knowledge_base.model.document_count"))
    total_chunks: int = Field(..., description=_("knowledge_base.model.total_chunks"))
    total_size_bytes: int = Field(..., description=_("knowledge_base.model.total_size_bytes"))
    status: str = Field(..., description=_("knowledge_base.model.status"))
    # 关联字段
    embedding_model_name: str | None = Field(None, description=_("knowledge_base.model.embedding_model_name"))
    vision_model_name: str | None = Field(None, description=_("knowledge_base.model.vision_model_name"))


class KnowledgeBaseListItem(TenantResponseSchema):
    """知识库列表项响应（精简字段）"""

    name: str = Field(..., description=_("knowledge_base.model.name"))
    description: str | None = Field(None, description=_("knowledge_base.model.description"))
    avatar: str | None = Field(None, description=_("knowledge_base.model.avatar"))
    status: str = Field(..., description=_("knowledge_base.model.status"))
    document_count: int = Field(..., description=_("knowledge_base.model.document_count"))
    total_chunks: int = Field(..., description=_("knowledge_base.model.total_chunks"))
    total_size_bytes: int = Field(..., description=_("knowledge_base.model.total_size_bytes"))
    embedding_model_name: str | None = Field(None, description=_("knowledge_base.model.embedding_model_name"))


# ==================== 文档 Schema ====================


class KnowledgeDocumentResponse(TenantResponseSchema):
    """知识文档响应"""

    knowledge_base_id: int = Field(..., description=_("knowledge_base.document_model.knowledge_base_id"))
    attachment_id: int | None = Field(None, description=_("knowledge_base.document_model.attachment_id"))
    file_name: str = Field(..., description=_("knowledge_base.document_model.file_name"))
    file_type: str = Field(..., description=_("knowledge_base.document_model.file_type"))
    file_size: int = Field(..., description=_("knowledge_base.document_model.file_size"))
    file_hash: str | None = Field(None, description=_("knowledge_base.document_model.file_hash"))
    source_url: str | None = Field(None, description=_("knowledge_base.document_model.source_url"))
    status: str = Field(..., description=_("knowledge_base.document_model.status"))
    error_message: str | None = Field(None, description=_("knowledge_base.document_model.error_message"))
    error_stage: str | None = Field(None, description=_("knowledge_base.document_model.error_stage"))
    retry_count: int = Field(..., description=_("knowledge_base.document_model.retry_count"))
    chunk_count: int = Field(..., description=_("knowledge_base.document_model.chunk_count"))
    token_count: int = Field(..., description=_("knowledge_base.document_model.token_count"))
    char_count: int = Field(..., description=_("knowledge_base.document_model.char_count"))
    processing_started_at: datetime | None = Field(None, description=_("knowledge_base.document_model.processing_started_at"))
    processing_completed_at: datetime | None = Field(None, description=_("knowledge_base.document_model.processing_completed_at"))


# ==================== 分块 Schema ====================


class DocumentChunkResponse(TenantResponseSchema):
    """文档分块响应"""

    document_id: int = Field(..., description=_("knowledge_base.chunk_model.document_id"))
    knowledge_base_id: int = Field(..., description=_("knowledge_base.chunk_model.knowledge_base_id"))
    chunk_index: int = Field(..., description=_("knowledge_base.chunk_model.chunk_index"))
    content: str = Field(..., description=_("knowledge_base.chunk_model.content"))
    char_count: int = Field(..., description=_("knowledge_base.chunk_model.char_count"))
    token_count: int = Field(..., description=_("knowledge_base.chunk_model.token_count"))
    metadata: dict | None = Field(None, alias="metadata_", description=_("knowledge_base.chunk_model.metadata"))


class DocumentChunkUpdate(BaseUpdateSchema):
    """编辑分块内容"""

    content: str = Field(..., description=_("knowledge_base.chunk_model.content"))


# ==================== 检索 Schema ====================


class QAPairCreate(BaseCreateSchema):
    """Q&A 问答对输入请求"""

    question: str = Field(
        ..., min_length=1, max_length=2000,
        description=_("knowledge_base.qa.question"),
    )
    answer: str = Field(
        ..., min_length=1, max_length=10000,
        description=_("knowledge_base.qa.answer"),
    )


class TextDocumentCreate(BaseCreateSchema):
    """直接文本输入请求"""

    title: str = Field(
        ..., min_length=1, max_length=200,
        description=_("knowledge_base.text.title"),
    )
    content: str = Field(
        ..., min_length=1, max_length=100000,
        description=_("knowledge_base.text.content"),
    )


class KnowledgeBaseSearchRequest(BaseCreateSchema):
    """检索测试请求"""

    query: str = Field(..., min_length=1, description=_("knowledge_base.search.query"))
    top_k: int = Field(5, ge=1, le=20, description=_("knowledge_base.model.top_k"))
    score_threshold: float = Field(0.5, ge=0.0, le=1.0, description=_("knowledge_base.model.score_threshold"))
    search_mode: str | None = Field(None, description=_("knowledge_base.model.search_mode"))


class ChunkSearchResult(BaseCreateSchema):
    """检索结果"""

    chunk_id: int = Field(..., description=_("knowledge_base.search.chunk_id"))
    content: str = Field(..., description=_("knowledge_base.chunk_model.content"))
    score: float = Field(..., description=_("knowledge_base.search.score"))
    metadata: dict | None = Field(None, description=_("knowledge_base.chunk_model.metadata"))
    document_name: str = Field(..., description=_("knowledge_base.document_model.file_name"))
    document_id: int = Field(..., description=_("knowledge_base.document_model.knowledge_base_id"))
    highlight: str | None = Field(None, description=_("knowledge_base.search.highlight"))


__all__ = [
    "KnowledgeBaseCreate",
    "KnowledgeBaseUpdate",
    "AdminKnowledgeBaseCreate",
    "AdminKnowledgeBaseUpdate",
    "KnowledgeBaseResponse",
    "KnowledgeBaseListItem",
    "KnowledgeDocumentResponse",
    "DocumentChunkResponse",
    "DocumentChunkUpdate",
    "QAPairCreate",
    "TextDocumentCreate",
    "KnowledgeBaseSearchRequest",
    "ChunkSearchResult",
]
