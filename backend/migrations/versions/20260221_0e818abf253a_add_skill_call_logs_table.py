"""add skill_call_logs table

[NO-OP] Empty migration - autogenerate detected no changes at creation time.
The actual skill_call_logs table was created in 18bd70ad08c1 (2026-02-24).
Kept to preserve Alembic chain.

Revision ID: 0e818abf253a
Revises: 61e838badbfa
Create Date: 2026-02-21 04:45:33.968939+00:00

"""

revision = '0e818abf253a'
down_revision = '61e838badbfa'
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    """Intentional no-op: Placeholder revision to preserve the Alembic chain; skill_call_logs schema is created elsewhere."""
    pass