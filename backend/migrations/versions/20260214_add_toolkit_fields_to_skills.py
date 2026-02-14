"""add toolkit_content and toolkit_meta to skills

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-02-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "skills",
        sa.Column("toolkit_content", sa.Text(), nullable=True, comment="Toolkit 源码"),
    )
    op.add_column(
        "skills",
        sa.Column(
            "toolkit_meta",
            sa.JSON(),
            nullable=True,
            comment="Toolkit 元数据",
        ),
    )


def downgrade() -> None:
    op.drop_column("skills", "toolkit_meta")
    op.drop_column("skills", "toolkit_content")
