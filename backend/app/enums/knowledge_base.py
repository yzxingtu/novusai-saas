"""
知识库相关枚举模块

定义知识库状态、文档状态、文档类型、分块策略、检索模式、查询改写策略等枚举
"""

from app.enums.base import LabeledStrEnum


class KBStatusEnum(LabeledStrEnum):
    """知识库状态枚举"""

    ACTIVE = ("active", "enum.knowledge_base.status.active")
    DISABLED = ("disabled", "enum.knowledge_base.status.disabled")


class DocumentStatusEnum(LabeledStrEnum):
    """文档处理状态枚举（状态机）"""

    PENDING = ("pending", "enum.knowledge_base.document_status.pending")
    PARSING = ("parsing", "enum.knowledge_base.document_status.parsing")
    CHUNKING = ("chunking", "enum.knowledge_base.document_status.chunking")
    EMBEDDING = ("embedding", "enum.knowledge_base.document_status.embedding")
    COMPLETED = ("completed", "enum.knowledge_base.document_status.completed")
    ERROR = ("error", "enum.knowledge_base.document_status.error")


class DocumentTypeEnum(LabeledStrEnum):
    """文档类型枚举"""

    PDF = ("pdf", "enum.knowledge_base.document_type.pdf")
    DOCX = ("docx", "enum.knowledge_base.document_type.docx")
    TXT = ("txt", "enum.knowledge_base.document_type.txt")
    MD = ("md", "enum.knowledge_base.document_type.md")
    CSV = ("csv", "enum.knowledge_base.document_type.csv")
    QA = ("qa", "enum.knowledge_base.document_type.qa")
    URL = ("url", "enum.knowledge_base.document_type.url")


class ChunkStrategyEnum(LabeledStrEnum):
    """文本分块策略枚举"""

    RECURSIVE = ("recursive", "enum.knowledge_base.chunk_strategy.recursive")
    SEMANTIC = ("semantic", "enum.knowledge_base.chunk_strategy.semantic")
    PARAGRAPH = ("paragraph", "enum.knowledge_base.chunk_strategy.paragraph")


class SearchModeEnum(LabeledStrEnum):
    """检索模式枚举"""

    HYBRID = ("hybrid", "enum.knowledge_base.search_mode.hybrid")
    VECTOR = ("vector", "enum.knowledge_base.search_mode.vector")
    KEYWORD = ("keyword", "enum.knowledge_base.search_mode.keyword")


class RewriteStrategyEnum(LabeledStrEnum):
    """查询改写策略枚举"""

    NONE = ("none", "enum.knowledge_base.rewrite_strategy.none")
    MULTI = ("multi", "enum.knowledge_base.rewrite_strategy.multi")
    HYDE = ("hyde", "enum.knowledge_base.rewrite_strategy.hyde")


__all__ = [
    "KBStatusEnum",
    "DocumentStatusEnum",
    "DocumentTypeEnum",
    "ChunkStrategyEnum",
    "SearchModeEnum",
    "RewriteStrategyEnum",
]
