"""add tenant_id to periodic_tasks

Revision ID: 20260208_0011
Revises: 20260208_0010
Create Date: 2026-02-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260208_0011"
down_revision = "20260208_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "periodic_tasks",
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=True,
            comment="所属租户ID（NULL表示平台级任务）",
        ),
    )
    op.create_index("ix_periodic_tasks_tenant_id", "periodic_tasks", ["tenant_id"])
    op.drop_constraint("uq_periodic_tasks_name", "periodic_tasks", type_="unique")
    op.create_unique_constraint(
        "uq_periodic_tasks_name_tenant", "periodic_tasks", ["name", "tenant_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_periodic_tasks_name_tenant", "periodic_tasks", type_="unique")
    op.create_unique_constraint("uq_periodic_tasks_name", "periodic_tasks", ["name"])
    op.drop_index("ix_periodic_tasks_tenant_id", "periodic_tasks")
    op.drop_column("periodic_tasks", "tenant_id")
