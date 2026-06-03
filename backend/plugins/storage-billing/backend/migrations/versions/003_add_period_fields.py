"""add period fields to storage billing ledger

Revision ID: sb_003_period_fields
Revises: sb_002_bindings
Create Date: 2026-03-24
"""

import sqlalchemy as sa
from alembic import op

revision = "sb_003_period_fields"
down_revision = "sb_002_bindings"
branch_labels = None


def upgrade():
    op.add_column(
        "px_storage_billing_runs",
        sa.Column(
            "period_type",
            sa.String(length=16),
            server_default="daily",
            nullable=False,
        ),
    )
    op.add_column(
        "px_storage_billing_runs",
        sa.Column("period_start", sa.Date(), nullable=True),
    )
    op.add_column(
        "px_storage_billing_runs",
        sa.Column("period_end", sa.Date(), nullable=True),
    )
    op.execute(
        """
        UPDATE px_storage_billing_runs
        SET period_start = billing_date,
            period_end = billing_date
        WHERE period_start IS NULL OR period_end IS NULL
        """
    )
    op.alter_column("px_storage_billing_runs", "period_start", nullable=False)
    op.alter_column("px_storage_billing_runs", "period_end", nullable=False)
    op.drop_index(
        "ix_px_storage_billing_runs_billing_date_status",
        table_name="px_storage_billing_runs",
    )
    op.create_index(
        "ix_px_storage_billing_runs_billing_date_status",
        "px_storage_billing_runs",
        ["period_type", "billing_date", "status"],
    )

    op.add_column(
        "px_storage_billing_provider_sources",
        sa.Column(
            "period_type",
            sa.String(length=16),
            server_default="daily",
            nullable=False,
        ),
    )
    op.add_column(
        "px_storage_billing_provider_sources",
        sa.Column("period_start", sa.Date(), nullable=True),
    )
    op.add_column(
        "px_storage_billing_provider_sources",
        sa.Column("period_end", sa.Date(), nullable=True),
    )
    op.execute(
        """
        UPDATE px_storage_billing_provider_sources
        SET period_start = billing_date,
            period_end = billing_date
        WHERE period_start IS NULL OR period_end IS NULL
        """
    )
    op.alter_column(
        "px_storage_billing_provider_sources",
        "period_start",
        nullable=False,
    )
    op.alter_column(
        "px_storage_billing_provider_sources",
        "period_end",
        nullable=False,
    )
    op.drop_index(
        "ix_px_storage_billing_provider_sources_provider_date",
        table_name="px_storage_billing_provider_sources",
    )
    op.create_index(
        "ix_px_storage_billing_provider_sources_provider_date",
        "px_storage_billing_provider_sources",
        ["provider_code", "period_type", "billing_date"],
    )

    op.add_column(
        "px_storage_billing_tenant_statements",
        sa.Column(
            "period_type",
            sa.String(length=16),
            server_default="daily",
            nullable=False,
        ),
    )
    op.add_column(
        "px_storage_billing_tenant_statements",
        sa.Column("period_start", sa.Date(), nullable=True),
    )
    op.add_column(
        "px_storage_billing_tenant_statements",
        sa.Column("period_end", sa.Date(), nullable=True),
    )
    op.execute(
        """
        UPDATE px_storage_billing_tenant_statements
        SET period_start = billing_date,
            period_end = billing_date
        WHERE period_start IS NULL OR period_end IS NULL
        """
    )
    op.alter_column(
        "px_storage_billing_tenant_statements",
        "period_start",
        nullable=False,
    )
    op.alter_column(
        "px_storage_billing_tenant_statements",
        "period_end",
        nullable=False,
    )
    op.drop_constraint(
        "uq_px_storage_billing_tenant_statements_tenant_date",
        "px_storage_billing_tenant_statements",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_px_storage_billing_tenant_statements_tenant_date",
        "px_storage_billing_tenant_statements",
        ["tenant_id", "period_type", "billing_date"],
    )
    op.drop_index(
        "ix_px_storage_billing_tenant_statements_tenant_status",
        table_name="px_storage_billing_tenant_statements",
    )
    op.create_index(
        "ix_px_storage_billing_tenant_statements_tenant_status",
        "px_storage_billing_tenant_statements",
        ["tenant_id", "period_type", "status"],
    )

    op.add_column(
        "px_storage_billing_tenant_daily_charges",
        sa.Column(
            "period_type",
            sa.String(length=16),
            server_default="daily",
            nullable=False,
        ),
    )
    op.add_column(
        "px_storage_billing_tenant_daily_charges",
        sa.Column("period_start", sa.Date(), nullable=True),
    )
    op.add_column(
        "px_storage_billing_tenant_daily_charges",
        sa.Column("period_end", sa.Date(), nullable=True),
    )
    op.execute(
        """
        UPDATE px_storage_billing_tenant_daily_charges
        SET period_start = billing_date,
            period_end = billing_date
        WHERE period_start IS NULL OR period_end IS NULL
        """
    )
    op.alter_column(
        "px_storage_billing_tenant_daily_charges",
        "period_start",
        nullable=False,
    )
    op.alter_column(
        "px_storage_billing_tenant_daily_charges",
        "period_end",
        nullable=False,
    )
    op.drop_constraint(
        "uq_px_storage_billing_tenant_daily_charge_key",
        "px_storage_billing_tenant_daily_charges",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_px_storage_billing_tenant_daily_charge_key",
        "px_storage_billing_tenant_daily_charges",
        [
            "tenant_id",
            "period_type",
            "billing_date",
            "provider_code",
            "driver_code",
            "charge_basis",
        ],
    )
    op.drop_index(
        "ix_px_storage_billing_tenant_daily_charges_tenant_date",
        table_name="px_storage_billing_tenant_daily_charges",
    )
    op.create_index(
        "ix_px_storage_billing_tenant_daily_charges_tenant_date",
        "px_storage_billing_tenant_daily_charges",
        ["tenant_id", "period_type", "billing_date"],
    )


