"""Add AI call log contract fields

Add agent_id / conversation_id to ai_call_logs so audit records can trace
the source agent and conversation.
为 ai_call_logs 增加 agent_id / conversation_id，便于审计追踪来源智能体与会话。

Revision ID: 20260321_ai_call_log_contract
Revises: 20260321_retired_runtime
Create Date: 2026-03-21 01:00:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260321_ai_call_log_contract"
down_revision: str | Sequence[str] | None = "20260321_retired_runtime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_call_logs",
        sa.Column("agent_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ai_call_logs",
        sa.Column("conversation_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_ai_call_logs_agent_id_agents",
        "ai_call_logs",
        "agents",
        ["agent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_ai_call_logs_conversation_id_agent_conversations",
        "ai_call_logs",
        "agent_conversations",
        ["conversation_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_ai_call_logs_agent_created",
        "ai_call_logs",
        ["agent_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_ai_call_logs_conv_created",
        "ai_call_logs",
        ["conversation_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_ai_call_logs_conv_created", table_name="ai_call_logs")
    op.drop_index("idx_ai_call_logs_agent_created", table_name="ai_call_logs")
    op.drop_constraint(
        "fk_ai_call_logs_conversation_id_agent_conversations",
        "ai_call_logs",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_ai_call_logs_agent_id_agents",
        "ai_call_logs",
        type_="foreignkey",
    )
    op.drop_column("ai_call_logs", "conversation_id")
    op.drop_column("ai_call_logs", "agent_id")
