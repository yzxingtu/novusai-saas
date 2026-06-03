"""add trace_id column to operation_logs

Revision ID: 20260318_0003_trace_id
Revises: 20260318_0002_litellm_desc
Create Date: 2026-03-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "20260318_0003_trace_id"
down_revision = "20260318_0002_litellm_desc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "operation_logs",
        sa.Column("trace_id", sa.String(length=64), nullable=True, comment="请求追踪 ID / Trace ID for request correlation"),
    )
    op.create_index("ix_operation_logs_trace_id", "operation_logs", ["trace_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_operation_logs_trace_id", table_name="operation_logs")
    op.drop_column("operation_logs", "trace_id")
