"""[NO-OP] replace_crud_generator_with_toolkit

Superseded by 20260216_remove_crud_generator_seed_data (all CRUD data soft-deleted).
Builtin CRUD Generator removed.

Original: Replace old CRUD Generator (builtin) agent/skill/package with new
CRUD Form Toolkit (toolkit type) agent/skill/package.

Revision ID: cc0216030000
Revises: cc0216020000
Create Date: 2026-02-16 03:00:00.000000+08:00

"""
from typing import Sequence, Union

import json

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "cc0216030000"
down_revision: Union[str, None] = "cc0216020000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _read_toolkit_source() -> str:
    """crud_form_toolkit.py removed; return empty for NO-OP migration."""
    return ""


_SYSTEM_PROMPT = """\
You are a CRUD Form Configuration Assistant for the NovusAI SaaS platform.

Your job is to help users configure CRUD (Create/Read/Update/Delete) modules by filling in the CrudConfig JSON structure through natural conversation.

## Your Tools

You have 6 tools:
1. **fill_crud_config** — Set the complete CrudConfig JSON (use for initial setup or full replacement)
2. **add_fields** — Add field definitions to the existing config
3. **add_relations** — Add relation definitions (belongs_to, has_many, many_to_many)
4. **add_enums** — Add enum definitions (status values, type options, etc.)
5. **suggest_fields** — Suggest additional fields based on the module purpose
6. **recommend_layout** — Recommend list/form layout configuration

## CrudConfig Schema (Key Fields)

```json
{
  "module": "order",              // kebab-case module name
  "table_name": "orders",         // snake_case database table name
  "display_name": "订单",          // Chinese display name
  "display_name_en": "Order",     // English display name
  "scope": "tenant",              // "tenant" or "admin"
  "parent_menu": "business",      // Parent menu identifier
  "description": "",              // Module description
  "soft_delete": true,
  "drag_sort": false,
  "has_status_toggle": true,
  "recyclable": true,
  "fields": [...],                // Array of FieldConfig
  "relations": [...],             // Array of RelationConfig
  "enums": [...],                 // Array of EnumDefinition
  "search_config": null,
  "list_config": {},
  "form_config": {},
  "operations": ["edit", "delete"]
}
```

## FieldConfig Schema

```json
{
  "name": "title",                // snake_case field name
  "type": "string",              // string|text|integer|float|decimal|boolean|datetime|date|json|enum|file
  "label_zh": "标题",
  "label_en": "Title",
  "required": false,
  "nullable": true,
  "unique": false,
  "max_length": 200,             // For string type
  "default": null,
  "index": false,
  "enum_ref": null,              // Reference to enums[].name
  "filterable": true,
  "sortable": false,
  "searchable": false,
  "search_op": "ilike",          // ilike|eq|gt|gte|lt|lte|in|between
  "in_list": true,
  "in_form": true,
  "form_component": "Input"      // Input|InputNumber|Select|Switch|DatePicker|TimePicker|RangePicker|Textarea|RichText|Upload|TreeSelect|Cascader|Rate|Slider|ColorPicker|JsonEditor
}
```

## RelationConfig Schema

```json
{
  "name": "category",
  "type": "belongs_to",          // belongs_to|has_many|many_to_many
  "target_table": "categories",
  "foreign_key": "category_id",
  "display_field": "name",
  "cascade_delete": false
}
```

## EnumDefinition Schema

```json
{
  "name": "OrderStatus",         // PascalCase
  "description": "订单状态",
  "values": [
    {"value": "pending", "label_zh": "待处理", "label_en": "Pending", "color": "processing"},
    {"value": "completed", "label_zh": "已完成", "label_en": "Completed", "color": "success"}
  ]
}
```

## Workflow

1. Ask the user what module they want to create
2. Use **fill_crud_config** with basic info + initial fields
3. Use **suggest_fields** if the user wants recommendations
4. Use **add_fields**, **add_enums**, **add_relations** incrementally
5. Use **recommend_layout** for list/form config optimization
6. Confirm the final configuration

## Rules

- Field names MUST be snake_case
- Module names MUST be kebab-case
- Table names MUST be snake_case (usually plural)
- Enum class names MUST be PascalCase
- Always provide both label_zh and label_en
- For enum fields, set type="enum" and enum_ref to the enum name
- For file upload fields, set type="file"
- Always include a sensible set of default fields (name/title, description, status, sort_order)
- Respect the existing project modules to avoid table name conflicts
"""


def _find_chat_model(conn) -> int | None:
    """Find the first active chat AI model."""
    row = conn.execute(text(
        "SELECT id FROM ai_models "
        "WHERE type = 'chat' AND is_active = true AND is_deleted = false "
        "ORDER BY id LIMIT 1"
    )).fetchone()
    return row[0] if row else None


