"""
租户域名 Schema

定义域名管理相关的请求和响应数据结构
"""

from datetime import datetime

from pydantic import Field, field_validator

from app.core.base_schema import BaseSchema
from app.core.i18n import _


class TenantDomainSimpleResponse(BaseSchema):
    """域名简略响应（用于租户响应嵌套）"""

    id: int = Field(..., description="域名 ID")
    domain: str = Field(..., description="域名")
    domain_type: str = Field("custom", description="域名类型: default/custom")
    is_primary: bool = Field(..., description="是否主域名")
    is_verified: bool = Field(..., description="是否已验证")
    ssl_status: str = Field(..., description="SSL 状态")


class TenantDomainVerificationInfo(BaseSchema):
    """域名验证 DNS 记录信息"""

    dns_type: str = Field("TXT", description="DNS 记录类型")
    dns_name: str = Field(..., description="DNS 记录名称")
    dns_value: str = Field(..., description="DNS 记录值")


class TenantDomainResponse(BaseSchema):
    """租户域名响应"""

    id: int = Field(..., description="域名 ID")
    tenant_id: int = Field(..., description="租户 ID")
    domain: str = Field(..., description="域名")
    domain_type: str = Field("custom", description="域名类型: default/custom")
    is_verified: bool = Field(..., description="是否已验证")
    verified_at: datetime | None = Field(None, description="验证时间")
    is_primary: bool = Field(..., description="是否主域名")
    ssl_status: str = Field(..., description="SSL 状态")
    ssl_expires_at: datetime | None = Field(None, description="SSL 到期时间")
    verification_token: str | None = Field(None, description="验证 Token")
    verification_info: TenantDomainVerificationInfo | None = Field(None, description="DNS 验证记录信息")
    remark: str | None = Field(None, description="备注")
    cname_target: str | None = Field(None, description="CNAME 解析目标")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class TenantDomainCreateRequest(BaseSchema):
    """创建域名请求"""

    domain: str = Field(
        ...,
        min_length=4,
        max_length=255,
        description="域名（如 app.example.com）",
    )
    is_primary: bool = Field(False, description="是否设为主域名")
    remark: str | None = Field(None, max_length=500, description="备注")

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """验证域名格式"""
        import re

        v = v.lower().strip()

        # 基本域名格式验证
        pattern = r"^([a-z0-9]([a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError(_("tenant_domain.invalid_format"))

        # 禁止使用平台域名
        from app.core.config import settings
        suffix = settings.TENANT_DOMAIN_SUFFIX.lstrip(".")
        if v.endswith(suffix):
            raise ValueError(_("tenant_domain.platform_suffix_forbidden", suffix=suffix))

        return v


class TenantDomainUpdateRequest(BaseSchema):
    """更新域名请求"""

    is_primary: bool | None = Field(None, description="是否设为主域名")
    remark: str | None = Field(None, max_length=500, description="备注")


class TenantDomainVerifyRequest(BaseSchema):
    """域名验证请求"""

    domain_id: int = Field(..., description="域名 ID")


class TenantSettingsResponse(BaseSchema):
    """租户设置响应"""

    tenant_id: int = Field(..., description="租户 ID")
    tenant_code: str = Field(..., description="租户代码")
    tenant_name: str = Field(..., description="租户名称")

    # 品牌设置
    logo_url: str | None = Field(None, description="Logo URL")
    favicon_url: str | None = Field(None, description="Favicon URL")
    theme_color: str | None = Field(None, description="主题色")

    # 登录设置
    captcha_enabled: bool = Field(False, description="是否启用验证码")
    login_methods: list[str] = Field(
        default_factory=lambda: ["password"],
        description="支持的登录方式",
    )

    # 域名信息
    subdomain: str = Field(..., description="租户子域名")
    subdomain_url: str = Field(..., description="子域名完整 URL")
    max_custom_domains: int = Field(0, description="最大自定义域名数量")
    custom_domain_count: int = Field(0, description="已绑定自定义域名数量")


class TenantSettingsUpdateRequest(BaseSchema):
    """更新租户设置请求"""

    # 品牌设置
    logo_url: str | None = Field(None, description="Logo URL")
    favicon_url: str | None = Field(None, description="Favicon URL")
    theme_color: str | None = Field(None, description="主题色（十六进制颜色码）")

    # 登录设置
    captcha_enabled: bool | None = Field(None, description="是否启用验证码")
    login_methods: list[str] | None = Field(None, description="支持的登录方式")

    @field_validator("theme_color")
    @classmethod
    def validate_theme_color(cls, v: str | None) -> str | None:
        """验证主题色格式"""
        if v is None:
            return v

        import re
        v = v.strip()
        if not re.match(r"^#[0-9a-fA-F]{6}$", v):
            raise ValueError(_("tenant_settings.invalid_theme_color"))

        return v.upper()

    @field_validator("login_methods")
    @classmethod
    def validate_login_methods(cls, v: list[str] | None) -> list[str] | None:
        """验证登录方式"""
        if v is None:
            return v

        allowed = {"password", "sms", "email", "wechat", "dingtalk", "oauth2"}
        for method in v:
            if method not in allowed:
                raise ValueError(_("tenant_settings.unsupported_login_method", method=method))

        if not v:
            raise ValueError(_("tenant_settings.at_least_one_login_method"))

        return v


__all__ = [
    "TenantDomainSimpleResponse",
    "TenantDomainVerificationInfo",
    "TenantDomainResponse",
    "TenantDomainCreateRequest",
    "TenantDomainUpdateRequest",
    "TenantDomainVerifyRequest",
    "TenantSettingsResponse",
    "TenantSettingsUpdateRequest",
]
