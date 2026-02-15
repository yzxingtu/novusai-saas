"""fix_crud_generator_skill_tools

Update crud_generator skill config and input_schema to align with
CrudGeneratorExecutor._DISPATCH (13 tools).

Problem:
  - config has 8 old tool names (suggest_fields, suggest_enums, etc.)
    that don't match Executor._DISPATCH keys (crud_suggest_fields, etc.)
  - input_schema is NULL (should contain multi_tool format with 13 tools)

Fix:
  - config → {"builtin_type": "crud_generator", "dev_only": true}
  - input_schema → build_skill_input_schema() (13 tools, multi_tool format)

Revision ID: aa0215010000
Revises: dd0215006000
Create Date: 2026-02-15 05:50:00.000000+08:00

"""
from typing import Sequence, Union

import json

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "aa0215010000"
down_revision: Union[str, None] = "dd0215006000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_CONFIG = {
    "builtin_type": "crud_generator",
    "dev_only": True,
}


def _get_input_schema() -> dict:
    """Build input_schema from skill_definitions (lazy import)."""
    from app.codegen.skill_definitions import build_skill_input_schema
    return build_skill_input_schema()


def upgrade() -> None:
    conn = op.get_bind()

    # Find the crud_generator skill
    row = conn.execute(text(
        "SELECT id, config, input_schema "
        "FROM skills "
        "WHERE name = 'crud_generator' AND is_deleted = false "
        "LIMIT 1"
    )).fetchone()

    if not row:
        print("[FIX] No crud_generator skill found, skipping.")
        return

    skill_id = row[0]
    old_config = row[1]
    old_input_schema = row[2]

    # Check if config has old tool_type format (needs fix)
    needs_config_fix = (
        isinstance(old_config, dict)
        and "tools" in old_config
        and "tool_type" in old_config
    )

    # Check if input_schema is NULL or missing tools
    needs_schema_fix = (
        old_input_schema is None
        or not isinstance(old_input_schema, dict)
        or not old_input_schema.get("multi_tool")
    )

    if not needs_config_fix and not needs_schema_fix:
        print(f"[FIX] Skill id={skill_id} already has correct config and input_schema, skipping.")
        return

    input_schema = _get_input_schema()
    tool_names = list(input_schema.get("tools", {}).keys())

    conn.execute(text(
        "UPDATE skills SET "
        "config = CAST(:config AS jsonb), "
        "input_schema = CAST(:input_schema AS jsonb), "
        "updated_at = NOW() "
        "WHERE id = :id"
    ), {
        "id": skill_id,
        "config": json.dumps(_NEW_CONFIG),
        "input_schema": json.dumps(input_schema),
    })

    print(
        f"[FIX] Updated skill id={skill_id}: "
        f"config={json.dumps(_NEW_CONFIG)}, "
        f"input_schema tools={tool_names} ({len(tool_names)} tools)"
    )


def downgrade() -> None:
    # No safe downgrade — old config format is broken anyway
    pass
