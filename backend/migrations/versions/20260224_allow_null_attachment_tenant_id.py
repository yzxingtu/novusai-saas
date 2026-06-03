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
    # 白名单静态 SQL（禁止动态表名拼接）/ Whitelist only — no dynamic identifiers
    op.execute(
        sa.text("UPDATE attachments SET tenant_id = 0 WHERE tenant_id IS NULL")
    )
    op.execute(
        sa.text(
            "UPDATE knowledge_documents SET tenant_id = 0 WHERE tenant_id IS NULL"
        )
    )
    op.execute(
        sa.text("UPDATE document_chunks SET tenant_id = 0 WHERE tenant_id IS NULL")
    )
    for table in ("attachments", "knowledge_documents", "document_chunks"):
        op.alter_column(
            table,
            "tenant_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
