"""Cleanup legacy schema residue and migrate agent skill bindings

Revision ID: 20260327_1500_cleanup_legacy
Revises: 20260326_0001_ai_log_snap
Create Date: 2026-03-27 15:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "20260327_1500_cleanup_legacy"
down_revision: str | Sequence[str] | None = "20260326_0001_ai_log_snap"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


LEGACY_EMPTY_TABLES = [
    "agent_publish_configs",
    "announcement_reads",
    "announcements",
    "tenant_subscription_logs",
    "tenant_subscriptions",
    "workflow_node_executions",
    "workflow_edges",
    "workflow_nodes",
    "workflow_runs",
    "workflows",
]


def _has_table(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def _validate_mappable_agent_skill_bindings() -> None:
    """Guard against dropping live package bindings that cannot expand to skills."""

    if not _has_table("agent_skill_bindings"):
        return

    unmappable_live_count = op.get_bind().execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM (
                SELECT b.id
                FROM agent_skill_bindings AS b
                LEFT JOIN skill_packages AS sp
                    ON sp.id = b.package_id
                LEFT JOIN skills AS s
                    ON s.package_id = b.package_id
                   AND COALESCE(s.is_deleted, FALSE) = FALSE
                WHERE COALESCE(b.is_deleted, FALSE) = FALSE
                GROUP BY b.id, COALESCE(sp.is_deleted, FALSE)
                HAVING COALESCE(sp.is_deleted, FALSE) = FALSE
                   AND COUNT(s.id) = 0
            ) AS unmappable
            """
        )
    ).scalar_one()

    if unmappable_live_count:
        raise RuntimeError(
            "Found live agent_skill_bindings rows that cannot be expanded to skills; "
            "cleanup migration aborted to avoid silent data loss."
        )


def _backfill_agent_skill_grants_from_bindings() -> None:
    """Expand old package-based bindings into direct skill grants."""

    if not _has_table("agent_skill_bindings"):
        return

    required_tables = ("agent_skill_grants", "skill_packages", "skills")
    missing_tables = [table_name for table_name in required_tables if not _has_table(table_name)]
    if missing_tables:
        raise RuntimeError(
            "Cannot migrate agent_skill_bindings because required tables are missing: "
            + ", ".join(missing_tables)
        )

    _validate_mappable_agent_skill_bindings()

    op.execute(
        sa.text(
            """
            INSERT INTO agent_skill_grants (
                tenant_id,
                agent_id,
                skill_id,
                enabled,
                config_override,
                sort_order,
                default_consent_mode,
                capability_consent_overrides,
                created_at,
                updated_at,
                is_deleted,
                deleted_at,
                delete_level,
                recycle_stage,
                promoted_to_global_at
            )
            SELECT
                expanded.tenant_id,
                expanded.agent_id,
                expanded.skill_id,
                expanded.enabled,
                expanded.config_override,
                expanded.expanded_sort_order,
                expanded.default_consent_mode,
                expanded.capability_consent_overrides,
                expanded.created_at,
                expanded.updated_at,
                expanded.is_deleted,
                expanded.deleted_at,
                expanded.delete_level,
                expanded.recycle_stage,
                expanded.promoted_to_global_at
            FROM (
                SELECT
                    b.tenant_id,
                    b.agent_id,
                    s.id AS skill_id,
                    b.enabled,
                    b.config_override,
                    COALESCE(b.sort_order, 0)
                        + ROW_NUMBER() OVER (
                            PARTITION BY b.id
                            ORDER BY s.id
                        ) - 1 AS expanded_sort_order,
                    COALESCE(b.consent_mode, 'auto') AS default_consent_mode,
                    b.skill_consent_overrides AS capability_consent_overrides,
                    COALESCE(b.created_at, NOW()) AS created_at,
                    COALESCE(b.updated_at, NOW()) AS updated_at,
                    COALESCE(b.is_deleted, FALSE) AS is_deleted,
                    b.deleted_at,
                    b.delete_level,
                    b.recycle_stage,
                    b.promoted_to_global_at
                FROM agent_skill_bindings AS b
                JOIN skill_packages AS sp
                    ON sp.id = b.package_id
                JOIN skills AS s
                    ON s.package_id = sp.id
                WHERE COALESCE(sp.is_deleted, FALSE) = FALSE
                  AND COALESCE(s.is_deleted, FALSE) = FALSE
            ) AS expanded
            ON CONFLICT (agent_id, skill_id) DO NOTHING
            """
        )
    )


def upgrade() -> None:
    _backfill_agent_skill_grants_from_bindings()

    if _has_table("agent_skill_bindings"):
        op.drop_table("agent_skill_bindings")

    for table_name in LEGACY_EMPTY_TABLES:
        if _has_table(table_name):
            op.drop_table(table_name)


def downgrade() -> None:
    """Intentional no-op.

    This migration removes retired runtime tables and expands package-based
    bindings into direct skill grants. The package -> skill expansion is lossy
    for downgrade purposes, so we keep downgrade as a documented no-op rather
    than reintroduce stale runtime paths with partial data.
    """

    pass
