"""merge page awareness skills into system core package

Move get_page_context and invoke_page_operation from the standalone
"页面感知" package into "系统核心技能包", then soft-delete the old package.

Also fix the core package scope from admin_only → global_shared so that
tenant-side agents can also access web_search and page awareness skills
via auto-bind.

Revision ID: 20260307_merge_page_pkg
Revises: 20260307_fix_op_timeout
Create Date: 2026-03-07 11:00:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect, text

revision: str = "20260307_merge_page_pkg"
down_revision: str | Sequence[str] | None = "20260307_fix_op_timeout"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CORE_PKG_NAME = "系统核心技能包"
_PAGE_PKG_NAME = "页面感知"
_NEW_CORE_SCOPE = "global_shared"


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Find the system core package ──
    core_row = conn.execute(
        text(
            "SELECT id, scope FROM skill_packages "
            "WHERE name = :name AND is_system = true AND is_deleted = false "
            "ORDER BY id LIMIT 1"
        ),
        {"name": _CORE_PKG_NAME},
    ).fetchone()

    if not core_row:
        print(f"[MERGE] WARNING: '{_CORE_PKG_NAME}' not found, skipping merge")
        return

    core_pkg_id = core_row[0]
    old_scope = core_row[1]

    # ── 2. Update core package scope to global_shared ──
    if old_scope != _NEW_CORE_SCOPE:
        conn.execute(
            text(
                "UPDATE skill_packages SET scope = :scope, updated_at = NOW() "
                "WHERE id = :id"
            ),
            {"scope": _NEW_CORE_SCOPE, "id": core_pkg_id},
        )
        print(f"[MERGE] Updated core package scope: {old_scope} → {_NEW_CORE_SCOPE}")

    # ── 3. Find the page awareness package ──
    page_row = conn.execute(
        text(
            "SELECT id FROM skill_packages "
            "WHERE name = :name AND is_system = true AND is_deleted = false "
            "ORDER BY id LIMIT 1"
        ),
        {"name": _PAGE_PKG_NAME},
    ).fetchone()

    if not page_row:
        print(f"[MERGE] '{_PAGE_PKG_NAME}' package not found, nothing to merge")
        return

    page_pkg_id = page_row[0]

    if page_pkg_id == core_pkg_id:
        print("[MERGE] Packages are already the same, skipping")
        return

    # ── 4. Move skills from page awareness → core package ──
    moved = conn.execute(
        text(
            "UPDATE skills SET package_id = :new_pkg, updated_at = NOW() "
            "WHERE package_id = :old_pkg AND is_deleted = false"
        ),
        {"new_pkg": core_pkg_id, "old_pkg": page_pkg_id},
    )
    print(f"[MERGE] Moved {moved.rowcount} skills from '{_PAGE_PKG_NAME}' → '{_CORE_PKG_NAME}'")

    # ── 5. Migrate agent_skill_bindings ──
    updated = conn.execute(
        text(
            "UPDATE agent_skill_bindings SET package_id = :new_pkg, updated_at = NOW() "
            "WHERE package_id = :old_pkg AND is_deleted = false"
        ),
        {"new_pkg": core_pkg_id, "old_pkg": page_pkg_id},
    )
    if updated.rowcount > 0:
        print(f"[MERGE] Migrated {updated.rowcount} bindings → core package")

    # ── 6. Deduplicate bindings (same agent may now have two bindings to core) ──
    conn.execute(
        text("""
            DELETE FROM agent_skill_bindings
            WHERE id NOT IN (
                SELECT MIN(id) FROM agent_skill_bindings
                WHERE package_id = :pkg_id AND is_deleted = false
                GROUP BY agent_id
            )
            AND package_id = :pkg_id
            AND is_deleted = false
        """),
        {"pkg_id": core_pkg_id},
    )

    # ── 7. Soft-delete the old page awareness package ──
    conn.execute(
        text(
            "UPDATE skill_packages SET is_deleted = true, deleted_at = NOW(), "
            "updated_at = NOW() WHERE id = :id"
        ),
        {"id": page_pkg_id},
    )
    print(f"[MERGE] Soft-deleted '{_PAGE_PKG_NAME}' package (id={page_pkg_id})")

    # ── 8. Normalize legacy scope='admin' on all active packages ──
    #      Old seeds used 'admin' which is not a valid ResourceScopeEnum value.
    #      Map: 'admin' → 'admin_only' (except the core package already set above).
    normalized = conn.execute(
        text(
            "UPDATE skill_packages SET scope = 'admin_only', updated_at = NOW() "
            "WHERE scope = 'admin' AND is_deleted = false"
        ),
    )
    if normalized.rowcount > 0:
        print(f"[MERGE] Normalized {normalized.rowcount} package(s) scope: 'admin' → 'admin_only'")

    # skills.scope 已在 d5e6f7a8b9c0 删除；仅当列仍存在时执行（兼容旧分支回放）
    skill_cols = {c["name"] for c in inspect(conn).get_columns("skills")}
    if "scope" in skill_cols:
        norm_skills = conn.execute(
            text(
                "UPDATE skills SET scope = 'admin_only', updated_at = NOW() "
                "WHERE scope = 'admin' AND is_deleted = false"
            ),
        )
        if norm_skills.rowcount > 0:
            print(
                f"[MERGE] Normalized {norm_skills.rowcount} skill(s) scope: 'admin' → 'admin_only'"
            )

    print("[MERGE] Page awareness skills merged into core package successfully.")


def downgrade() -> None:
    # Downgrade is complex for data merges.
    # The old package remains soft-deleted and can be restored manually.
    print("[MERGE] Downgrade: no-op. Old package remains soft-deleted.")
