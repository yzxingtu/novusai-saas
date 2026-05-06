"""中文: 增强通知模板作用域并新增投递记录。

EN: Add notification template scoping and durable delivery records.

Revision ID: 20260507_0031_notif_gov
Revises: 20260507_0030_binding_disable
Create Date: 2026-05-07

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260507_0031_notif_gov"
down_revision: str | Sequence[str] | None = "20260507_0030_binding_disable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(bind, table_name: str) -> bool:
    return table_name in sa.inspect(bind).get_table_names()


def _column_names(bind, table_name: str) -> set[str]:
    if not _has_table(bind, table_name):
        return set()
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    if not _has_table(bind, table_name):
        return set()
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def _drop_global_code_unique(bind) -> None:
    inspector = sa.inspect(bind)
    for constraint in inspector.get_unique_constraints("notification_templates"):
        if constraint.get("column_names") == ["code"]:
            op.drop_constraint(
                constraint["name"],
                "notification_templates",
                type_="unique",
            )
    for index in inspector.get_indexes("notification_templates"):
        if index.get("unique") and index.get("column_names") == ["code"]:
            op.drop_index(index["name"], table_name="notification_templates")


def _create_index_once(
    bind,
    name: str,
    table_name: str,
    columns: list[str],
    *,
    unique: bool = False,
    postgresql_where=None,
) -> None:
    if name in _index_names(bind, table_name):
        return
    op.create_index(
        name,
        table_name,
        columns,
        unique=unique,
        postgresql_where=postgresql_where,
    )


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "notification_templates"):
        return

    columns = _column_names(bind, "notification_templates")
    if "scope" not in columns:
        op.add_column(
            "notification_templates",
            sa.Column(
                "scope",
                sa.String(length=20),
                nullable=False,
                server_default="platform",
                comment="作用域: platform/tenant/plugin/source",
            ),
        )
    if "source" not in columns:
        op.add_column(
            "notification_templates",
            sa.Column(
                "source",
                sa.String(length=100),
                nullable=True,
                comment="模板来源: core/plugin/import 等",
            ),
        )
    if "plugin_name" not in columns:
        op.add_column(
            "notification_templates",
            sa.Column(
                "plugin_name",
                sa.String(length=100),
                nullable=True,
                comment="插件名称（插件模板所属）",
            ),
        )
    if "is_enabled" not in columns:
        op.add_column(
            "notification_templates",
            sa.Column(
                "is_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
                comment="是否启用",
            ),
        )
    if "override_of" not in columns:
        op.add_column(
            "notification_templates",
            sa.Column(
                "override_of",
                sa.Integer(),
                nullable=True,
                comment="覆盖的模板 ID",
            ),
        )
    if "locked_fields" not in columns:
        op.add_column(
            "notification_templates",
            sa.Column(
                "locked_fields",
                postgresql.ARRAY(sa.String(length=50)),
                nullable=True,
                comment="锁定字段列表",
            ),
        )

    bind.execute(
        sa.text(
            """
            UPDATE notification_templates
            SET
                scope = CASE
                    WHEN code LIKE 'plugin.%' THEN 'plugin'
                    WHEN tenant_id IS NOT NULL AND tenant_id <> 0 THEN 'tenant'
                    ELSE 'platform'
                END,
                source = CASE
                    WHEN code LIKE 'plugin.%' THEN 'plugin'
                    ELSE COALESCE(source, 'core')
                END,
                plugin_name = CASE
                    WHEN code LIKE 'plugin.%' THEN split_part(code, '.', 2)
                    ELSE plugin_name
                END,
                is_enabled = COALESCE(is_enabled, true)
            WHERE is_deleted = false
            """
        )
    )

    _drop_global_code_unique(bind)

    _create_index_once(
        bind, "ix_notification_templates_scope", "notification_templates", ["scope"]
    )
    _create_index_once(
        bind, "ix_notification_templates_source", "notification_templates", ["source"]
    )
    _create_index_once(
        bind,
        "ix_notification_templates_plugin_name",
        "notification_templates",
        ["plugin_name"],
    )
    _create_index_once(
        bind,
        "ix_notification_templates_is_enabled",
        "notification_templates",
        ["is_enabled"],
    )
    _create_index_once(
        bind,
        "ix_notification_templates_override_of",
        "notification_templates",
        ["override_of"],
    )
    _create_index_once(
        bind,
        "uq_notification_templates_platform_code",
        "notification_templates",
        ["code"],
        unique=True,
        postgresql_where=sa.text(
            "is_deleted = false AND scope = 'platform' AND tenant_id IS NULL"
        ),
    )
    _create_index_once(
        bind,
        "uq_notification_templates_tenant_code",
        "notification_templates",
        ["tenant_id", "code"],
        unique=True,
        postgresql_where=sa.text(
            "is_deleted = false AND scope = 'tenant' AND tenant_id IS NOT NULL"
        ),
    )
    _create_index_once(
        bind,
        "uq_notification_templates_plugin_code",
        "notification_templates",
        ["code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false AND scope = 'plugin'"),
    )
    _create_index_once(
        bind,
        "uq_notification_templates_source_code",
        "notification_templates",
        ["source", "code"],
        unique=True,
        postgresql_where=sa.text(
            "is_deleted = false AND scope = 'source' AND source IS NOT NULL"
        ),
    )

    if not _has_table(bind, "notification_deliveries"):
        op.create_table(
            "notification_deliveries",
            sa.Column(
                "notification_id",
                sa.Integer(),
                nullable=True,
                comment="收件箱通知 ID（非 inbox 渠道可为空）",
            ),
            sa.Column(
                "template_id", sa.Integer(), nullable=True, comment="通知模板 ID"
            ),
            sa.Column(
                "template_code",
                sa.String(length=100),
                nullable=False,
                comment="通知模板编码",
            ),
            sa.Column(
                "channel",
                sa.String(length=20),
                nullable=False,
                comment="投递渠道: ws/inbox/email/webhook",
            ),
            sa.Column(
                "recipient_type",
                sa.String(length=20),
                nullable=False,
                comment="接收人类型: admin/tenant_admin/tenant_user",
            ),
            sa.Column(
                "recipient_id", sa.Integer(), nullable=False, comment="接收人 ID"
            ),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                nullable=True,
                comment="企业 ID（NULL=平台级）",
            ),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="pending",
                comment="状态: pending/queued/sent/failed/skipped",
            ),
            sa.Column(
                "attempt",
                sa.Integer(),
                nullable=False,
                server_default="0",
                comment="投递尝试次数",
            ),
            sa.Column(
                "task_id", sa.String(length=100), nullable=True, comment="异步任务 ID"
            ),
            sa.Column("last_error", sa.Text(), nullable=True, comment="最近错误信息"),
            sa.Column(
                "delivered_at", sa.DateTime(), nullable=True, comment="投递完成时间"
            ),
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                comment="创建时间 / Created at",
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                comment="更新时间 / Updated at",
            ),
            sa.Column(
                "is_deleted",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
                comment="软删除标记 / Soft-delete flag",
            ),
            sa.Column(
                "deleted_at",
                sa.DateTime(),
                nullable=True,
                comment="删除时间 / Deleted at",
            ),
            sa.Column(
                "delete_level",
                sa.String(length=20),
                nullable=True,
                comment="删除侧别 / Delete scope: tenant=tenant side, admin=admin side",
            ),
            sa.Column(
                "recycle_stage",
                sa.String(length=20),
                nullable=True,
                comment="回收站阶段 / Recycle stage: module/global",
            ),
            sa.Column(
                "promoted_to_global_at",
                sa.DateTime(),
                nullable=True,
                comment="进入总回收站时间 / Promoted to global recycle bin at",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    _create_index_once(
        bind,
        "idx_notification_deliveries_notification",
        "notification_deliveries",
        ["notification_id"],
    )
    _create_index_once(
        bind,
        "idx_notification_deliveries_template",
        "notification_deliveries",
        ["template_code", "channel"],
    )
    _create_index_once(
        bind,
        "idx_notification_deliveries_template_id",
        "notification_deliveries",
        ["template_id"],
    )
    _create_index_once(
        bind,
        "idx_notification_deliveries_recipient",
        "notification_deliveries",
        ["recipient_type", "recipient_id", "tenant_id"],
    )
    _create_index_once(
        bind,
        "idx_notification_deliveries_status",
        "notification_deliveries",
        ["status", "created_at"],
    )
    _create_index_once(
        bind,
        "idx_notification_deliveries_task_id",
        "notification_deliveries",
        ["task_id"],
    )
    _create_index_once(
        bind,
        "ix_notification_deliveries_id",
        "notification_deliveries",
        ["id"],
    )
    _create_index_once(
        bind,
        "ix_notification_deliveries_is_deleted",
        "notification_deliveries",
        ["is_deleted"],
    )
    _create_index_once(
        bind,
        "ix_notification_deliveries_recycle_stage",
        "notification_deliveries",
        ["recycle_stage"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, "notification_deliveries"):
        for index_name in [
            "ix_notification_deliveries_recycle_stage",
            "ix_notification_deliveries_is_deleted",
            "ix_notification_deliveries_id",
            "idx_notification_deliveries_task_id",
            "idx_notification_deliveries_status",
            "idx_notification_deliveries_recipient",
            "idx_notification_deliveries_template_id",
            "idx_notification_deliveries_template",
            "idx_notification_deliveries_notification",
        ]:
            if index_name in _index_names(bind, "notification_deliveries"):
                op.drop_index(index_name, table_name="notification_deliveries")
        op.drop_table("notification_deliveries")

    if not _has_table(bind, "notification_templates"):
        return

    for index_name in [
        "uq_notification_templates_source_code",
        "uq_notification_templates_plugin_code",
        "uq_notification_templates_tenant_code",
        "uq_notification_templates_platform_code",
        "ix_notification_templates_override_of",
        "ix_notification_templates_is_enabled",
        "ix_notification_templates_plugin_name",
        "ix_notification_templates_source",
        "ix_notification_templates_scope",
    ]:
        if index_name in _index_names(bind, "notification_templates"):
            op.drop_index(index_name, table_name="notification_templates")

    columns = _column_names(bind, "notification_templates")
    for column_name in [
        "locked_fields",
        "override_of",
        "is_enabled",
        "plugin_name",
        "source",
        "scope",
    ]:
        if column_name in columns:
            op.drop_column("notification_templates", column_name)

    op.create_unique_constraint(
        "uq_notification_templates_code_legacy",
        "notification_templates",
        ["code"],
    )
