"""fix agent assignment seed data

Update feature_name and description to readable values (not i18n keys).
Fix crud_generator agent_id to point to the new 'CRUD 表单助手' agent.

Revision ID: 20260216_fix_aa
Revises: 20260216_awm
Create Date: 2026-02-16
"""

from alembic import op
from sqlalchemy import text

revision = "20260216_fix_aa"
down_revision = "20260216_awm"
branch_labels = None
depends_on = None

_FIXES = [
    {
        "feature_code": "crud_generator",
        "feature_name": "CRUD Code Generator",
        "description": "AI-assisted CRUD module configuration",
        "agent_name": "CRUD 表单助手",
    },
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


def upgrade() -> None:
    conn = op.get_bind()

    for item in _FIXES:
        update_fields = {
            "feature_code": item["feature_code"],
            "feature_name": item["feature_name"],
            "description": item["description"],
        }

        # Resolve agent_id if agent_name is specified
        if "agent_name" in item:
            result = conn.execute(
                text(
                    "SELECT id FROM agents "
                    "WHERE name = :name AND is_deleted = false "
                    "ORDER BY is_system DESC LIMIT 1"
                ),
                {"name": item["agent_name"]},
            )
            row = result.fetchone()
            if row:
                update_fields["agent_id"] = row[0]
                conn.execute(
                    text(
                        "UPDATE system_agent_assignments SET "
                        "feature_name = :feature_name, "
                        "description = :description, "
                        "agent_id = :agent_id, "
                        "updated_at = NOW() "
                        "WHERE feature_code = :feature_code "
                        "AND tenant_id IS NULL AND is_deleted = false"
                    ),
                    update_fields,
                )
                continue

        conn.execute(
            text(
                "UPDATE system_agent_assignments SET "
                "feature_name = :feature_name, "
                "description = :description, "
                "updated_at = NOW() "
                "WHERE feature_code = :feature_code "
                "AND tenant_id IS NULL AND is_deleted = false"
            ),
            update_fields,
        )


def downgrade() -> None:
    pass
