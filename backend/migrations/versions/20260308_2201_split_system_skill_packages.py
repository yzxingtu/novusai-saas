"""split system core skill package into purpose-specific packages

Split "系统核心技能包" into:
  A. 系统引擎技能包  — llm_chat + llm_embedding (internal, not for function calling)
  B. 平台数据管理    — data intelligence / management skills (admin_only)
  C. 联网搜索       — web_search (admin_tenant)

All new packages use bind_mode=manual.
Existing AgentSkillBindings pointing to the old core package are kept pointing
to package A and complemented with bindings to B/C for the same agents
(migration compensation).

Revision ID: 20260308_split_packages
Revises: 20260308_target_audience
Create Date: 2026-03-08 22:01:00.000000+00:00

"""

from __future__ import annotations

import json
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260308_split_packages"
down_revision: str | Sequence[str] | None = "20260308_target_audience"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# ── Package definitions ──────────────────────────────────────────────────────

_PKG_A_NAME = "系统核心技能包"   # existing — keep, rename to 系统引擎技能包
_PKG_A_NEW_NAME = "系统引擎技能包"
_PKG_A_NEW_DESC = "系统内部引擎能力包。包含 LLM 聊天和文本向量化等核心调度技能，供系统内部使用，不直接暴露给用户。"

_PKG_B_NAME = "平台数据管理"
_PKG_B_DESC = "平台数据管理能力包。包含数据智能、Text-to-SQL 等数据操作技能，仅限管理端使用。"

_PKG_C_NAME = "联网搜索"
_PKG_C_DESC = "联网搜索能力包。提供 web_search（联网搜索）和 fetch_url（网页抓取）工具，支持管理端和企业端智能体使用。"

# Skills that belong to each new package (matched by name + type)
_ENGINE_SKILLS = {"llm_chat", "llm_embedding"}
_WEB_SEARCH_SKILLS = {"web_search"}
_PAGE_BUILTIN_TYPES = {"page_context", "page_operation"}
# Remaining skills (not in the above sets) → data management package B


def _extract_builtin_type(skill_config: object) -> str | None:
    payload = skill_config
    if isinstance(skill_config, str):
        try:
            payload = json.loads(skill_config)
        except json.JSONDecodeError:
            return None

    if not isinstance(payload, dict):
        return None

    builtin_type = payload.get("builtin_type")
    if not isinstance(builtin_type, str):
        return None
    normalized = builtin_type.strip()
    return normalized if normalized else None


def _is_page_awareness_skill(skill_type: str, skill_config: object) -> bool:
    if skill_type != "builtin":
        return False
    return _extract_builtin_type(skill_config) in _PAGE_BUILTIN_TYPES


def _retire_page_awareness_skill(conn, skill_id: int) -> None:
    conn.execute(
        text(
            "UPDATE skills SET "
            "is_active = false, is_deleted = true, updated_at = NOW() "
            "WHERE id = :id"
        ),
        {"id": skill_id},
    )


def _find_package_by_name(conn, name: str) -> int | None:
    row = conn.execute(
        text(
            "SELECT id FROM skill_packages "
            "WHERE name = :name AND tenant_id IS NULL AND is_system = true AND is_deleted = false "
            "ORDER BY id LIMIT 1"
        ),
        {"name": name},
    ).fetchone()
    return row[0] if row else None


def _create_system_package(conn, name: str, desc: str, scope: str,
                            target_audience: str, is_recommended: bool,
                            sort_order: int) -> int:
    row = conn.execute(
        text(
            "INSERT INTO skill_packages "
            "(tenant_id, name, description, scope, bind_mode, is_system, is_active, "
            " is_recommended, target_audience, sort_order, "
            " created_at, updated_at, is_deleted) "
            "VALUES "
            "(NULL, :name, :desc, :scope, 'manual', true, true, "
            " :is_recommended, :target_audience, :sort_order, "
            " NOW(), NOW(), false) "
            "RETURNING id"
        ),
        {
            "name": name,
            "desc": desc,
            "scope": scope,
            "is_recommended": is_recommended,
            "target_audience": target_audience,
            "sort_order": sort_order,
        },
    ).fetchone()
    return row[0]


