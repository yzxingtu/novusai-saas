"""Cleanup legacy page-awareness skill grants / Ensure UI runtime skills bound."""

from __future__ import annotations

from alembic import op
from sqlalchemy import MetaData, Table, and_, bindparam, func, inspect, or_, select

revision: str = "20260410_cleanup_legacy_grants"
down_revision: str | None = "20260409_ui_runtime_page_tools"
branch_labels: str | None = None
depends_on: str | None = None

LEGACY_SKILL_NAMES = ("get_page_context", "invoke_page_operation")
LEGACY_SKILL_PREFIXES = ("pageop_",)
UI_RUNTIME_SKILL_NAMES = (
    "ui_get_snapshot",
    "ui_read_region",
    "ui_read_table",
    "ui_list_interactables",
    "ui_click",
    "ui_open_surface",
    "ui_get_form_state",
    "ui_set_field",
    "ui_fill_form",
    "ui_submit_form",
)


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


def _ui_skill_ids(conn, skills_table: Table) -> list[int]:
    stmt = select(skills_table.c.id).where(skills_table.c.name.in_(bindparam("ui_names", expanding=True)))
    rows = conn.execute(stmt, {"ui_names": list(UI_RUNTIME_SKILL_NAMES)}).fetchall()
    return [int(row[0]) for row in rows]


def _agent_rows_to_fix(conn, agent_skill_grants: Table, agents: Table, legacy_skill_ids: list[int]) -> list[dict[str, object]]:
    stmt = (
        select(agent_skill_grants.c.agent_id, agents.c.owner_tenant_id)
        .select_from(
            agent_skill_grants.join(agents, agents.c.id == agent_skill_grants.c.agent_id)
        )
        .where(
            agent_skill_grants.c.skill_id.in_(legacy_skill_ids),
            agent_skill_grants.c.is_deleted.is_(False),
        )
        .distinct()
    )
    rows = conn.execute(stmt).fetchall()
    return [
        {"agent_id": int(row[0]), "owner_tenant_id": row[1]}
        for row in rows
    ]


def _soft_delete_legacy_grants(conn, agent_skill_grants: Table, legacy_skill_ids: list[int]) -> None:
    if not legacy_skill_ids:
        return
    stmt = (
        agent_skill_grants.update()
        .where(agent_skill_grants.c.skill_id.in_(legacy_skill_ids))
        .where(agent_skill_grants.c.is_deleted.is_(False))
        .values(
            is_deleted=True,
            deleted_at=func.coalesce(agent_skill_grants.c.deleted_at, func.now()),
            enabled=False,
        )
    )
    conn.execute(stmt)


def _ensure_ui_grants(
    conn,
    agent_skill_grants: Table,
    agents_table: Table,
    agent_rows: list[dict[str, object]],
    ui_skill_ids: list[int],
) -> None:
    if not ui_skill_ids or not agent_rows:
        return

    for agent in agent_rows:
        agent_id = agent["agent_id"]
        tenant_id = agent["owner_tenant_id"]

        max_sort = (
            conn.execute(
                select(func.coalesce(func.max(agent_skill_grants.c.sort_order), -1)).where(
                    agent_skill_grants.c.agent_id == agent_id
                )
            )
            .scalar_one()
        )
        next_sort = max_sort + 1

        for skill_id in ui_skill_ids:
            exists = conn.execute(
                select(
                    agent_skill_grants.c.id,
                    agent_skill_grants.c.is_deleted,
                    agent_skill_grants.c.sort_order,
                )
                .where(agent_skill_grants.c.agent_id == agent_id)
                .where(agent_skill_grants.c.skill_id == skill_id)
            ).fetchone()

            if exists:
                grant_id, deleted, _ = exists
                if deleted:
                    conn.execute(
                        agent_skill_grants.update()
                        .where(agent_skill_grants.c.id == grant_id)
                        .values(
                            is_deleted=False,
                            deleted_at=None,
                            enabled=True,
                            default_consent_mode="auto",
                            sort_order=next_sort,
                        )
                    )
                    next_sort += 1
                continue

            values = {
                "agent_id": agent_id,
                "skill_id": skill_id,
                "tenant_id": tenant_id,
                "enabled": True,
                "sort_order": next_sort,
                "default_consent_mode": "auto",
            }
            conn.execute(agent_skill_grants.insert().values(**values))
            next_sort += 1


def upgrade() -> None:
    conn = op.get_bind()
    columns = _table_columns(conn, "skills")
    if not columns:
        return
    skills_table = _reflect_table(conn, "skills")
    legacy_ids = _legacy_skill_ids(conn, skills_table)
    if not legacy_ids:
        return
    ui_ids = _ui_skill_ids(conn, skills_table)
    agent_skill_table = _reflect_table(conn, "agent_skill_grants")
    agents_table = _reflect_table(conn, "agents")
    agent_rows = _agent_rows_to_fix(conn, agent_skill_table, agents_table, legacy_ids)
    if not agent_rows:
        return

    _soft_delete_legacy_grants(conn, agent_skill_table, legacy_ids)
    _ensure_ui_grants(conn, agent_skill_table, agents_table, agent_rows, ui_ids)


def downgrade() -> None:
    pass
