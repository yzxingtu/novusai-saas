"""add unique constraint on codegen_configs.resource

Revision ID: 20260319_codegen_resource_uq
Revises: 20260317_001_versions
Create Date: 2026-03-19 12:00:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "20260319_codegen_resource_uq"
down_revision: str | Sequence[str] | None = "20260317_001_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("codegen_configs"):
        print(
            "[codegen] Table codegen_configs not present yet (revision graph branch); "
            "skip uq_codegen_configs_resource"
        )
        return
    for uc in insp.get_unique_constraints("codegen_configs") or []:
        if uc.get("name") == "uq_codegen_configs_resource":
            print("[codegen] uq_codegen_configs_resource already exists, skip")
            return
    op.create_unique_constraint(
        "uq_codegen_configs_resource",
        "codegen_configs",
        ["resource"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not inspect(bind).has_table("codegen_configs"):
        return
    op.execute(
        sa.text(
            "ALTER TABLE codegen_configs DROP CONSTRAINT IF EXISTS uq_codegen_configs_resource"
        )
    )
