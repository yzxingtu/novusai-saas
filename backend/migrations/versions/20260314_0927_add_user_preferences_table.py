"""add_user_preferences_table

Revision ID: d17cdc15627c
Revises: 20260314_add_scope
Create Date: 2026-03-14 09:27:54.230107+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd17cdc15627c'
down_revision: Union[str, None] = '20260314_add_scope'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema."""
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("scope", sa.String(30), nullable=False, index=True,
                  comment="Scope: platform_global, tenant_global, admin, tenant_admin"),
        sa.Column("tenant_id", sa.Integer, nullable=False, default=0, index=True,
                  comment="Tenant ID (0 = platform level)"),
        sa.Column("user_id", sa.Integer, nullable=True, default=None, index=True,
                  comment="User ID (NULL = global record)"),
        sa.Column("preferences", sa.Text, nullable=False, server_default="{}",
                  comment="Preferences JSON"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1",
                  comment="Global record change version"),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.text("false"), index=True),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("scope", "tenant_id", "user_id",
                            name="uq_user_pref_scope_tenant_user"),
    )


def downgrade() -> None:
    """Downgrade database schema."""
    op.drop_table("user_preferences")
