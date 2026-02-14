"""drop orphaned tool_definitions table

The tool_definitions table was replaced by the skills table in the
Tool → Skill architecture migration (20260213_data_migrate_tools_to_skills).
The ORM model was deleted but the table was never dropped.

Revision ID: cc0215005000
Revises: bb0215004500
Create Date: 2026-02-15 01:22:00.000000+08:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "cc0215005000"
down_revision: Union[str, None] = "bb0215004500"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Clean up any ai_table_policies rows referencing tool_definitions
    conn.execute(sa.text(
        "DELETE FROM ai_table_policies WHERE table_name = 'tool_definitions'"
    ))
    conn.execute(sa.text(
        "DELETE FROM ai_table_policy_overrides "
        "WHERE policy_id NOT IN (SELECT id FROM ai_table_policies)"
    ))

    # Drop the orphaned table (IF EXISTS — may have been dropped manually)
    conn.execute(sa.text("DROP TABLE IF EXISTS tool_definitions CASCADE"))


def downgrade() -> None:
    # Recreate tool_definitions table (empty — data was migrated to skills)
    op.create_table(
        "tool_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("input_schema", postgresql.JSON(), nullable=True),
        sa.Column("output_schema", postgresql.JSON(), nullable=True),
        sa.Column("config", postgresql.JSON(), nullable=True),
        sa.Column("timeout", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delete_level", sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_definitions_tenant_id", "tool_definitions", ["tenant_id"])
    op.create_index("ix_tool_definitions_name", "tool_definitions", ["name"])
    op.create_index("ix_tool_definitions_type", "tool_definitions", ["type"])
    op.create_index("ix_tool_definitions_is_system", "tool_definitions", ["is_system"])
    op.create_index("ix_tool_definitions_is_deleted", "tool_definitions", ["is_deleted"])
