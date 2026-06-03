"""seed system.ai_writing agent assignment

Creates a global SystemAgentAssignment for the platform-level AI writing feature.
Agent is initially NULL — admin configures via the agent assignment UI.

Revision ID: 20260314_ai_wr
Revises: 67ac03130752
Create Date: 2026-03-14
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260314_ai_wr"
down_revision: str | Sequence[str] | None = "67ac03130752"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FEATURE_CODE = "system.ai_writing"
FEATURE_NAME = "AI Writing Assistant"
DESCRIPTION = (
    "Platform-level AI writing agent for rich text editors. "
    "Supports: continue, optimize, proofread, translate, summarize, expand, rewrite, custom, chat."
)


def upgrade() -> None:
    conn = op.get_bind()

    existing = conn.execute(text(
        "SELECT id FROM system_agent_assignments "
        "WHERE feature_code = :code AND tenant_id IS NULL AND is_deleted = false"
    ), {"code": FEATURE_CODE}).fetchone()

    if existing:
        print(f"[SEED] {FEATURE_CODE} assignment already exists (id={existing[0]})")
    else:
        result = conn.execute(text(
            "INSERT INTO system_agent_assignments "
            "(feature_code, feature_name, description, tenant_id, agent_id, "
            " is_active, created_at, updated_at, is_deleted) "
            "VALUES "
            "(:code, :name, :desc, NULL, NULL, "
            " true, NOW(), NOW(), false) "
            "RETURNING id"
        ), {
            "code": FEATURE_CODE,
            "name": FEATURE_NAME,
            "desc": DESCRIPTION,
        })
        assign_id = result.fetchone()[0]
        print(f"[SEED] Created {FEATURE_CODE} assignment (id={assign_id}, agent_id=NULL)")

    print(f"[SEED] {FEATURE_CODE} seeding done.")


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text(
        "DELETE FROM system_agent_assignments "
        "WHERE feature_code = :code AND tenant_id IS NULL"
    ), {"code": FEATURE_CODE})
    print(f"[SEED] Removed {FEATURE_CODE} assignment.")
