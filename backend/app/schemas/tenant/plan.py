"""
企业套餐相关 Schema / Tenant Plan Schema

定义套餐管理 API 的请求和响应数据结构
Defines plan management API request and response data structures.
"""

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field, field_validator

from app.core.base_schema import BaseSchema
from app.core.i18n import _
from app.enums import BillingCycle

# ==================== 配额结构 / Quota Structure ====================


class QuotaSchema(BaseSchema):
    """配额结构定义 / Quota structure definition"""

    storage_limit_gb: int | None = Field(None, ge=0, description="存储限制(GB)")
    max_users: int | None = Field(None, ge=0, description="最大用户数")
    max_admins: int | None = Field(None, ge=0, description="最大管理员数")
    max_custom_domains: int | None = Field(None, ge=0, description="最大自定义域名数")
    allow_custom_domain: bool | None = Field(None, description="是否允许自定义域名")
    api_calls_per_month: int | None = Field(None, ge=0, description="每月API调用次数")
    max_file_size_mb: int | None = Field(None, ge=0, description="最大文件大小(MB)")

    def to_dict(self) -> dict[str, Any]:
        """转换为字典，仅包含非空值 / Convert to dict, non-null values only"""
        return {k: v for k, v in self.model_dump().items() if v is not None}


class FeaturesSchema(BaseSchema):
    """特性标记结构定义 / Features structure definition"""

    ai_enabled: bool | None = Field(None, description="是否启用AI功能")
    advanced_analytics: bool | None = Field(None, description="是否启用高级分析")
    white_label: bool | None = Field(None, description="是否支持白标")
    priority_support: bool | None = Field(None, description="是否优先支持")
    storage_billing_enabled: bool | None = Field(
        None, description="是否启用对象存储账单对账收费"
    )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典，仅包含非空值 / Convert to dict, non-null values only"""
        return {k: v for k, v in self.model_dump().items() if v is not None}


# ==================== 响应 Schema / Response Schemas ====================


class TenantPlanResponse(BaseSchema):
    """套餐响应 / Plan response"""

    id: int = Field(..., description="套餐 ID")
    code: str = Field(..., description="套餐代码")
    name: str = Field(..., description="套餐名称")
    description: str | None = Field(None, description="套餐描述")
    price: Decimal | None = Field(None, description="价格")
    billing_cycle: str = Field(..., description="计费周期")
    is_active: bool = Field(..., description="是否启用")
    sort_order: int = Field(0, description="排序顺序")
    quota: dict | None = Field(None, description="配额配置")
    features: dict | None = Field(None, description="特性标记")
    tenants_count: int = Field(0, description="使用该套餐的企业数")
    permissions_count: int = Field(0, description="关联权限数")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    @classmethod
    def from_model(cls, plan) -> "TenantPlanResponse":
        """从模型创建响应 / Build response from model"""
        return cls(
            id=plan.id,
            code=plan.code,
            name=plan.name,
            description=plan.description,
            price=plan.price,
            billing_cycle=plan.billing_cycle,
            is_active=plan.is_active,
            sort_order=plan.sort_order,
            quota=plan.quota,
            features=plan.features,
            tenants_count=plan.tenants_count,
            permissions_count=plan.permissions_count,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )


class PermissionSimpleResponse(BaseSchema):
    """权限简要响应（用于套餐详情） / Permission simple response (for plan detail)"""

    id: int = Field(..., description="权限 ID")
    code: str = Field(..., description="权限代码")
    name: str = Field(..., description="权限名称")
    type: str = Field(..., description="权限类型")
    resource: str = Field(..., description="资源标识")


class PermissionTreeSimpleResponse(BaseSchema):
    """权限树简要响应（用于套餐权限分配） / Permission tree simple response (for plan permission assignment)"""

    id: int = Field(..., description="权限 ID")
    code: str = Field(..., description="权限代码")
    name: str = Field(..., description="权限名称")
    type: str = Field(..., description="权限类型")
    resource: str | None = Field(None, description="资源标识")
    parent_id: int | None = Field(None, description="父级权限 ID")
    sort_order: int = Field(0, description="排序")
    children: list["PermissionTreeSimpleResponse"] = Field(
        default_factory=list, description="子权限"
    )


# 解决循环引用 / Resolve forward references
PermissionTreeSimpleResponse.model_rebuild()


class TenantPlanDetailResponse(TenantPlanResponse):
    """套餐详情响应（含权限列表） / Plan detail response (with permissions list)"""

    permissions: list[PermissionSimpleResponse] = Field(
        default_factory=list, description="关联权限列表"
    )

    @classmethod
    def from_model(
        cls,
        plan,
        translate_fn: Callable[[str], str] | None = None,
    ) -> "TenantPlanDetailResponse":
        """从模型创建详情响应 / Build detail response from model.

        Args:
            plan: TenantPlan ORM 对象 / TenantPlan ORM instance
            translate_fn: 可选的权限名称翻译函数 / Optional permission name translator
        """
        active_permissions = [p for p in plan.permissions if p.is_enabled]
        return cls(
            id=plan.id,
            code=plan.code,
            name=plan.name,
            description=plan.description,
            price=plan.price,
            billing_cycle=plan.billing_cycle,
            is_active=plan.is_active,
            sort_order=plan.sort_order,
            quota=plan.quota,
            features=plan.features,
            tenants_count=plan.tenants_count,
            permissions_count=len(active_permissions),
            created_at=plan.created_at,
            updated_at=plan.updated_at,
            permissions=[
                PermissionSimpleResponse(
                    id=p.id,
                    code=p.code,
                    name=translate_fn(p.name) if translate_fn else p.name,
                    type=p.type,
                    resource=p.resource,
                )
                for p in active_permissions
            ],
        )


# ==================== 请求 Schema ====================


class TenantPlanCreateRequest(BaseSchema):
    """创建套餐请求 / Create plan request"""

    name: str = Field(..., min_length=1, max_length=100, description="套餐名称")
    description: str | None = Field(None, max_length=500, description="套餐描述")
    price: Decimal | None = Field(None, ge=0, description="价格")
    billing_cycle: str = Field(
        default=BillingCycle.MONTHLY.value, description="计费周期"
    )
    is_active: bool = Field(True, description="是否启用")
    sort_order: int = Field(0, ge=0, description="排序顺序")
    quota: QuotaSchema | None = Field(None, description="配额配置")
    features: FeaturesSchema | None = Field(None, description="特性标记")

    @field_validator("billing_cycle")
    @classmethod
    def validate_billing_cycle(cls, v: str) -> str:
        """验证计费周期 / Validate billing cycle"""
        if v not in BillingCycle.values():
            raise ValueError(_("tenant_plan.invalid_billing_cycle"))
        return v


class TenantPlanUpdateRequest(BaseSchema):
    """更新套餐请求 / Update plan request"""

    name: str | None = Field(None, min_length=1, max_length=100, description="套餐名称")
    description: str | None = Field(None, max_length=500, description="套餐描述")
    price: Decimal | None = Field(None, ge=0, description="价格")
    billing_cycle: str | None = Field(None, description="计费周期")
    is_active: bool | None = Field(None, description="是否启用")
    sort_order: int | None = Field(None, ge=0, description="排序顺序")
    quota: QuotaSchema | None = Field(None, description="配额配置")
    features: FeaturesSchema | None = Field(None, description="特性标记")

    @field_validator("billing_cycle")
    @classmethod
    def validate_billing_cycle(cls, v: str | None) -> str | None:
        """验证计费周期 / Validate billing cycle"""
        if v is not None and v not in BillingCycle.values():
            raise ValueError(_("tenant_plan.invalid_billing_cycle"))
        return v


class TenantPlanPermissionsRequest(BaseSchema):
    """设置套餐权限请求 / Set plan permissions request"""

    permission_ids: list[int] = Field(
        default_factory=list, description="权限ID列表（仅支持菜单类型权限）"
    )


__all__ = [
    "QuotaSchema",
    "FeaturesSchema",
    "TenantPlanResponse",
    "TenantPlanDetailResponse",
    "PermissionSimpleResponse",
    "PermissionTreeSimpleResponse",
    "TenantPlanCreateRequest",
    "TenantPlanUpdateRequest",
    "TenantPlanPermissionsRequest",
]
