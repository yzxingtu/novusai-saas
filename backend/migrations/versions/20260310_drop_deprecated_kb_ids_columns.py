"""drop deprecated knowledge_base_ids columns from agents and agent_versions

Revision ID: 20260310_drop_kb_ids
Revises: 20260309_fix_agent_kb_cols
Create Date: 2026-03-10

knowledge_base_ids field has been replaced by AgentKnowledgeBaseBinding
intermediate table. This column is no longer read at runtime.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260310_drop_kb_ids"
down_revision = "20260309_fix_agent_kb_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("agents", "knowledge_base_ids")
    op.drop_column("agent_versions", "knowledge_base_ids")


def downgrade() -> None:
    op.add_column(
        "agent_versions",
        sa.Column("knowledge_base_ids", sa.JSON(), nullable=True),
    )
    op.add_column(
        "agents",
        sa.Column("knowledge_base_ids", sa.JSON(), nullable=True),
    )
