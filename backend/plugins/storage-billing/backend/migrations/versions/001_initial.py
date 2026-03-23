"""create storage billing plugin tables

Revision ID: sb_001_init
Revises:
Create Date: 2026-03-23

branch_labels = ('plugin_storage_billing',)
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "sb_001_init"
down_revision = None
branch_labels = ("plugin_storage_billing",)


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delete_level", sa.String(length=20), nullable=True),
        sa.Column("recycle_stage", sa.String(length=20), nullable=True),
        sa.Column("promoted_to_global_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _jsonb_object() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def _jsonb_array() -> sa.TextClause:
    return sa.text("'[]'::jsonb")


def upgrade():
    op.create_table(
        "px_storage_billing_runs",
        *_base_columns(),
        sa.Column("run_key", sa.String(length=40), nullable=False),
        sa.Column("billing_date", sa.Date(), nullable=False),
        sa.Column("trigger_type", sa.String(length=20), server_default="schedule", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("provider_codes_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_array(), nullable=False),
        sa.Column("requested_scope_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("operator_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.UniqueConstraint("run_key", name="uq_px_storage_billing_runs_run_key"),
    )
    op.create_index("ix_px_storage_billing_runs_billing_date_status", "px_storage_billing_runs", ["billing_date", "status"])

    op.create_table(
        "px_storage_billing_provider_sources",
        *_base_columns(),
        sa.Column("source_key", sa.String(length=40), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("px_storage_billing_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_code", sa.String(length=50), nullable=False),
        sa.Column("driver_code", sa.String(length=50), nullable=False),
        sa.Column("billing_date", sa.Date(), nullable=False),
        sa.Column("source_status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("currency", sa.String(length=8), server_default="CNY", nullable=False),
        sa.Column("amount_total", sa.Numeric(18, 6), server_default="0", nullable=False),
        sa.Column("usage_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.UniqueConstraint("source_key", name="uq_px_storage_billing_provider_sources_source_key"),
    )
    op.create_index("ix_px_storage_billing_provider_sources_provider_date", "px_storage_billing_provider_sources", ["provider_code", "billing_date"])
    op.create_index("ix_px_storage_billing_provider_sources_run_status", "px_storage_billing_provider_sources", ["run_id", "source_status"])

    op.create_table(
        "px_storage_billing_tenant_statements",
        *_base_columns(),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("billing_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("currency", sa.String(length=8), server_default="CNY", nullable=False),
        sa.Column("amount_total", sa.Numeric(18, 6), server_default="0", nullable=False),
        sa.Column("charge_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "billing_date", name="uq_px_storage_billing_tenant_statements_tenant_date"),
    )
    op.create_index("ix_px_storage_billing_tenant_statements_tenant_status", "px_storage_billing_tenant_statements", ["tenant_id", "status"])

    op.create_table(
        "px_storage_billing_tenant_daily_charges",
        *_base_columns(),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("billing_date", sa.Date(), nullable=False),
        sa.Column("provider_code", sa.String(length=50), nullable=False),
        sa.Column("driver_code", sa.String(length=50), nullable=False),
        sa.Column("charge_basis", sa.String(length=32), server_default="egress_traffic", nullable=False),
        sa.Column("usage_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("amount_total", sa.Numeric(18, 6), server_default="0", nullable=False),
        sa.Column("currency", sa.String(length=8), server_default="CNY", nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("px_storage_billing_provider_sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("statement_id", sa.Integer(), sa.ForeignKey("px_storage_billing_tenant_statements.id", ondelete="SET NULL"), nullable=True),
        sa.Column("details_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "billing_date",
            "provider_code",
            "driver_code",
            "charge_basis",
            name="uq_px_storage_billing_tenant_daily_charge_key",
        ),
    )
    op.create_index("ix_px_storage_billing_tenant_daily_charges_tenant_date", "px_storage_billing_tenant_daily_charges", ["tenant_id", "billing_date"])
    op.create_index("ix_px_storage_billing_tenant_daily_charges_statement", "px_storage_billing_tenant_daily_charges", ["statement_id"])


def downgrade():
    op.drop_index("ix_px_storage_billing_tenant_daily_charges_statement", table_name="px_storage_billing_tenant_daily_charges")
    op.drop_index("ix_px_storage_billing_tenant_daily_charges_tenant_date", table_name="px_storage_billing_tenant_daily_charges")
    op.drop_table("px_storage_billing_tenant_daily_charges")
    op.drop_index("ix_px_storage_billing_tenant_statements_tenant_status", table_name="px_storage_billing_tenant_statements")
    op.drop_table("px_storage_billing_tenant_statements")
    op.drop_index("ix_px_storage_billing_provider_sources_run_status", table_name="px_storage_billing_provider_sources")
    op.drop_index("ix_px_storage_billing_provider_sources_provider_date", table_name="px_storage_billing_provider_sources")
    op.drop_table("px_storage_billing_provider_sources")
    op.drop_index("ix_px_storage_billing_runs_billing_date_status", table_name="px_storage_billing_runs")
    op.drop_table("px_storage_billing_runs")
