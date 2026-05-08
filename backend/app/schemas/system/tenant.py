"""
企业相关 Schema / Tenant Schema

定义企业 API 的请求和响应数据结构
Defines tenant API request and response data structures.
"""

from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from app.core.base_schema import BaseSchema
from app.schemas.tenant.domain import TenantDomainSimpleResponse

_RETIRED_TENANT_INPUT_FIELDS = frozenset({"plan", "settings"})


def _reject_retired_tenant_input_fields(data: Any) -> Any:
    """中文: 企业写入只接受新契约字段，退役字段进入请求即拒绝。

    EN: Tenant writes accept only new-contract fields; retired fields are
    rejected on input.
    """
    if isinstance(data, dict):
        retired = _RETIRED_TENANT_INPUT_FIELDS & set(data.keys())
        if retired:
            fields = ", ".join(sorted(retired))
            raise ValueError(f"{fields} is retired; use plan_id or ConfigService")
    return data


class TenantPlanInfo(BaseSchema):
    """企业套餐信息（简略） / Tenant plan info (brief)."""

    id: int = Field(..., description="套餐 ID")
    code: str = Field(..., description="套餐代码")
    name: str = Field(..., description="套餐名称")


class TenantStorageStats(BaseSchema):
    """企业存储统计信息 / Tenant storage statistics."""

    used_bytes: int = Field(0, description="已使用存储空间（字节）")
    limit_bytes: int = Field(0, description="存储限制（字节），0 表示无限制")
    limit_gb: int = Field(0, description="存储限制（GB），0 表示无限制")
    usage_percent: float = Field(0.0, description="使用率百分比")
    file_count: int = Field(0, description="附件总数")
    unlimited: bool = Field(True, description="是否无限制")


class TenantResponse(BaseSchema):
    """企业信息响应 / Tenant info response."""

    id: int = Field(..., description="企业 ID")
    code: str = Field(..., description="企业编码")
    name: str = Field(..., description="企业名称")
    contact_name: str | None = Field(None, description="联系人姓名")
    contact_phone: str | None = Field(None, description="联系人电话")
    contact_email: str | None = Field(None, description="联系人邮箱")
    is_active: bool = Field(..., description="是否启用")
    # 套餐信息（新版） / Plan info (new)
    plan_id: int | None = Field(None, description="套餐 ID")
    plan_info: TenantPlanInfo | None = Field(None, description="套餐信息")
    quota: dict[str, Any] | None = Field(None, description="配额配置")
    expires_at: datetime | None = Field(None, description="到期时间")
    remark: str | None = Field(None, description="备注")
    # 域名信息 / Domains
    primary_domain: TenantDomainSimpleResponse | None = Field(
        None, description="主域名"
    )
    domains: list[TenantDomainSimpleResponse] = Field(
        default_factory=list, description="域名列表"
    )
    domain_count: int = Field(0, description="域名数量")
    # 存储配额信息 / Storage quota
    storage_stats: TenantStorageStats | None = Field(None, description="存储统计信息")
    # 时间字段 / Timestamps
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    @model_validator(mode="before")
    @classmethod
    def extract_tenant_info(cls, data: Any) -> Any:
        """从 ORM 关系中提取套餐和域名信息 / Extract plan and domain info from ORM relations."""
        # 如果是 ORM 对象，转换为字典 / If ORM object, convert to dict
        if hasattr(data, "__table__"):
            result = {
                "id": data.id,
                "code": data.code,
                "name": data.name,
                "contact_name": data.contact_name,
                "contact_phone": data.contact_phone,
                "contact_email": data.contact_email,
                "is_active": data.is_active,
                "plan_id": data.plan_id,
                "quota": data.quota,
                "expires_at": data.expires_at,
                "remark": data.remark,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }

            # 提取套餐信息 / Extract plan
            if hasattr(data, "tenant_plan") and data.tenant_plan is not None:
                plan = data.tenant_plan
                result["plan_info"] = {
                    "id": plan.id,
                    "code": plan.code,
                    "name": plan.name,
                }

            # 提取域名信息 / Extract domains
            if hasattr(data, "domains") and data.domains:
                domains_list = [
                    {
                        "id": d.id,
                        "domain": d.domain,
                        "domain_type": d.domain_type,
                        "is_primary": d.is_primary,
                        "is_verified": d.is_verified,
                        "ssl_status": d.ssl_status,
                    }
                    for d in data.domains
                    if not d.is_deleted
                ]
                result["domains"] = domains_list
                result["domain_count"] = len(domains_list)
                # 找到主域名 / Pick primary domain
                result["primary_domain"] = next(
                    (d for d in domains_list if d["is_primary"]), None
                )

            return result
        return data


