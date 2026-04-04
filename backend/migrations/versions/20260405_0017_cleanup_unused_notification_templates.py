"""cleanup unused notification templates

Revision ID: 20260405_notif_tpl_cleanup
Revises: 20260404_tenant_org_perm
Create Date: 2026-04-05
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "20260405_notif_tpl_cleanup"
down_revision: str | Sequence[str] | None = "20260404_tenant_org_perm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REMOVED_TEMPLATE_ROWS: tuple[dict[str, object], ...] = (
    {
        "code": "system.announcement",
        "category": "system",
        "title_template": "系统公告",
        "body_template": "{content}",
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "system.maintenance",
        "category": "system",
        "title_template": "系统维护通知",
        "body_template": "系统将于 {start_time} 开始维护，预计持续 {duration}，维护期间服务可能不可用。",
        "channels": ["ws", "inbox"],
        "priority": "high",
    },
    {
        "code": "system.security_alert",
        "category": "system",
        "title_template": "安全警告",
        "body_template": "{message}",
        "channels": ["ws", "inbox", "email"],
        "priority": "urgent",
    },
    {
        "code": "plugin.novusdoc-pro.comment_added",
        "category": "biz",
        "title_template": "新评论",
        "body_template": None,
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "plugin.novusdoc-pro.mention",
        "category": "biz",
        "title_template": "有人@了你",
        "body_template": None,
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
    {
        "code": "plugin.novusdoc-pro.share_received",
        "category": "biz",
        "title_template": "收到文档分享",
        "body_template": None,
        "channels": ["ws", "inbox"],
        "priority": "normal",
    },
)


def _has_table(bind, table_name: str) -> bool:
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _notification_template_table() -> sa.Table:
    return sa.table(
        "notification_templates",
        sa.column("code", sa.String(length=100)),
        sa.column("category", sa.String(length=50)),
        sa.column("title_template", sa.Text()),
        sa.column("body_template", sa.Text()),
        sa.column("channels", sa.ARRAY(sa.String(length=20))),
        sa.column("priority", sa.String(length=20)),
        sa.column("is_system", sa.Boolean()),
        sa.column("tenant_id", sa.Integer()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
        sa.column("is_deleted", sa.Boolean()),
        sa.column("deleted_at", sa.DateTime()),
        sa.column("delete_level", sa.String(length=20)),
        sa.column("recycle_stage", sa.String(length=20)),
        sa.column("promoted_to_global_at", sa.DateTime()),
    )


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "notification_templates"):
        return

    notification_templates = _notification_template_table()
    removed_codes = [row["code"] for row in REMOVED_TEMPLATE_ROWS]
    bind.execute(
        sa.delete(notification_templates).where(
            notification_templates.c.code.in_(removed_codes)
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "notification_templates"):
        return

    notification_templates = _notification_template_table()
    removed_codes = [row["code"] for row in REMOVED_TEMPLATE_ROWS]
    existing_codes = {
        row[0]
        for row in bind.execute(
            sa.select(notification_templates.c.code).where(
                notification_templates.c.code.in_(removed_codes)
            )
        )
    }
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows_to_restore = [
        {
            "code": row["code"],
            "category": row["category"],
            "title_template": row["title_template"],
            "body_template": row["body_template"],
            "channels": row["channels"],
            "priority": row["priority"],
            "is_system": True,
            "tenant_id": None,
            "created_at": now,
            "updated_at": now,
            "is_deleted": False,
            "deleted_at": None,
            "delete_level": None,
            "recycle_stage": None,
            "promoted_to_global_at": None,
        }
        for row in REMOVED_TEMPLATE_ROWS
        if row["code"] not in existing_codes
    ]
    if rows_to_restore:
        bind.execute(sa.insert(notification_templates), rows_to_restore)
