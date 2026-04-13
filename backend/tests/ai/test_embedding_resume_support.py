from __future__ import annotations

from types import SimpleNamespace

import pytest


def _chunk(chunk_index: int, content_hash: str, content: str = "content"):
    return SimpleNamespace(
        chunk_index=chunk_index,
        content_hash=content_hash,
        content=content,
        char_count=len(content),
        metadata={"index": chunk_index},
    )


def test_plan_embedding_resume_uses_matching_prefix() -> None:
    from app.ai.rag.embedding_resume_support import (
        EmbeddedChunkSnapshot,
        plan_embedding_resume,
    )

    plan = plan_embedding_resume(
        chunk_data_list=[_chunk(0, "a"), _chunk(1, "b"), _chunk(2, "c")],
        existing_chunks=[
            EmbeddedChunkSnapshot(chunk_index=0, content_hash="a"),
            EmbeddedChunkSnapshot(chunk_index=1, content_hash="b"),
        ],
    )

    assert plan.restart_required is False
    assert plan.existing_chunk_count == 2


def test_plan_embedding_resume_restarts_on_hash_mismatch() -> None:
    from app.ai.rag.embedding_resume_support import (
        EmbeddedChunkSnapshot,
        plan_embedding_resume,
    )

    plan = plan_embedding_resume(
        chunk_data_list=[_chunk(0, "a"), _chunk(1, "b")],
        existing_chunks=[
            EmbeddedChunkSnapshot(chunk_index=0, content_hash="a"),
            EmbeddedChunkSnapshot(chunk_index=1, content_hash="mismatch"),
        ],
    )

    assert plan.restart_required is True
    assert plan.existing_chunk_count == 0


def test_validate_embedding_batch_count_raises_on_missing_vectors() -> None:
    from app.ai.rag.embedding_resume_support import validate_embedding_batch_count

    with pytest.raises(ValueError, match="expected 2, got 1"):
        validate_embedding_batch_count(
            texts=["first", "second"],
            embeddings=[[0.1, 0.2]],
        )


def test_build_chunk_rows_rejects_incomplete_embeddings() -> None:
    from app.ai.rag.embedding_resume_support import build_chunk_rows

    with pytest.raises(ValueError, match="expected 2, got 1"):
        build_chunk_rows(
            chunks=[_chunk(0, "a"), _chunk(1, "b")],
            embeddings=[[0.1, 0.2]],
            document_id=9,
            knowledge_base_id=12,
            tenant_id=5,
        )
