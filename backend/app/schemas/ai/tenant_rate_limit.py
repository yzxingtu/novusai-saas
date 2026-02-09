"""
租户 AI 模型速率限制配置 Schema
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TenantRateLimitBase(BaseModel):
    """租户速率限制配置基础 Schema"""
    
    model_id: int = Field(..., description="模型 ID")
    rpm_limit: Optional[int] = Field(None, ge=0, description="RPM 限制（每分钟请求数）")
    tpm_limit: Optional[int] = Field(None, ge=0, description="TPM 限制（每分钟 Token 数）")
    description: Optional[str] = Field(None, max_length=500, description="描述")


class TenantRateLimitCreate(TenantRateLimitBase):
    """创建租户速率限制配置"""
    
    pass


class TenantRateLimitUpdate(BaseModel):
    """更新租户速率限制配置"""
    
    rpm_limit: Optional[int] = Field(None, ge=0, description="RPM 限制")
    tpm_limit: Optional[int] = Field(None, ge=0, description="TPM 限制")
    description: Optional[str] = Field(None, max_length=500, description="描述")
    is_active: Optional[bool] = Field(None, description="是否启用")


class TenantRateLimitResponse(TenantRateLimitBase):
    """租户速率限制配置响应"""
    
    id: int
    tenant_id: int
    is_active: bool
    model_name: Optional[str] = Field(None, description="模型名称")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class EffectiveRateLimits(BaseModel):
    """有效速率限制响应"""
    
    rpm_limit: Optional[int] = Field(None, description="RPM 限制")
    tpm_limit: Optional[int] = Field(None, description="TPM 限制")
    source: str = Field(..., description="来源（tenant/model/none）")


__all__ = [
    "TenantRateLimitCreate",
    "TenantRateLimitUpdate",
    "TenantRateLimitResponse",
    "EffectiveRateLimits",
]