def downgrade():
    op.drop_index(
        "ix_px_storage_billing_tenant_daily_charges_tenant_date",
        table_name="px_storage_billing_tenant_daily_charges",
    )
    op.create_index(
        "ix_px_storage_billing_tenant_daily_charges_tenant_date",
        "px_storage_billing_tenant_daily_charges",
        ["tenant_id", "billing_date"],
    )
    op.drop_constraint(
        "uq_px_storage_billing_tenant_daily_charge_key",
        "px_storage_billing_tenant_daily_charges",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_px_storage_billing_tenant_daily_charge_key",
        "px_storage_billing_tenant_daily_charges",
        ["tenant_id", "billing_date", "provider_code", "driver_code", "charge_basis"],
    )
    op.drop_column("px_storage_billing_tenant_daily_charges", "period_end")
    op.drop_column("px_storage_billing_tenant_daily_charges", "period_start")
    op.drop_column("px_storage_billing_tenant_daily_charges", "period_type")

    op.drop_index(
        "ix_px_storage_billing_tenant_statements_tenant_status",
        table_name="px_storage_billing_tenant_statements",
    )
    op.create_index(
        "ix_px_storage_billing_tenant_statements_tenant_status",
        "px_storage_billing_tenant_statements",
        ["tenant_id", "status"],
    )
    op.drop_constraint(
        "uq_px_storage_billing_tenant_statements_tenant_date",
        "px_storage_billing_tenant_statements",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_px_storage_billing_tenant_statements_tenant_date",
        "px_storage_billing_tenant_statements",
        ["tenant_id", "billing_date"],
    )
    op.drop_column("px_storage_billing_tenant_statements", "period_end")
    op.drop_column("px_storage_billing_tenant_statements", "period_start")
    op.drop_column("px_storage_billing_tenant_statements", "period_type")

    op.drop_index(
        "ix_px_storage_billing_provider_sources_provider_date",
        table_name="px_storage_billing_provider_sources",
    )
    op.create_index(
        "ix_px_storage_billing_provider_sources_provider_date",
        "px_storage_billing_provider_sources",
        ["provider_code", "billing_date"],
    )
    op.drop_column("px_storage_billing_provider_sources", "period_end")
    op.drop_column("px_storage_billing_provider_sources", "period_start")
    op.drop_column("px_storage_billing_provider_sources", "period_type")

    op.drop_index(
        "ix_px_storage_billing_runs_billing_date_status",
        table_name="px_storage_billing_runs",
    )
    op.create_index(
        "ix_px_storage_billing_runs_billing_date_status",
        "px_storage_billing_runs",
        ["billing_date", "status"],
    )
    op.drop_column("px_storage_billing_runs", "period_end")
    op.drop_column("px_storage_billing_runs", "period_start")
    op.drop_column("px_storage_billing_runs", "period_type")
