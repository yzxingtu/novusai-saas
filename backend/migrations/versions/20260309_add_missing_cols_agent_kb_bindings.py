"""add missing deleted_at and delete_level columns to agent_knowledge_base_bindings

Revision ID: 20260309_fix_agent_kb_cols
Revises: 20260308_add_agent_kb_bindings
Create Date: 2026-03-09

Adds deleted_at and delete_level columns that BaseModel provides but were
missing from the original migration.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260309_fix_agent_kb_cols"
down_revision = "20260308_add_agent_kb_bindings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_knowledge_base_bindings",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agent_knowledge_base_bindings",
        sa.Column("delete_level", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_knowledge_base_bindings", "delete_level")
    op.drop_column("agent_knowledge_base_bindings", "deleted_at")
