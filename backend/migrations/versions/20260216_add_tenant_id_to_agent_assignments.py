"""add tenant_id to system_agent_assignments

Adds tenant_id column for tenant-level overrides.
Changes unique constraint from feature_code alone to (feature_code, tenant_id).
Adds partial unique index for global defaults (tenant_id IS NULL).

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
    pass
