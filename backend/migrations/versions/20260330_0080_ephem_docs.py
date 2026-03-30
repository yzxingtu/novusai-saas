"""Add ephemeral documents

Revision ID: 20260330_0080_ephem
Revises: 20260330_0070_mem_prof
Create Date: 2026-03-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260330_0080_ephem"
down_revision: str | Sequence[str] | None = "20260330_0070_mem_prof"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ephemeral_documents",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("scope_type", sa.String(length=50), nullable=False, server_default="conversation_scoped"),
        sa.Column("scope_key", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False, server_default="Ephemeral Document"),
        sa.Column("content_kind", sa.String(length=20), nullable=False, server_default="text"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("promoted_knowledge_base_id", sa.Integer(), nullable=True),
        sa.Column("promoted_document_id", sa.Integer(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ephemeral_documents_tenant_id", "ephemeral_documents", ["tenant_id"], unique=False)
    op.create_index("ix_ephemeral_documents_conversation_id", "ephemeral_documents", ["conversation_id"], unique=False)
    op.create_index("ix_ephemeral_documents_agent_id", "ephemeral_documents", ["agent_id"], unique=False)
    op.create_index("ix_ephemeral_documents_user_id", "ephemeral_documents", ["user_id"], unique=False)
    op.create_index("ix_ephemeral_documents_scope_type", "ephemeral_documents", ["scope_type"], unique=False)
    op.create_index("ix_ephemeral_documents_scope_key", "ephemeral_documents", ["scope_key"], unique=False)
    op.create_index("ix_ephemeral_documents_content_hash", "ephemeral_documents", ["content_hash"], unique=False)
    op.create_index("ix_ephemeral_documents_status", "ephemeral_documents", ["status"], unique=False)
    op.create_index("ix_ephemeral_documents_expires_at", "ephemeral_documents", ["expires_at"], unique=False)
    op.create_index(
        "idx_ephemeral_documents_scope_hash",
        "ephemeral_documents",
        ["tenant_id", "scope_type", "scope_key", "content_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_ephemeral_documents_scope_hash", table_name="ephemeral_documents")
    op.drop_index("ix_ephemeral_documents_expires_at", table_name="ephemeral_documents")
    op.drop_index("ix_ephemeral_documents_status", table_name="ephemeral_documents")
    op.drop_index("ix_ephemeral_documents_content_hash", table_name="ephemeral_documents")
    op.drop_index("ix_ephemeral_documents_scope_key", table_name="ephemeral_documents")
    op.drop_index("ix_ephemeral_documents_scope_type", table_name="ephemeral_documents")
    op.drop_index("ix_ephemeral_documents_user_id", table_name="ephemeral_documents")
    op.drop_index("ix_ephemeral_documents_agent_id", table_name="ephemeral_documents")
    op.drop_index("ix_ephemeral_documents_conversation_id", table_name="ephemeral_documents")
    op.drop_index("ix_ephemeral_documents_tenant_id", table_name="ephemeral_documents")
    op.drop_table("ephemeral_documents")
