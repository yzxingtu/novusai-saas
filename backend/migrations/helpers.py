"""
Alembic migration helpers — idempotent operations for tables with unique constraints.

Usage in a migration file:

    from migrations.helpers import safe_rename_permission_resource

    def upgrade() -> None:
        safe_rename_permission_resource("ai_skill_registry", "plugin_skill_registry")
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text


def safe_rename_permission_resource(
    old_resource: str,
    new_resource: str,
    *,
    old_menu_key: str | None = None,
    new_menu_key: str | None = None,
) -> None:
    """Rename a permission resource idempotently.

    Handles the case where ``@permission_resource`` auto-seeding has already
    created rows with *new_resource* before this migration runs (the common
    scenario when the code is deployed before the migration executes).

    Steps:
      1. Delete old rows whose new equivalents already exist (avoids UniqueViolation).
      2. Rename any remaining old rows to the new resource name.

    Parameters
    ----------
    old_resource:
        Current resource prefix in ``permissions.code``, e.g. ``"ai_skill_registry"``.
    new_resource:
        Target resource prefix, e.g. ``"plugin_skill_registry"``.
    old_menu_key:
        Optional old menu i18n key in ``permissions.name``.
        Defaults to ``"menu.admin.{old_resource}"``.
    new_menu_key:
        Optional new menu i18n key.
        Defaults to ``"menu.admin.{new_resource}"``.
    """
    if old_menu_key is None:
        old_menu_key = f"menu.admin.{old_resource}"
    if new_menu_key is None:
        new_menu_key = f"menu.admin.{new_resource}"

    conn = op.get_bind()

    conn.execute(
        text(
            "DELETE FROM permissions "
            "WHERE code LIKE :old_pattern "
            "AND EXISTS ("
            "  SELECT 1 FROM permissions p2 "
            "  WHERE p2.code = REPLACE(permissions.code, :old_res, :new_res) "
            "  AND p2.scope = permissions.scope"
            ")"
        ).bindparams(
            old_pattern=f"%{old_resource}%",
            old_res=old_resource,
            new_res=new_resource,
        )
    )

    conn.execute(
        text(
            "UPDATE permissions SET "
            "code = REPLACE(code, :old_res, :new_res), "
            "name = REPLACE(name, :old_menu, :new_menu) "
            "WHERE code LIKE :old_pattern"
        ).bindparams(
            old_res=old_resource,
            new_res=new_resource,
            old_menu=old_menu_key,
            new_menu=new_menu_key,
            old_pattern=f"%{old_resource}%",
        )
    )


def safe_rename_unique_column_value(
    table: str,
    column: str,
    old_value: str,
    new_value: str,
    *,
    unique_columns: list[str] | None = None,
) -> None:
    """Rename a value in a column that participates in a unique constraint.

    Handles pre-existing rows with *new_value* by deleting old rows first
    (only when new equivalents already exist).

    .. note::

       SQL identifiers (table/column names) are interpolated via f-string
       because PostgreSQL ``text()`` bind parameters only support *values*,
       not *identifiers*.  All identifier arguments originate from migration
       developers as hardcoded string literals — never from user input — so
       there is no injection risk.  ``# noqa: S608`` markers acknowledge this.

    Parameters
    ----------
    table:
        Table name.
    column:
        Column whose value is being renamed.
    old_value:
        Substring to find (uses LIKE + REPLACE).
    new_value:
        Substring to replace with.
    unique_columns:
        Other columns that participate in the unique constraint alongside
        *column*.  Used to match "equivalent" rows.  If ``None``, only
        *column* is compared (simple unique).
    """
    conn = op.get_bind()

    if unique_columns:
        scope_match = " AND ".join(
            f"p2.{c} = {table}.{c}" for c in unique_columns
        )
    else:
        scope_match = "1 = 1"

    conn.execute(
        text(
            f"DELETE FROM {table} "  # noqa: S608 — table name is caller-controlled
            f"WHERE {column} LIKE :old_pattern "
            f"AND EXISTS ("
            f"  SELECT 1 FROM {table} p2 "
            f"  WHERE p2.{column} = REPLACE({table}.{column}, :old_val, :new_val) "
            f"  AND {scope_match}"
            f")"
        ).bindparams(
            old_pattern=f"%{old_value}%",
            old_val=old_value,
            new_val=new_value,
        )
    )

    conn.execute(
        text(
            f"UPDATE {table} SET "  # noqa: S608
            f"{column} = REPLACE({column}, :old_val, :new_val) "
            f"WHERE {column} LIKE :old_pattern"
        ).bindparams(
            old_val=old_value,
            new_val=new_value,
            old_pattern=f"%{old_value}%",
        )
    )
