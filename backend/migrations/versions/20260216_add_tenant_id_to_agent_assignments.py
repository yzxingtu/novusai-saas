"""[NO-OP] add tenant_id to system_agent_assignments

Operations (tenant_id column, composite unique constraint, partial index)
were folded into the initial table creation migration (20260216_saa).
Kept to preserve Alembic chain.

Revision ID: 20260216_saa_tid
Revises: 20260216_saa_seed
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa

revision = "20260216_saa_tid"
down_revision = "20260216_saa_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op: tenant_id, composite unique constraint, and partial index
    # are now included in the initial table creation migration (20260216_saa).
    pass


def downgrade() -> None:
    """Intentional no-op: tenant_id and constraints are defined in the initial table migration; this revision only preserves the chain."""
    pass
