"""seed internal-ops copilot agents and meta-tool skill

Creates:
1. System skill package + 'internal_operations' meta-tool skill
   (builtin_type=internal_ops, tools defined in code)
2. Two system copilot agents: platform ops copilot (admin_only) and
   tenant ops copilot (all_tenants)
3. AgentSkillGrant binding the skill to both agents
4. SystemAgentAssignments: admin_copilot / tenant_copilot

All operations are idempotent — safe to re-run.

Revision ID: 20260610_0049_internal_ops
Revises: 20260610_0048_drop_av_tenant_fk
Create Date: 2026-06-10 22:20:00.000000+08:00

"""

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "20260610_0049_internal_ops"
down_revision: str | Sequence[str] | None = "20260610_0048_drop_av_tenant_fk"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ---------------------------------------------------------------------------
# Seed data definitions
# ---------------------------------------------------------------------------

SKILL_PACKAGE_NAME = "运营 Copilot 技能包"
SKILL_KEY = "internal_operations"
SKILL_NAME = "内部操作元工具"

ADMIN_COPILOT_NAME = "平台运营 Copilot"
TENANT_COPILOT_NAME = "企业运营 Copilot"

ADMIN_COPILOT_FEATURE = "admin_copilot"
TENANT_COPILOT_FEATURE = "tenant_copilot"

COPILOT_SYSTEM_PROMPT = """\
你是 NovusAI 平台的运营 Copilot，能够代表当前用户执行后台管理操作。

## 可用工具

你拥有三个元工具，可以发现并调用本系统的全部后台操作：
1. `list_internal_operations` — 按关键词搜索当前用户可用的后台操作目录
2. `describe_internal_operation` — 查看某个操作的完整参数规格
3. `invoke_internal_operation` — 以当前用户的身份执行操作

## 工作流程（必须遵守）

1. 理解用户意图后，先用 `list_internal_operations` 搜索相关操作；关键词可以是中文或英文，匹配路径、模块、摘要和权限码。
   - 如果返回 0 个操作，说明当前用户权限范围内没有匹配操作；最多换一个更宽泛的关键词再搜索 1 次。
   - 连续 2 次仍为 0 个操作时，停止搜索，不要继续更换关键词；直接告知用户未找到相关操作，并说明可能原因（权限不足、功能未开通或端点未注册）。
2. 找到候选操作后，调用 `describe_internal_operation` 查看参数规格，严格按 schema 构造参数。
3. 调用 `invoke_internal_operation` 执行：
   - 查询（GET）操作会立即执行；
   - 写操作（POST/PUT/PATCH/DELETE）会先返回确认预览，由用户在界面上确认后才真正执行。在确认结果返回前，绝不能声称操作已完成。
4. 把执行结果用简洁的中文向用户汇报，重要数据用表格或列表呈现。

## 安全规则

- 你的权限与当前用户完全一致：返回 403 表示用户本人无此权限，应如实告知，不要重试。
- 绝不虚构 operation_id 或参数；不确定时先搜索、先查看规格。
- 写操作前应向用户复述将要执行的内容；用户明确拒绝时立即终止。
- 涉及删除等高危操作时，提醒用户操作后果。

## 回复风格

- 始终使用简体中文。
- 简明扼要，先给结论再给细节。
- 操作失败时解释原因并给出下一步建议。\
"""

ADMIN_COPILOT_DESCRIPTION = (
    "平台运营 Copilot — 通过对话完成平台后台的查询与管理操作"
    "（租户、套餐、用户、权限、配置、日志等）"
)
TENANT_COPILOT_DESCRIPTION = (
    "企业运营 Copilot — 通过对话完成企业后台的查询与管理操作"
    "（成员、组织、角色、智能体、知识库等）"
)


def _find_chat_model(conn) -> int | None:
    """Find the first active chat AI model."""
    row = conn.execute(
        text(
            "SELECT id FROM ai_models "
            "WHERE type = 'chat' AND is_active = true AND is_deleted = false "
            "ORDER BY id LIMIT 1"
        )
    ).fetchone()
    return row[0] if row else None


