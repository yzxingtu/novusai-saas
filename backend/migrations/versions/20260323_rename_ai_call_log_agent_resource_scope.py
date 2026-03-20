"""Rename ai_call_logs.agent_distribution_mode -> agent_resource_scope (+ widen)

Revision ID: 20260323_acl_ars
Revises: 20260321_akso
Create Date: 2026-03-23

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect, text

revision: str = "20260323_acl_ars"
down_revision: str | Sequence[str] | None = "20260321_akso"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(bind, table: str) -> set[str]:
    return {c["name"] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if "ai_call_logs" not in inspect(bind).get_table_names():
        return
    cols = _column_names(bind, "ai_call_logs")
    if "agent_distribution_mode" in cols and "agent_resource_scope" not in cols:
        op.execute(
            text(
                "ALTER TABLE ai_call_logs RENAME COLUMN "
                "agent_distribution_mode TO agent_resource_scope",
            ),
        )
    if "agent_resource_scope" in _column_names(bind, "ai_call_logs"):
        op.execute(
            text("ALTER TABLE ai_call_logs ALTER COLUMN agent_resource_scope TYPE VARCHAR(40)"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "ai_call_logs" not in inspect(bind).get_table_names():
        return
    cols = _column_names(bind, "ai_call_logs")
    if "agent_resource_scope" in cols and "agent_distribution_mode" not in cols:
        op.execute(
            text("ALTER TABLE ai_call_logs ALTER COLUMN agent_resource_scope TYPE VARCHAR(20)"),
        )
        op.execute(
            text(
                "ALTER TABLE ai_call_logs RENAME COLUMN "
                "agent_resource_scope TO agent_distribution_mode",
            ),
        )
