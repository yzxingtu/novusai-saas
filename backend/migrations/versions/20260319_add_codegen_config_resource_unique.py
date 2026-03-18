"""add unique constraint on codegen_configs.resource

Revision ID: 20260319_codegen_resource_uq
Revises: 20260319_page_op_75
Create Date: 2026-03-19 12:00:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260319_codegen_resource_uq"
down_revision: str | Sequence[str] | None = "20260319_page_op_75"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_codegen_configs_resource",
        "codegen_configs",
        ["resource"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_codegen_configs_resource",
        "codegen_configs",
        type_="unique",
    )
