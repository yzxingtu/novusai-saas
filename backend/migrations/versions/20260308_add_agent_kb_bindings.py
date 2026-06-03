"""add agent_knowledge_base_bindings table

Revision ID: 20260308_add_agent_kb_bindings
Revises: 05f5370dfb35
Create Date: 2026-03-08

Creates agent_knowledge_base_bindings table for Agent <-> KnowledgeBase M:N binding
with weight, enabled, and sort_order per binding.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260308_add_agent_kb_bindings"
down_revision = "05f5370dfb35"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_knowledge_base_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name="fk_agent_kb_bindings_agent_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["knowledge_bases.id"],
            name="fk_agent_kb_bindings_kb_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "agent_id",
            "knowledge_base_id",
            name="uq_agent_knowledge_base_binding",
        ),
    )
    op.create_index(
        "ix_agent_kb_bindings_tenant_id",
        "agent_knowledge_base_bindings",
        ["tenant_id"],
    )
    op.create_index(
        "ix_agent_kb_bindings_agent_id",
        "agent_knowledge_base_bindings",
        ["agent_id"],
    )
    op.create_index(
        "ix_agent_kb_bindings_kb_id",
        "agent_knowledge_base_bindings",
        ["knowledge_base_id"],
    )
    op.create_index(
        "ix_agent_kb_bindings_agent_enabled",
        "agent_knowledge_base_bindings",
        ["agent_id", "enabled"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_kb_bindings_agent_enabled",
        table_name="agent_knowledge_base_bindings",
    )
    op.drop_index(
        "ix_agent_kb_bindings_kb_id",
        table_name="agent_knowledge_base_bindings",
    )
    op.drop_index(
        "ix_agent_kb_bindings_agent_id",
        table_name="agent_knowledge_base_bindings",
    )
    op.drop_index(
        "ix_agent_kb_bindings_tenant_id",
        table_name="agent_knowledge_base_bindings",
    )
    op.drop_table("agent_knowledge_base_bindings")
