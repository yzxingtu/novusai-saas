"""add system_agent_assignments table

Revision ID: 20260216_saa
Revises: cc0216030000
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa

revision = "20260216_saa"
down_revision = "cc0216030000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_agent_assignments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("feature_code", sa.String(100), nullable=False, index=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("feature_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("agent_id", sa.Integer(), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false"), index=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("feature_code", "tenant_id", name="uq_feature_code_tenant_id"),
    )
    # Partial unique index for global defaults (tenant_id IS NULL)
    op.create_index(
        "ix_feature_code_global",
        "system_agent_assignments",
        ["feature_code"],
        unique=True,
        postgresql_where=sa.text("tenant_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("system_agent_assignments")
