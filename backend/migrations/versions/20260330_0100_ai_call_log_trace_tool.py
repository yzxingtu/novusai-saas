"""Add trace_id and tool_call_id to ai_call_logs

Revision ID: 20260330_0100_calltrace
Revises: 20260330_0090_actrace
Create Date: 2026-03-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260330_0100_calltrace"
down_revision: str | Sequence[str] | None = "20260330_0090_actrace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_call_logs",
        sa.Column("trace_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "ai_call_logs",
        sa.Column("tool_call_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_ai_call_logs_trace_id",
        "ai_call_logs",
        ["trace_id"],
        unique=False,
    )
    op.create_index(
        "ix_ai_call_logs_tool_call_id",
        "ai_call_logs",
        ["tool_call_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_call_logs_tool_call_id", table_name="ai_call_logs")
    op.drop_index("ix_ai_call_logs_trace_id", table_name="ai_call_logs")
    op.drop_column("ai_call_logs", "tool_call_id")
    op.drop_column("ai_call_logs", "trace_id")
