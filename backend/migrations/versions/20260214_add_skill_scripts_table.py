"""add skill_scripts table and migrate existing script_content data

Creates the skill_scripts table for multi-script support per skill.
Migrates existing Skill.script_content data into SkillScript records.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-02-14 06:00:00.000000+08:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "00db1351b7c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create skill_scripts table
    op.create_table(
        "skill_scripts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("language", sa.String(20), nullable=False, server_default="python"),
        sa.Column("is_entry", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_skill_scripts_skill_id", "skill_scripts", ["skill_id"])
    op.create_index("ix_skill_scripts_skill_entry", "skill_scripts", ["skill_id", "is_entry"])
    op.create_index("ix_skill_scripts_skill_sort", "skill_scripts", ["skill_id", "sort_order"])

    # 2. Migrate existing script_content data to skill_scripts
    conn = op.get_bind()
    results = conn.execute(
        sa.text(
            "SELECT id, script_content, script_language "
            "FROM skills "
            "WHERE script_content IS NOT NULL AND script_content != '' "
            "AND type = 'script' AND is_deleted = false"
        )
    ).fetchall()

    for row in results:
        skill_id = row[0]
        content = row[1]
        language = row[2] or "python"
        ext = ".py" if language == "python" else f".{language}"
        filename = f"main{ext}"

        conn.execute(
            sa.text(
                "INSERT INTO skill_scripts (skill_id, filename, content, language, is_entry, sort_order, is_deleted) "
                "VALUES (:skill_id, :filename, :content, :language, true, 0, false)"
            ),
            {
                "skill_id": skill_id,
                "filename": filename,
                "content": content,
                "language": language,
            },
        )


def downgrade() -> None:
    # Copy entry scripts back to skills.script_content
    conn = op.get_bind()
    results = conn.execute(
        sa.text(
            "SELECT skill_id, content, language "
            "FROM skill_scripts "
            "WHERE is_entry = true AND is_deleted = false"
        )
    ).fetchall()

    for row in results:
        conn.execute(
            sa.text(
                "UPDATE skills SET script_content = :content, script_language = :language "
                "WHERE id = :skill_id"
            ),
            {"content": row[1], "language": row[2], "skill_id": row[0]},
        )

    op.drop_index("ix_skill_scripts_skill_sort", table_name="skill_scripts")
    op.drop_index("ix_skill_scripts_skill_entry", table_name="skill_scripts")
    op.drop_index("ix_skill_scripts_skill_id", table_name="skill_scripts")
    op.drop_table("skill_scripts")
