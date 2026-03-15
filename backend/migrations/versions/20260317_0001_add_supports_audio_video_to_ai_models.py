"""add supports_audio and supports_video to ai_models

Revision ID: 20260317_0001_audio_video
Revises: 20260316_page_op_v3
Create Date: 2026-03-17

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260317_0001_audio_video"
down_revision: str | Sequence[str] | None = "20260316_page_op_v3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_models",
        sa.Column("supports_audio", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "ai_models",
        sa.Column("supports_video", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("ai_models", "supports_video")
    op.drop_column("ai_models", "supports_audio")
