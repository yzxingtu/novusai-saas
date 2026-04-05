"""add identity snapshots to operation and ai action logs

Revision ID: 20260405_log_identity_snapshots
Revises: 20260405_retire_ai_policy_di
Create Date: 2026-04-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260405_log_identity_snapshots"
down_revision: str | Sequence[str] | None = "20260405_retire_ai_policy_di"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(bind, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(bind)
    return any(
        column["name"] == column_name
        for column in inspector.get_columns(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_column(bind, "operation_logs", "identity_snapshot"):
        op.add_column(
            "operation_logs",
            sa.Column("identity_snapshot", sa.JSON(), nullable=True),
        )

    if not _has_column(bind, "ai_action_logs", "operator_snapshot"):
        op.add_column(
            "ai_action_logs",
            sa.Column("operator_snapshot", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _has_column(bind, "ai_action_logs", "operator_snapshot"):
        op.drop_column("ai_action_logs", "operator_snapshot")

    if _has_column(bind, "operation_logs", "identity_snapshot"):
        op.drop_column("operation_logs", "identity_snapshot")
