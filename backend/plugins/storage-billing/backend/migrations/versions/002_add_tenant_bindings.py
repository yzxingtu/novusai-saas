"""add storage billing tenant bindings

Revision ID: sb_002_bindings
Revises: sb_001_init
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "sb_002_bindings"
down_revision = "sb_001_init"
branch_labels = None


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


def upgrade():
    op.create_table(
        "px_storage_billing_tenant_bindings",
        *_base_columns(),
        sa.Column("binding_key", sa.String(length=40), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("provider_code", sa.String(length=50), nullable=False),
        sa.Column("driver_code", sa.String(length=50), nullable=False),
        sa.Column("provider_profile_code", sa.String(length=64), nullable=False),
        sa.Column("billing_mode", sa.String(length=32), server_default="official_reconciled", nullable=False),
        sa.Column("scope_type", sa.String(length=32), server_default="bucket", nullable=False),
        sa.Column("scope_value", sa.String(length=255), nullable=False),
        sa.Column("bucket_name", sa.String(length=255), nullable=True),
        sa.Column("domain_name", sa.String(length=255), nullable=True),
        sa.Column("account_identifier", sa.String(length=255), nullable=True),
        sa.Column("tag_key", sa.String(length=128), nullable=True),
        sa.Column("tag_value", sa.String(length=255), nullable=True),
        sa.Column("validation_status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("validation_message", sa.Text(), nullable=True),
        sa.Column("entitlement_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), server_default=_jsonb_object(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("binding_key", name="uq_px_storage_billing_tenant_bindings_key"),
        sa.UniqueConstraint(
            "tenant_id",
            "provider_code",
            "scope_type",
            "scope_value",
            name="uq_px_storage_billing_tenant_bindings_scope",
        ),
    )
    op.create_index(
        "ix_px_storage_billing_tenant_bindings_tenant_provider",
        "px_storage_billing_tenant_bindings",
        ["tenant_id", "provider_code"],
    )
    op.create_index(
        "ix_px_storage_billing_tenant_bindings_validation",
        "px_storage_billing_tenant_bindings",
        ["validation_status", "is_active"],
    )


def downgrade():
    op.drop_index(
        "ix_px_storage_billing_tenant_bindings_validation",
        table_name="px_storage_billing_tenant_bindings",
    )
    op.drop_index(
        "ix_px_storage_billing_tenant_bindings_tenant_provider",
        table_name="px_storage_billing_tenant_bindings",
    )
    op.drop_table("px_storage_billing_tenant_bindings")
