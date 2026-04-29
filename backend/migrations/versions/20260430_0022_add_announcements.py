"""add announcement management tables

Revision ID: 20260430_0022_announcements
Revises: 20260410_cleanup_legacy_grants
Create Date: 2026-04-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260430_0022_announcements"
down_revision: str | Sequence[str] | None = "20260410_cleanup_legacy_grants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, comment="创建时间 / Created at"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, comment="更新时间 / Updated at"),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="软删除标记 / Soft-delete flag",
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True, comment="删除时间 / Deleted at"),
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
    ]


def _tenant_column() -> sa.Column:
    return sa.Column("tenant_id", sa.Integer(), nullable=False, comment="企业ID / Tenant ID")


def upgrade() -> None:
    op.create_table(
        "announcements",
        *_base_columns(),
        _tenant_column(),
        sa.Column("title", sa.String(length=200), nullable=False, comment="公告标题"),
        sa.Column(
            "scope",
            sa.String(length=20),
            nullable=False,
            server_default="tenant",
            comment="公告端别: admin/tenant",
        ),
        sa.Column("content", sa.Text(), nullable=True, comment="公告内容"),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="draft",
            comment="公告状态",
        ),
        sa.Column(
            "priority",
            sa.String(length=20),
            nullable=False,
            server_default="normal",
            comment="公告优先级",
        ),
        sa.Column(
            "require_response",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="是否需要反馈",
        ),
        sa.Column(
            "form_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="表单配置",
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True, comment="发布时间"),
        sa.Column(
            "recipient_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="接收人数",
        ),
        sa.Column(
            "response_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="回执人数",
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="排序",
        ),
    )
    op.create_index("ix_announcements_tenant_id", "announcements", ["tenant_id"])
    op.create_index("ix_announcements_is_deleted", "announcements", ["is_deleted"])
    op.create_index("ix_announcements_recycle_stage", "announcements", ["recycle_stage"])
    op.create_index("idx_announcements_scope_status", "announcements", ["scope", "status"])
    op.create_index("idx_announcements_tenant_scope", "announcements", ["tenant_id", "scope"])

    op.create_table(
        "announcement_deliveries",
        *_base_columns(),
        _tenant_column(),
        sa.Column("announcement_id", sa.Integer(), nullable=False, comment="公告 ID"),
        sa.Column(
            "recipient_type",
            sa.String(length=20),
            nullable=False,
            comment="接收人类型: admin/tenant_admin/tenant_user",
        ),
        sa.Column("recipient_id", sa.Integer(), nullable=False, comment="接收人 ID"),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
            comment="状态: pending/read/submitted",
        ),
        sa.Column("notification_id", sa.Integer(), nullable=True, comment="关联通知 ID"),
        sa.Column("read_at", sa.DateTime(), nullable=True, comment="已读时间"),
        sa.Column(
            "form_schema_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
            comment="表单配置版本",
        ),
        sa.Column("submitted_at", sa.DateTime(), nullable=True, comment="提交/已读时间"),
        sa.ForeignKeyConstraint(
            ["announcement_id"],
            ["announcements.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "announcement_id",
            "recipient_type",
            "recipient_id",
            name="uq_announcement_delivery_recipient",
        ),
    )
    op.create_index("ix_announcement_deliveries_tenant_id", "announcement_deliveries", ["tenant_id"])
    op.create_index("ix_announcement_deliveries_is_deleted", "announcement_deliveries", ["is_deleted"])
    op.create_index(
        "ix_announcement_deliveries_recycle_stage",
        "announcement_deliveries",
        ["recycle_stage"],
    )
    op.create_index(
        "idx_announcement_deliveries_recipient_status",
        "announcement_deliveries",
        ["recipient_type", "recipient_id", "status"],
    )
    op.create_index(
        "idx_announcement_deliveries_announcement",
        "announcement_deliveries",
        ["announcement_id"],
    )

    op.create_table(
        "announcement_responses",
        *_base_columns(),
        _tenant_column(),
        sa.Column("announcement_id", sa.Integer(), nullable=False, comment="公告 ID"),
        sa.Column("delivery_id", sa.Integer(), nullable=False, comment="投递 ID"),
        sa.Column(
            "recipient_type",
            sa.String(length=20),
            nullable=False,
            comment="接收人类型: admin/tenant_admin/tenant_user",
        ),
        sa.Column("recipient_id", sa.Integer(), nullable=False, comment="接收人 ID"),
        sa.Column(
            "answers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="反馈答案",
        ),
        sa.Column("submitted_at", sa.DateTime(), nullable=False, comment="提交时间"),
        sa.ForeignKeyConstraint(
            ["announcement_id"],
            ["announcements.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["delivery_id"],
            ["announcement_deliveries.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "announcement_id",
            "recipient_type",
            "recipient_id",
            name="uq_announcement_response_recipient",
        ),
        sa.UniqueConstraint("delivery_id", name="uq_announcement_response_delivery"),
    )
    op.create_index("ix_announcement_responses_tenant_id", "announcement_responses", ["tenant_id"])
    op.create_index("ix_announcement_responses_is_deleted", "announcement_responses", ["is_deleted"])
    op.create_index(
        "ix_announcement_responses_recycle_stage",
        "announcement_responses",
        ["recycle_stage"],
    )
    op.create_index(
        "idx_announcement_responses_announcement",
        "announcement_responses",
        ["announcement_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_announcement_responses_announcement", table_name="announcement_responses")
    op.drop_index("ix_announcement_responses_recycle_stage", table_name="announcement_responses")
    op.drop_index("ix_announcement_responses_is_deleted", table_name="announcement_responses")
    op.drop_index("ix_announcement_responses_tenant_id", table_name="announcement_responses")
    op.drop_table("announcement_responses")

    op.drop_index("idx_announcement_deliveries_announcement", table_name="announcement_deliveries")
    op.drop_index(
        "idx_announcement_deliveries_recipient_status",
        table_name="announcement_deliveries",
    )
    op.drop_index("ix_announcement_deliveries_recycle_stage", table_name="announcement_deliveries")
    op.drop_index("ix_announcement_deliveries_is_deleted", table_name="announcement_deliveries")
    op.drop_index("ix_announcement_deliveries_tenant_id", table_name="announcement_deliveries")
    op.drop_table("announcement_deliveries")

    op.drop_index("idx_announcements_tenant_scope", table_name="announcements")
    op.drop_index("idx_announcements_scope_status", table_name="announcements")
    op.drop_index("ix_announcements_recycle_stage", table_name="announcements")
    op.drop_index("ix_announcements_is_deleted", table_name="announcements")
    op.drop_index("ix_announcements_tenant_id", table_name="announcements")
    op.drop_table("announcements")
