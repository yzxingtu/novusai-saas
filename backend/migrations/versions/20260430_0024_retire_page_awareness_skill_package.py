"""retire page awareness skill package

Revision ID: 20260430_0024_retire_page_skill
Revises: 20260430_0023_kb_scope_owner
Create Date: 2026-04-30

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import MetaData, Table, bindparam, func, inspect, or_, select

revision: str = "20260430_0024_retire_page_skill"
down_revision: str | Sequence[str] | None = "20260430_0023_kb_scope_owner"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PAGE_AWARENESS_PACKAGE_NAME = "页面感知交互"
PAGE_AWARENESS_PACKAGE_SKILL_NAMES = (
    "append_content",
    "editor_ops",
    "get_editor_html",
    "get_editor_text",
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
    "get_page_context",
    "insert_content",
    "invoke_page_operation",
    "list_page_operations",
    "page_ops",
    "replace_content",
    "replace_section",
)
PAGE_AWARENESS_GLOBAL_SKILL_NAMES = (
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
    "get_page_context",
    "invoke_page_operation",
    "list_page_operations",
    "page_ops",
)
PAGE_AWARENESS_GLOBAL_SKILL_PREFIXES = ("pageop_",)


def _table_columns(conn, table_name: str) -> set[str]:
    inspector = inspect(conn)
    if not inspector.has_table(table_name):
        return set()
    return {
        str(column["name"])
        for column in inspector.get_columns(table_name)
        if column.get("name")
    }


def _reflect_table(conn, table_name: str) -> Table:
    return Table(table_name, MetaData(), autoload_with=conn)


def _soft_delete_values(table: Table, columns: set[str]) -> dict[str, object]:
    values: dict[str, object] = {}
    if "is_active" in columns:
        values["is_active"] = False
    if "is_recommended" in columns:
        values["is_recommended"] = False
    if "enabled" in columns:
        values["enabled"] = False
    if "is_deleted" in columns:
        values["is_deleted"] = True
    if "deleted_at" in columns:
        values["deleted_at"] = func.coalesce(table.c.deleted_at, func.now())
    if "delete_level" in columns:
        values["delete_level"] = "admin"
    if "recycle_stage" in columns:
        values["recycle_stage"] = "module"
    if "promoted_to_global_at" in columns:
        values["promoted_to_global_at"] = None
    if "updated_at" in columns:
        values["updated_at"] = func.now()
    return values


def _page_package_ids(conn) -> list[int]:
    columns = _table_columns(conn, "skill_packages")
    if not columns or "id" not in columns or "name" not in columns:
        return []

    skill_packages = _reflect_table(conn, "skill_packages")
    stmt = (
        select(skill_packages.c.id)
        .where(skill_packages.c.name == bindparam("package_name"))
        .order_by(skill_packages.c.id)
    )
    rows = conn.execute(
        stmt,
        {"package_name": PAGE_AWARENESS_PACKAGE_NAME},
    ).fetchall()
    return [int(row[0]) for row in rows]


def _page_skill_ids(conn, package_ids: list[int]) -> list[int]:
    columns = _table_columns(conn, "skills")
    if not columns or "id" not in columns or "name" not in columns:
        return []

    skills = _reflect_table(conn, "skills")
    predicates = [
        skills.c.name.in_(bindparam("global_skill_names", expanding=True))
    ]
    params: dict[str, object] = {
        "global_skill_names": list(PAGE_AWARENESS_GLOBAL_SKILL_NAMES),
    }

    for idx, prefix in enumerate(PAGE_AWARENESS_GLOBAL_SKILL_PREFIXES):
        param_name = f"skill_prefix_{idx}"
        predicates.append(skills.c.name.like(bindparam(param_name)))
        params[param_name] = f"{prefix}%"

    if package_ids and "package_id" in columns:
        predicates.append(
            skills.c.package_id.in_(bindparam("package_ids", expanding=True))
        )
        params["package_ids"] = package_ids

    stmt = select(skills.c.id).where(or_(*predicates)).order_by(skills.c.id)
    rows = conn.execute(stmt, params).fetchall()
    return [int(row[0]) for row in rows]


def _retire_agent_skill_grants(conn, skill_ids: list[int]) -> None:
    if not skill_ids:
        return
    columns = _table_columns(conn, "agent_skill_grants")
    if not columns or "skill_id" not in columns:
        return

    agent_skill_grants = _reflect_table(conn, "agent_skill_grants")
    values = _soft_delete_values(agent_skill_grants, columns)
    if not values:
        return

    stmt = (
        agent_skill_grants.update()
        .where(agent_skill_grants.c.skill_id.in_(bindparam("skill_ids", expanding=True)))
        .values(**values)
    )
    conn.execute(stmt, {"skill_ids": skill_ids})


def _retire_legacy_agent_skill_bindings(
    conn,
    *,
    package_ids: list[int],
    skill_ids: list[int],
) -> None:
    columns = _table_columns(conn, "agent_skill_bindings")
    if not columns:
        return

    agent_skill_bindings = _reflect_table(conn, "agent_skill_bindings")
    predicates = []
    params: dict[str, object] = {}
    if skill_ids and "skill_id" in columns:
        predicates.append(
            agent_skill_bindings.c.skill_id.in_(
                bindparam("binding_skill_ids", expanding=True)
            )
        )
        params["binding_skill_ids"] = skill_ids
    if package_ids and "package_id" in columns:
        predicates.append(
            agent_skill_bindings.c.package_id.in_(
                bindparam("binding_package_ids", expanding=True)
            )
        )
        params["binding_package_ids"] = package_ids
    if not predicates:
        return

    values = _soft_delete_values(agent_skill_bindings, columns)
    if not values:
        return

    stmt = agent_skill_bindings.update().where(or_(*predicates)).values(**values)
    conn.execute(stmt, params)


def _retire_skills(conn, package_ids: list[int]) -> list[int]:
    skill_ids = _page_skill_ids(conn, package_ids)
    columns = _table_columns(conn, "skills")
    if not columns or "id" not in columns:
        return skill_ids

    skills = _reflect_table(conn, "skills")
    values = _soft_delete_values(skills, columns)
    if not values or not skill_ids:
        return skill_ids

    stmt = (
        skills.update()
        .where(skills.c.id.in_(bindparam("skill_ids", expanding=True)))
        .values(**values)
    )
    conn.execute(stmt, {"skill_ids": skill_ids})
    return skill_ids


def _retire_packages(conn, package_ids: list[int]) -> None:
    columns = _table_columns(conn, "skill_packages")
    if not columns or "id" not in columns or not package_ids:
        return

    skill_packages = _reflect_table(conn, "skill_packages")
    values = _soft_delete_values(skill_packages, columns)
    if not values:
        return

    stmt = (
        skill_packages.update()
        .where(skill_packages.c.id.in_(bindparam("package_ids", expanding=True)))
        .values(**values)
    )
    conn.execute(stmt, {"package_ids": package_ids})


def upgrade() -> None:
    conn = op.get_bind()
    package_ids = _page_package_ids(conn)
    skill_ids = _retire_skills(conn, package_ids)
    _retire_agent_skill_grants(conn, skill_ids)
    _retire_legacy_agent_skill_bindings(
        conn,
        package_ids=package_ids,
        skill_ids=skill_ids,
    )
    _retire_packages(conn, package_ids)


def downgrade() -> None:
    # New-system boundary: page awareness must not be restored by downgrade.
    # 新系统边界：页面感知不再通过 downgrade 恢复。
    pass
