"""Fix expires_at column type from String to DateTime

Revision ID: novusdoc_pro_002
Revises: novusdoc_pro_001
Create Date: 2026-02-26

The initial migration created px_novusdoc_pro_shares.expires_at as String(50),
but the model declares DateTime(timezone=True). This migration fixes the mismatch.
"""

from alembic import op

revision = "novusdoc_pro_002"
down_revision = "novusdoc_pro_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert expires_at from String(50) to DateTime with timezone
    # Existing string values (ISO 8601) are auto-parsed by PostgreSQL CAST
    op.execute(
        "ALTER TABLE px_novusdoc_pro_shares "
        "ALTER COLUMN expires_at TYPE TIMESTAMP WITH TIME ZONE "
        "USING expires_at::TIMESTAMP WITH TIME ZONE"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE px_novusdoc_pro_shares "
        "ALTER COLUMN expires_at TYPE VARCHAR(50) "
        "USING expires_at::VARCHAR(50)"
    )