def upgrade() -> None:
    conn = op.get_bind()

    # ========================================
    # 1. Soft-delete old CRUD Generator data
    # ========================================

    # Soft-delete old bindings
    conn.execute(text(
        "UPDATE agent_skill_bindings SET is_deleted = true, deleted_at = NOW() "
        "WHERE agent_id IN ("
        "  SELECT id FROM agents "
        "  WHERE name IN ('crud_generator_assistant', 'CRUD 生成助手') "
        "  AND tenant_id IS NULL AND is_deleted = false"
        ") AND is_deleted = false"
    ))

    # Soft-delete old agent
    conn.execute(text(
        "UPDATE agents SET is_deleted = true, deleted_at = NOW() "
        "WHERE name IN ('crud_generator_assistant', 'CRUD 生成助手') "
        "AND tenant_id IS NULL AND is_system = true AND is_deleted = false"
    ))

    # Soft-delete old skill
    conn.execute(text(
        "UPDATE skills SET is_deleted = true, deleted_at = NOW() "
        "WHERE name = 'crud_generator' AND tenant_id IS NULL "
        "AND is_deleted = false"
    ))

    # Soft-delete old package
    conn.execute(text(
        "UPDATE skill_packages SET is_deleted = true, deleted_at = NOW() "
        "WHERE name = 'CRUD Generator 技能包' AND tenant_id IS NULL "
        "AND is_deleted = false"
    ))

    print("[SEED] Soft-deleted old CRUD Generator agent/skill/package/bindings")

    # ========================================
    # 2. Create new SkillPackage
    # ========================================

    existing_pkg = conn.execute(text(
        "SELECT id FROM skill_packages "
        "WHERE name = 'CRUD 表单工具包' AND tenant_id IS NULL AND is_deleted = false"
    )).fetchone()

    if existing_pkg:
        pkg_id = existing_pkg[0]
        print(f"[SEED] SkillPackage 'CRUD 表单工具包' already exists (id={pkg_id})")
    else:
        result = conn.execute(text(
            "INSERT INTO skill_packages "
            "(tenant_id, name, description, scope, is_system, is_active, sort_order, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, 'CRUD 表单工具包', "
            " 'AI 驱动的 CRUD 表单配置工具集 — 通过自然语言对话填充模块配置', "
            " 'admin', true, true, 10, NOW(), NOW(), false) "
            "RETURNING id"
        ))
        pkg_id = result.fetchone()[0]
        print(f"[SEED] Created SkillPackage 'CRUD 表单工具包' (id={pkg_id})")

    # ========================================
    # 3. Create new Skill (toolkit type)
    # ========================================

    toolkit_content = _read_toolkit_source()

    existing_skill = conn.execute(text(
        "SELECT id FROM skills "
        "WHERE name = 'crud_form_toolkit' AND tenant_id IS NULL AND is_deleted = false"
    )).fetchone()

    skill_config = json.dumps({"dev_only": True})

    if existing_skill:
        skill_id = existing_skill[0]
        conn.execute(text(
            "UPDATE skills SET "
            "toolkit_content = :toolkit_content, "
            "config = CAST(:config AS jsonb), "
            "updated_at = NOW() "
            "WHERE id = :id"
        ), {
            "id": skill_id,
            "toolkit_content": toolkit_content,
            "config": skill_config,
        })
        print(f"[SEED] Skill 'crud_form_toolkit' already exists (id={skill_id}), updated")
    else:
        result = conn.execute(text(
            "INSERT INTO skills "
            "(tenant_id, package_id, name, description, type, "
            " config, toolkit_content, "
            " is_system, is_active, timeout, sort_order, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :package_id, 'crud_form_toolkit', "
            " 'AI \u9a71\u52a8 CRUD \u8868\u5355\u914d\u7f6e \u2014 6 \u4e2a Tool: fill/add_fields/relations/enums + suggest + layout', "
            " 'toolkit', CAST(:config AS jsonb), :toolkit_content, "
            " true, true, 120, 0, NOW(), NOW(), false) "
            "RETURNING id"
        ), {
            "package_id": pkg_id,
            "config": skill_config,
            "toolkit_content": toolkit_content,
        })
        skill_id = result.fetchone()[0]
        print(f"[SEED] Created Skill 'crud_form_toolkit' (id={skill_id})")

    # ========================================
    # 4. Create new Agent
    # ========================================

    existing_agent = conn.execute(text(
        "SELECT id FROM agents "
        "WHERE name = 'CRUD 表单助手' AND tenant_id IS NULL AND is_deleted = false"
    )).fetchone()

    _welcome = (
        "你好！我是 CRUD 代码生成助手。告诉我你需要什么功能模块，我来帮你生成配置。\n"
        "例如：\"我需要一个订单管理模块，包含订单编号、金额、状态\""
    )
    _questions = json.dumps([
        "我需要一个订单管理模块",
        "帮我生成一个文章管理的 CRUD",
        "创建一个系统配置管理模块",
        "我有一个 CREATE TABLE SQL，帮我转成 CRUD 配置",
    ], ensure_ascii=False)

    if existing_agent:
        agent_id = existing_agent[0]
        conn.execute(text(
            "UPDATE agents SET "
            "system_prompt = :system_prompt, "
            "welcome_message = :welcome, "
            "suggested_questions = CAST(:questions AS jsonb), "
            "updated_at = NOW() "
            "WHERE id = :id"
        ), {
            "id": agent_id,
            "system_prompt": _SYSTEM_PROMPT,
            "welcome": _welcome,
            "questions": _questions,
        })
        print(f"[SEED] Agent 'CRUD 表单助手' already exists (id={agent_id}), updated prompt+welcome")
    else:
        model_id = _find_chat_model(conn)
        if not model_id:
            print("[SEED] WARNING: No active chat model found, skipping agent creation.")
            return

        result = conn.execute(text(
            "INSERT INTO agents "
            "(tenant_id, name, description, scope, system_prompt, model_id, "
            " temperature, execution_mode, status, visibility, is_system, "
            " welcome_message, suggested_questions, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, 'CRUD 表单助手', "
            " 'CRUD 表单配置助手 — 通过自然语言对话生成模块配置、字段定义、枚举和关联关系', "
            " 'admin', :system_prompt, :model_id, "
            " 0.3, 'conversation', 'published', 'public', true, "
            " :welcome, CAST(:questions AS jsonb), "
            " NOW(), NOW(), false) "
            "RETURNING id"
        ), {
            "system_prompt": _SYSTEM_PROMPT,
            "model_id": model_id,
            "welcome": _welcome,
            "questions": _questions,
        })
        agent_id = result.fetchone()[0]
        print(f"[SEED] Created Agent 'CRUD 表单助手' (id={agent_id}, model_id={model_id})")

    # ========================================
    # 5. Create AgentSkillBinding
    # ========================================

    existing_binding = conn.execute(text(
        "SELECT id FROM agent_skill_bindings "
        "WHERE agent_id = :agent_id AND package_id = :package_id AND is_deleted = false"
    ), {"agent_id": agent_id, "package_id": pkg_id}).fetchone()

    if not existing_binding:
        conn.execute(text(
            "INSERT INTO agent_skill_bindings "
            "(tenant_id, agent_id, package_id, enabled, sort_order, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :agent_id, :package_id, true, 0, NOW(), NOW(), false)"
        ), {"agent_id": agent_id, "package_id": pkg_id})
        print(f"[SEED] Bound package (id={pkg_id}) to agent 'CRUD 表单助手'")
    else:
        print(f"[SEED] Binding already exists")

    print("[SEED] CRUD Form Toolkit seed done.")


