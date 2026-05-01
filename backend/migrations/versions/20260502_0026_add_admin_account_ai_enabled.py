"""add admin account ai enabled

Revision ID: 20260502_0026_admin_ai_enabled
Revises: 20260430_0025_retired_runtime
Create Date: 2026-05-02

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260502_0026_admin_ai_enabled"
down_revision: str | Sequence[str] | None = "20260430_0025_retired_runtime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_TABLES = ("admins", "tenant_admins")


def _has_column(table_name: str, column_name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table(table_name):
        return False
    return any(
        column.get("name") == column_name
        for column in inspector.get_columns(table_name)
    )


def _add_ai_enabled_column(table_name: str) -> None:
    if _has_column(table_name, "ai_enabled"):
        return
    op.add_column(
        table_name,
        sa.Column(
            "ai_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="是否允许使用 AI 对话 / AI chat enabled",
        ),
    )


def _drop_ai_enabled_column(table_name: str) -> None:
    if not _has_column(table_name, "ai_enabled"):
        return
    op.drop_column(table_name, "ai_enabled")


def upgrade() -> None:
    for table_name in _TABLES:
        _add_ai_enabled_column(table_name)


def downgrade() -> None:
    for table_name in reversed(_TABLES):
        _drop_ai_enabled_column(table_name)
