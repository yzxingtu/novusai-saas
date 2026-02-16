"""seed agent welcome messages

Fill welcome_message and suggested_questions for 3 system agents.

Revision ID: 20260216_awm
Revises: 20260216_saa_tid
Create Date: 2026-02-16
"""

import json

from alembic import op
from sqlalchemy import text

revision = "20260216_awm"
down_revision = "20260216_saa_tid"
branch_labels = None
depends_on = None

AGENT_WELCOME_DATA = [
    {
        "name": "智能助手",
        "welcome_message": "你好！我是智能助手，可以帮助你解答问题、撰写内容和提供建议。有什么我可以帮你的吗？",
        "suggested_questions": [
            "帮我总结一下这段文字的要点",
            "请用简洁的语言解释一下什么是微服务架构",
            "帮我写一封商务邮件的模板",
        ],
    },
    {
        "name": "CRUD 生成助手",
        "welcome_message": "你好！我是 CRUD 代码生成助手，可以帮你快速生成前后端 CRUD 代码。告诉我你想创建什么功能模块吧！",
        "suggested_questions": [
            "帮我生成一个用户管理模块的 CRUD 代码",
            "我想创建一个订单管理表，包含订单号、金额、状态字段",
            "帮我查看当前项目有哪些数据表可以生成代码",
        ],
    },
    {
        "name": "数据分析助手",
        "welcome_message": "你好！我可以直接查询和分析系统中的数据。你可以用自然语言告诉我你想了解什么，我会帮你查询并分析结果。",
        "suggested_questions": [
            "查看系统中有多少个租户",
            "统计最近 7 天的 AI 调用次数",
            "列出最近创建的 10 条操作日志",
        ],
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    for item in AGENT_WELCOME_DATA:
        sq_json = json.dumps(item["suggested_questions"], ensure_ascii=False)
        conn.execute(
            text(
                "UPDATE agents SET "
                "welcome_message = :welcome_message, "
                "suggested_questions = :suggested_questions "
                "WHERE name = :name AND is_system = true AND is_deleted = false"
            ),
            {
                "name": item["name"],
                "welcome_message": item["welcome_message"],
                "suggested_questions": sq_json,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()

    for item in AGENT_WELCOME_DATA:
        conn.execute(
            text(
                "UPDATE agents SET "
                "welcome_message = NULL, "
                "suggested_questions = NULL "
                "WHERE name = :name AND is_system = true AND is_deleted = false"
            ),
            {"name": item["name"]},
        )
