"""add kb visibility field and tenant access table

Revision ID: kb_visibility_001
Revises: (auto-detected)
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa

revision = "kb_visibility_001"
down_revision = "18bd70ad08c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add visibility column to knowledge_bases
    op.add_column(
        "knowledge_bases",
        sa.Column(
            "visibility",
            sa.String(20),
            nullable=False,
            server_default="private",
            comment="知识库可见性: private/all_tenants/assigned",
        ),
    )
    op.create_index("ix_knowledge_bases_visibility", "knowledge_bases", ["visibility"])

    # 2. Create knowledge_base_tenant_access table
    op.create_table(
        "knowledge_base_tenant_access",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["knowledge_base_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("knowledge_base_id", "tenant_id", name="uq_kb_tenant_access"),
    )
    op.create_index("ix_kb_tenant_access_tenant", "knowledge_base_tenant_access", ["tenant_id"])
    op.create_index("ix_kb_tenant_access_kb", "knowledge_base_tenant_access", ["knowledge_base_id"])

    # 3. Data migration: existing global scope KBs → visibility=all_tenants
    op.execute(
        "UPDATE knowledge_bases SET visibility = 'all_tenants' WHERE scope = 'global'"
    )


def downgrade() -> None:
    op.drop_table("knowledge_base_tenant_access")
    op.drop_index("ix_knowledge_bases_visibility", "knowledge_bases")
    op.drop_column("knowledge_bases", "visibility")
