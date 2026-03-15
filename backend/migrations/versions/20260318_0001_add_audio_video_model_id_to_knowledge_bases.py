"""add audio_model_id and video_model_id to knowledge_bases

Revision ID: 20260318_0001_kb_av
Revises: 20260317_0001_audio_video
Create Date: 2026-03-18

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260318_0001_kb_av"
down_revision: str | Sequence[str] | None = "20260317_0001_audio_video"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_bases",
        sa.Column("audio_model_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("video_model_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_knowledge_bases_audio_model_id",
        "knowledge_bases",
        "ai_models",
        ["audio_model_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_knowledge_bases_video_model_id",
        "knowledge_bases",
        "ai_models",
        ["video_model_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_knowledge_bases_audio_model_id"),
        "knowledge_bases",
        ["audio_model_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_bases_video_model_id"),
        "knowledge_bases",
        ["video_model_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_knowledge_bases_video_model_id",
        "knowledge_bases",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_knowledge_bases_audio_model_id",
        "knowledge_bases",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_knowledge_bases_video_model_id"),
        table_name="knowledge_bases",
    )
    op.drop_index(
        op.f("ix_knowledge_bases_audio_model_id"),
        table_name="knowledge_bases",
    )
    op.drop_column("knowledge_bases", "video_model_id")
    op.drop_column("knowledge_bases", "audio_model_id")
