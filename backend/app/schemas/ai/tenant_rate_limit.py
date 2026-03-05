"""
租户 AI 模型速率限制配置 Schema
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TenantRateLimitBase(BaseModel):
    """租户速率限制配置基础 Schema"""

    model_id: int = Field(..., description="模型 ID")
    rpm_limit: int | None = Field(None, ge=0, description="RPM 限制（每分钟请求数）")
    tpm_limit: int | None = Field(None, ge=0, description="TPM 限制（每分钟 Token 数）")
    description: str | None = Field(None, max_length=500, description="描述")


class TenantRateLimitCreate(TenantRateLimitBase):
    """创建租户速率限制配置"""

    pass


class AdminRateLimitCreate(TenantRateLimitBase):
    """管理端创建速率限制配置（需指定 tenant_id）"""

    tenant_id: int = Field(..., description="租户 ID")


class TenantRateLimitUpdate(BaseModel):
    """更新租户速率限制配置"""

    rpm_limit: int | None = Field(None, ge=0, description="RPM 限制")
    tpm_limit: int | None = Field(None, ge=0, description="TPM 限制")
    description: str | None = Field(None, max_length=500, description="描述")
    is_active: bool | None = Field(None, description="是否启用")


class TenantRateLimitResponse(TenantRateLimitBase):
    """租户速率限制配置响应"""

    id: int
    tenant_id: int
    is_active: bool
    model_name: str | None = Field(None, description="模型名称")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_model(cls, obj) -> TenantRateLimitResponse:
        """从 ORM 对象构建响应，自动提取关联 model_name"""
        model_name = None
        try:
            model_obj = getattr(obj, "model", None)
            if model_obj is not None:
                model_name = model_obj.name
        except AttributeError:
            pass

        return cls(
            id=obj.id,
            tenant_id=obj.tenant_id,
            model_id=obj.model_id,
            rpm_limit=obj.rpm_limit,
            tpm_limit=obj.tpm_limit,
            description=obj.description,
            is_active=obj.is_active,
            model_name=model_name,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class EffectiveRateLimits(BaseModel):
    """有效速率限制响应"""

    rpm_limit: int | None = Field(None, description="RPM 限制")
    tpm_limit: int | None = Field(None, description="TPM 限制")
    source: str = Field(..., description="来源（tenant/model/none）")


__all__ = [
    "TenantRateLimitCreate",
    "AdminRateLimitCreate",
    "TenantRateLimitUpdate",
    "TenantRateLimitResponse",
    "EffectiveRateLimits",
]
