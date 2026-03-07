from pydantic import Field

from app.core.base_schema import BaseSchema


class StoragePublicConfig(BaseSchema):
    """存储公开配置"""
    driver: str | None = Field(None, description="存储引擎")
    base_url: str | None = Field(None, description="文件访问基础 URL")
    chunk_size_mb: int | None = Field(None, description="默认分片大小（MB）")
    max_file_size_mb: int | None = Field(None, description="单文件大小限制（MB）")
    allowed_extensions: str | None = Field(None, description="允许的文件扩展名")


class PlatformPublicConfig(BaseSchema):
    site_name: str = Field(..., description="站点名称")
    site_description: str | None = Field(None, description="站点描述")
    site_logo: str | None = Field(None, description="站点 Logo")
    site_favicon: str | None = Field(None, description="站点 Favicon")
    site_copyright: str | None = Field(None, description="版权信息")
    site_icp: str | None = Field(None, description="ICP 备案号")
    tenant_domain_suffix: str | None = Field(None, description="租户默认域名后缀")
    domain_verification_prefix: str | None = Field(None, description="域名验证 DNS 前缀")
    maintenance_mode: bool | None = Field(None, description="维护模式开关")
    maintenance_message: str | None = Field(None, description="维护提示信息")
    login_captcha_enabled: bool | None = Field(None, description="登录验证码开关")
    captcha_provider: str | None = Field(None, description="验证码驱动")
    captcha_difficulty: str | None = Field(None, description="验证码难度")
    captcha_enable_threshold_admin: int | None = Field(None, description="验证码启用阈值")
    login_max_attempts: int | None = Field(None, description="登录失败锁定次数")
    login_lockout_minutes: int | None = Field(None, description="账户锁定时长")
    password_min_length: int | None = Field(None, description="密码最小长度")
    password_complexity: str | None = Field(None, description="密码复杂度")
    password_expiry_days: int | None = Field(None, description="密码过期天数")
    session_timeout_minutes: int | None = Field(None, description="会话超时时间")
    session_max_devices: int | None = Field(None, description="最大登录设备数")

    # 域名检测
    platform_domains: list[str] = Field(default_factory=list, description="平台管理端域名列表")

    # 存储配置
    storage: StoragePublicConfig | None = Field(None, description="存储配置")


__all__ = ["PlatformPublicConfig", "StoragePublicConfig"]
