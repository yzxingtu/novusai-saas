"""populate builtin skill config.tools

Add tools array to llm_chat and llm_embedding builtin skills so the
frontend can display tool list in the edit form.
Also fix descriptions for packages that were missed in the previous migration.

Revision ID: a1b2c3d4e5f6
Revises: f7a8b9c0d1e2
Create Date: 2026-02-15 00:33:00.000000+08:00
"""

import json
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "aa0215003300"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Builtin skill config with tools
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

BUILTIN_SKILL_ORIGINAL_CONFIGS = {
    "llm_chat": {"builtin_type": "llm_chat"},
    "llm_embedding": {"builtin_type": "llm_embedding"},
}

# ---------------------------------------------------------------------------
# Package descriptions that were missed
# ---------------------------------------------------------------------------

PACKAGE_DESC_FIXES = [
    {
        "name": "系统数据智能技能包",
        "description": (
            "系统内置的数据智能能力包。通过自然语言查询和操作数据库（Text-to-SQL），"
            "自动使用所有已配置的表策略。适用于平台管理员进行数据分析和管理操作。"
            "不可删除或禁用。"
        ),
        "original": "系统内置的数据智能技能包，提供自然语言查询和操作数据库的能力",
    },
    {
        "name": "CRUD Generator 技能包",
        "description": (
            "CRUD 代码生成 AI 辅助工具集。包含字段建议、枚举生成、标签翻译、"
            "插槽代码生成、Schema 审查、校验规则建议、搜索配置建议、"
            "模板语法解释等 8 种开发辅助工具。供 CRUD Generator Wizard 使用。"
        ),
        "original": "CRUD 代码生成 AI 辅助工具集",
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Update builtin skill configs with tools
    for skill_name, config in BUILTIN_SKILL_TOOLS.items():
        conn.execute(
            text(
                "UPDATE skills SET config = CAST(:config AS jsonb), updated_at = NOW() "
                "WHERE name = :name AND tenant_id IS NULL AND is_system = true "
                "AND is_deleted = false"
            ),
            {"name": skill_name, "config": json.dumps(config)},
        )
        print(f"[FIX] Updated config.tools for skill '{skill_name}'")

    # 2. Fix missed package descriptions
    for pkg in PACKAGE_DESC_FIXES:
        conn.execute(
            text(
                "UPDATE skill_packages SET description = :desc, updated_at = NOW() "
                "WHERE name = :name AND is_system = true AND is_deleted = false"
            ),
            {"name": pkg["name"], "desc": pkg["description"]},
        )
        print(f"[FIX] Updated description for package '{pkg['name']}'")


def downgrade() -> None:
    conn = op.get_bind()

    for skill_name, config in BUILTIN_SKILL_ORIGINAL_CONFIGS.items():
        conn.execute(
            text(
                "UPDATE skills SET config = CAST(:config AS jsonb), updated_at = NOW() "
                "WHERE name = :name AND tenant_id IS NULL AND is_system = true "
                "AND is_deleted = false"
            ),
            {"name": skill_name, "config": json.dumps(config)},
        )

    for pkg in PACKAGE_DESC_FIXES:
        conn.execute(
            text(
                "UPDATE skill_packages SET description = :desc, updated_at = NOW() "
                "WHERE name = :name AND is_system = true AND is_deleted = false"
            ),
            {"name": pkg["name"], "desc": pkg["original"]},
        )
