"""Allow NULL tenant_id in attachments, knowledge_documents, document_chunks
for global/admin KB resources

Revision ID: kb_attachment_null_tid
Revises: kb_visibility_001
Create Date: 2026-02-24
"""
from alembic import op
import sqlalchemy as sa

revision = "kb_attachment_null_tid"
down_revision = "kb_visibility_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("attachments", "knowledge_documents", "document_chunks"):
        op.alter_column(
            table,
            "tenant_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    for table in ("attachments", "knowledge_documents", "document_chunks"):
        op.execute(f"UPDATE {table} SET tenant_id = 0 WHERE tenant_id IS NULL")
        op.alter_column(
            table,
            "tenant_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
