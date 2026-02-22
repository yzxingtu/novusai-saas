"""seed system_agent_assignments

[NO-OP] Originally inserted 4 agent assignment records, but all were
subsequently deleted (20260216_rmcg + 75773a96dac5 + manual cleanup).
Net effect is zero. Kept as placeholder to preserve Alembic chain.

Revision ID: 20260216_saa_seed
Revises: 20260216_saa
Create Date: 2026-02-16
"""

revision = "20260216_saa_seed"
down_revision = "20260216_saa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
