"""drop scope column from ai_table_policies

The `scope` field was redundant for platform-level table policies.
AITablePolicy is always platform-scoped (BaseModel, not TenantModel).
Tenant customization is handled via AITablePolicyOverride.

This migration:
  1. Drops the composite index idx_ai_table_policies_scope_active
  2. Drops the single-column index ix_ai_table_policies_scope
  3. Drops the scope column itself

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-02-14 19:30:00.000000+08:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop indexes that reference scope
    op.drop_index(
        "idx_ai_table_policies_scope_active",
        table_name="ai_table_policies",
    )
    op.drop_index(
        op.f("ix_ai_table_policies_scope"),
        table_name="ai_table_policies",
    )

    # Drop the scope column
    op.drop_column("ai_table_policies", "scope")


def downgrade() -> None:
    # Re-add scope column with default 'platform'
    op.add_column(
        "ai_table_policies",
        sa.Column(
            "scope",
            sa.String(length=20),
            nullable=False,
            server_default="platform",
            comment="作用域",
        ),
    )

    # Re-create indexes
    op.create_index(
        op.f("ix_ai_table_policies_scope"),
        "ai_table_policies",
        ["scope"],
    )
    op.create_index(
        "idx_ai_table_policies_scope_active",
        "ai_table_policies",
        ["scope", "is_active"],
    )
