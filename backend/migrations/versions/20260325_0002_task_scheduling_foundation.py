"""Task scheduling foundation tables

Revision ID: 20260325_task_sched_foundation
Revises: 20260325_skill_arch_foundation
Create Date: 2026-03-25

Adds the first slice of the next-generation task scheduling architecture:
- task_definitions
- tenant_task_bindings
- task_runs
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260325_task_sched_foundation"
down_revision: str | Sequence[str] | None = "20260325_skill_arch_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "task_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
        sa.Column("owner_tenant_id", sa.Integer(), nullable=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("definition_type", sa.String(length=30), nullable=False, server_default="system"),
        sa.Column("handler_path", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False, server_default="maintenance"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scope", sa.String(length=32), nullable=False, server_default="admin_only"),
        sa.Column("default_schedule_type", sa.String(length=20), nullable=True, server_default="interval"),
        sa.Column("default_cron_expression", sa.String(length=100), nullable=True),
        sa.Column("default_interval_seconds", sa.Integer(), nullable=True),
        sa.Column("default_queue", sa.String(length=50), nullable=False, server_default="scheduled"),
        sa.Column("default_args", sa.JSON(), nullable=True),
        sa.Column("default_kwargs", sa.JSON(), nullable=True),
        sa.Column("config_schema", sa.JSON(), nullable=True),
        sa.Column("is_system_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_editable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_deletable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["owner_tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_definitions_code", "task_definitions", ["code"], unique=True)
    op.create_index(
        "ix_task_definitions_scope_type",
        "task_definitions",
        ["scope", "definition_type"],
    )
    op.create_index(
        "ix_task_definitions_owner_enabled",
        "task_definitions",
        ["owner_tenant_id", "is_enabled"],
    )
    op.create_index("ix_task_definitions_owner_tenant_id", "task_definitions", ["owner_tenant_id"])
    op.create_index("ix_task_definitions_is_deleted", "task_definitions", ["is_deleted"])
    op.create_index("ix_task_definitions_recycle_stage", "task_definitions", ["recycle_stage"])

    op.create_table(
        "tenant_task_bindings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
        sa.Column("task_definition_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("schedule_type_override", sa.String(length=20), nullable=True),
        sa.Column("cron_expression_override", sa.String(length=100), nullable=True),
        sa.Column("interval_seconds_override", sa.Integer(), nullable=True),
        sa.Column("config_override", sa.JSON(), nullable=True),
        sa.Column("args_override", sa.JSON(), nullable=True),
        sa.Column("kwargs_override", sa.JSON(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.String(length=20), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["task_definition_id"], ["task_definitions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_definition_id",
            "tenant_id",
            name="uq_tenant_task_binding_definition_tenant",
        ),
    )
    op.create_index(
        "ix_tenant_task_bindings_tenant_enabled",
        "tenant_task_bindings",
        ["tenant_id", "is_enabled"],
    )
    op.create_index(
        "ix_tenant_task_bindings_definition_enabled",
        "tenant_task_bindings",
        ["task_definition_id", "is_enabled"],
    )
    op.create_index("ix_tenant_task_bindings_task_definition_id", "tenant_task_bindings", ["task_definition_id"])
    op.create_index("ix_tenant_task_bindings_tenant_id", "tenant_task_bindings", ["tenant_id"])
    op.create_index("ix_tenant_task_bindings_is_deleted", "tenant_task_bindings", ["is_deleted"])
    op.create_index("ix_tenant_task_bindings_recycle_stage", "tenant_task_bindings", ["recycle_stage"])

    op.create_table(
        "task_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
        sa.Column("celery_task_id", sa.String(length=100), nullable=False),
        sa.Column("task_definition_id", sa.Integer(), nullable=True),
        sa.Column("binding_id", sa.Integer(), nullable=True),
        sa.Column("task_code_snapshot", sa.String(length=100), nullable=False),
        sa.Column("task_name_snapshot", sa.String(length=200), nullable=False),
        sa.Column("handler_path_snapshot", sa.String(length=255), nullable=False),
        sa.Column("trigger_source", sa.String(length=30), nullable=False, server_default="scheduler"),
        sa.Column("run_kind", sa.String(length=30), nullable=False, server_default="platform"),
        sa.Column("owner_tenant_id", sa.Integer(), nullable=True),
        sa.Column("effective_tenant_id", sa.Integer(), nullable=True),
        sa.Column("queue", sa.String(length=50), nullable=False, server_default="default"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("args_summary", sa.JSON(), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message_public", sa.Text(), nullable=True),
        sa.Column("error_message_internal", sa.Text(), nullable=True),
        sa.Column("traceback_internal", sa.Text(), nullable=True),
        sa.Column("trace_id", sa.String(length=100), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["task_definition_id"], ["task_definitions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["binding_id"], ["tenant_task_bindings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_tenant_id"], ["tenants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["effective_tenant_id"], ["tenants.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_runs_celery_task_id", "task_runs", ["celery_task_id"], unique=True)
    op.create_index(
        "ix_task_runs_definition_status",
        "task_runs",
        ["task_definition_id", "status"],
    )
    op.create_index(
        "ix_task_runs_effective_tenant_created",
        "task_runs",
        ["effective_tenant_id", "created_at"],
    )
    op.create_index(
        "ix_task_runs_trigger_kind_created",
        "task_runs",
        ["trigger_source", "run_kind", "created_at"],
    )
    op.create_index("ix_task_runs_task_definition_id", "task_runs", ["task_definition_id"])
    op.create_index("ix_task_runs_binding_id", "task_runs", ["binding_id"])
    op.create_index("ix_task_runs_owner_tenant_id", "task_runs", ["owner_tenant_id"])
    op.create_index("ix_task_runs_effective_tenant_id", "task_runs", ["effective_tenant_id"])
    op.create_index("ix_task_runs_is_deleted", "task_runs", ["is_deleted"])
    op.create_index("ix_task_runs_recycle_stage", "task_runs", ["recycle_stage"])


def downgrade() -> None:
    op.drop_index("ix_task_runs_recycle_stage", table_name="task_runs")
    op.drop_index("ix_task_runs_is_deleted", table_name="task_runs")
    op.drop_index("ix_task_runs_effective_tenant_id", table_name="task_runs")
    op.drop_index("ix_task_runs_owner_tenant_id", table_name="task_runs")
    op.drop_index("ix_task_runs_binding_id", table_name="task_runs")
    op.drop_index("ix_task_runs_task_definition_id", table_name="task_runs")
    op.drop_index("ix_task_runs_trigger_kind_created", table_name="task_runs")
    op.drop_index("ix_task_runs_effective_tenant_created", table_name="task_runs")
    op.drop_index("ix_task_runs_definition_status", table_name="task_runs")
    op.drop_index("ix_task_runs_celery_task_id", table_name="task_runs")
    op.drop_table("task_runs")

    op.drop_index("ix_tenant_task_bindings_recycle_stage", table_name="tenant_task_bindings")
    op.drop_index("ix_tenant_task_bindings_is_deleted", table_name="tenant_task_bindings")
    op.drop_index("ix_tenant_task_bindings_tenant_id", table_name="tenant_task_bindings")
    op.drop_index("ix_tenant_task_bindings_task_definition_id", table_name="tenant_task_bindings")
    op.drop_index("ix_tenant_task_bindings_definition_enabled", table_name="tenant_task_bindings")
    op.drop_index("ix_tenant_task_bindings_tenant_enabled", table_name="tenant_task_bindings")
    op.drop_table("tenant_task_bindings")

    op.drop_index("ix_task_definitions_recycle_stage", table_name="task_definitions")
    op.drop_index("ix_task_definitions_is_deleted", table_name="task_definitions")
    op.drop_index("ix_task_definitions_owner_tenant_id", table_name="task_definitions")
    op.drop_index("ix_task_definitions_owner_enabled", table_name="task_definitions")
    op.drop_index("ix_task_definitions_scope_type", table_name="task_definitions")
    op.drop_index("ix_task_definitions_code", table_name="task_definitions")
    op.drop_table("task_definitions")
