"""Add execution decisions table

Revision ID: 20260329_0050_exec_decisions
Revises: 20260329_0040_exec_trust
Create Date: 2026-03-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260329_0050_exec_decisions"
down_revision: str | Sequence[str] | None = "20260329_0040_exec_trust"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "execution_decisions",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("operator_id", sa.Integer(), nullable=True),
        sa.Column("operator_type", sa.String(length=50), nullable=True),
        sa.Column("decision_type", sa.String(length=50), nullable=False),
        sa.Column("subject_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "decision_scope",
            sa.String(length=30),
            nullable=False,
            server_default="once",
        ),
        sa.Column("risk_level", sa.String(length=50), nullable=True),
        sa.Column(
            "auto_approved",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("tool_call_id", sa.String(length=100), nullable=True),
        sa.Column("tool_name", sa.String(length=100), nullable=True),
        sa.Column("action_name", sa.String(length=100), nullable=True),
        sa.Column("table_name", sa.String(length=100), nullable=True),
        sa.Column("correlation_key", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_execution_decisions_id", "execution_decisions", ["id"], unique=False)
    op.create_index("ix_execution_decisions_tenant_id", "execution_decisions", ["tenant_id"], unique=False)
    op.create_index("ix_execution_decisions_conversation_id", "execution_decisions", ["conversation_id"], unique=False)
    op.create_index("ix_execution_decisions_agent_id", "execution_decisions", ["agent_id"], unique=False)
    op.create_index("ix_execution_decisions_operator_id", "execution_decisions", ["operator_id"], unique=False)
    op.create_index("ix_execution_decisions_operator_type", "execution_decisions", ["operator_type"], unique=False)
    op.create_index("ix_execution_decisions_decision_type", "execution_decisions", ["decision_type"], unique=False)
    op.create_index("ix_execution_decisions_subject_type", "execution_decisions", ["subject_type"], unique=False)
    op.create_index("ix_execution_decisions_status", "execution_decisions", ["status"], unique=False)
    op.create_index("ix_execution_decisions_tool_call_id", "execution_decisions", ["tool_call_id"], unique=False)
    op.create_index("ix_execution_decisions_tool_name", "execution_decisions", ["tool_name"], unique=False)
    op.create_index("ix_execution_decisions_correlation_key", "execution_decisions", ["correlation_key"], unique=False)
    op.create_index(
        "uq_execution_decisions_tenant_correlation",
        "execution_decisions",
        ["tenant_id", "correlation_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_execution_decisions_tenant_correlation", table_name="execution_decisions")
    op.drop_index("ix_execution_decisions_correlation_key", table_name="execution_decisions")
    op.drop_index("ix_execution_decisions_tool_name", table_name="execution_decisions")
    op.drop_index("ix_execution_decisions_tool_call_id", table_name="execution_decisions")
    op.drop_index("ix_execution_decisions_status", table_name="execution_decisions")
    op.drop_index("ix_execution_decisions_subject_type", table_name="execution_decisions")
    op.drop_index("ix_execution_decisions_decision_type", table_name="execution_decisions")
    op.drop_index("ix_execution_decisions_operator_type", table_name="execution_decisions")
    op.drop_index("ix_execution_decisions_operator_id", table_name="execution_decisions")
    op.drop_index("ix_execution_decisions_agent_id", table_name="execution_decisions")
    op.drop_index("ix_execution_decisions_conversation_id", table_name="execution_decisions")
    op.drop_index("ix_execution_decisions_tenant_id", table_name="execution_decisions")
    op.drop_index("ix_execution_decisions_id", table_name="execution_decisions")
    op.drop_table("execution_decisions")
