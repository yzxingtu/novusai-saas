"""enrich system skill package descriptions and populate builtin tools

Update system skill packages and skills with richer descriptions
that explain usage scenarios and capabilities.
Also populate config.tools for builtin skills so frontend can display tool list.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-02-15 00:30:00.000000+08:00
"""

import json
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Updated descriptions
# ---------------------------------------------------------------------------

PACKAGE_UPDATES = [
    {
        "name": "系统聊天技能包",
        "description": (
            "系统内置的 LLM 聊天能力包。提供多轮对话、流式输出、"
            "Function Calling 等核心聊天功能。系统聊天 Agent 默认绑定此技能包，"
            "作为所有 AI 对话的基础能力层。不可删除或禁用。"
        ),
    },
    {
        "name": "系统向量化技能包",
        "description": (
            "系统内置的文本向量化能力包。调用 Embedding 模型将文本转换为高维向量，"
            "用于知识库文档索引和语义检索。系统 Embedding Agent 默认绑定此技能包。"
            "不可删除或禁用。"
        ),
    },
    {
        "name": "系统数据智能技能包",
        "description": (
            "系统内置的数据智能能力包。通过自然语言查询和操作数据库（Text-to-SQL），"
            "自动使用所有已配置的表策略。适用于平台管理员进行数据分析和管理操作。"
            "不可删除或禁用。"
        ),
    },
]

SKILL_UPDATES = [
    {
        "name": "llm_chat",
        "description": (
            "LLM 聊天工具：直接调用大语言模型进行多轮对话，"
            "支持流式输出和 Function Calling。"
            "作为系统聊天 Agent 的核心技能。"
        ),
    },
    {
        "name": "llm_embedding",
        "description": (
            "文本向量化工具：调用 Embedding 模型将文本转换为语义向量，"
            "用于知识库文档的索引构建和相似度检索。"
        ),
    },
    {
        "name": "平台数据管理",
        "description": (
            "数据智能技能：自动使用所有已配置的表策略，"
            "支持自然语言查询（Text-to-SQL）和 CRUD 操作，"
            "为平台管理员提供便捷的数据管理能力。"
        ),
    },
]

# Original descriptions for downgrade
PACKAGE_ORIGINALS = [
    {
        "name": "系统聊天技能包",
        "description": "系统内置的 LLM 聊天能力，供系统聊天 Agent 使用",
    },
    {
        "name": "系统向量化技能包",
        "description": "系统内置的文本向量化能力，供系统 Embedding Agent 使用",
    },
    {
        "name": "系统数据智能技能包",
        "description": "系统内置的数据智能技能包，提供自然语言查询和操作数据库的能力",
    },
]

SKILL_ORIGINALS = [
    {
        "name": "llm_chat",
        "description": "直接调用 LLM 进行多轮聊天对话",
    },
    {
        "name": "llm_embedding",
        "description": "调用 Embedding 模型将文本转换为向量",
    },
    {
        "name": "平台数据管理",
        "description": (
            "平台管理员的数据操作技能。自动使用所有已配置的表策略，"
            "支持自然语言查询和 CRUD 操作。"
        ),
    },
]


# ---------------------------------------------------------------------------
# Builtin skill config.tools definitions
# ---------------------------------------------------------------------------

BUILTIN_SKILL_TOOLS = {
    "llm_chat": {
        "builtin_type": "llm_chat",
        "tools": [
            {
                "name": "llm_chat",
                "description": "调用大语言模型进行多轮对话，支持流式输出和 Function Calling",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "用户消息内容"},
                        "system_prompt": {"type": "string", "description": "系统提示词（可选）"},
                    },
                    "required": ["message"],
                },
            },
        ],
    },
    "llm_embedding": {
        "builtin_type": "llm_embedding",
        "tools": [
            {
                "name": "llm_embedding",
                "description": "调用 Embedding 模型将文本转换为语义向量，用于索引和相似度检索",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "待向量化的文本"},
                    },
                    "required": ["text"],
                },
            },
        ],
    },
}

# Original configs for downgrade
BUILTIN_SKILL_ORIGINAL_CONFIGS = {
    "llm_chat": {"builtin_type": "llm_chat"},
    "llm_embedding": {"builtin_type": "llm_embedding"},
}


def _update_descriptions(
    conn,
    package_data: list[dict],
    skill_data: list[dict],
) -> None:
    for pkg in package_data:
        conn.execute(
            text(
                "UPDATE skill_packages SET description = :desc, updated_at = NOW() "
                "WHERE name = :name AND tenant_id IS NULL AND is_system = true"
            ),
            {"name": pkg["name"], "desc": pkg["description"]},
        )

    for skill in skill_data:
        conn.execute(
            text(
                "UPDATE skills SET description = :desc, updated_at = NOW() "
                "WHERE name = :name AND tenant_id IS NULL AND is_system = true"
            ),
            {"name": skill["name"], "desc": skill["description"]},
        )


def _update_builtin_configs(conn, configs: dict) -> None:
    for skill_name, config in configs.items():
        conn.execute(
            text(
                "UPDATE skills SET config = CAST(:config AS jsonb), updated_at = NOW() "
                "WHERE name = :name AND tenant_id IS NULL AND is_system = true"
            ),
            {"name": skill_name, "config": json.dumps(config)},
        )


def upgrade() -> None:
    conn = op.get_bind()
    _update_descriptions(conn, PACKAGE_UPDATES, SKILL_UPDATES)
    _update_builtin_configs(conn, BUILTIN_SKILL_TOOLS)
    print("[SEED] Enriched system skill package/skill descriptions and populated builtin tools.")


def downgrade() -> None:
    conn = op.get_bind()
    _update_descriptions(conn, PACKAGE_ORIGINALS, SKILL_ORIGINALS)
    _update_builtin_configs(conn, BUILTIN_SKILL_ORIGINAL_CONFIGS)
    print("[SEED] Reverted system skill package/skill descriptions and builtin configs.")
