"""scope ai model code uniqueness by provider

Revision ID: 20260404_ai_model_code
Revises: 20260403_agent_src
Create Date: 2026-04-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "20260404_ai_model_code"
down_revision: str | Sequence[str] | None = "20260403_agent_src"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CODE_INDEX = "ix_ai_models_code"
_PROVIDER_CODE_UNIQUE_INDEX = "uq_ai_models_provider_code_active"


def _has_index(bind, table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()

    if _has_index(bind, "ai_models", _CODE_INDEX):
        op.drop_index(_CODE_INDEX, table_name="ai_models")

    if not _has_index(bind, "ai_models", _CODE_INDEX):
        op.create_index(_CODE_INDEX, "ai_models", ["code"], unique=False)

    if not _has_index(bind, "ai_models", _PROVIDER_CODE_UNIQUE_INDEX):
        op.create_index(
            _PROVIDER_CODE_UNIQUE_INDEX,
            "ai_models",
            ["provider_id", "code"],
            unique=True,
            postgresql_where=text("is_deleted = false"),
        )


def downgrade() -> None:
    bind = op.get_bind()

    duplicate_rows = bind.execute(
        text(
            """
            SELECT code
            FROM ai_models
            WHERE is_deleted = false
            GROUP BY code
            HAVING COUNT(*) > 1
            LIMIT 1
            """
        )
    ).fetchone()
    if duplicate_rows is not None:
        raise RuntimeError(
            "Cannot downgrade ai_models code uniqueness: duplicate active codes exist across providers"
        )

    if _has_index(bind, "ai_models", _PROVIDER_CODE_UNIQUE_INDEX):
        op.drop_index(_PROVIDER_CODE_UNIQUE_INDEX, table_name="ai_models")

    if _has_index(bind, "ai_models", _CODE_INDEX):
        op.drop_index(_CODE_INDEX, table_name="ai_models")

    if not _has_index(bind, "ai_models", _CODE_INDEX):
        op.create_index(_CODE_INDEX, "ai_models", ["code"], unique=True)