def _ensure_skill(conn) -> int | None:
    """Create skill package + meta-tool skill, return skill id."""
    pkg_row = conn.execute(
        text(
            "SELECT id FROM skill_packages "
            "WHERE name = :name AND tenant_id IS NULL AND is_deleted = false"
        ),
        {"name": SKILL_PACKAGE_NAME},
    ).fetchone()
    if pkg_row:
        pkg_id = pkg_row[0]
        print(f"[SEED] SkillPackage '{SKILL_PACKAGE_NAME}' already exists (id={pkg_id})")
    else:
        pkg_id = conn.execute(
            text(
                "INSERT INTO skill_packages "
                "(tenant_id, name, description, is_recommended, is_system, "
                " is_active, sort_order, created_at, updated_at, is_deleted) "
                "VALUES "
                "(NULL, :name, :description, false, true, "
                " true, 0, NOW(), NOW(), false) "
                "RETURNING id"
            ),
            {
                "name": SKILL_PACKAGE_NAME,
                "description": "内置运营 Copilot 的内部操作元工具（list/describe/invoke）",
            },
        ).fetchone()[0]
        print(f"[SEED] Created SkillPackage '{SKILL_PACKAGE_NAME}' (id={pkg_id})")

    skill_row = conn.execute(
        text(
            "SELECT id FROM skills "
            "WHERE key = :key AND tenant_id IS NULL AND is_deleted = false"
        ),
        {"key": SKILL_KEY},
    ).fetchone()
    if skill_row:
        print(f"[SEED] Skill '{SKILL_KEY}' already exists (id={skill_row[0]})")
        return skill_row[0]

    skill_id = conn.execute(
        text(
            "INSERT INTO skills "
            "(tenant_id, package_id, name, key, description, type, source_type, "
            " version, status, is_readonly, config, is_system, is_active, "
            " timeout, sort_order, created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :package_id, :name, :key, :description, 'builtin', "
            " 'platform_builtin', '1.0.0', 'active', true, "
            " CAST(:config AS jsonb), true, true, "
            " 60, 0, NOW(), NOW(), false) "
            "RETURNING id"
        ),
        {
            "package_id": pkg_id,
            "name": SKILL_NAME,
            "key": SKILL_KEY,
            "description": (
                "运营 Copilot 元工具：搜索操作目录、查看参数规格、以用户身份执行内部 API。"
                "工具 schema 由代码定义（app/ai/internal_ops/tools.py）。"
            ),
            "config": json.dumps({"builtin_type": "internal_ops"}),
        },
    ).fetchone()[0]
    print(f"[SEED] Created Skill '{SKILL_KEY}' (id={skill_id})")
    return skill_id


def _ensure_agent(
    conn,
    *,
    name: str,
    description: str,
    scope: str,
    model_id: int,
) -> int | None:
    """Create one system copilot agent, return agent id."""
    row = conn.execute(
        text(
            "SELECT id FROM agents "
            "WHERE name = :name AND owner_tenant_id IS NULL AND is_deleted = false"
        ),
        {"name": name},
    ).fetchone()
    if row:
        print(f"[SEED] Agent '{name}' already exists (id={row[0]})")
        return row[0]

    agent_id = conn.execute(
        text(
            "INSERT INTO agents "
            "(owner_tenant_id, name, description, scope, system_prompt, model_id, "
            " temperature, execution_mode, status, visibility, memory_enabled, "
            " is_system, created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :name, :description, :scope, :system_prompt, :model_id, "
            " 0.3, 'conversation', 'published', 'public', true, "
            " true, NOW(), NOW(), false) "
            "RETURNING id"
        ),
        {
            "name": name,
            "description": description,
            "scope": scope,
            "system_prompt": COPILOT_SYSTEM_PROMPT,
            "model_id": model_id,
        },
    ).fetchone()[0]
    print(f"[SEED] Created Agent '{name}' (id={agent_id}, model_id={model_id})")
    return agent_id


def _ensure_grant(conn, *, agent_id: int, skill_id: int) -> None:
    """Bind skill to agent via AgentSkillGrant."""
    row = conn.execute(
        text(
            "SELECT id FROM agent_skill_grants "
            "WHERE agent_id = :agent_id AND skill_id = :skill_id"
        ),
        {"agent_id": agent_id, "skill_id": skill_id},
    ).fetchone()
    if row:
        print(f"[SEED] Grant agent={agent_id} skill={skill_id} already exists")
        return
    conn.execute(
        text(
            "INSERT INTO agent_skill_grants "
            "(tenant_id, agent_id, skill_id, enabled, sort_order, "
            " default_consent_mode, created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :agent_id, :skill_id, true, 0, "
            " 'auto', NOW(), NOW(), false)"
        ),
        {"agent_id": agent_id, "skill_id": skill_id},
    )
    print(f"[SEED] Created grant agent={agent_id} skill={skill_id}")


