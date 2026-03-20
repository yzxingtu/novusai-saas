"""Merge heads + AI billing ledger schema (tenant publications, agents modes, call log ledger, drop usage stats)

Revision ID: 20260322_ai_billing_ledger_merge
Revises: 20260321_ai_call_log_contract, 6de5182f2be1
Create Date: 2026-03-22

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision: str = "20260322_ai_billing_ledger_merge"
down_revision: str | Sequence[str] | None = (
    "20260321_ai_call_log_contract",
    "6de5182f2be1",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(bind, name: str) -> bool:
    return name in inspect(bind).get_table_names()


def _column_names(bind, table: str) -> set[str]:
    return {c["name"] for c in inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()

    # ── tenant_agent_publications ───────────────────────────────────────────
    if not _table_exists(bind, "tenant_agent_publications"):
        op.create_table(
            "tenant_agent_publications",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column("delete_level", sa.String(length=20), nullable=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("agent_id", sa.Integer(), nullable=False),
            sa.Column(
                "enabled_for_users",
                sa.Boolean(),
                nullable=False,
                server_default="false",
            ),
            sa.Column(
                "access_type",
                sa.String(length=50),
                nullable=False,
                server_default="all_users",
            ),
            sa.Column("tenant_user_role_ids", sa.JSON(), nullable=True),
            sa.Column("tenant_user_ids", sa.JSON(), nullable=True),
            sa.Column("org_node_ids", sa.JSON(), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("published_by", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(
                ["agent_id"],
                ["agents.id"],
                name="fk_tenant_agent_publications_agent_id",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_tenant_agent_publications_tenant_agent",
            "tenant_agent_publications",
            ["tenant_id", "agent_id"],
            unique=True,
        )
        op.create_index(
            op.f("ix_tenant_agent_publications_agent_id"),
            "tenant_agent_publications",
            ["agent_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_tenant_agent_publications_tenant_id"),
            "tenant_agent_publications",
            ["tenant_id"],
            unique=False,
        )

    # ── agents: owner_type + distribution_mode ─────────────────────────────
    acols = _column_names(bind, "agents")
    if "owner_type" not in acols:
        op.add_column(
            "agents",
            sa.Column(
                "owner_type",
                sa.String(length=20),
                nullable=False,
                server_default="tenant",
            ),
        )
    if "distribution_mode" not in acols:
        op.add_column(
            "agents",
            sa.Column(
                "distribution_mode",
                sa.String(length=20),
                nullable=False,
                server_default="owner_only",
            ),
        )

    if "scope" in acols:
        op.execute(
            text(
                """
                UPDATE agents SET owner_type = CASE
                    WHEN tenant_id IS NULL THEN 'platform'
                    ELSE 'tenant'
                END
                """
            ),
        )
        op.execute(
            text(
                """
                UPDATE agents SET distribution_mode = CASE scope
                    WHEN 'admin_only' THEN 'internal'
                    WHEN 'admin' THEN 'internal'
                    WHEN 'all_tenants' THEN 'all_tenants'
                    WHEN 'tenant' THEN 'all_tenants'
                    WHEN 'global_shared' THEN 'all_tenants'
                    WHEN 'selected_tenants' THEN 'selected_tenants'
                    WHEN 'admin_and_selected_tenants' THEN 'selected_tenants'
                    WHEN 'tenant_user' THEN 'all_tenants'
                    WHEN 'global' THEN 'all_tenants'
                    ELSE 'owner_only'
                END
                WHERE scope IS NOT NULL
                """
            ),
        )

    op.execute(text("ALTER TABLE agents ALTER COLUMN owner_type DROP DEFAULT"))
    op.execute(text("ALTER TABLE agents ALTER COLUMN distribution_mode DROP DEFAULT"))

    # ── ai_call_logs: billing + publication + display snapshots ─────────────
    lcols = _column_names(bind, "ai_call_logs")
    ledger_cols: list[tuple[str, sa.Column]] = [
        ("billing_tenant_id", sa.Column("billing_tenant_id", sa.Integer(), nullable=True)),
        ("actor_user_id", sa.Column("actor_user_id", sa.Integer(), nullable=True)),
        ("actor_user_type", sa.Column("actor_user_type", sa.String(50), nullable=True)),
        ("access_channel", sa.Column("access_channel", sa.String(50), nullable=True)),
        ("agent_owner_type", sa.Column("agent_owner_type", sa.String(20), nullable=True)),
        (
            "agent_owner_tenant_id",
            sa.Column("agent_owner_tenant_id", sa.Integer(), nullable=True),
        ),
        (
            "agent_distribution_mode",
            sa.Column("agent_distribution_mode", sa.String(20), nullable=True),
        ),
        (
            "tenant_publication_id",
            sa.Column("tenant_publication_id", sa.Integer(), nullable=True),
        ),
        (
            "publication_enabled_snapshot",
            sa.Column("publication_enabled_snapshot", sa.Boolean(), nullable=True),
        ),
        (
            "publication_access_type_snapshot",
            sa.Column("publication_access_type_snapshot", sa.String(50), nullable=True),
        ),
        ("agent_id_snapshot", sa.Column("agent_id_snapshot", sa.Integer(), nullable=True)),
        (
            "agent_name_snapshot",
            sa.Column("agent_name_snapshot", sa.String(200), nullable=True),
        ),
        (
            "billing_tenant_name_snapshot",
            sa.Column("billing_tenant_name_snapshot", sa.String(200), nullable=True),
        ),
        (
            "model_name_snapshot",
            sa.Column("model_name_snapshot", sa.String(200), nullable=True),
        ),
        (
            "provider_name_snapshot",
            sa.Column("provider_name_snapshot", sa.String(200), nullable=True),
        ),
    ]
    for name, col in ledger_cols:
        if name not in lcols:
            op.add_column("ai_call_logs", col)

    # FK publication → tenant_agent_publications (idempotent check)
    if _table_exists(bind, "tenant_agent_publications"):
        fks = inspect(bind).get_foreign_keys("ai_call_logs")
        has_pub_fk = any(
            fk.get("referred_table") == "tenant_agent_publications"
            for fk in fks
        )
        if not has_pub_fk:
            op.create_foreign_key(
                "fk_ai_call_logs_tenant_publication_id",
                "ai_call_logs",
                "tenant_agent_publications",
                ["tenant_publication_id"],
                ["id"],
                ondelete="SET NULL",
            )

    op.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_ai_call_logs_billing_tenant_id
            ON ai_call_logs (billing_tenant_id)
            """
        ),
    )
    op.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_call_logs_billing_tenant_created
            ON ai_call_logs (billing_tenant_id, created_at)
            """
        ),
    )
    op.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_ai_call_logs_agent_id_snapshot
            ON ai_call_logs (agent_id_snapshot)
            """
        ),
    )

    # ── drop legacy aggregate table ─────────────────────────────────────────
    if _table_exists(bind, "ai_usage_stats"):
        op.drop_table("ai_usage_stats")


def downgrade() -> None:
    raise NotImplementedError(
        "20260322_ai_billing_ledger_merge downgrade not supported (merge + schema)",
    )
