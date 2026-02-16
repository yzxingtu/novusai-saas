"""add consent_mode to agent_skill_bindings

Add consent_mode column to agent_skill_bindings table.
Controls whether tools in the bound skill package require user consent
before execution: auto (default), ask, reject.

Revision ID: cc0216020000
Revises: cc0216010000
Create Date: 2026-02-16 02:00:00.000000+08:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "cc0216020000"
down_revision: Union[str, None] = "cc0216010000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_skill_bindings",
        sa.Column(
            "consent_mode",
            sa.String(20),
            nullable=False,
            server_default="auto",
            comment="Tool consent mode: auto / ask / reject",
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_skill_bindings", "consent_mode")
