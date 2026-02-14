"""drop old skill fields (script_content, script_language) and skill_scripts table

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-02-14

After data migration converted all HTTP/Email/Code/Script skills to Toolkit,
the old fields and SkillScript table are no longer needed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop old script fields from skills table
    op.drop_column("skills", "script_content")
    op.drop_column("skills", "script_language")

    # Drop skill_scripts table
    op.drop_table("skill_scripts")


def downgrade() -> None:
    # Recreate skill_scripts table
    op.create_table(
        "skill_scripts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("language", sa.String(20), nullable=False, server_default="python"),
        sa.Column("is_entry", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_skill_scripts_skill_id", "skill_scripts", ["skill_id"])
    op.create_index("ix_skill_scripts_skill_entry", "skill_scripts", ["skill_id", "is_entry"])
    op.create_index("ix_skill_scripts_skill_sort", "skill_scripts", ["skill_id", "sort_order"])

    # Recreate old script fields on skills table
    op.add_column("skills", sa.Column("script_content", sa.Text(), nullable=True))
    op.add_column("skills", sa.Column("script_language", sa.String(20), nullable=True))
