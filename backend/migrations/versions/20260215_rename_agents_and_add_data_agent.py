"""rename system agents to Chinese and add data analysis agent

1. Rename system_chat_agent → 智能助手
2. Rename crud_generator_assistant → CRUD 生成助手
3. Create 数据分析助手 system agent bound to 系统数据智能技能包

Revision ID: bb0215004500
Revises: aa0215003300
Create Date: 2026-02-15 00:45:00.000000+08:00
"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "bb0215004500"
down_revision: Union[str, None] = "aa0215003300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DATA_AGENT_NAME = "数据分析助手"
_DATA_PKG_NAME = "系统数据智能技能包"

_DATA_AGENT_PROMPT = (
    "你是一个专业的数据分析助手。你可以直接查询和操作数据库。\n\n"
    "## 核心规则\n"
    "1. 当用户提出任何关于数据的问题（查询、统计、列表、计数等），"
    "你必须立即调用 data_query 工具，将用户的自然语言问题传入。\n"
    "2. 当用户要求创建、修改或删除数据时，使用对应的 "
    "data_create、data_update、data_delete 工具。\n"
    "3. 禁止生成 SQL 代码让用户自己执行。你拥有直接执行的能力，"
    "必须使用工具完成操作。\n"
    "4. 禁止说你无法访问数据库。你可以通过工具直接访问。\n\n"
    "## 工作流程\n"
    "- 理解用户的自然语言查询意图\n"
    "- 调用工具执行数据库操作\n"
    "- 对查询结果进行分析、总结和格式化呈现\n"
    "- 写操作前先预览，等用户确认后再执行\n\n"
    "## 注意事项\n"
    "- 对敏感数据操作要谨慎提醒\n"
    "- 用简洁清晰的方式呈现查询结果（表格、列表等）\n"
    "- 如果查询结果较多，提供摘要和关键指标"
)


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Rename system_chat_agent → 智能助手
    conn.execute(text(
        "UPDATE agents SET name = :new_name, updated_at = NOW() "
        "WHERE name = 'system_chat_agent' AND is_system = true AND is_deleted = false"
    ), {"new_name": "智能助手"})
    print("[SEED] Renamed system_chat_agent → 智能助手")

    # 2. Rename crud_generator_assistant → CRUD 生成助手
    conn.execute(text(
        "UPDATE agents SET name = :new_name, updated_at = NOW() "
        "WHERE name = 'crud_generator_assistant' AND is_system = true AND is_deleted = false"
    ), {"new_name": "CRUD 生成助手"})
    print("[SEED] Renamed crud_generator_assistant → CRUD 生成助手")

    # 3. Create 数据分析助手 agent (idempotent)
    existing = conn.execute(text(
        "SELECT id FROM agents "
        "WHERE name = :name AND is_system = true AND is_deleted = false"
    ), {"name": _DATA_AGENT_NAME}).fetchone()

    agent_id: int | None
    if existing:
        agent_id = existing[0]
        print(f"[SEED] Agent '{_DATA_AGENT_NAME}' already exists (id={agent_id})")
    else:
        # 与「智能助手」共用 model_id；空库无已种子化系统智能体时跳过创建（避免 model_id NOT NULL 失败）
        chat_agent = conn.execute(text(
            "SELECT model_id FROM agents "
            "WHERE name = '智能助手' AND is_system = true AND is_deleted = false"
        )).fetchone()
        model_id = chat_agent[0] if chat_agent else None

        if model_id is None:
            print(
                "[SEED] WARNING: No model_id from 智能助手 (empty DB or seed skipped); "
                f"skipping creation of '{_DATA_AGENT_NAME}'. Configure an AI model and re-run if needed."
            )
            agent_id = None
        else:
            result = conn.execute(text(
                "INSERT INTO agents "
                "(tenant_id, name, description, scope, system_prompt, model_id, "
                " temperature, execution_mode, status, visibility, is_system, "
                " created_at, updated_at, is_deleted) "
                "VALUES "
                "(NULL, :name, :desc, 'admin', :prompt, :model_id, "
                " 0.3, 'tool_call', 'published', 'private', true, "
                " NOW(), NOW(), false) "
                "RETURNING id"
            ), {
                "name": _DATA_AGENT_NAME,
                "desc": "系统数据分析智能体，支持自然语言查询和操作数据库",
                "prompt": _DATA_AGENT_PROMPT,
                "model_id": model_id,
            })
            agent_id = result.fetchone()[0]
            print(f"[SEED] Created agent '{_DATA_AGENT_NAME}' (id={agent_id})")

    if agent_id is None:
        print("[SEED] Skipping data-agent ↔ package binding (no agent id)")
        return

    # 4. Bind agent to 系统数据智能技能包
    pkg = conn.execute(text(
        "SELECT id FROM skill_packages "
        "WHERE name = :name AND is_system = true AND is_deleted = false"
    ), {"name": _DATA_PKG_NAME}).fetchone()

    if not pkg:
        print(f"[WARN] Package '{_DATA_PKG_NAME}' not found, skipping binding")
        return

    pkg_id = pkg[0]
    existing_bind = conn.execute(text(
        "SELECT id FROM agent_skill_bindings "
        "WHERE agent_id = :agent_id AND package_id = :pkg_id AND is_deleted = false"
    ), {"agent_id": agent_id, "pkg_id": pkg_id}).fetchone()

    if existing_bind:
        print(f"[SEED] Binding already exists")
    else:
        conn.execute(text(
            "INSERT INTO agent_skill_bindings "
            "(agent_id, package_id, enabled, sort_order, created_at, updated_at, is_deleted) "
            "VALUES (:agent_id, :pkg_id, true, 1, NOW(), NOW(), false)"
        ), {"agent_id": agent_id, "pkg_id": pkg_id})
        print(f"[SEED] Bound '{_DATA_AGENT_NAME}' → '{_DATA_PKG_NAME}'")


def downgrade() -> None:
    conn = op.get_bind()

    # Remove data agent and binding
    agent = conn.execute(text(
        "SELECT id FROM agents "
        "WHERE name = :name AND is_system = true AND is_deleted = false"
    ), {"name": _DATA_AGENT_NAME}).fetchone()

    if agent:
        conn.execute(text(
            "DELETE FROM agent_skill_bindings WHERE agent_id = :id"
        ), {"id": agent[0]})
        conn.execute(text(
            "DELETE FROM agents WHERE id = :id"
        ), {"id": agent[0]})

    # Revert names
    conn.execute(text(
        "UPDATE agents SET name = 'system_chat_agent', updated_at = NOW() "
        "WHERE name = '智能助手' AND is_system = true"
    ))
    conn.execute(text(
        "UPDATE agents SET name = 'crud_generator_assistant', updated_at = NOW() "
        "WHERE name = 'CRUD 生成助手' AND is_system = true"
    ))
    print("[SEED] Reverted agent names and removed data analysis agent")
