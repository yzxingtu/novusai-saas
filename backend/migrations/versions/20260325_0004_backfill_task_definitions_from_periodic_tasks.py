"""Backfill task definitions from legacy periodic tasks

Revision ID: 20260325_backfill_task_defs
Revises: 20260325_task_definition_ops
Create Date: 2026-03-25
"""

from __future__ import annotations

from collections.abc import Sequence
from hashlib import md5

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260325_backfill_task_defs"
down_revision: str | Sequence[str] | None = "20260325_task_definition_ops"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(bind, table_name: str) -> bool:
    return inspect(bind).has_table(table_name)


def _column_names(bind, table_name: str) -> set[str]:
    inspector = inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def _build_code(task_path: str) -> str:
    leaf = task_path.split(".")[-1][:48]
    digest = md5(task_path.encode("utf-8")).hexdigest()[:8]
    return f"task.{leaf}.{digest}"


def upgrade() -> None:
    bind = op.get_bind()
    if not (
        _has_table(bind, "periodic_tasks")
        and _has_table(bind, "task_definitions")
        and _has_table(bind, "tenant_task_bindings")
    ):
        return

    task_definition_columns = _column_names(bind, "task_definitions")
    tenant_binding_columns = _column_names(bind, "tenant_task_bindings")

    task_definition_additions: list[tuple[str, sa.Column]] = [
        (
            "default_args",
            sa.Column("default_args", sa.JSON(), nullable=True, comment="默认位置参数"),
        ),
        (
            "max_retries",
            sa.Column("max_retries", sa.Integer(), nullable=False, server_default="0"),
        ),
        (
            "retry_delay",
            sa.Column("retry_delay", sa.Integer(), nullable=False, server_default="60"),
        ),
        (
            "timeout",
            sa.Column("timeout", sa.Integer(), nullable=False, server_default="3600"),
        ),
        (
            "notify_on_failure",
            sa.Column(
                "notify_on_failure",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        ),
        (
            "notify_emails",
            sa.Column("notify_emails", sa.Text(), nullable=True),
        ),
        (
            "last_run_at",
            sa.Column("last_run_at", sa.DateTime(), nullable=True),
        ),
        (
            "next_run_at",
            sa.Column("next_run_at", sa.DateTime(), nullable=True),
        ),
    ]

    for name, column in task_definition_additions:
        if name not in task_definition_columns:
            op.add_column("task_definitions", column)
            task_definition_columns.add(name)

    tenant_binding_additions: list[tuple[str, sa.Column]] = [
        (
            "args_override",
            sa.Column("args_override", sa.JSON(), nullable=True, comment="覆盖位置参数"),
        ),
    ]

    for name, column in tenant_binding_additions:
        if name not in tenant_binding_columns:
            op.add_column("tenant_task_bindings", column)
            tenant_binding_columns.add(name)

    periodic_tasks = sa.table(
        "periodic_tasks",
        sa.column("id", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("task_path", sa.String()),
        sa.column("schedule_type", sa.String()),
        sa.column("cron_expression", sa.String()),
        sa.column("interval_seconds", sa.Integer()),
        sa.column("args", sa.JSON()),
        sa.column("kwargs", sa.JSON()),
        sa.column("is_active", sa.Boolean()),
        sa.column("last_run_at", sa.DateTime()),
        sa.column("next_run_at", sa.DateTime()),
        sa.column("description", sa.Text()),
        sa.column("owner_tenant_id", sa.Integer()),
        sa.column("scope", sa.String()),
        sa.column("is_locked", sa.Boolean()),
        sa.column("is_editable", sa.Boolean()),
        sa.column("max_retries", sa.Integer()),
        sa.column("retry_delay", sa.Integer()),
        sa.column("timeout", sa.Integer()),
        sa.column("notify_on_failure", sa.Boolean()),
        sa.column("notify_emails", sa.Text()),
        sa.column("is_deleted", sa.Boolean()),
    )

    task_definitions = sa.table(
        "task_definitions",
        sa.column("id", sa.Integer()),
        sa.column("owner_tenant_id", sa.Integer()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("definition_type", sa.String()),
        sa.column("handler_path", sa.String()),
        sa.column("category", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("scope", sa.String()),
        sa.column("default_schedule_type", sa.String()),
        sa.column("default_cron_expression", sa.String()),
        sa.column("default_interval_seconds", sa.Integer()),
        sa.column("default_queue", sa.String()),
        sa.column("default_args", sa.JSON()),
        sa.column("default_kwargs", sa.JSON()),
        sa.column("config_schema", sa.JSON()),
        sa.column("is_system_builtin", sa.Boolean()),
        sa.column("max_retries", sa.Integer()),
        sa.column("retry_delay", sa.Integer()),
        sa.column("timeout", sa.Integer()),
        sa.column("notify_on_failure", sa.Boolean()),
        sa.column("notify_emails", sa.Text()),
        sa.column("is_enabled", sa.Boolean()),
        sa.column("is_editable", sa.Boolean()),
        sa.column("is_deletable", sa.Boolean()),
        sa.column("last_run_at", sa.DateTime()),
        sa.column("next_run_at", sa.DateTime()),
    )

    tenant_task_bindings = sa.table(
        "tenant_task_bindings",
        sa.column("id", sa.Integer()),
        sa.column("task_definition_id", sa.Integer()),
        sa.column("tenant_id", sa.Integer()),
        sa.column("is_enabled", sa.Boolean()),
        sa.column("schedule_type_override", sa.String()),
        sa.column("cron_expression_override", sa.String()),
        sa.column("interval_seconds_override", sa.Integer()),
        sa.column("config_override", sa.JSON()),
        sa.column("args_override", sa.JSON()),
        sa.column("kwargs_override", sa.JSON()),
        sa.column("last_run_at", sa.DateTime()),
        sa.column("next_run_at", sa.DateTime()),
        sa.column("last_status", sa.String()),
        sa.column("last_error_message", sa.Text()),
    )

    rows = bind.execute(
        sa.select(periodic_tasks).where(periodic_tasks.c.is_deleted.is_(False))
    ).mappings().all()

    for row in rows:
        code = _build_code(str(row["task_path"]))
        existing_definition = bind.execute(
            sa.select(task_definitions.c.id).where(task_definitions.c.code == code)
        ).scalar_one_or_none()

        if existing_definition is None:
            insert_stmt = sa.insert(task_definitions).values(
                owner_tenant_id=row["owner_tenant_id"],
                code=code,
                name=row["name"],
                definition_type="system",
                handler_path=row["task_path"],
                category="maintenance",
                description=row["description"],
                scope=row["scope"] or "admin_only",
                default_schedule_type=row["schedule_type"],
                default_cron_expression=row["cron_expression"],
                default_interval_seconds=row["interval_seconds"],
                default_queue="scheduled",
                default_args=row["args"],
                default_kwargs=row["kwargs"],
                config_schema={
                    "legacy_periodic_task_id": row["id"],
                    "source": "periodic_tasks",
                },
                is_system_builtin=bool(row["is_locked"] and not row["is_editable"]),
                max_retries=row["max_retries"] or 0,
                retry_delay=row["retry_delay"] or 60,
                timeout=row["timeout"] or 3600,
                notify_on_failure=bool(row["notify_on_failure"]),
                notify_emails=row["notify_emails"],
                is_enabled=bool(row["is_active"]),
                is_editable=bool(row["is_editable"]),
                is_deletable=not bool(row["is_locked"]),
                last_run_at=row["last_run_at"],
                next_run_at=row["next_run_at"],
            )
            bind.execute(insert_stmt)
            existing_definition = bind.execute(
                sa.select(task_definitions.c.id).where(task_definitions.c.code == code)
            ).scalar_one()
        else:
            bind.execute(
                sa.update(task_definitions)
                .where(task_definitions.c.id == existing_definition)
                .values(
                    owner_tenant_id=row["owner_tenant_id"],
                    name=row["name"],
                    handler_path=row["task_path"],
                    description=row["description"],
                    scope=row["scope"] or "admin_only",
                    default_schedule_type=row["schedule_type"],
                    default_cron_expression=row["cron_expression"],
                    default_interval_seconds=row["interval_seconds"],
                    default_args=row["args"],
                    default_kwargs=row["kwargs"],
                    max_retries=row["max_retries"] or 0,
                    retry_delay=row["retry_delay"] or 60,
                    timeout=row["timeout"] or 3600,
                    notify_on_failure=bool(row["notify_on_failure"]),
                    notify_emails=row["notify_emails"],
                    is_enabled=bool(row["is_active"]),
                    is_editable=bool(row["is_editable"]),
                    is_deletable=not bool(row["is_locked"]),
                    last_run_at=row["last_run_at"],
                    next_run_at=row["next_run_at"],
                )
            )

        if row["owner_tenant_id"] is None:
            continue

        existing_binding = bind.execute(
            sa.select(tenant_task_bindings.c.id).where(
                sa.and_(
                    tenant_task_bindings.c.task_definition_id == existing_definition,
                    tenant_task_bindings.c.tenant_id == row["owner_tenant_id"],
                )
            )
        ).scalar_one_or_none()

        binding_values = {
            "task_definition_id": existing_definition,
            "tenant_id": row["owner_tenant_id"],
            "is_enabled": bool(row["is_active"]),
            "schedule_type_override": None,
            "cron_expression_override": None,
            "interval_seconds_override": None,
            "config_override": {
                "legacy_periodic_task_id": row["id"],
                "source": "periodic_tasks",
            },
            "args_override": None,
            "kwargs_override": None,
            "last_run_at": row["last_run_at"],
            "next_run_at": row["next_run_at"],
            "last_status": None,
            "last_error_message": None,
        }

        if existing_binding is None:
            bind.execute(sa.insert(tenant_task_bindings).values(**binding_values))
        else:
            bind.execute(
                sa.update(tenant_task_bindings)
                .where(tenant_task_bindings.c.id == existing_binding)
                .values(**binding_values)
            )


def downgrade() -> None:
    bind = op.get_bind()
    if not (_has_table(bind, "task_definitions") and _has_table(bind, "tenant_task_bindings")):
        return

    bind.execute(
        sa.text(
            """
            DELETE FROM tenant_task_bindings
            WHERE config_override ->> 'source' = 'periodic_tasks'
            """
        )
    )
    bind.execute(
        sa.text(
            """
            DELETE FROM task_definitions
            WHERE config_schema ->> 'source' = 'periodic_tasks'
            """
        )
    )
