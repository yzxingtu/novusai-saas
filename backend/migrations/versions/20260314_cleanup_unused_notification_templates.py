"""soft-delete 23 unused notification templates

Revision ID: 20260314_cleanup_ntpl
Revises: 20260314_litellm_sync
Create Date: 2026-03-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260314_cleanup_ntpl"
down_revision: str | None = "20260314_litellm_sync"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEPRECATED_CODES = [
    # system
    "system.version_update",
    "system.welcome",
    # ai
    "ai.chat_complete",
    "ai.image_ready",
    "ai.chat_reply",
    "ai.kb_index_progress",
    "ai.quota_warning",
    "ai.quota_exhausted",
    # task
    "task.completed",
    "task.export_ready",
    "task.import_complete",
    "task.import_failed",
    # biz
    "biz.tenant_created",
    "biz.tenant_expired",
    "biz.plan_changed",
    "biz.plugin_update_available",
    "biz.domain_ssl_expiring",
    "biz.storage_warning",
    "biz.sub_admin_created",
    # audit (all)
    "audit.suspicious_login",
    "audit.permission_changed",
    "audit.role_changed",
    "audit.account_locked",
]


def upgrade() -> None:
    conn = op.get_bind()
    existing = conn.execute(
        sa.text("SELECT code FROM notification_templates WHERE code = ANY(:codes) AND is_deleted = false"),
        {"codes": DEPRECATED_CODES},
    ).scalars().all()

    if existing:
        conn.execute(
            sa.text(
                "UPDATE notification_templates SET is_deleted = true, deleted_at = now() "
                "WHERE code = ANY(:codes) AND is_deleted = false"
            ),
            {"codes": DEPRECATED_CODES},
        )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE notification_templates SET is_deleted = false, deleted_at = NULL "
            "WHERE code = ANY(:codes)"
        ),
        {"codes": DEPRECATED_CODES},
    )
