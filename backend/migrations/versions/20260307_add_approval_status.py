"""add approval_status to tenant_users

Adds approval_status column to tenant_users table for registration approval workflow.

Revision ID: 20260307_approval
Revises: 20260307_user_roles
Create Date: 2026-03-07 23:00:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260307_approval"
down_revision: str = "20260307_user_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenant_users",
        sa.Column(
            "approval_status",
            sa.String(20),
            nullable=False,
            server_default="approved",
            comment="审批状态: pending/approved/rejected",
        ),
    )


def downgrade() -> None:
    op.drop_column("tenant_users", "approval_status")
