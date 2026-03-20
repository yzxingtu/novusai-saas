"""Idempotent repair: periodic_tasks.tenant_id -> owner_tenant_id

Revision ID: 20260324_pt_otid_repair
Revises: 20260323_acl_ars

ORM expects owner_tenant_id (unified scope refactor). If the DB was stamped to head
without running 20260320_urps, or the rename step was skipped, startup fails when
loading periodic tasks. 与 20260321_akso 内 _repair_20260320_urps_skipped 互补
（后者亦会 rename 多表 tenant_id→owner_tenant_id；本迁移专注 periodic_tasks 残留）。

This migration is a no-op when owner_tenant_id already exists. 无 downgrade。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260324_pt_otid_repair"
down_revision: str | Sequence[str] | None = "20260323_acl_ars"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(bind, table: str) -> set[str]:
    insp = inspect(bind)
    if not insp.has_table(table):
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _column_names(bind, "periodic_tasks")
    if not cols:
        return
    if "owner_tenant_id" in cols:
        return
    if "tenant_id" not in cols:
        return

    insp = inspect(bind)
    for uc in insp.get_unique_constraints("periodic_tasks") or []:
        if uc.get("name") == "uq_periodic_tasks_name_tenant":
            op.drop_constraint(
                "uq_periodic_tasks_name_tenant",
                "periodic_tasks",
                type_="unique",
            )
            break

    op.alter_column(
        "periodic_tasks",
        "tenant_id",
        new_column_name="owner_tenant_id",
        existing_type=sa.Integer(),
        existing_nullable=True,
    )

    insp_after = inspect(bind)
    names = {
        u.get("name")
        for u in (insp_after.get_unique_constraints("periodic_tasks") or [])
    }
    if "uq_periodic_tasks_name_owner_tenant" not in names:
        op.create_unique_constraint(
            "uq_periodic_tasks_name_owner_tenant",
            "periodic_tasks",
            ["name", "owner_tenant_id"],
        )


def downgrade() -> None:
    """Intentional no-op.

    Reverting tenant_id → owner_tenant_id would fight 20260320_urps (no downgrade)
    and could break ORM. Documented as allowed repair-migration pattern.
    """
    pass
