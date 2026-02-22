"""fix agent assignment seed data

[NO-OP] Originally fixed feature_name/description on agent assignment records,
but all records were subsequently deleted. Kept to preserve Alembic chain.

Revision ID: 20260216_fix_aa
Revises: 20260216_awm
Create Date: 2026-02-16
"""

revision = "20260216_fix_aa"
down_revision = "20260216_awm"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