class TenantCreateRequest(BaseSchema):
    """创建企业请求 / Create tenant request."""

    name: str = Field(..., min_length=1, max_length=100, description="企业名称")
    contact_name: str | None = Field(None, max_length=50, description="联系人姓名")
    contact_phone: str | None = Field(None, max_length=20, description="联系人电话")
    contact_email: str | None = Field(None, description="联系人邮箱")
    # 套餐 ID（新版）
    plan_id: int | None = Field(None, description="套餐 ID")
    quota: dict[str, Any] | None = Field(
        None, description="配额配置（可覆盖套餐默认值）"
    )
    expires_at: datetime | None = Field(None, description="到期时间")
    remark: str | None = Field(None, max_length=500, description="备注")
    # 企业超级管理员账号（必填） / Tenant super admin (required)
    admin_username: str = Field(
        ..., min_length=2, max_length=50, description="管理员用户名"
    )
    admin_email: str = Field(..., description="管理员邮箱")
    admin_password: str = Field(
        ..., min_length=6, max_length=100, description="管理员密码"
    )

    @model_validator(mode="before")
    @classmethod
    def reject_retired_fields(cls, data: Any) -> Any:
        return _reject_retired_tenant_input_fields(data)


class TenantUpdateRequest(BaseSchema):
    """更新企业请求 / Update tenant request."""

    name: str | None = Field(None, min_length=1, max_length=100, description="企业名称")
    contact_name: str | None = Field(None, max_length=50, description="联系人姓名")
    contact_phone: str | None = Field(None, max_length=20, description="联系人电话")
    contact_email: str | None = Field(None, description="联系人邮箱")
    # 套餐 ID（新版）
    plan_id: int | None = Field(None, description="套餐 ID")
    quota: dict[str, Any] | None = Field(
        None, description="配额配置（可覆盖套餐默认值）"
    )
    expires_at: datetime | None = Field(None, description="到期时间")
    remark: str | None = Field(None, max_length=500, description="备注")

    @model_validator(mode="before")
    @classmethod
    def reject_retired_fields(cls, data: Any) -> Any:
        return _reject_retired_tenant_input_fields(data)


class TenantStatusRequest(BaseSchema):
    """企业状态切换请求 / Tenant status toggle request."""

    is_active: bool = Field(..., description="是否启用")


class TenantImpersonateRequest(BaseSchema):
    """一键登录企业后台请求 / Impersonate tenant admin request."""

    role_id: int | None = Field(None, description="目标角色 ID（可选）")


class TenantImpersonateResponse(BaseSchema):
    """一键登录企业后台响应 / Impersonate tenant admin response."""

    impersonate_token: str = Field(
        ..., description="一键登录 Token（60秒有效，一次性）"
    )
    tenant_code: str = Field(..., description="企业编码")
    tenant_name: str = Field(..., description="企业名称")
    expires_in: int = Field(60, description="Token 有效期（秒）")


class TenantResetOwnerPasswordRequest(BaseSchema):
    """重置企业超级管理员密码请求 / Reset tenant super admin password request."""

    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


__all__ = [
    "TenantPlanInfo",
    "TenantStorageStats",
    "TenantResponse",
    "TenantCreateRequest",
    "TenantUpdateRequest",
    "TenantStatusRequest",
    "TenantImpersonateRequest",
    "TenantImpersonateResponse",
    "TenantResetOwnerPasswordRequest",
]
