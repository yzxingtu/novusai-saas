# -*- coding: utf-8 -*-
"""drop agent_versions.tenant_id foreign key constraint.

The agent_versions table was created with a FK on tenant_id -> tenants.id.
However, platform-level agents use PLATFORM_TENANT_ID = 0 which has no
matching row in the tenants table, causing IntegrityError on publish.

This aligns agent_versions with the project convention used by
notifications, attachments, knowledge_documents, etc., where tenant_id
is a plain Integer column (0 = platform-level) without FK constraints.

Fixes #1
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260610_0048_drop_av_tenant_fk"
down_revision: str | Sequence[str] | None = "20260530_0047_ann_pending_idx"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove FK constraint on agent_versions.tenant_id."""
    op.drop_constraint(
        "agent_versions_tenant_id_fkey",
        "agent_versions",
        type_="foreignkey",
    )


def downgrade() -> None:
    """Restore FK constraint on agent_versions.tenant_id."""
    op.create_foreign_key(
        "agent_versions_tenant_id_fkey",
        "agent_versions",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
