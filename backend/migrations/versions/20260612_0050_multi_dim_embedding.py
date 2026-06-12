# -*- coding: utf-8 -*-
"""document_chunks multi-column embedding + ai_models.embedding_dimensions.

- Remove the legacy single `embedding` column (vector(1536)) from document_chunks.
- Add per-dimension columns: embedding_1024 vector(1024), embedding_1536 vector(1536).
- Create independent HNSW indexes for each dimension column.
- Add `embedding_dimensions` column to ai_models table (nullable Integer, for embedding type models).

Fixes #17
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260612_0050_multi_dim_embedding"
down_revision: str | Sequence[str] | None = "20260610_0049_internal_ops"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add multi-dimension embedding columns and HNSW indexes."""

    # 1. Drop the old single-dimension HNSW index and column
    op.execute(sa.text("DROP INDEX IF EXISTS ix_chunk_embedding"))
    op.execute(sa.text("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding"))

    # 2. Add per-dimension embedding columns
    op.execute(
        sa.text(
            "ALTER TABLE document_chunks ADD COLUMN embedding_1024 vector(1024)"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE document_chunks ADD COLUMN embedding_1536 vector(1536)"
        )
    )

    # 3. Create independent HNSW indexes for each dimension
    op.execute(
        sa.text("""
            CREATE INDEX ix_chunk_emb_1024
            ON document_chunks
            USING hnsw (embedding_1024 vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """)
    )
    op.execute(
        sa.text("""
            CREATE INDEX ix_chunk_emb_1536
            ON document_chunks
            USING hnsw (embedding_1536 vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """)
    )

    # 4. Add embedding_dimensions column to ai_models table
    op.add_column(
        "ai_models",
        sa.Column(
            "embedding_dimensions",
            sa.Integer(),
            nullable=True,
            comment="Embedding output dimensions (only for embedding type models)",
        ),
    )


def downgrade() -> None:
    """Revert to single-dimension embedding column."""

    # 4. Remove ai_models.embedding_dimensions
    op.drop_column("ai_models", "embedding_dimensions")

    # 3. Drop per-dimension HNSW indexes
    op.execute(sa.text("DROP INDEX IF EXISTS ix_chunk_emb_1536"))
    op.execute(sa.text("DROP INDEX IF EXISTS ix_chunk_emb_1024"))

    # 2. Drop per-dimension columns
    op.execute(
        sa.text("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding_1536")
    )
    op.execute(
        sa.text("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding_1024")
    )

    # 1. Restore the old single-dimension column and index
    op.execute(sa.text("ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)"))
    op.execute(
        sa.text("""
            CREATE INDEX ix_chunk_embedding
            ON document_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """)
    )
