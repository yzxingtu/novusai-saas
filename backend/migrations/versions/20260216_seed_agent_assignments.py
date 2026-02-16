"""seed system_agent_assignments

Insert 4 preset system agent assignment records.
Agent IDs are resolved by name at migration time.

Revision ID: 20260216_saa_seed
Revises: 20260216_saa
Create Date: 2026-02-16
"""

from alembic import op
from sqlalchemy import text

revision = "20260216_saa_seed"
down_revision = "20260216_saa"
branch_labels = None
depends_on = None

SEED_ASSIGNMENTS = [
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
        "agent_name": "数据分析助手",
    },
    {
        "feature_code": "general_chat",
        "feature_name": "General AI Chat",
        "description": "General-purpose AI chat assistant",
        "agent_name": "智能助手",
    },
    {
        "feature_code": "translation",
        "feature_name": "AI Translation",
        "description": "Multi-language text translation",
        "agent_name": "智能助手",
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    for item in SEED_ASSIGNMENTS:
        # Resolve agent_id by name (non-deleted, prefer is_system=true)
        result = conn.execute(
            text(
                "SELECT id FROM agents "
                "WHERE name = :name AND is_deleted = false "
                "ORDER BY is_system DESC LIMIT 1"
            ),
            {"name": item["agent_name"]},
        )
        row = result.fetchone()
        agent_id = row[0] if row else None

        conn.execute(
            text(
                "INSERT INTO system_agent_assignments "
                "(feature_code, feature_name, description, agent_id, is_active, is_deleted, created_at, updated_at) "
                "VALUES (:feature_code, :feature_name, :description, :agent_id, true, false, NOW(), NOW()) "
                "ON CONFLICT (feature_code) WHERE tenant_id IS NULL DO NOTHING"
            ),
            {
                "feature_code": item["feature_code"],
                "feature_name": item["feature_name"],
                "description": item["description"],
                "agent_id": agent_id,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    for item in SEED_ASSIGNMENTS:
        conn.execute(
            text("DELETE FROM system_agent_assignments WHERE feature_code = :code"),
            {"code": item["feature_code"]},
        )
