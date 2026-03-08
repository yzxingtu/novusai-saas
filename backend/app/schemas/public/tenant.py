"""
租户公开配置 Schema

定义登录前可获取的租户公开信息
"""

from pydantic import Field

from app.core.base_schema import BaseSchema
from app.schemas.public.platform import StoragePublicConfig


class TenantPublicConfig(BaseSchema):
    """
    租户公开配置

    登录页面可获取的租户信息（无需认证）
    """

    # 基本信息
    tenant_id: int = Field(..., description="租户 ID")
    tenant_code: str = Field(..., description="租户代码")
    tenant_name: str = Field(..., description="租户名称")

    # 品牌设置
    logo_url: str | None = Field(None, description="Logo URL")
    favicon_url: str | None = Field(None, description="Favicon URL")
    login_bg: str | None = Field(None, description="登录页背景图")
    login_title: str | None = Field(None, description="登录页标题")
    login_subtitle: str | None = Field(None, description="登录页副标题")
    footer_copyright: str | None = Field(None, description="页脚版权")

    # 登录设置
    captcha_enabled: bool = Field(False, description="是否启用验证码")
    captcha_provider: str | None = Field(None, description="验证码驱动")
    captcha_difficulty: str | None = Field(None, description="验证码难度")
    captcha_enable_threshold: int | None = Field(None, description="验证码启用阈值")
    login_methods: list[str] = Field(
        default_factory=lambda: ["password"],
        description="支持的登录方式",
    )
    login_max_attempts: int | None = Field(None, description="登录失败锁定次数")
    login_lockout_minutes: int | None = Field(None, description="登录锁定时长（分钟）")
    password_min_length: int | None = Field(None, description="密码最小长度")
    password_complexity: str | None = Field(None, description="密码复杂度")
    session_timeout: int | None = Field(None, description="会话超时时间（分钟）")

    # 功能开关
    allow_registration: bool | None = Field(None, description="允许用户注册")
    registration_approval: bool | None = Field(None, description="注册需审批")
    allow_profile_edit: bool | None = Field(None, description="允许修改资料")
    email_notification: bool | None = Field(None, description="启用邮件通知")
    sms_notification: bool | None = Field(None, description="启用短信通知")
    api_access: bool | None = Field(None, description="启用 API 访问")
    file_upload: bool | None = Field(None, description="启用文件上传")

    # 注册页链接
    privacy_policy_url: str | None = Field(None, description="隐私政策链接")
    terms_url: str | None = Field(None, description="服务条款链接")

    # 域名信息
    subdomain: str = Field(..., description="租户子域名")
    subdomain_url: str = Field(..., description="子域名完整 URL")

    # 存储配置
    storage: StoragePublicConfig | None = Field(None, description="存储配置")


class DomainVerificationInfo(BaseSchema):
    """
    域名验证信息

    用于指导用户配置 DNS 记录
    """

    # 要验证的域名
    domain: str = Field(..., description="待验证域名")

    # CNAME 配置
    cname_target: str = Field(..., description="CNAME 解析目标")
    cname_name: str = Field(
        "@",
        description="CNAME 记录名称（通常为 @ 或子域名）",
    )

    # TXT 验证记录（可选，用于验证域名所有权）
    txt_name: str | None = Field(None, description="TXT 记录名称")
    txt_value: str | None = Field(None, description="TXT 记录值")

    # 验证状态
    is_verified: bool = Field(False, description="是否已验证")

    # 配置说明
    instructions: str = Field(
        "",
        description="配置说明",
    )


__all__ = [
    "TenantPublicConfig",
    "DomainVerificationInfo",
]
