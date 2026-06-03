"""harden knowledge base scope owner invariants

Revision ID: 20260430_0023_kb_scope_owner
Revises: 20260430_0022_announcements
Create Date: 2026-04-30

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260430_0023_kb_scope_owner"
down_revision: str | Sequence[str] | None = "20260430_0022_announcements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CONSTRAINT_NAME = "ck_knowledge_bases_scope_owner_tenant"


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE knowledge_bases
            SET scope = 'all_tenants'
            WHERE owner_tenant_id IS NOT NULL
              AND scope <> 'all_tenants'
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM resource_tenant_assignments AS r
            USING knowledge_bases AS kb
            WHERE r.resource_type = 'knowledge_base'
              AND r.resource_id = kb.id
              AND kb.owner_tenant_id IS NOT NULL
            """
        )
    )
    op.create_check_constraint(
        CONSTRAINT_NAME,
        "knowledge_bases",
        "((owner_tenant_id IS NULL AND scope IN "
        "('global_shared', 'admin_only', 'all_tenants', "
        "'admin_and_selected_tenants', 'selected_tenants')) OR "
        "(owner_tenant_id IS NOT NULL AND scope = 'all_tenants'))",
    )


def downgrade() -> None:
    op.drop_constraint(
        CONSTRAINT_NAME,
        "knowledge_bases",
        type_="check",
    )
