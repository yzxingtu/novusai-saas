"""
Retriever contracts and context types.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.models.ai.knowledge_base import KnowledgeBase


@dataclass
class ChunkSearchResult:
    """Search result item / 检索结果项"""

    chunk_id: int
    content: str
    score: float
    metadata: dict | None = None
    document_name: str = ""
    document_id: int = 0
    chunk_index: int = 0
    highlight: str | None = None
    knowledge_base_id: int = 0
    raw_score: float | None = None
    fusion_score: float | None = None
    kb_weight: float | None = None
    recall_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """For serialization / 用于序列化"""
        return asdict(self)


@dataclass
class SearchKBContext:
    """Runtime retrieval context for one KB / 单个知识库的运行时检索上下文。"""

    knowledge_base: KnowledgeBase
    weight: float = 1.0

    @property
    def kb_id(self) -> int:
        return int(self.knowledge_base.id)

    @property
    def embedding_signature(self) -> tuple[int, int]:
        return (
            int(getattr(self.knowledge_base, "embedding_model_id", 0) or 0),
            int(getattr(self.knowledge_base, "embedding_dimensions", 0) or 0),
        )

    def cache_signature(self) -> str:
        model_id, dimensions = self.embedding_signature
        return f"{self.kb_id}:{round(float(self.weight), 3)}:{model_id}:{dimensions}"


__all__ = ["ChunkSearchResult", "SearchKBContext"]
