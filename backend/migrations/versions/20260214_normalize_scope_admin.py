"""normalize_scope_admin_only_to_admin

Standardize ResourceScopeEnum: rename 'admin_only' → 'admin' in agents and
knowledge_bases tables to align with SkillScopeEnum and architecture rules.

Revision ID: b1c2d3e4f5a6
Revises: a7b8c9d0e1f2
Create Date: 2026-02-14 04:30:00.000000+08:00

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Normalize agents scope
    result = conn.execute(text(
        "UPDATE agents SET scope = 'admin' WHERE scope = 'admin_only'"
    ))
    print(f"[MIGRATE] Updated {result.rowcount} agents: scope 'admin_only' → 'admin'")

    # Normalize knowledge_bases scope
    result = conn.execute(text(
        "UPDATE knowledge_bases SET scope = 'admin' WHERE scope = 'admin_only'"
    ))
    print(f"[MIGRATE] Updated {result.rowcount} knowledge_bases: scope 'admin_only' → 'admin'")


def downgrade() -> None:
    conn = op.get_bind()

    # Revert agents scope
    result = conn.execute(text(
        "UPDATE agents SET scope = 'admin_only' WHERE scope = 'admin'"
    ))
    print(f"[MIGRATE] Reverted {result.rowcount} agents: scope 'admin' → 'admin_only'")

    # Revert knowledge_bases scope
    result = conn.execute(text(
        "UPDATE knowledge_bases SET scope = 'admin_only' WHERE scope = 'admin'"
    ))
    print(f"[MIGRATE] Reverted {result.rowcount} knowledge_bases: scope 'admin' → 'admin_only'")
