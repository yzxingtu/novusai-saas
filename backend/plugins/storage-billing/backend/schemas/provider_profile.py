"""Provider profile request schemas. / 提供方配置请求模式。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProviderProfilePayloadSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    profile_code: str | None = Field(default=None, max_length=64)
    bill_source: str | None = Field(default=None, max_length=64)
    region: str | None = Field(default=None, max_length=64)
    access_key: str | None = Field(default=None, max_length=255)
    secret_key: str | None = Field(default=None, max_length=255)
    access_key_id: str | None = Field(default=None, max_length=255)
    access_key_secret: str | None = Field(default=None, max_length=255)
    secret_id: str | None = Field(default=None, max_length=255)
    bill_bucket: str | None = Field(default=None, max_length=255)
    bill_prefix: str | None = Field(default=None, max_length=255)
    account_identifier: str | None = Field(default=None, max_length=255)


class UpdateProviderProfilesRequestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providers: dict[str, ProviderProfilePayloadSchema] = Field(default_factory=dict)
