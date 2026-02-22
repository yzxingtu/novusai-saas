"""remove unused agent assignment seed data

Remove 3 unused feature_code records from system_agent_assignments:
- data_analysis: no frontend/backend code calls resolve('data_analysis')
- general_chat: global AI chat uses useGlobalAIChatStore directly, not agent assignment
- translation: use-ai-translate.ts uses global chat clipboard, not resolve('translation')

Only crud_generator is actually used (CRUD generator page resolves it).

Revision ID: 75773a96dac5
Revises: 5c37f4f986ac
Create Date: 2026-02-22 03:44:10.405267+00:00

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '75773a96dac5'
down_revision: Union[str, None] = '5c37f4f986ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UNUSED_FEATURE_CODES = ["data_analysis", "general_chat", "translation"]


def upgrade() -> None:
    conn = op.get_bind()
    for code in UNUSED_FEATURE_CODES:
        conn.execute(
            text(
                "DELETE FROM system_agent_assignments "
                "WHERE feature_code = :code AND tenant_id IS NULL"
            ),
            {"code": code},
        )


def downgrade() -> None:
    conn = op.get_bind()
    restore_data = [
        {
            "feature_code": "data_analysis",
            "feature_name": "Data Analysis",
            "description": "AI-driven data querying and analytics",
        },
        {
            "feature_code": "general_chat",
            "feature_name": "General AI Chat",
            "description": "General-purpose AI chat assistant",
        },
        {
            "feature_code": "translation",
            "feature_name": "AI Translation",
            "description": "Multi-language text translation",
        },
    ]
    for item in restore_data:
        conn.execute(
            text(
                "INSERT INTO system_agent_assignments "
                "(feature_code, feature_name, description, is_active, is_deleted, created_at, updated_at) "
                "VALUES (:feature_code, :feature_name, :description, true, false, NOW(), NOW()) "
                "ON CONFLICT (feature_code) WHERE tenant_id IS NULL DO NOTHING"
            ),
            item,
        )
