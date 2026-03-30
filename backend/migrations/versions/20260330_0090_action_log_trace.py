"""Add trace_id and tool_call_id to ai_action_logs

Revision ID: 20260330_0090_actrace
Revises: 20260330_0080_ephem
Create Date: 2026-03-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260330_0090_actrace"
down_revision: str | Sequence[str] | None = "20260330_0080_ephem"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_action_logs",
        sa.Column("trace_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "ai_action_logs",
        sa.Column("tool_call_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_ai_action_logs_trace_id",
        "ai_action_logs",
        ["trace_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_action_logs_tool_call_id",
        "ai_action_logs",
        ["tool_call_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_action_logs_tool_call_id", table_name="ai_action_logs")
    op.drop_index("ix_ai_action_logs_trace_id", table_name="ai_action_logs")
    op.drop_column("ai_action_logs", "tool_call_id")
    op.drop_column("ai_action_logs", "trace_id")
