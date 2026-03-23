"""fix workflow version nullability

Revision ID: wo_002_wf_ver_nullable_fix
Revises: wo_001_init
Create Date: 2026-03-23
"""

import sqlalchemy as sa
from alembic import op


revision = "wo_002_wf_ver_nullable_fix"
down_revision = "wo_001_init"
branch_labels = None


def upgrade():
    op.alter_column(
        "px_workflow_orchestration_triggers",
        "workflow_version_id",
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.alter_column(
        "px_workflow_orchestration_releases",
        "workflow_version_id",
        existing_type=sa.Integer(),
        nullable=False,
    )


def downgrade():
    return None
