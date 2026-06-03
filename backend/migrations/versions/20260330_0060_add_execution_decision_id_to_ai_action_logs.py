"""Add execution_decision_id to ai_action_logs

Revision ID: 20260330_0060_log_decision
Revises: 20260329_0050_exec_decisions
Create Date: 2026-03-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260330_0060_log_decision"
down_revision: str | Sequence[str] | None = "20260329_0050_exec_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_action_logs",
        sa.Column("execution_decision_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_ai_action_logs_execution_decision_id",
        "ai_action_logs",
        ["execution_decision_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_action_logs_execution_decision_id",
        table_name="ai_action_logs",
    )
    op.drop_column("ai_action_logs", "execution_decision_id")
