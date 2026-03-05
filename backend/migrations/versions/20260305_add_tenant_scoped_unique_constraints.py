"""add tenant-scoped unique constraints for tenant_admins and tenant_users

Adds UniqueConstraint on (tenant_id, username) and (tenant_id, email) for tenant_admins,
and (tenant_id, username), (tenant_id, email), (tenant_id, phone) for tenant_users.

Revision ID: 20260305_tenant_uq
Revises: c1a4f0e2b9d3
Create Date: 2026-03-05 16:00:00.000000+00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260305_tenant_uq"
down_revision: str | Sequence[str] | None = "c1a4f0e2b9d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # tenant_admins: (tenant_id, username) unique
    op.create_unique_constraint(
        "uq_tenant_admin_tenant_username",
        "tenant_admins",
        ["tenant_id", "username"],
    )
    # tenant_admins: (tenant_id, email) unique
    op.create_unique_constraint(
        "uq_tenant_admin_tenant_email",
        "tenant_admins",
        ["tenant_id", "email"],
    )

    # tenant_users: (tenant_id, username) unique
    op.create_unique_constraint(
        "uq_tenant_user_tenant_username",
        "tenant_users",
        ["tenant_id", "username"],
    )
    # tenant_users: (tenant_id, email) unique
    op.create_unique_constraint(
        "uq_tenant_user_tenant_email",
        "tenant_users",
        ["tenant_id", "email"],
    )
    # tenant_users: (tenant_id, phone) unique
    op.create_unique_constraint(
        "uq_tenant_user_tenant_phone",
        "tenant_users",
        ["tenant_id", "phone"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_tenant_user_tenant_phone", "tenant_users", type_="unique")
    op.drop_constraint("uq_tenant_user_tenant_email", "tenant_users", type_="unique")
    op.drop_constraint("uq_tenant_user_tenant_username", "tenant_users", type_="unique")
    op.drop_constraint("uq_tenant_admin_tenant_email", "tenant_admins", type_="unique")
    op.drop_constraint("uq_tenant_admin_tenant_username", "tenant_admins", type_="unique")