def downgrade() -> None:
    """Remove new CRUD Form Toolkit data and restore old CRUD Generator data."""
    conn = op.get_bind()

    # Remove new binding
    conn.execute(text(
        "DELETE FROM agent_skill_bindings "
        "WHERE agent_id IN ("
        "  SELECT id FROM agents WHERE name = 'CRUD 表单助手' AND tenant_id IS NULL"
        ")"
    ))

    # Remove new agent
    conn.execute(text(
        "DELETE FROM agents "
        "WHERE name = 'CRUD 表单助手' AND tenant_id IS NULL AND is_system = true"
    ))

    # Remove new skill
    conn.execute(text(
        "DELETE FROM skills "
        "WHERE name = 'crud_form_toolkit' AND tenant_id IS NULL AND is_system = true"
    ))

    # Remove new package
    conn.execute(text(
        "DELETE FROM skill_packages "
        "WHERE name = 'CRUD 表单工具包' AND tenant_id IS NULL AND is_system = true"
    ))

    # Restore old CRUD Generator data
    conn.execute(text(
        "UPDATE skill_packages SET is_deleted = false, deleted_at = NULL "
        "WHERE name = 'CRUD Generator 技能包' AND tenant_id IS NULL AND is_deleted = true"
    ))
    conn.execute(text(
        "UPDATE skills SET is_deleted = false, deleted_at = NULL "
        "WHERE name = 'crud_generator' AND tenant_id IS NULL AND is_deleted = true"
    ))
    conn.execute(text(
        "UPDATE agents SET is_deleted = false, deleted_at = NULL "
        "WHERE name IN ('crud_generator_assistant', 'CRUD 生成助手') "
        "AND tenant_id IS NULL AND is_system = true AND is_deleted = true"
    ))
    conn.execute(text(
        "UPDATE agent_skill_bindings SET is_deleted = false, deleted_at = NULL "
        "WHERE agent_id IN ("
        "  SELECT id FROM agents "
        "  WHERE name IN ('crud_generator_assistant', 'CRUD 生成助手') "
        "  AND tenant_id IS NULL"
        ") AND is_deleted = true"
    ))

    print("[SEED] CRUD Form Toolkit data removed, old CRUD Generator restored.")
