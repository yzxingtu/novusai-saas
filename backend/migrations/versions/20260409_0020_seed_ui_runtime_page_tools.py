"""retire legacy page awareness tools without seeding UI runtime tools

Revision ID: 20260409_ui_runtime_page_tools
Revises: 20260405_log_identity_snapshots
Create Date: 2026-04-09
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import MetaData, Table, and_, bindparam, func, inspect, or_

revision: str = "20260409_ui_runtime_page_tools"
down_revision: str | Sequence[str] | None = "20260405_log_identity_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_SKILL_NAMES = (
    "get_page_context",
    "invoke_page_operation",
    "list_page_operations",
    "page_ops",
)
LEGACY_SKILL_PREFIXES = ("pageop_",)


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


def _soft_delete_legacy_skills(conn) -> None:
    columns = _table_columns(conn, "skills")
    if not columns or "name" not in columns:
        return

    skills = _reflect_table(conn, "skills")
    values: dict[str, object] = {}
    if "is_active" in columns:
        values["is_active"] = False
    if "is_deleted" in columns:
        values["is_deleted"] = True
    if "updated_at" in columns:
        values["updated_at"] = func.now()
    if "deleted_at" in columns and "is_deleted" in columns:
        values["deleted_at"] = func.coalesce(skills.c.deleted_at, func.now())

    if not values:
        return

    legacy_predicates = [
        skills.c.name.in_(bindparam("legacy_names", expanding=True))
    ]
    prefix_params: dict[str, object] = {}
    for idx, prefix in enumerate(LEGACY_SKILL_PREFIXES):
        param_name = f"legacy_prefix_{idx}"
        legacy_predicates.append(skills.c.name.like(bindparam(param_name)))
        prefix_params[param_name] = f"{prefix}%"

    where_clauses = [or_(*legacy_predicates)]
    if "type" in columns:
        where_clauses.append(skills.c.type == "builtin")
    if "tenant_id" in columns:
        where_clauses.append(skills.c.tenant_id.is_(None))

    stmt = skills.update().where(and_(*where_clauses)).values(**values)
    conn.execute(
        stmt,
        {
            "legacy_names": list(LEGACY_SKILL_NAMES),
            **prefix_params,
        },
    )


def upgrade() -> None:
    _soft_delete_legacy_skills(op.get_bind())


def downgrade() -> None:
    # New-system boundary: retired page tools must not be restored.
    pass
