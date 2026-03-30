"""notification_pref_add_global_layer

Revision ID: 67ac03130752
Revises: d17cdc15627c
Create Date: 2026-03-14 09:49:25.150677+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '67ac03130752'
down_revision: Union[str, None] = 'd17cdc15627c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column("tenant_id", sa.Integer(), nullable=False, server_default="0",
                  comment="租户 ID（0 = 平台级）"),
    )

    op.alter_column(
        "notification_preferences",
        "user_id",
        existing_type=sa.Integer(),
        nullable=True,
        comment="用户 ID（NULL = 全局记录）",
    )

    # backfill tenant_id for existing tenant_admin rows
    op.execute(sa.text(
        """
        UPDATE notification_preferences np
        SET tenant_id = ta.tenant_id
        FROM tenant_admins ta
        WHERE np.user_type = 'tenant_admin'
          AND np.user_id = ta.id
        """
    ))

    op.drop_constraint("uq_notification_pref", "notification_preferences", type_="unique")

    op.create_unique_constraint(
        "uq_notification_pref_v2",
        "notification_preferences",
        ["user_type", "tenant_id", "user_id", "category"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_notification_pref_v2", "notification_preferences", type_="unique")

    # delete global rows before restoring NOT NULL
    op.execute(sa.text("DELETE FROM notification_preferences WHERE user_id IS NULL"))

    op.alter_column(
        "notification_preferences",
        "user_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.create_unique_constraint(
        "uq_notification_pref",
        "notification_preferences",
        ["user_type", "user_id", "category"],
    )

    op.drop_column("notification_preferences", "tenant_id")
