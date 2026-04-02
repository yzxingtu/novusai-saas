"""add call_type to ai_call_logs

Revision ID: 20260402_call_type
Revises: 20260401_int_modes
Create Date: 2026-04-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260402_call_type"
down_revision: str | Sequence[str] | None = "20260401_int_modes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_call_logs",
        sa.Column(
            "call_type",
            sa.String(length=50),
            server_default="main_chat",
            nullable=False,
            comment="调用类型: main_chat/internal_memory/internal_tool",
        ),
    )
    op.create_index(
        "idx_ai_call_logs_call_type",
        "ai_call_logs",
        ["call_type"],
    )
    op.create_index(
        "idx_ai_call_logs_conv_call_type",
        "ai_call_logs",
        ["conversation_id", "call_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_ai_call_logs_conv_call_type", table_name="ai_call_logs")
    op.drop_index("idx_ai_call_logs_call_type", table_name="ai_call_logs")
    op.drop_column("ai_call_logs", "call_type")
