"""Cleanup legacy page-awareness skill grants."""

from __future__ import annotations

from alembic import op
from sqlalchemy import MetaData, Table, bindparam, func, inspect, or_, select

revision: str = "20260410_cleanup_legacy_grants"
down_revision: str | None = "20260409_ui_runtime_page_tools"
branch_labels: str | None = None
depends_on: str | None = None

LEGACY_SKILL_NAMES = (
    "get_page_context",
    "invoke_page_operation",
    "list_page_operations",
    "page_ops",
)
LEGACY_SKILL_PREFIXES = ("pageop_",)


def _reflect_table(conn, table_name: str) -> Table:
    return Table(table_name, MetaData(), autoload_with=conn)


def _table_columns(conn, table_name: str) -> set[str]:
    inspector = inspect(conn)
    if not inspector.has_table(table_name):
        return set()
    return {str(column["name"]) for column in inspector.get_columns(table_name)}


def _legacy_skill_ids(conn, skills_table: Table) -> list[int]:
    predicates = [skills_table.c.name.in_(bindparam("legacy_names", expanding=True))]
    params = {"legacy_names": list(LEGACY_SKILL_NAMES)}
    for idx, prefix in enumerate(LEGACY_SKILL_PREFIXES):
        key = f"legacy_prefix_{idx}"
        predicates.append(skills_table.c.name.like(bindparam(key)))
        params[key] = f"{prefix}%"

    stmt = select(skills_table.c.id).where(or_(*predicates))
    rows = conn.execute(stmt, params).fetchall()
    return [int(row[0]) for row in rows]


def _soft_delete_legacy_grants(
    conn,
    agent_skill_grants: Table,
    legacy_skill_ids: list[int],
) -> None:
    if not legacy_skill_ids:
        return

    values: dict[str, object] = {}
    columns = set(agent_skill_grants.c.keys())
    if "is_deleted" in columns:
        values["is_deleted"] = True
    if "deleted_at" in columns:
        values["deleted_at"] = func.coalesce(
            agent_skill_grants.c.deleted_at,
            func.now(),
        )
    if "enabled" in columns:
        values["enabled"] = False
    if "updated_at" in columns:
        values["updated_at"] = func.now()
    if not values:
        return

    stmt = (
        agent_skill_grants.update()
        .where(agent_skill_grants.c.skill_id.in_(legacy_skill_ids))
        .values(**values)
    )
    conn.execute(stmt)


def upgrade() -> None:
    conn = op.get_bind()
    skill_columns = _table_columns(conn, "skills")
    grant_columns = _table_columns(conn, "agent_skill_grants")
    if not skill_columns or "id" not in skill_columns or "name" not in skill_columns:
        return
    if not grant_columns or "skill_id" not in grant_columns:
        return

    skills_table = _reflect_table(conn, "skills")
    legacy_ids = _legacy_skill_ids(conn, skills_table)
    if not legacy_ids:
        return

    agent_skill_table = _reflect_table(conn, "agent_skill_grants")
    _soft_delete_legacy_grants(conn, agent_skill_table, legacy_ids)


def downgrade() -> None:
    # New-system boundary: retired page grants must not be restored.
    pass
