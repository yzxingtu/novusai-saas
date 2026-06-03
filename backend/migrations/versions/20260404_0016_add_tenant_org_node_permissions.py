"""add tenant org node permissions

Revision ID: 20260404_tenant_org_perm
Revises: 20260404_ai_model_code
Create Date: 2026-04-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260404_tenant_org_perm"
down_revision: str | Sequence[str] | None = "20260404_ai_model_code"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if not _has_table(bind, "tenant_org_node_permissions"):
        op.create_table(
            "tenant_org_node_permissions",
            sa.Column("org_node_id", sa.Integer(), nullable=False),
            sa.Column("permission_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(
                ["org_node_id"],
                ["tenant_org_nodes.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["permission_id"],
                ["permissions.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("org_node_id", "permission_id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "tenant_org_node_permissions"):
        op.drop_table("tenant_org_node_permissions")
