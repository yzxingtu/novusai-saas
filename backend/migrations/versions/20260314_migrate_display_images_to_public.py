"""migrate display-class image attachments to public visibility

Revision ID: 20260314_display_imgs_public
Revises: 20260313_page_awareness_v2
Create Date: 2026-03-14 10:00:00.000000+00:00

"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "20260314_display_imgs_public"
down_revision = "20260313_page_awareness_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        text(
            """
            UPDATE attachments
            SET visibility = 'public'
            WHERE visibility = 'private'
              AND mime_type LIKE 'image/%'
              AND source IN ('platform_admin', 'tenant_admin', 'tenant_user')
              AND (
                business_type IS NULL
                OR business_type IN ('avatar', 'brand', 'provider_icon', '')
              )
            """
        )
    )


def downgrade() -> None:
    pass
