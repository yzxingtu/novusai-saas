"""Tenant binding request schemas. / 租户计费绑定请求模式。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _StorageTenantBindingBaseSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: int | None = Field(default=None, gt=0)
    provider_code: str | None = Field(default=None, max_length=50)
    driver_code: str | None = Field(default=None, max_length=50)
    provider_profile_code: str | None = Field(default=None, max_length=64)
    billing_mode: str | None = Field(default=None, max_length=32)
    scope_type: str | None = Field(default=None, max_length=32)
    scope_value: str | None = Field(default=None, max_length=255)
    bucket_name: str | None = Field(default=None, max_length=255)
    domain_name: str | None = Field(default=None, max_length=255)
    account_identifier: str | None = Field(default=None, max_length=255)
    tag_key: str | None = Field(default=None, max_length=128)
    tag_value: str | None = Field(default=None, max_length=255)
    metadata_json: dict = Field(default_factory=dict)
    is_active: bool | None = None


class CreateStorageTenantBindingRequestSchema(_StorageTenantBindingBaseSchema):
    tenant_id: int = Field(gt=0)
    provider_code: str = Field(min_length=1, max_length=50)
    scope_type: str = Field(min_length=1, max_length=32)
    scope_value: str | None = Field(default=None, max_length=255)


class UpdateStorageTenantBindingRequestSchema(_StorageTenantBindingBaseSchema):
    pass
