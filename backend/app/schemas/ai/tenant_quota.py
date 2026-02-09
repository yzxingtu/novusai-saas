"""
租户 AI 配额配置 Schema
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TenantQuotaBase(BaseModel):
    """租户配额配置基础 Schema"""
    
    model_id: Optional[int] = Field(None, description="模型 ID（None 表示全局配额）")
    period: str = Field(default="monthly", description="周期（daily/monthly）")
    limit: int = Field(..., gt=0, description="配额限制（Token 数量）")
    quota_type: str = Field(default="soft", description="配额类型（soft/hard）")
    warning_threshold: Optional[int] = Field(default=80, ge=0, le=100, description="预警阈值（百分比）")
    description: Optional[str] = Field(None, max_length=500, description="描述")


class TenantQuotaCreate(TenantQuotaBase):
    """创建租户配额配置"""
    
    pass


class AdminTenantQuotaCreate(TenantQuotaBase):
    """平台管理员创建租户配额（含 tenant_id）"""
    
    tenant_id: int = Field(..., description="租户 ID")


class TenantQuotaUpdate(BaseModel):
    """更新租户配额配置"""
    
    limit: Optional[int] = Field(None, gt=0, description="配额限制")
    quota_type: Optional[str] = Field(None, description="配额类型")
    warning_threshold: Optional[int] = Field(None, ge=0, le=100, description="预警阈值")
    description: Optional[str] = Field(None, max_length=500, description="描述")
    is_active: Optional[bool] = Field(None, description="是否启用")


class TenantQuotaResponse(TenantQuotaBase):
    """租户配额配置响应"""
    
    id: int
    tenant_id: int
    is_active: bool
    tenant_name: Optional[str] = Field(None, description="租户名称")
    model_name: Optional[str] = Field(None, description="模型名称")
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class TenantQuotaWithUsage(BaseModel):
    """租户配额配置及使用量响应"""
    
    quota: TenantQuotaResponse
    usage: int = Field(..., description="已使用 Token 数")
    limit: int = Field(..., description="配额限制")
    usage_percent: float = Field(..., description="使用百分比")
    is_warning: bool = Field(..., description="是否达到预警阈值")
    is_exceeded: bool = Field(..., description="是否超出配额")
    remaining: int = Field(..., description="剩余配额")


__all__ = [
    "TenantQuotaCreate",
    "AdminTenantQuotaCreate",
    "TenantQuotaUpdate",
    "TenantQuotaResponse",
    "TenantQuotaWithUsage",
]