def upgrade() -> None:
    conn = op.get_bind()

    # ── 0. Validation: record existing binding count ─────────────────────────
    before_count = conn.execute(
        text("SELECT COUNT(*) FROM agent_skill_bindings WHERE is_deleted = false")
    ).scalar() or 0
    before_agent_count = conn.execute(
        text("SELECT COUNT(DISTINCT agent_id) FROM agent_skill_bindings WHERE is_deleted = false")
    ).scalar() or 0
    print(f"[SPLIT] Before: {before_count} bindings across {before_agent_count} agents")

    # ── 1. Find existing core package (package A) ─────────────────────────────
    # Try both old and new name (idempotent)
    pkg_a_id = _find_package_by_name(conn, _PKG_A_NEW_NAME)
    if not pkg_a_id:
        pkg_a_id = _find_package_by_name(conn, _PKG_A_NAME)

    if not pkg_a_id:
        print(f"[SPLIT] WARNING: '{_PKG_A_NAME}' not found, skipping split")
        return

    # ── 2. Update Package A: rename, set target_audience=all, bind_mode=manual ─
    conn.execute(
        text(
            "UPDATE skill_packages SET "
            "name = :new_name, description = :new_desc, "
            "bind_mode = 'manual', target_audience = 'all', "
            "is_recommended = false, updated_at = NOW() "
            "WHERE id = :id"
        ),
        {"new_name": _PKG_A_NEW_NAME, "new_desc": _PKG_A_NEW_DESC, "id": pkg_a_id},
    )
    print(f"[SPLIT] Updated Package A (id={pkg_a_id}): renamed to '{_PKG_A_NEW_NAME}', bind_mode=manual")

    # ── 3. Get all non-deleted skills in Package A ────────────────────────────
    skills = conn.execute(
        text(
            "SELECT id, name, type, config::text AS config_text FROM skills "
            "WHERE package_id = :pkg_id AND is_deleted = false "
            "ORDER BY name"
        ),
        {"pkg_id": pkg_a_id},
    ).fetchall()
    print(f"[SPLIT] Package A currently has {len(skills)} skills: {[s[1] for s in skills]}")

    # ── 4. Create/find Package B (平台数据管理) ──────────────────────────────
    pkg_b_id = _find_package_by_name(conn, _PKG_B_NAME)
    if not pkg_b_id:
        pkg_b_id = _create_system_package(
            conn, _PKG_B_NAME, _PKG_B_DESC,
            scope="admin_only", target_audience="admin_only",
            is_recommended=True, sort_order=2,
        )
        print(f"[SPLIT] Created Package B '{_PKG_B_NAME}' (id={pkg_b_id})")
    else:
        print(f"[SPLIT] Package B '{_PKG_B_NAME}' already exists (id={pkg_b_id})")

    # ── 5. Create/find Package C (联网搜索) ───────────────────────────────────
    pkg_c_id = _find_package_by_name(conn, _PKG_C_NAME)
    if not pkg_c_id:
        pkg_c_id = _create_system_package(
            conn, _PKG_C_NAME, _PKG_C_DESC,
            scope="global_shared", target_audience="admin_tenant",
            is_recommended=True, sort_order=3,
        )
        print(f"[SPLIT] Created Package C '{_PKG_C_NAME}' (id={pkg_c_id})")
    else:
        print(f"[SPLIT] Package C '{_PKG_C_NAME}' already exists (id={pkg_c_id})")

    # ── 6. Move skills from Package A to B/C and retire page-awareness skills ─
    for skill_id, skill_name, skill_type, skill_config_text in skills:
        if skill_name in _ENGINE_SKILLS:
            # Keep in Package A
            continue
        elif skill_name in _WEB_SEARCH_SKILLS:
            target_pkg = pkg_c_id
            target_name = _PKG_C_NAME
        elif _is_page_awareness_skill(skill_type, skill_config_text):
            _retire_page_awareness_skill(conn, skill_id)
            print(f"[SPLIT]   Retired page-awareness skill '{skill_name}' (id={skill_id})")
            continue
        else:
            # Default: data management skills → Package B
            target_pkg = pkg_b_id
            target_name = _PKG_B_NAME

        # Check if skill already moved (idempotent)
        already = conn.execute(
            text(
                "SELECT id FROM skills WHERE id = :id AND package_id = :pkg"
            ),
            {"id": skill_id, "pkg": target_pkg},
        ).fetchone()

        if already:
            print(f"[SPLIT]   Skill '{skill_name}' already in Package {target_name}")
            continue

        conn.execute(
            text(
                "UPDATE skills SET package_id = :pkg, updated_at = NOW() WHERE id = :id"
            ),
            {"pkg": target_pkg, "id": skill_id},
        )
        print(f"[SPLIT]   Moved skill '{skill_name}' (id={skill_id}) → '{target_name}' (id={target_pkg})")

    # ── 7. Migration compensation: create explicit bindings ──────────────────
    # For each agent that had a binding to Package A (old core),
    # create bindings to B and C as well (complement).
    agents_with_a = conn.execute(
        text(
            "SELECT DISTINCT agent_id FROM agent_skill_bindings "
            "WHERE package_id = :pkg AND is_deleted = false"
        ),
        {"pkg": pkg_a_id},
    ).fetchall()
    agent_ids = [row[0] for row in agents_with_a]
    print(f"[SPLIT] {len(agent_ids)} agents have binding to Package A — creating complementary bindings")

    new_pkgs = [
        (pkg_b_id, _PKG_B_NAME),
        (pkg_c_id, _PKG_C_NAME),
    ]

    for agent_id in agent_ids:
        # Get max sort_order for this agent's existing bindings
        max_order_row = conn.execute(
            text(
                "SELECT COALESCE(MAX(sort_order), 0) FROM agent_skill_bindings "
                "WHERE agent_id = :agent_id AND is_deleted = false"
            ),
            {"agent_id": agent_id},
        ).fetchone()
        sort_order = (max_order_row[0] or 0) + 1

        for new_pkg_id, new_pkg_name in new_pkgs:
            # Check if binding already exists (idempotent)
            existing = conn.execute(
                text(
                    "SELECT id FROM agent_skill_bindings "
                    "WHERE agent_id = :agent_id AND package_id = :pkg_id "
                    "AND is_deleted = false"
                ),
                {"agent_id": agent_id, "pkg_id": new_pkg_id},
            ).fetchone()

            if existing:
                continue

            conn.execute(
                text(
                    "INSERT INTO agent_skill_bindings "
                    "(agent_id, package_id, enabled, consent_mode, sort_order, "
                    " created_at, updated_at, is_deleted) "
                    "VALUES "
                    "(:agent_id, :pkg_id, true, 'auto', :sort_order, NOW(), NOW(), false)"
                ),
                {"agent_id": agent_id, "pkg_id": new_pkg_id, "sort_order": sort_order},
            )
            sort_order += 1

    # ── 8. Validate binding counts ────────────────────────────────────────────
    after_count = conn.execute(
        text("SELECT COUNT(*) FROM agent_skill_bindings WHERE is_deleted = false")
    ).scalar() or 0
    after_agent_count = conn.execute(
        text("SELECT COUNT(DISTINCT agent_id) FROM agent_skill_bindings WHERE is_deleted = false")
    ).scalar() or 0
    print(f"[SPLIT] After: {after_count} bindings across {after_agent_count} agents")

    if after_count < before_count:
        raise Exception(
            f"[SPLIT] ABORT: binding count decreased! "
            f"before={before_count}, after={after_count}"
        )
    if after_agent_count < before_agent_count:
        raise Exception(
            f"[SPLIT] ABORT: distinct agent count decreased! "
            f"before={before_agent_count}, after={after_agent_count}"
        )

    print("[SPLIT] System skill package split completed successfully.")


def downgrade() -> None:
    # Downgrade for data splits is complex. Packages remain and can be cleaned manually.
    print("[SPLIT] Downgrade: no-op. New packages remain and can be cleaned manually.")
