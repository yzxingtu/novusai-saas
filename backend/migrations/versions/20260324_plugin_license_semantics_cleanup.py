"""Normalize plugin license semantics to trial/fixed_term/perpetual

Revision ID: 20260324_plugin_license_sem
Revises: 20260324_conv_owner_scope
Create Date: 2026-03-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260324_plugin_license_sem"
down_revision: str | Sequence[str] | None = "20260324_conv_owner_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE plugin_licenses
            SET license_type = 'fixed_term'
            WHERE license_type = 'perpetual'
              AND expires_at IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE plugin_licenses
            SET license_type = 'perpetual'
            WHERE license_type = 'fixed_term'
            """
        )
    )
