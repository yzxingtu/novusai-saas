"""add admin org node permissions

Revision ID: 20260325_org_node_perm
Revises: 20260325_org_authority_rebuild
Create Date: 2026-03-25 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "20260325_org_node_perm"
down_revision = "20260325_org_authority_rebuild"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_org_node_permissions",
        sa.Column("org_node_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_node_id"],
            ["admin_org_nodes.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("org_node_id", "permission_id"),
    )

    op.execute(
        """
        INSERT INTO admin_org_node_permissions (org_node_id, permission_id)
        SELECT DISTINCT arp.role_id, arp.permission_id
        FROM admin_role_permissions AS arp
        INNER JOIN admin_org_nodes AS aon ON aon.id = arp.role_id
        INNER JOIN permissions AS p ON p.id = arp.permission_id
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("admin_org_node_permissions")
