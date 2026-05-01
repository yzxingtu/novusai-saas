"""Remove package-local scope from skills.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-02-15 00:00:00.000000+08:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "d5e6f7a8b9c0"
down_revision: str | Sequence[str] | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    indexes = _indexes("skills")
    if "ix_skills_tenant_scope" in indexes:
        op.drop_index("ix_skills_tenant_scope", table_name="skills")
    if "ix_skills_scope" in indexes:
        op.drop_index("ix_skills_scope", table_name="skills")
    if "scope" in _columns("skills"):
        op.drop_column("skills", "scope")


def downgrade() -> None:
    if "scope" not in _columns("skills"):
        op.add_column(
            "skills",
            sa.Column(
                "scope",
                sa.String(length=20),
                nullable=False,
                server_default="tenant",
                comment="作用域",
            ),
        )
