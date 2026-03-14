"""
企业 AI 配额配置 Schema / Tenant AI Quota Schema
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TenantQuotaBase(BaseModel):
    """企业配额配置基础 Schema / Tenant quota base schema"""

    model_id: int | None = Field(None, description="模型 ID（None 表示全局配额）")
    period: str = Field(default="monthly", description="周期（daily/monthly）")
    limit: int = Field(..., gt=0, description="配额限制（Token 数量）")
    quota_type: str = Field(default="soft", description="配额类型（soft/hard）")
    warning_threshold: int | None = Field(default=80, ge=0, le=100, description="预警阈值（百分比）")
    description: str | None = Field(None, max_length=500, description="描述")


class TenantQuotaCreate(TenantQuotaBase):
    """创建企业配额配置 / Create tenant quota"""

    pass


class AdminTenantQuotaCreate(TenantQuotaBase):
    """平台管理员创建企业配额（含 tenant_id） / Admin create tenant quota (with tenant_id)"""

    tenant_id: int = Field(..., description="企业 ID")


class TenantQuotaUpdate(BaseModel):
    """更新企业配额配置 / Update tenant quota"""

    limit: int | None = Field(None, gt=0, description="配额限制")
    quota_type: str | None = Field(None, description="配额类型")
    warning_threshold: int | None = Field(None, ge=0, le=100, description="预警阈值")
    description: str | None = Field(None, max_length=500, description="描述")
    is_active: bool | None = Field(None, description="是否启用")


class TenantQuotaResponse(TenantQuotaBase):
    """企业配额配置响应 / Tenant quota response"""

    id: int
    tenant_id: int
    is_active: bool
    tenant_name: str | None = Field(None, description="企业名称")
    model_name: str | None = Field(None, description="模型名称")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_model(cls, obj) -> TenantQuotaResponse:
        """从 ORM 对象构建响应，自动提取关联 model_name / Build response from ORM, extract model_name"""
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
            period=obj.period,
            limit=obj.limit,
            quota_type=obj.quota_type,
            warning_threshold=obj.warning_threshold,
            is_active=obj.is_active,
            description=obj.description,
            model_name=model_name,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class TenantQuotaWithUsage(BaseModel):
    """企业配额配置及使用量响应 / Tenant quota with usage response"""

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
