"""Storage billing ledger models. / 对象存储对账计费台账模型。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel

from .enums import (
    StorageBillingChargeBasisEnum,
    StorageBillingPeriodTypeEnum,
    StorageBillingRunStatusEnum,
    StorageBillingSourceStatusEnum,
    StorageBillingStatementStatusEnum,
)


def _make_run_key() -> str:
    return f"sbr-{uuid4().hex[:16]}"


def _make_source_key() -> str:
    return f"sbs-{uuid4().hex[:16]}"


class StorageBillingRun(BaseModel):
    __tablename__ = "px_storage_billing_runs"
    __table_args__ = (
        UniqueConstraint("run_key", name="uq_px_storage_billing_runs_run_key"),
        Index(
            "ix_px_storage_billing_runs_billing_date_status",
            "period_type",
            "billing_date",
            "status",
        ),
    )

    run_key: Mapped[str] = mapped_column(
        String(40), nullable=False, default=_make_run_key
    )
    period_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=StorageBillingPeriodTypeEnum.DAILY.value,
    )
    billing_date: Mapped[date] = mapped_column(Date(), nullable=False)
    period_start: Mapped[date] = mapped_column(Date(), nullable=False)
    period_end: Mapped[date] = mapped_column(Date(), nullable=False)
    trigger_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="schedule"
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=StorageBillingRunStatusEnum.PENDING.value
    )
    provider_codes_json: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    requested_scope_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    summary_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    operator_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class StorageProviderBillSource(BaseModel):
    __tablename__ = "px_storage_billing_provider_sources"
    __table_args__ = (
        UniqueConstraint(
            "source_key", name="uq_px_storage_billing_provider_sources_source_key"
        ),
        Index(
            "ix_px_storage_billing_provider_sources_provider_date",
            "provider_code",
            "period_type",
            "billing_date",
        ),
        Index(
            "ix_px_storage_billing_provider_sources_run_status",
            "run_id",
            "source_status",
        ),
    )

    source_key: Mapped[str] = mapped_column(
        String(40), nullable=False, default=_make_source_key
    )
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("px_storage_billing_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_code: Mapped[str] = mapped_column(String(50), nullable=False)
    driver_code: Mapped[str] = mapped_column(String(50), nullable=False)
    period_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=StorageBillingPeriodTypeEnum.DAILY.value,
    )
    billing_date: Mapped[date] = mapped_column(Date(), nullable=False)
    period_start: Mapped[date] = mapped_column(Date(), nullable=False)
    period_end: Mapped[date] = mapped_column(Date(), nullable=False)
    source_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=StorageBillingSourceStatusEnum.PENDING.value
    )
    source_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    amount_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0")
    )
    usage_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    raw_payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class StorageTenantStatement(BaseModel):
    __tablename__ = "px_storage_billing_tenant_statements"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "period_type",
            "billing_date",
            name="uq_px_storage_billing_tenant_statements_tenant_date",
        ),
        Index(
            "ix_px_storage_billing_tenant_statements_tenant_status",
            "tenant_id",
            "period_type",
            "status",
        ),
    )

    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    period_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=StorageBillingPeriodTypeEnum.DAILY.value,
    )
    billing_date: Mapped[date] = mapped_column(Date(), nullable=False)
    period_start: Mapped[date] = mapped_column(Date(), nullable=False)
    period_end: Mapped[date] = mapped_column(Date(), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=StorageBillingStatementStatusEnum.DRAFT.value,
    )
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    amount_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0")
    )
    charge_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class StorageTenantDailyCharge(BaseModel):
    __tablename__ = "px_storage_billing_tenant_daily_charges"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "period_type",
            "billing_date",
            "provider_code",
            "driver_code",
            "charge_basis",
            name="uq_px_storage_billing_tenant_daily_charge_key",
        ),
        Index(
            "ix_px_storage_billing_tenant_daily_charges_tenant_date",
            "tenant_id",
            "period_type",
            "billing_date",
        ),
        Index("ix_px_storage_billing_tenant_daily_charges_statement", "statement_id"),
    )

    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    period_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=StorageBillingPeriodTypeEnum.DAILY.value,
    )
    billing_date: Mapped[date] = mapped_column(Date(), nullable=False)
    period_start: Mapped[date] = mapped_column(Date(), nullable=False)
    period_end: Mapped[date] = mapped_column(Date(), nullable=False)
    provider_code: Mapped[str] = mapped_column(String(50), nullable=False)
    driver_code: Mapped[str] = mapped_column(String(50), nullable=False)
    charge_basis: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=StorageBillingChargeBasisEnum.EGRESS_TRAFFIC.value,
    )
    usage_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    amount_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal("0")
    )
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="CNY")
    source_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("px_storage_billing_provider_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    statement_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("px_storage_billing_tenant_statements.id", ondelete="SET NULL"),
        nullable=True,
    )
    details_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


__all__ = [
    "StorageBillingRun",
    "StorageProviderBillSource",
    "StorageTenantDailyCharge",
    "StorageTenantStatement",
]
