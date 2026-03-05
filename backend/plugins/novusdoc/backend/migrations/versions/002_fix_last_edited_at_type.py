"""Fix last_edited_at column type from String to DateTime

Revision ID: novusdoc_002
Revises: novusdoc_001
Create Date: 2026-02-26

The initial migration created px_novusdoc_documents.last_edited_at as String(50),
but the model declares DateTime(timezone=True). This migration fixes the mismatch.
"""

from alembic import op

revision = "novusdoc_002"
down_revision = "novusdoc_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert last_edited_at from String(50) to DateTime with timezone
    # Existing string values (ISO 8601) are auto-parsed by PostgreSQL CAST
    op.execute(
        "ALTER TABLE px_novusdoc_documents "
        "ALTER COLUMN last_edited_at TYPE TIMESTAMP WITH TIME ZONE "
        "USING last_edited_at::TIMESTAMP WITH TIME ZONE"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE px_novusdoc_documents "
        "ALTER COLUMN last_edited_at TYPE VARCHAR(50) "
        "USING last_edited_at::VARCHAR(50)"
    )
