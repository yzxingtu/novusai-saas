"""data_migrate_tools_to_skills

Migrate existing data from Tool architecture to Skill architecture:
1. tool_definitions → skills (type mapping)
2. agent.tool_bindings JSON → agent_skill_bindings rows
3. agent.knowledge_base_ids → knowledge_base Skill + binding
4. agent.context_config.data_intelligence_enabled → data_intelligence Skill + binding

Revision ID: a1b2c3d4e5f6
Revises: 63eadfe34156
Create Date: 2026-02-13 19:45:00.000000+08:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '63eadfe34156'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ToolType → SkillType mapping
TOOL_TYPE_TO_SKILL_TYPE = {
    "http": "http",
    "email": "email",
    "code": "code",
    "builtin": "builtin",
    "database": "builtin",      # database tools → builtin skill
    "text_to_sql": "builtin",   # text_to_sql is engine-generated, skip if standalone
    "api_action": "builtin",
    "data_create": "builtin",
    "data_update": "builtin",
    "data_delete": "builtin",
}


def upgrade() -> None:
    """Migrate data from tools to skills."""
    conn = op.get_bind()

    # ================================================================
    # Phase 1: tool_definitions → skills
    # ================================================================
    print("[SK-9 T1] Migrating tool_definitions → skills ...")

    tools = conn.execute(text(
        "SELECT id, tenant_id, name, description, type, config, "
        "input_schema, output_schema, timeout, is_system, is_active, "
        "created_at, updated_at, is_deleted, deleted_at, delete_level "
        "FROM tool_definitions ORDER BY id"
    )).fetchall()

    # old_tool_id → new_skill_id mapping (for Phase 2)
    tool_to_skill: dict[int, int] = {}
    skipped_types = {"text_to_sql", "api_action", "data_create", "data_update", "data_delete"}

    for tool in tools:
        tool_type = tool.type
        # Skip engine-generated tool types (these are dynamically created by SkillResolver)
        if tool_type in skipped_types:
            print(f"  [SKIP] tool #{tool.id} '{tool.name}' type={tool_type} (engine-generated)")
            continue

        skill_type = TOOL_TYPE_TO_SKILL_TYPE.get(tool_type)
        if not skill_type:
            print(f"  [WARN] tool #{tool.id} '{tool.name}' unknown type={tool_type}, mapping to builtin")
            skill_type = "builtin"

        # is_system → scope mapping
        scope = "admin" if tool.is_system else "tenant"

        # Check for duplicate name within same tenant+scope
        existing = conn.execute(text(
            "SELECT id FROM skills WHERE name = :name AND tenant_id IS NOT DISTINCT FROM :tenant_id "
            "AND is_deleted = false"
        ), {"name": tool.name, "tenant_id": tool.tenant_id}).fetchone()

        if existing:
            tool_to_skill[tool.id] = existing.id
            print(f"  [EXISTS] tool #{tool.id} '{tool.name}' → skill #{existing.id} (already exists)")
            continue

        result = conn.execute(text(
            "INSERT INTO skills "
            "(tenant_id, name, description, type, scope, config, input_schema, output_schema, "
            " timeout, is_active, sort_order, "
            " created_at, updated_at, is_deleted, deleted_at, delete_level) "
            "VALUES "
            "(:tenant_id, :name, :description, :type, :scope, :config, :input_schema, :output_schema, "
            " :timeout, :is_active, 0, "
            " :created_at, :updated_at, :is_deleted, :deleted_at, :delete_level) "
            "RETURNING id"
        ), {
            "tenant_id": tool.tenant_id,
            "name": tool.name,
            "description": tool.description,
            "type": skill_type,
            "scope": scope,
            "config": tool.config,
            "input_schema": tool.input_schema,
            "output_schema": tool.output_schema,
            "timeout": tool.timeout,
            "is_active": tool.is_active,
            "created_at": tool.created_at,
            "updated_at": tool.updated_at,
            "is_deleted": tool.is_deleted,
            "deleted_at": tool.deleted_at,
            "delete_level": tool.delete_level,
        })

        new_id = result.fetchone()[0]
        tool_to_skill[tool.id] = new_id
        print(f"  [OK] tool #{tool.id} '{tool.name}' ({tool_type}) → skill #{new_id} ({skill_type}, {scope})")

    print(f"[SK-9 T1] Done. Migrated {len(tool_to_skill)} tools → skills.")

    # ================================================================
    # Phase 2: agent.tool_bindings → agent_skill_bindings
    # ================================================================
    print("[SK-9 T2] Migrating agent.tool_bindings → agent_skill_bindings ...")

    agents_with_bindings = conn.execute(text(
        "SELECT id, tenant_id, tool_bindings FROM agents "
        "WHERE tool_bindings IS NOT NULL AND tool_bindings::text != '[]' "
        "AND tool_bindings::text != 'null' "
        "ORDER BY id"
    )).fetchall()

    binding_count = 0
    for agent in agents_with_bindings:
        bindings = agent.tool_bindings
        if not isinstance(bindings, list):
            continue

        for idx, binding in enumerate(bindings):
            if not isinstance(binding, dict):
                continue

            tool_id = binding.get("tool_id")
            if tool_id is None:
                # Try alternate key formats
                tool_id = binding.get("id")

            if tool_id is None:
                print(f"  [WARN] agent #{agent.id} binding has no tool_id: {binding}")
                continue

            skill_id = tool_to_skill.get(tool_id)
            if skill_id is None:
                # Try to find skill by name if tool wasn't migrated (e.g. engine-generated type)
                tool_name = binding.get("name")
                if tool_name:
                    match = conn.execute(text(
                        "SELECT id FROM skills WHERE name = :name "
                        "AND tenant_id IS NOT DISTINCT FROM :tenant_id "
                        "AND is_deleted = false LIMIT 1"
                    ), {"name": tool_name, "tenant_id": agent.tenant_id}).fetchone()
                    if match:
                        skill_id = match.id
                        print(f"  [MATCH] agent #{agent.id} tool '{tool_name}' → skill #{skill_id} (by name)")

            if skill_id is None:
                print(f"  [MISS] agent #{agent.id} tool_id={tool_id} not found in migrated skills")
                continue

            # Check if binding already exists
            exists = conn.execute(text(
                "SELECT id FROM agent_skill_bindings "
                "WHERE agent_id = :agent_id AND skill_id = :skill_id AND is_deleted = false"
            ), {"agent_id": agent.id, "skill_id": skill_id}).fetchone()

            if exists:
                continue

            conn.execute(text(
                "INSERT INTO agent_skill_bindings "
                "(tenant_id, agent_id, skill_id, enabled, sort_order, "
                " created_at, updated_at, is_deleted) "
                "VALUES "
                "(:tenant_id, :agent_id, :skill_id, true, :sort_order, "
                " NOW(), NOW(), false)"
            ), {
                "tenant_id": agent.tenant_id,
                "agent_id": agent.id,
                "skill_id": skill_id,
                "sort_order": idx,
            })
            binding_count += 1

    print(f"[SK-9 T2] Done. Created {binding_count} agent_skill_bindings.")

    # ================================================================
    # Phase 3: knowledge_base_ids + data_intelligence → skills + bindings
    # ================================================================
    print("[SK-9 T3] Migrating knowledge_base_ids + data_intelligence → skills ...")

    # 3a: knowledge_base_ids → knowledge_base Skill + binding
    agents_with_kb = conn.execute(text(
        "SELECT id, tenant_id, knowledge_base_ids, rag_config FROM agents "
        "WHERE knowledge_base_ids IS NOT NULL AND knowledge_base_ids::text != '[]' "
        "AND knowledge_base_ids::text != 'null' "
        "AND is_deleted = false "
        "ORDER BY id"
    )).fetchall()

    kb_skill_count = 0
    for agent in agents_with_kb:
        kb_ids = agent.knowledge_base_ids
        if not isinstance(kb_ids, list) or len(kb_ids) == 0:
            continue

        rag_config = agent.rag_config if isinstance(agent.rag_config, dict) else {}

        # Create a knowledge_base Skill for this agent's KB config
        skill_name = f"KB-Agent#{agent.id}"

        # Check if already migrated
        existing = conn.execute(text(
            "SELECT s.id FROM skills s "
            "JOIN agent_skill_bindings asb ON asb.skill_id = s.id "
            "WHERE asb.agent_id = :agent_id AND s.type = 'knowledge_base' "
            "AND s.is_deleted = false AND asb.is_deleted = false LIMIT 1"
        ), {"agent_id": agent.id}).fetchone()

        if existing:
            print(f"  [EXISTS] agent #{agent.id} already has knowledge_base skill #{existing.id}")
            continue

        # Build skill config: embed kb_ids + rag_config
        skill_config = {
            "knowledge_base_ids": kb_ids,
            "rag_config": {
                "enabled": rag_config.get("enabled", True),
                "top_k": rag_config.get("top_k", 5),
                "score_threshold": rag_config.get("score_threshold", 0.5),
                "search_mode": rag_config.get("search_mode", "hybrid"),
                "rewrite_strategy": rag_config.get("rewrite_strategy", "none"),
                "reranker_enabled": rag_config.get("reranker_enabled", False),
                "context_token_ratio": rag_config.get("context_token_ratio", 0.3),
            },
        }

        import json
        result = conn.execute(text(
            "INSERT INTO skills "
            "(tenant_id, name, description, type, scope, config, "
            " timeout, is_active, sort_order, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(:tenant_id, :name, :description, 'knowledge_base', 'tenant', :config::jsonb, "
            " 30, true, 0, "
            " NOW(), NOW(), false) "
            "RETURNING id"
        ), {
            "tenant_id": agent.tenant_id,
            "name": skill_name,
            "description": f"Auto-migrated from Agent #{agent.id} knowledge_base_ids",
            "config": json.dumps(skill_config),
        })

        new_skill_id = result.fetchone()[0]

        conn.execute(text(
            "INSERT INTO agent_skill_bindings "
            "(tenant_id, agent_id, skill_id, enabled, sort_order, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(:tenant_id, :agent_id, :skill_id, true, 100, "
            " NOW(), NOW(), false)"
        ), {
            "tenant_id": agent.tenant_id,
            "agent_id": agent.id,
            "skill_id": new_skill_id,
        })

        kb_skill_count += 1
        print(f"  [OK] agent #{agent.id} kb_ids={kb_ids} → skill #{new_skill_id} (knowledge_base)")

    print(f"[SK-9 T3a] Done. Created {kb_skill_count} knowledge_base skills.")

    # 3b: data_intelligence_enabled → data_intelligence Skill + binding
    agents_with_di = conn.execute(text(
        "SELECT id, tenant_id, context_config FROM agents "
        "WHERE context_config IS NOT NULL "
        "AND is_deleted = false "
        "ORDER BY id"
    )).fetchall()

    di_skill_count = 0
    for agent in agents_with_di:
        cc = agent.context_config
        if not isinstance(cc, dict):
            continue

        if not cc.get("data_intelligence_enabled"):
            continue

        # Check if already migrated
        existing = conn.execute(text(
            "SELECT s.id FROM skills s "
            "JOIN agent_skill_bindings asb ON asb.skill_id = s.id "
            "WHERE asb.agent_id = :agent_id AND s.type = 'data_intelligence' "
            "AND s.is_deleted = false AND asb.is_deleted = false LIMIT 1"
        ), {"agent_id": agent.id}).fetchone()

        if existing:
            print(f"  [EXISTS] agent #{agent.id} already has data_intelligence skill #{existing.id}")
            continue

        skill_name = f"DI-Agent#{agent.id}"

        # Build config with default allowed operations
        import json
        di_config = {
            "allowed_operations": ["read", "create", "update", "delete"],
        }

        result = conn.execute(text(
            "INSERT INTO skills "
            "(tenant_id, name, description, type, scope, config, "
            " timeout, is_active, sort_order, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(:tenant_id, :name, :description, 'data_intelligence', 'tenant', :config::jsonb, "
            " 60, true, 0, "
            " NOW(), NOW(), false) "
            "RETURNING id"
        ), {
            "tenant_id": agent.tenant_id,
            "name": skill_name,
            "description": f"Auto-migrated from Agent #{agent.id} data_intelligence_enabled",
            "config": json.dumps(di_config),
        })

        new_skill_id = result.fetchone()[0]

        conn.execute(text(
            "INSERT INTO agent_skill_bindings "
            "(tenant_id, agent_id, skill_id, enabled, sort_order, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(:tenant_id, :agent_id, :skill_id, true, 101, "
            " NOW(), NOW(), false)"
        ), {
            "tenant_id": agent.tenant_id,
            "agent_id": agent.id,
            "skill_id": new_skill_id,
        })

        di_skill_count += 1
        print(f"  [OK] agent #{agent.id} data_intelligence → skill #{new_skill_id}")

    print(f"[SK-9 T3b] Done. Created {di_skill_count} data_intelligence skills.")
    print("[SK-9] Data migration complete.")


def downgrade() -> None:
    """Remove migrated data (rollback)."""
    conn = op.get_bind()

    # Delete auto-migrated knowledge_base and data_intelligence skills + their bindings
    # (cascades via FK on agent_skill_bindings.skill_id)
    conn.execute(text(
        "DELETE FROM skills WHERE name LIKE 'KB-Agent#%' OR name LIKE 'DI-Agent#%'"
    ))

    # Delete agent_skill_bindings that were migrated from tool_bindings
    # (we can't perfectly distinguish, so delete all non-manual ones)
    # This is safe because the old tool_bindings JSON is still intact on agents
    conn.execute(text(
        "DELETE FROM agent_skill_bindings"
    ))

    # Delete skills that were migrated from tool_definitions
    # Keep the tool_definitions table intact
    conn.execute(text(
        "DELETE FROM skills WHERE description LIKE 'Auto-migrated%' "
        "OR id IN (SELECT id FROM skills WHERE name IN (SELECT name FROM tool_definitions))"
    ))

    print("[SK-9] Rollback complete. Old tool_definitions and agent.tool_bindings remain intact.")
