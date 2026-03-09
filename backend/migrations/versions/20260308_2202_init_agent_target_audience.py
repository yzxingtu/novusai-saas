"""initialize agent target_audience and migrate org_node_ids to tenant_role_ids

DML:
1. agents with is_system=true → target_audience='admin_tenant'
2. agents with scope='admin_only' → target_audience='admin_only'
3. others keep server_default 'admin_tenant' (no change needed)
4. agent_access: copy org_node_ids → tenant_role_ids where access_type='org_node'
   and tenant_role_ids is NULL (preserve any already-set values)

Revision ID: 20260308_init_audience
Revises: 20260308_split_packages
Create Date: 2026-03-08 22:02:00.000000+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260308_init_audience"
down_revision: str | Sequence[str] | None = "20260308_split_packages"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. System agents → target_audience = 'admin_tenant' ─────────────────
    result = conn.execute(
        text(
            "UPDATE agents SET target_audience = 'admin_tenant', updated_at = NOW() "
            "WHERE is_system = true AND is_deleted = false "
            "AND (target_audience IS NULL OR target_audience = 'admin_tenant')"
        )
    )
    print(f"[INIT] Set {result.rowcount} system agent(s) target_audience = 'admin_tenant'")

    # ── 2. admin_only scope agents → target_audience = 'admin_only' ──────────
    result = conn.execute(
        text(
            "UPDATE agents SET target_audience = 'admin_only', updated_at = NOW() "
            "WHERE scope = 'admin_only' AND is_deleted = false "
            "AND target_audience != 'admin_only'"
        )
    )
    print(f"[INIT] Set {result.rowcount} admin_only agent(s) target_audience = 'admin_only'")

    # ── 3. All agents should now have target_audience set (server_default handles rest) ──
    # Verify no NULL values remain
    null_count = conn.execute(
        text(
            "SELECT COUNT(*) FROM agents "
            "WHERE target_audience IS NULL AND is_deleted = false"
        )
    ).scalar() or 0

    if null_count > 0:
        # Fallback: set any remaining NULLs to 'admin_tenant'
        conn.execute(
            text(
                "UPDATE agents SET target_audience = 'admin_tenant', updated_at = NOW() "
                "WHERE target_audience IS NULL AND is_deleted = false"
            )
        )
        print(f"[INIT] Fallback: set {null_count} agent(s) with NULL target_audience to 'admin_tenant'")

    # ── 4. Migrate org_node_ids → tenant_role_ids ─────────────────────────────
    # For access_type='org_node' entries where org_node_ids is not null
    # and tenant_role_ids is null: copy the data as migration.
    # Note: org_node_ids contains org node IDs, not role IDs. This is a
    # best-effort migration — the values are semantically different but both
    # represent "which entities have access". Phase 3 will clean this up.
    result = conn.execute(
        text(
            "UPDATE agent_access SET "
            "tenant_role_ids = org_node_ids, updated_at = NOW() "
            "WHERE access_type = 'org_node' "
            "AND org_node_ids IS NOT NULL "
            "AND tenant_role_ids IS NULL "
            "AND is_deleted = false"
        )
    )
    print(f"[INIT] Migrated org_node_ids → tenant_role_ids for {result.rowcount} agent_access record(s)")

    # ── 5. Validation ─────────────────────────────────────────────────────────
    total_agents = conn.execute(
        text("SELECT COUNT(*) FROM agents WHERE is_deleted = false")
    ).scalar() or 0
    null_audience = conn.execute(
        text(
            "SELECT COUNT(*) FROM agents "
            "WHERE target_audience IS NULL AND is_deleted = false"
        )
    ).scalar() or 0

    if null_audience > 0:
        raise Exception(
            f"[INIT] ABORT: {null_audience}/{total_agents} agents still have NULL target_audience"
        )

    print(f"[INIT] Validation passed: all {total_agents} active agents have target_audience set.")


def downgrade() -> None:
    conn = op.get_bind()

    # Revert tenant_role_ids where it was copied from org_node_ids
    conn.execute(
        text(
            "UPDATE agent_access SET tenant_role_ids = NULL, updated_at = NOW() "
            "WHERE access_type = 'org_node' AND tenant_role_ids IS NOT NULL "
            "AND is_deleted = false"
        )
    )

    # Reset all agent target_audience back to server_default
    conn.execute(
        text(
            "UPDATE agents SET target_audience = 'admin_tenant', updated_at = NOW() "
            "WHERE is_deleted = false"
        )
    )

    print("[INIT] Downgrade: reverted agent target_audience and tenant_role_ids.")
