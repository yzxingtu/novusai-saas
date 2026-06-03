"""中文: 同步插件技能运行状态。

EN: Synchronize plugin skill runtime status.

Revision ID: 20260509_0039_skill_status
Revises: 20260509_0038_admin_actionlog
Create Date: 2026-05-09

"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260509_0039_skill_status"
down_revision: str | Sequence[str] | None = "20260509_0038_admin_actionlog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _columns(bind: sa.Connection, table_name: str) -> set[str]:
    if not _has_table(bind, table_name):
        return set()
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _table(table_name: str, columns: set[str]) -> sa.TableClause:
    typed_columns: dict[str, Any] = {
        "id": sa.Integer(),
        "package_id": sa.Integer(),
        "source_plugin": sa.String(),
        "source_type": sa.String(),
        "status": sa.String(),
        "is_active": sa.Boolean(),
        "is_deleted": sa.Boolean(),
        "updated_at": sa.DateTime(timezone=True),
    }
    return sa.table(
        table_name,
        *(sa.column(name, typed_columns.get(name)) for name in columns),
    )


def _status_values(columns: set[str]) -> dict[str, Any]:
    values: dict[str, Any] = {"status": "active"}
    if "updated_at" in columns:
        values["updated_at"] = sa.func.now()
    return values


def _disabled_values(columns: set[str]) -> dict[str, Any]:
    values: dict[str, Any] = {"status": "disabled"}
    if "updated_at" in columns:
        values["updated_at"] = sa.func.now()
    return values


def upgrade() -> None:
    bind = op.get_bind()
    package_columns = _columns(bind, "skill_packages")
    skill_columns = _columns(bind, "skills")
    required_package_columns = {"id", "source_plugin", "is_active", "is_deleted"}
    required_skill_columns = {
        "package_id",
        "source_type",
        "status",
        "is_active",
        "is_deleted",
    }
    if not (
        required_package_columns.issubset(package_columns)
        and required_skill_columns.issubset(skill_columns)
    ):
        return

    packages = _table("skill_packages", package_columns)
    skills = _table("skills", skill_columns)
    plugin_package_clause = (
        packages.c.source_plugin.is_not(None),
        packages.c.source_plugin != "",
        packages.c.is_deleted.is_(False),
    )
    plugin_skill_clause = (
        skills.c.package_id == packages.c.id,
        skills.c.source_type == "plugin",
        skills.c.is_deleted.is_(False),
    )

    bind.execute(
        sa.update(skills)
        .where(
            *plugin_package_clause,
            *plugin_skill_clause,
            packages.c.is_active.is_(True),
            skills.c.is_active.is_(True),
            skills.c.status != "active",
        )
        .values(**_status_values(skill_columns))
    )
    bind.execute(
        sa.update(skills)
        .where(
            *plugin_package_clause,
            *plugin_skill_clause,
            sa.or_(
                packages.c.is_active.is_(False),
                skills.c.is_active.is_(False),
            ),
            skills.c.status != "disabled",
        )
        .values(**_disabled_values(skill_columns))
    )


def downgrade() -> None:
    pass
