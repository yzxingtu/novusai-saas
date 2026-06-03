"""Add execution trust policies table

Revision ID: 20260329_0040_exec_trust
Revises: 20260329_0030_memory_records
Create Date: 2026-03-29
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260329_0040_exec_trust"
down_revision: str | Sequence[str] | None = "20260329_0030_memory_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "execution_trust_policies",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("operator_id", sa.Integer(), nullable=True),
        sa.Column("operator_type", sa.String(length=50), nullable=True),
        sa.Column("tool_family", sa.String(length=100), nullable=True),
        sa.Column("allowed_tool_names", sa.JSON(), nullable=True),
        sa.Column("risk_level_cap", sa.String(length=50), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.Column("grant_reason", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
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
    op.create_index("ix_execution_trust_policies_id", "execution_trust_policies", ["id"], unique=False)
    op.create_index("ix_execution_trust_policies_tenant_id", "execution_trust_policies", ["tenant_id"], unique=False)
    op.create_index("ix_execution_trust_policies_conversation_id", "execution_trust_policies", ["conversation_id"], unique=False)
    op.create_index("ix_execution_trust_policies_agent_id", "execution_trust_policies", ["agent_id"], unique=False)
    op.create_index("ix_execution_trust_policies_operator_id", "execution_trust_policies", ["operator_id"], unique=False)
    op.create_index("ix_execution_trust_policies_operator_type", "execution_trust_policies", ["operator_type"], unique=False)
    op.create_index("ix_execution_trust_policies_tool_family", "execution_trust_policies", ["tool_family"], unique=False)
    op.create_index("ix_execution_trust_policies_expires_at", "execution_trust_policies", ["expires_at"], unique=False)
    op.create_index("ix_execution_trust_policies_is_active", "execution_trust_policies", ["is_active"], unique=False)
    op.create_index(
        "idx_exec_trust_scope",
        "execution_trust_policies",
        ["tenant_id", "conversation_id", "agent_id", "operator_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "idx_exec_trust_operator_family",
        "execution_trust_policies",
        ["tenant_id", "operator_type", "operator_id", "tool_family", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_exec_trust_operator_family", table_name="execution_trust_policies")
    op.drop_index("idx_exec_trust_scope", table_name="execution_trust_policies")
    op.drop_index("ix_execution_trust_policies_is_active", table_name="execution_trust_policies")
    op.drop_index("ix_execution_trust_policies_expires_at", table_name="execution_trust_policies")
    op.drop_index("ix_execution_trust_policies_tool_family", table_name="execution_trust_policies")
    op.drop_index("ix_execution_trust_policies_operator_type", table_name="execution_trust_policies")
    op.drop_index("ix_execution_trust_policies_operator_id", table_name="execution_trust_policies")
    op.drop_index("ix_execution_trust_policies_agent_id", table_name="execution_trust_policies")
    op.drop_index("ix_execution_trust_policies_conversation_id", table_name="execution_trust_policies")
    op.drop_index("ix_execution_trust_policies_tenant_id", table_name="execution_trust_policies")
    op.drop_index("ix_execution_trust_policies_id", table_name="execution_trust_policies")
    op.drop_table("execution_trust_policies")
