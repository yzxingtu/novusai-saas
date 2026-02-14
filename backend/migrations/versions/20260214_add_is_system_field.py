"""add_is_system_field

Add is_system boolean column to agents, skills, and skill_packages tables
to mark system-managed records that cannot be deleted or have key properties modified.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-02-14 00:00:00.000000+08:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("agents", "skills", "skill_packages"):
        op.add_column(
            table,
            sa.Column(
                "is_system",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
                comment="系统记录标记，不可删除或修改关键属性",
            ),
        )
        op.create_index(f"ix_{table}_is_system", table, ["is_system"])


def downgrade() -> None:
    for table in ("agents", "skills", "skill_packages"):
        op.drop_index(f"ix_{table}_is_system", table_name=table)
        op.drop_column(table, "is_system")
