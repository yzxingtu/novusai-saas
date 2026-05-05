"""
Embedding resume and batch validation support for RAG processing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.ai.rag.chunker import ChunkData


@dataclass(frozen=True)
class EmbeddedChunkSnapshot:
    chunk_index: int
    content_hash: str


@dataclass(frozen=True)
class EmbeddingResumePlan:
    existing_chunk_count: int = 0
    restart_required: bool = False


def plan_embedding_resume(
    *,
    chunk_data_list: Sequence[ChunkData],
    existing_chunks: Sequence[EmbeddedChunkSnapshot],
) -> EmbeddingResumePlan:
    if not existing_chunks:
        return EmbeddingResumePlan()

    if len(existing_chunks) > len(chunk_data_list):
        return EmbeddingResumePlan(restart_required=True)

    for position, existing in enumerate(existing_chunks):
        expected = chunk_data_list[position]
        if existing.chunk_index != expected.chunk_index or str(
            existing.content_hash or ""
        ) != str(expected.content_hash or ""):
            return EmbeddingResumePlan(restart_required=True)

    return EmbeddingResumePlan(existing_chunk_count=len(existing_chunks))


def validate_embedding_batch_count(
    *,
    texts: Sequence[str],
    embeddings: Sequence[list[float]] | None,
) -> None:
    if len(embeddings or []) != len(texts):
        raise ValueError(
            f"Embedding response count mismatch: expected {len(texts)}, got {len(embeddings or [])}"
        )


def build_chunk_rows(
    *,
    chunks: Sequence[ChunkData],
    embeddings: Sequence[list[float]],
    document_id: int,
    knowledge_base_id: int,
    tenant_id: int | None,
) -> list[dict[str, Any]]:
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"Embedding row count mismatch: expected {len(chunks)}, got {len(embeddings)}"
        )

    rows: list[dict[str, Any]] = []
    for chunk, embedding in zip(chunks, embeddings, strict=True):
        rows.append(
            {
                "document_id": document_id,
                "knowledge_base_id": knowledge_base_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "content_hash": chunk.content_hash,
                "char_count": chunk.char_count,
                "token_count": 0,
                "embedding": embedding,
                "metadata_": chunk.metadata,
                "tenant_id": tenant_id,
            }
        )
    return rows


__all__ = [
    "EmbeddedChunkSnapshot",
    "EmbeddingResumePlan",
    "build_chunk_rows",
    "plan_embedding_resume",
    "validate_embedding_batch_count",
]
