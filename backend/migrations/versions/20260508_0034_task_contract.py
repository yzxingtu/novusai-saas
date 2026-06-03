"""中文: 规范化内置周期任务契约。

EN: Canonicalize built-in periodic task contracts.

Revision ID: 20260508_0034_task_contract
Revises: 20260508_0033_retire_search
Create Date: 2026-05-08

"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260508_0034_task_contract"
down_revision: str | Sequence[str] | None = "20260508_0033_retire_search"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_TASK_RUNS_CODE = "task.clean_expired_task_logs.81d841c7"
OLD_TASK_RUNS_HANDLER = "app.tasks.scheduled.clean_expired_task_logs"
TASK_RUNS_CODE = "task.clean_expired_task_runs.81d841c7"
TASK_RUNS_HANDLER = "app.tasks.scheduled.clean_expired_task_runs"

RECYCLE_BIN_CODE = "task.cleanup_recycle_bin.09fba947"
RECYCLE_BIN_HANDLER = "app.tasks.recycle_bin.cleanup_recycle_bin"

NOTIFICATION_CLEANUP_CODE = "task.cleanup_expired_notifications.adf20b24"
NOTIFICATION_CLEANUP_HANDLER = (
    "app.tasks.notification_cleanup.cleanup_expired_notifications"
)


def _has_table(bind: sa.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)


def _columns(bind: sa.Connection, table_name: str) -> set[str]:
    if not _has_table(bind, table_name):
        return set()
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _task_definitions_table(columns: set[str]) -> sa.TableClause:
    typed_columns = {
        "default_kwargs": sa.JSON(),
        "is_enabled": sa.Boolean(),
        "is_deleted": sa.Boolean(),
    }
    return sa.table(
        "task_definitions",
        *(
            sa.column(column_name, typed_columns.get(column_name))
            for column_name in columns
        ),
    )


def _task_bindings_table(columns: set[str]) -> sa.TableClause:
    typed_columns = {
        "kwargs_override": sa.JSON(),
        "is_enabled": sa.Boolean(),
        "is_deleted": sa.Boolean(),
    }
    return sa.table(
        "tenant_task_bindings",
        *(
            sa.column(column_name, typed_columns.get(column_name))
            for column_name in columns
        ),
    )


def _now_value(columns: set[str]) -> dict[str, Any]:
    if "updated_at" not in columns:
        return {}
    return {"updated_at": sa.func.now()}


def _canonical_recycle_kwargs(raw: Any) -> dict[str, int]:
    default_days = 30
    if not isinstance(raw, dict):
        return {
            "module_retention_days": default_days,
            "global_retention_days": default_days,
        }

    if "retention_days" in raw:
        days = raw.get("retention_days") or default_days
        return {
            "module_retention_days": days,
            "global_retention_days": days,
        }

    return {
        "module_retention_days": raw.get("module_retention_days") or default_days,
        "global_retention_days": raw.get("global_retention_days") or default_days,
    }


def _canonical_notification_cleanup_kwargs(raw: Any) -> dict[str, Any]:
    _ = raw
    return {}


def _retire_task_definition_rows(
    bind: sa.Connection,
    task_definitions: sa.TableClause,
    columns: set[str],
    ids: list[int],
) -> None:
    if not ids:
        return
    values: dict[str, Any] = _now_value(columns)
    if "is_enabled" in columns:
        values["is_enabled"] = False
    if "is_deleted" in columns:
        values["is_deleted"] = True
    if not values:
        return
    bind.execute(
        sa.update(task_definitions)
        .where(task_definitions.c.id.in_(ids))
        .values(**values)
    )


def _canonicalize_task_run_cleanup_definition(bind: sa.Connection) -> None:
    columns = _columns(bind, "task_definitions")
    required = {"id", "code", "handler_path"}
    if not required.issubset(columns):
        return

    task_definitions = _task_definitions_table(columns)
    old_rows = (
        bind.execute(
            sa.select(
                task_definitions.c.id,
                task_definitions.c.code,
                task_definitions.c.handler_path,
            )
            .where(
                sa.or_(
                    task_definitions.c.code == OLD_TASK_RUNS_CODE,
                    task_definitions.c.handler_path == OLD_TASK_RUNS_HANDLER,
                )
            )
            .order_by(task_definitions.c.id.asc())
        )
        .mappings()
        .all()
    )
    canonical_row = bind.execute(
        sa.select(task_definitions.c.id)
        .where(task_definitions.c.code == TASK_RUNS_CODE)
        .order_by(task_definitions.c.id.asc())
        .limit(1)
    ).first()

    canonical_values: dict[str, Any] = {
        "code": TASK_RUNS_CODE,
        "handler_path": TASK_RUNS_HANDLER,
        **_now_value(columns),
    }
    if "name" in columns:
        canonical_values["name"] = "清理过期任务运行记录"
    if "description" in columns:
        canonical_values["description"] = "清理超过保留期的任务运行记录"
    if "default_kwargs" in columns:
        canonical_values["default_kwargs"] = {}

    if old_rows and canonical_row is None:
        primary_id = int(old_rows[0]["id"])
        bind.execute(
            sa.update(task_definitions)
            .where(task_definitions.c.id == primary_id)
            .values(**canonical_values)
        )
        _retire_task_definition_rows(
            bind,
            task_definitions,
            columns,
            [int(row["id"]) for row in old_rows[1:]],
        )
    elif old_rows:
        _retire_task_definition_rows(
            bind,
            task_definitions,
            columns,
            [int(row["id"]) for row in old_rows],
        )

    bind.execute(
        sa.update(task_definitions)
        .where(
            sa.or_(
                task_definitions.c.code == TASK_RUNS_CODE,
                task_definitions.c.handler_path == TASK_RUNS_HANDLER,
            )
        )
        .values(**canonical_values)
    )


def _canonicalize_recycle_bin_kwargs(bind: sa.Connection) -> None:
    columns = _columns(bind, "task_definitions")
    required = {"id", "code", "handler_path", "default_kwargs"}
    if not required.issubset(columns):
        return

    task_definitions = _task_definitions_table(columns)
    rows = (
        bind.execute(
            sa.select(
                task_definitions.c.id,
                task_definitions.c.default_kwargs,
            ).where(
                sa.or_(
                    task_definitions.c.code == RECYCLE_BIN_CODE,
                    task_definitions.c.handler_path == RECYCLE_BIN_HANDLER,
                )
            )
        )
        .mappings()
        .all()
    )
    definition_ids = [int(row["id"]) for row in rows]
    for row in rows:
        bind.execute(
            sa.update(task_definitions)
            .where(task_definitions.c.id == int(row["id"]))
            .values(
                default_kwargs=_canonical_recycle_kwargs(row["default_kwargs"]),
                **_now_value(columns),
            )
        )

    binding_columns = _columns(bind, "tenant_task_bindings")
    binding_required = {"id", "task_definition_id", "kwargs_override"}
    if not definition_ids or not binding_required.issubset(binding_columns):
        return

    task_bindings = _task_bindings_table(binding_columns)
    binding_rows = (
        bind.execute(
            sa.select(
                task_bindings.c.id,
                task_bindings.c.kwargs_override,
            ).where(task_bindings.c.task_definition_id.in_(definition_ids))
        )
        .mappings()
        .all()
    )
    for row in binding_rows:
        kwargs_override = row["kwargs_override"]
        if (
            not isinstance(kwargs_override, dict)
            or "retention_days" not in kwargs_override
        ):
            continue
        bind.execute(
            sa.update(task_bindings)
            .where(task_bindings.c.id == int(row["id"]))
            .values(
                kwargs_override=_canonical_recycle_kwargs(kwargs_override),
                **_now_value(binding_columns),
            )
        )


def _canonicalize_notification_cleanup_kwargs(bind: sa.Connection) -> None:
    columns = _columns(bind, "task_definitions")
    required = {"id", "code", "handler_path", "default_kwargs"}
    if not required.issubset(columns):
        return

    task_definitions = _task_definitions_table(columns)
    rows = (
        bind.execute(
            sa.select(
                task_definitions.c.id,
            ).where(
                sa.or_(
                    task_definitions.c.code == NOTIFICATION_CLEANUP_CODE,
                    task_definitions.c.handler_path == NOTIFICATION_CLEANUP_HANDLER,
                )
            )
        )
        .mappings()
        .all()
    )
    definition_ids = [int(row["id"]) for row in rows]
    for row in rows:
        bind.execute(
            sa.update(task_definitions)
            .where(task_definitions.c.id == int(row["id"]))
            .values(
                default_kwargs=_canonical_notification_cleanup_kwargs(None),
                **_now_value(columns),
            )
        )

    binding_columns = _columns(bind, "tenant_task_bindings")
    binding_required = {"id", "task_definition_id", "kwargs_override"}
    if not definition_ids or not binding_required.issubset(binding_columns):
        return

    task_bindings = _task_bindings_table(binding_columns)
    binding_rows = (
        bind.execute(
            sa.select(
                task_bindings.c.id,
                task_bindings.c.kwargs_override,
            ).where(task_bindings.c.task_definition_id.in_(definition_ids))
        )
        .mappings()
        .all()
    )
    for row in binding_rows:
        kwargs_override = row["kwargs_override"]
        if (
            not isinstance(kwargs_override, dict)
            or "retention_days" not in kwargs_override
        ):
            continue
        bind.execute(
            sa.update(task_bindings)
            .where(task_bindings.c.id == int(row["id"]))
            .values(
                kwargs_override=_canonical_notification_cleanup_kwargs(kwargs_override),
                **_now_value(binding_columns),
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    _canonicalize_task_run_cleanup_definition(bind)
    _canonicalize_recycle_bin_kwargs(bind)
    _canonicalize_notification_cleanup_kwargs(bind)


def downgrade() -> None:
    pass
