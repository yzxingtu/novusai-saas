"""remove unused agent assignment seed data

[NO-OP] Originally deleted 3 unused agent assignment records,
but data was already manually cleaned before migration ran.
Kept to preserve Alembic chain.

Revision ID: 75773a96dac5
Revises: 5c37f4f986ac
Create Date: 2026-02-22 03:44:10.405267+00:00

"""

revision = '75773a96dac5'
down_revision = '5c37f4f986ac'
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    """Intentional no-op: Placeholder revision; seed rows were already removed and chain continuity is the only purpose."""
    pass
