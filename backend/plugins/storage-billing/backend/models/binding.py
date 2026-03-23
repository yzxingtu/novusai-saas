"""Storage billing tenant binding models. / 对象存储对账租户绑定模型。"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel

from .enums import (
    StorageBillingModeEnum,
    StorageBillingScopeTypeEnum,
    StorageBillingValidationStatusEnum,
    StorageProviderCodeEnum,
)


def _make_binding_key() -> str:
    return f"sbb-{uuid4().hex[:16]}"


class StorageTenantBinding(BaseModel):
    __tablename__ = "px_storage_billing_tenant_bindings"
    __table_args__ = (
        UniqueConstraint("binding_key", name="uq_px_storage_billing_tenant_bindings_key"),
        UniqueConstraint(
            "tenant_id",
            "provider_code",
            "scope_type",
            "scope_value",
            name="uq_px_storage_billing_tenant_bindings_scope",
        ),
        Index("ix_px_storage_billing_tenant_bindings_tenant_provider", "tenant_id", "provider_code"),
        Index("ix_px_storage_billing_tenant_bindings_validation", "validation_status", "is_active"),
    )

    binding_key: Mapped[str] = mapped_column(String(40), nullable=False, default=_make_binding_key)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=StorageProviderCodeEnum.TENCENT_COS.value,
    )
    driver_code: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_profile_code: Mapped[str] = mapped_column(String(64), nullable=False)
    billing_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=StorageBillingModeEnum.OFFICIAL_RECONCILED.value,
    )
    scope_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=StorageBillingScopeTypeEnum.BUCKET.value,
    )
    scope_value: Mapped[str] = mapped_column(String(255), nullable=False)
    bucket_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    domain_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tag_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tag_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    validation_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=StorageBillingValidationStatusEnum.PENDING.value,
    )
    validation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    entitlement_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = ["StorageTenantBinding"]
