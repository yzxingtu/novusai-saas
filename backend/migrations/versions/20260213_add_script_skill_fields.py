"""add_script_skill_fields

Add script_content and script_language columns to skills table
for the new script skill type.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-13 23:00:00.000000+08:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "skills",
        sa.Column(
            "script_content",
            sa.Text(),
            nullable=True,
            comment="脚本内容（type=script 时使用）",
        ),
    )
    op.add_column(
        "skills",
        sa.Column(
            "script_language",
            sa.String(20),
            nullable=True,
            comment="脚本语言（python）",
        ),
    )


def downgrade() -> None:
    op.drop_column("skills", "script_language")
    op.drop_column("skills", "script_content")
