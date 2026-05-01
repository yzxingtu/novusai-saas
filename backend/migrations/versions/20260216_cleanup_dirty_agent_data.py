"""cleanup dirty agent data

DB audit found 3 data issues requiring cleanup:

DB-1: Duplicate CRUD agent (id=21 'crud_generator_assistant') created by
      fix_crud_generator_agent migration after rename_agents already renamed
      agent 17 to 'CRUD 生成助手'. Delete agent 21 + its binding + conversations.

DB-2: skill_packages id=18 '系统数据智能技能包' has scope='global' while all
      other system packages use scope='admin'. Unify to 'admin'.

DB-3: Agent id=20 '数据分析助手' has execution_mode='tool_call' which is not
      a valid AgentExecutionModeEnum value. Fix to 'conversation'.

Revision ID: cc0216010000
Revises: aa0215030000
Create Date: 2026-02-16 01:00:00.000000+08:00
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "cc0216010000"
down_revision: Union[str, None] = "aa0215030000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- DB-1: Delete duplicate CRUD agent (name='crud_generator_assistant') ---
    dup_agent = conn.execute(text(
        "SELECT id FROM agents "
        "WHERE name = 'crud_generator_assistant' "
        "AND tenant_id IS NULL AND is_deleted = false "
        "LIMIT 1"
    )).fetchone()

    if dup_agent:
        dup_id = dup_agent[0]

        # Delete conversation messages belonging to the duplicate agent
        conn.execute(text(
            "DELETE FROM conversation_messages "
            "WHERE conversation_id IN ("
            "  SELECT id FROM agent_conversations WHERE agent_id = :aid"
            ")"
        ), {"aid": dup_id})

        # Delete conversations
        conn.execute(text(
            "DELETE FROM agent_conversations WHERE agent_id = :aid"
        ), {"aid": dup_id})

        # Delete the agent itself
        conn.execute(text(
            "DELETE FROM agents WHERE id = :aid"
        ), {"aid": dup_id})

        print(f"[CLEANUP] DB-1: Deleted duplicate agent "
              f"'crud_generator_assistant' (id={dup_id}) + related data")
    else:
        print("[CLEANUP] DB-1: No duplicate 'crud_generator_assistant' found, skipping")

    # --- DB-2: Unify scope for 系统数据智能技能包 ---
    result = conn.execute(text(
        "UPDATE skill_packages SET scope = 'admin', updated_at = NOW() "
        "WHERE name = '系统数据智能技能包' "
        "AND scope = 'global' AND is_deleted = false"
    ))
    print(f"[CLEANUP] DB-2: Updated {result.rowcount} skill_packages scope "
          f"global → admin")

    # --- DB-3: Fix invalid execution_mode ---
    result = conn.execute(text(
        "UPDATE agents SET execution_mode = 'conversation', updated_at = NOW() "
        "WHERE name = '数据分析助手' "
        "AND execution_mode = 'tool_call' AND is_deleted = false"
    ))
    print(f"[CLEANUP] DB-3: Updated {result.rowcount} agents execution_mode "
          f"tool_call → conversation")


def downgrade() -> None:
    conn = op.get_bind()

    # --- Revert DB-3: Restore execution_mode ---
    conn.execute(text(
        "UPDATE agents SET execution_mode = 'tool_call', updated_at = NOW() "
        "WHERE name = '数据分析助手' "
        "AND execution_mode = 'conversation' AND is_deleted = false"
    ))

    # --- Revert DB-2: Restore scope ---
    conn.execute(text(
        "UPDATE skill_packages SET scope = 'global', updated_at = NOW() "
        "WHERE name = '系统数据智能技能包' "
        "AND scope = 'admin' AND is_deleted = false"
    ))

    # --- DB-1: Cannot fully restore deleted agent data ---
    # The duplicate agent was a migration bug; restoring it would recreate the problem.
    # If needed, re-run 20260215_fix_crud_generator_agent.py manually.
    print("[DOWNGRADE] DB-1: Duplicate agent not restored (was a migration bug)")
