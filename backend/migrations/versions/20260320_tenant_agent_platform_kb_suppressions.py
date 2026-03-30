"""tenant_agent_platform_kb_suppressions: per-tenant opt-out from platform KB RAG

Revision ID: 20260320_tapks
Revises: 20260322_ai_billing_ledger_merge
Create Date: 2026-03-20

"""
import sqlalchemy as sa
from alembic import op

revision = "20260320_tapks"
down_revision = "20260322_ai_billing_ledger_merge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_agent_platform_kb_suppressions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("knowledge_base_id", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_tapks_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name="fk_tapks_agent_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_base_id"],
            ["knowledge_bases.id"],
            name="fk_tapks_kb_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_tapks_tenant_agent",
        "tenant_agent_platform_kb_suppressions",
        ["tenant_id", "agent_id"],
    )
    op.create_index(
        "ix_tapks_tenant_id",
        "tenant_agent_platform_kb_suppressions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_tapks_agent_id",
        "tenant_agent_platform_kb_suppressions",
        ["agent_id"],
    )
    op.create_index(
        "ix_tapks_kb_id",
        "tenant_agent_platform_kb_suppressions",
        ["knowledge_base_id"],
    )
    op.create_index(
        "ix_tapks_is_deleted",
        "tenant_agent_platform_kb_suppressions",
        ["is_deleted"],
    )
    op.execute(sa.text(
        """
        CREATE UNIQUE INDEX uq_tapks_active
        ON tenant_agent_platform_kb_suppressions (tenant_id, agent_id, knowledge_base_id)
        WHERE is_deleted = false
        """
    ))


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS uq_tapks_active"))
    op.drop_table("tenant_agent_platform_kb_suppressions")