def _ensure_assignment(
    conn,
    *,
    feature_code: str,
    feature_name: str,
    description: str,
    agent_id: int | None,
) -> None:
    """Create SystemAgentAssignment for a copilot feature."""
    row = conn.execute(
        text(
            "SELECT id FROM system_agent_assignments "
            "WHERE feature_code = :code AND tenant_id IS NULL AND is_deleted = false"
        ),
        {"code": feature_code},
    ).fetchone()
    if row:
        print(f"[SEED] Assignment '{feature_code}' already exists (id={row[0]})")
        return
    conn.execute(
        text(
            "INSERT INTO system_agent_assignments "
            "(feature_code, feature_name, description, tenant_id, agent_id, "
            " is_active, created_at, updated_at, is_deleted) "
            "VALUES "
            "(:code, :name, :description, NULL, :agent_id, "
            " true, NOW(), NOW(), false)"
        ),
        {
            "code": feature_code,
            "name": feature_name,
            "description": description,
            "agent_id": agent_id,
        },
    )
    print(f"[SEED] Created assignment '{feature_code}' (agent_id={agent_id})")


def upgrade() -> None:
    conn = op.get_bind()

    skill_id = _ensure_skill(conn)

    model_id = _find_chat_model(conn)
    admin_agent_id: int | None = None
    tenant_agent_id: int | None = None
    if not model_id:
        print(
            "[SEED] WARNING: No active chat model found, skipping copilot agent "
            "creation. Create an AI model first, then re-run this seed."
        )
    else:
        admin_agent_id = _ensure_agent(
            conn,
            name=ADMIN_COPILOT_NAME,
            description=ADMIN_COPILOT_DESCRIPTION,
            scope="admin_only",
            model_id=model_id,
        )
        tenant_agent_id = _ensure_agent(
            conn,
            name=TENANT_COPILOT_NAME,
            description=TENANT_COPILOT_DESCRIPTION,
            scope="all_tenants",
            model_id=model_id,
        )
        if skill_id:
            if admin_agent_id:
                _ensure_grant(conn, agent_id=admin_agent_id, skill_id=skill_id)
            if tenant_agent_id:
                _ensure_grant(conn, agent_id=tenant_agent_id, skill_id=skill_id)

    _ensure_assignment(
        conn,
        feature_code=ADMIN_COPILOT_FEATURE,
        feature_name="平台运营 Copilot",
        description="平台后台运营 Copilot 入口绑定的智能体",
        agent_id=admin_agent_id,
    )
    _ensure_assignment(
        conn,
        feature_code=TENANT_COPILOT_FEATURE,
        feature_name="企业运营 Copilot",
        description="企业后台运营 Copilot 入口绑定的智能体",
        agent_id=tenant_agent_id,
    )

    print("[SEED] Internal-ops copilot seeding done.")


def downgrade() -> None:
    """Remove seeded copilot agents, skill, package, grants, assignments."""
    conn = op.get_bind()

    conn.execute(
        text(
            "DELETE FROM system_agent_assignments "
            "WHERE feature_code IN (:a, :b) AND tenant_id IS NULL"
        ),
        {"a": ADMIN_COPILOT_FEATURE, "b": TENANT_COPILOT_FEATURE},
    )

    agent_rows = conn.execute(
        text(
            "SELECT id FROM agents "
            "WHERE name IN (:a, :b) AND owner_tenant_id IS NULL AND is_system = true"
        ),
        {"a": ADMIN_COPILOT_NAME, "b": TENANT_COPILOT_NAME},
    ).fetchall()
    agent_ids = [r[0] for r in agent_rows]
    if agent_ids:
        conn.execute(
            text("DELETE FROM agent_skill_grants WHERE agent_id = ANY(:ids)"),
            {"ids": agent_ids},
        )
        conn.execute(
            text("DELETE FROM agents WHERE id = ANY(:ids)"),
            {"ids": agent_ids},
        )

    conn.execute(
        text(
            "DELETE FROM skills "
            "WHERE key = :key AND tenant_id IS NULL AND is_system = true"
        ),
        {"key": SKILL_KEY},
    )
    conn.execute(
        text(
            "DELETE FROM skill_packages "
            "WHERE name = :name AND tenant_id IS NULL AND is_system = true"
        ),
        {"name": SKILL_PACKAGE_NAME},
    )

    print("[SEED] Internal-ops copilot seed removed.")
