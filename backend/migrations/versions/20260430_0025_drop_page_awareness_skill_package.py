"""drop page awareness skill package

Revision ID: 20260430_0025_drop_page_skill
Revises: 20260430_0024_retire_page_skill
Create Date: 2026-04-30

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import MetaData, Table, bindparam, inspect, or_, select

revision: str = "20260430_0025_drop_page_skill"
down_revision: str | Sequence[str] | None = "20260430_0024_retire_page_skill"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PAGE_AWARENESS_PACKAGE_NAME = "页面感知交互"
PAGE_AWARENESS_TOOL_NAMES = (
    "editor_ops",
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
)
PAGE_AWARENESS_TOOL_PREFIX = "pageop_"


def _table_columns(conn, table_name: str) -> set[str]:
    inspector = inspect(conn)
    if not inspector.has_table(table_name):
        return set()
    return {
        str(column["name"])
        for column in inspector.get_columns(table_name)
        if column.get("name")
    }


def _reflect_table(conn, table_name: str) -> Table | None:
    if not _table_columns(conn, table_name):
        return None
    return Table(table_name, MetaData(), autoload_with=conn)


def _fetch_ids(conn, stmt, params: dict[str, object]) -> list[int]:
    return [int(row[0]) for row in conn.execute(stmt, params).fetchall()]


def _page_package_ids(conn) -> list[int]:
    columns = _table_columns(conn, "skill_packages")
    if not {"id", "name"}.issubset(columns):
        return []
    skill_packages = _reflect_table(conn, "skill_packages")
    if skill_packages is None:
        return []
    return _fetch_ids(
        conn,
        select(skill_packages.c.id)
        .where(skill_packages.c.name == bindparam("package_name"))
        .order_by(skill_packages.c.id),
        {"package_name": PAGE_AWARENESS_PACKAGE_NAME},
    )


def _page_skill_ids(conn, package_ids: list[int]) -> list[int]:
    columns = _table_columns(conn, "skills")
    if not {"id", "name"}.issubset(columns):
        return []
    skills = _reflect_table(conn, "skills")
    if skills is None:
        return []

    predicates = [
        skills.c.name.in_(bindparam("tool_names", expanding=True)),
        skills.c.name.like(bindparam("tool_prefix")),
    ]
    params: dict[str, object] = {
        "tool_names": list(PAGE_AWARENESS_TOOL_NAMES),
        "tool_prefix": f"{PAGE_AWARENESS_TOOL_PREFIX}%",
    }
    if package_ids and "package_id" in columns:
        predicates.append(skills.c.package_id.in_(bindparam("package_ids", expanding=True)))
        params["package_ids"] = package_ids

    return _fetch_ids(
        conn,
        select(skills.c.id).where(or_(*predicates)).order_by(skills.c.id),
        params,
    )


def _page_capability_ids(conn) -> list[int]:
    columns = _table_columns(conn, "capabilities")
    if "id" not in columns:
        return []
    capabilities = _reflect_table(conn, "capabilities")
    if capabilities is None:
        return []

    predicates = []
    params: dict[str, object] = {
        "tool_names": list(PAGE_AWARENESS_TOOL_NAMES),
        "tool_prefix": f"{PAGE_AWARENESS_TOOL_PREFIX}%",
    }
    if "key" in columns:
        predicates.extend(
            [
                capabilities.c.key.in_(bindparam("tool_names", expanding=True)),
                capabilities.c.key.like(bindparam("tool_prefix")),
            ]
        )
    if "executor_ref" in columns:
        predicates.extend(
            [
                capabilities.c.executor_ref.in_(
                    bindparam("executor_tool_names", expanding=True)
                ),
                capabilities.c.executor_ref.like(bindparam("executor_tool_prefix")),
            ]
        )
        params["executor_tool_names"] = list(PAGE_AWARENESS_TOOL_NAMES)
        params["executor_tool_prefix"] = f"{PAGE_AWARENESS_TOOL_PREFIX}%"
    if not predicates:
        return []
    return _fetch_ids(
        conn,
        select(capabilities.c.id).where(or_(*predicates)).order_by(capabilities.c.id),
        params,
    )


def _delete_by_ids(conn, table_name: str, column_name: str, ids: list[int]) -> None:
    if not ids:
        return
    columns = _table_columns(conn, table_name)
    if column_name not in columns:
        return
    table = _reflect_table(conn, table_name)
    if table is None:
        return
    stmt = table.delete().where(
        table.c[column_name].in_(bindparam("target_ids", expanding=True))
    )
    conn.execute(stmt, {"target_ids": ids})


def _delete_legacy_agent_skill_bindings(
    conn,
    *,
    package_ids: list[int],
    skill_ids: list[int],
) -> None:
    columns = _table_columns(conn, "agent_skill_bindings")
    if not columns:
        return
    agent_skill_bindings = _reflect_table(conn, "agent_skill_bindings")
    if agent_skill_bindings is None:
        return

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

    conn.execute(agent_skill_bindings.delete().where(or_(*predicates)), params)


def upgrade() -> None:
    conn = op.get_bind()
    package_ids = _page_package_ids(conn)
    skill_ids = _page_skill_ids(conn, package_ids)
    capability_ids = _page_capability_ids(conn)

    _delete_by_ids(conn, "agent_skill_grants", "skill_id", skill_ids)
    _delete_legacy_agent_skill_bindings(
        conn,
        package_ids=package_ids,
        skill_ids=skill_ids,
    )
    _delete_by_ids(conn, "skill_resources", "skill_id", skill_ids)
    _delete_by_ids(conn, "skill_capability_bindings", "skill_id", skill_ids)
    _delete_by_ids(
        conn,
        "skill_capability_bindings",
        "capability_id",
        capability_ids,
    )
    _delete_by_ids(conn, "capabilities", "id", capability_ids)
    _delete_by_ids(conn, "skills", "id", skill_ids)
    _delete_by_ids(conn, "skill_packages", "id", package_ids)


def downgrade() -> None:
    # New-system boundary: page awareness must not be restored by downgrade.
    # 新系统边界：页面感知不再通过 downgrade 恢复。
    pass
