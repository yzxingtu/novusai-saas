"""Drop deprecated skill_packages.target_audience column

Revision ID: 20260324_drop_skill_pkg_aud
Revises: 20260324_plugin_license_sem
Create Date: 2026-03-24

SkillPackage no longer carries package-level audience semantics. Effective
availability is determined by ownership + agent binding, so the legacy
target_audience column can be removed from the schema.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "20260324_drop_skill_pkg_aud"
down_revision: str | Sequence[str] | None = "20260324_plugin_license_sem"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(bind, table: str) -> set[str]:
    insp = inspect(bind)
    if not insp.has_table(table):
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _index_names(bind, table: str) -> set[str]:
    insp = inspect(bind)
    if not insp.has_table(table):
        return set()
    return {idx["name"] for idx in insp.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    cols = _column_names(bind, "skill_packages")
    if not cols:
        return

    if "ix_skill_packages_target_audience" in _index_names(bind, "skill_packages"):
        op.drop_index(
            "ix_skill_packages_target_audience",
            table_name="skill_packages",
        )

    if "target_audience" in cols:
        op.drop_column("skill_packages", "target_audience")


def downgrade() -> None:
    bind = op.get_bind()
    cols = _column_names(bind, "skill_packages")
    if not cols:
        return

    if "target_audience" not in cols:
        op.add_column(
            "skill_packages",
            sa.Column(
                "target_audience",
                sa.String(length=20),
                nullable=False,
                server_default="all",
                comment="目标受众：all / admin_only / admin_tenant",
            ),
        )

    if "ix_skill_packages_target_audience" not in _index_names(bind, "skill_packages"):
        op.create_index(
            "ix_skill_packages_target_audience",
            "skill_packages",
            ["target_audience"],
        )
