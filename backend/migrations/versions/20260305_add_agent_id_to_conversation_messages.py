"""add agent_id to conversation_messages

Adds agent_id column (nullable FK → agents.id, ondelete=SET NULL) to
conversation_messages table for multi-agent conversation tracking.

Revision ID: 20260305_msg_agent
Revises: 20260305_tenant_uq
Create Date: 2026-03-05 18:30:00.000000+00:00

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260305_msg_agent"
down_revision: str | Sequence[str] | None = "20260305_tenant_uq"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversation_messages",
        sa.Column("agent_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_conv_msg_agent_id",
        "conversation_messages",
        ["agent_id"],
    )
    op.create_foreign_key(
        "fk_conv_msg_agent_id",
        "conversation_messages",
        "agents",
        ["agent_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_conv_msg_agent_id", "conversation_messages", type_="foreignkey")
    op.drop_index("ix_conv_msg_agent_id", table_name="conversation_messages")
    op.drop_column("conversation_messages", "agent_id")
