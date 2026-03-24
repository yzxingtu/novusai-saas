"""add storage migration cleanup and metadata columns / 补齐迁移清理与元数据字段

Revision ID: sm_002_cleanup_meta
Revises: sm_001_init
Create Date: 2026-03-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "sm_002_cleanup_meta"
down_revision = "sm_001_init"
branch_labels = None


def _get_column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if table_name not in existing_tables:
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    task_columns = _get_column_names("px_storage_migration_tasks")
    if task_columns:
        if "source_cleanup_started_at" not in task_columns:
            op.add_column(
                "px_storage_migration_tasks",
                sa.Column(
                    "source_cleanup_started_at",
                    sa.DateTime(timezone=True),
                    nullable=True,
                    comment="Source cleanup started time",
                ),
            )
        if "source_cleanup_completed_at" not in task_columns:
            op.add_column(
                "px_storage_migration_tasks",
                sa.Column(
                    "source_cleanup_completed_at",
                    sa.DateTime(timezone=True),
                    nullable=True,
                    comment="Source cleanup completed time",
                ),
            )
        if "source_cleanup_deleted_files" not in task_columns:
            op.add_column(
                "px_storage_migration_tasks",
                sa.Column(
                    "source_cleanup_deleted_files",
                    sa.Integer(),
                    nullable=False,
                    server_default=sa.text("0"),
                    comment="Deleted source file count",
                ),
            )
        if "source_cleanup_error_count" not in task_columns:
            op.add_column(
                "px_storage_migration_tasks",
                sa.Column(
                    "source_cleanup_error_count",
                    sa.Integer(),
                    nullable=False,
                    server_default=sa.text("0"),
                    comment="Source cleanup error count",
                ),
            )

    log_columns = _get_column_names("px_storage_migration_logs")
    if log_columns and "old_meta" not in log_columns:
        op.add_column(
            "px_storage_migration_logs",
            sa.Column(
                "old_meta",
                sa.JSON(),
                nullable=True,
                comment="Original attachment metadata snapshot",
            ),
        )


def downgrade():
    log_columns = _get_column_names("px_storage_migration_logs")
    if "old_meta" in log_columns:
        op.drop_column("px_storage_migration_logs", "old_meta")

    task_columns = _get_column_names("px_storage_migration_tasks")
    for column_name in (
        "source_cleanup_error_count",
        "source_cleanup_deleted_files",
        "source_cleanup_completed_at",
        "source_cleanup_started_at",
    ):
        if column_name in task_columns:
            op.drop_column("px_storage_migration_tasks", column_name)
