"""
租户公开 API

提供登录前可访问的租户公开信息接口
"""

from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import settings
from app.core.deps import DbSession
from app.core.i18n import _
from app.core.response import success
from app.middleware.tenant import get_tenant_context
from app.configs.service import ConfigService
from app.schemas.public import TenantPublicConfig, DomainVerificationInfo
from app.rbac.decorators import public


router = APIRouter(prefix="/tenant", tags=["租户公开接口"])


@router.get("/config", summary="获取当前租户公开配置")
@public
async def get_tenant_public_config(request: Request, db: DbSession):
    """
    获取当前租户的公开配置
    
    根据请求的域名自动识别租户，返回该租户的公开配置信息。
    
    **域名识别规则:**
    - 子域名模式: `{tenant_code}.app.novusai.com`
    - 自定义域名模式: 用户绑定的独立域名
    
    **返回内容:**
    - 租户基本信息（名称、logo 等）
    - 登录配置（验证码、登录方式等）
    - 品牌设置（主题色等）
    
    此接口无需认证，用于前端登录页面获取租户信息。
    """
    tenant_ctx = get_tenant_context(request)
    
    if not tenant_ctx or not tenant_ctx.is_resolved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_("tenant.not_found"),
        )
    
    tenant = tenant_ctx.tenant
    
    config_service = ConfigService(db)
    general_config = await config_service.get_tenant_configs_by_group(
        tenant_id=tenant.id,
        group_code="tenant_general",
    )
    appearance_config = await config_service.get_tenant_configs_by_group(
        tenant_id=tenant.id,
        group_code="tenant_appearance",
    )
    feature_config = await config_service.get_tenant_configs_by_group(
        tenant_id=tenant.id,
        group_code="tenant_features",
    )
    configs = {**general_config, **appearance_config, **feature_config}

    subdomain_url = f"https://{tenant.code}{settings.TENANT_DOMAIN_SUFFIX}"
    
    return success(
        data=TenantPublicConfig(
            tenant_id=tenant.id,
            tenant_code=tenant.code,
            tenant_name=tenant.name,
            logo_url=configs.get("tenant_logo"),
            favicon_url=configs.get("tenant_favicon"),
            theme_color=configs.get("tenant_primary_color"),
            login_bg=configs.get("tenant_login_bg"),
            primary_color=configs.get("tenant_primary_color"),
            accent_color=configs.get("tenant_accent_color"),
            login_title=configs.get("tenant_login_title"),
            login_subtitle=configs.get("tenant_login_subtitle"),
            footer_copyright=configs.get("tenant_footer_copyright"),
            captcha_enabled=configs.get("tenant_captcha_enabled", False),
            captcha_provider=configs.get("tenant_captcha_provider"),
            captcha_difficulty=configs.get("tenant_captcha_difficulty"),
            captcha_enable_threshold=configs.get("tenant_captcha_enable_threshold"),
            login_methods=configs.get("tenant_login_methods", ["password"]),
            login_max_attempts=configs.get("tenant_login_max_attempts"),
            login_lockout_minutes=configs.get("tenant_login_lockout_minutes"),
            password_min_length=configs.get("tenant_password_min_length"),
            password_complexity=configs.get("tenant_password_complexity"),
            session_timeout=configs.get("tenant_session_timeout"),
            allow_registration=configs.get("tenant_allow_registration"),
            registration_approval=configs.get("tenant_registration_approval"),
            allow_profile_edit=configs.get("tenant_allow_profile_edit"),
            email_notification=configs.get("tenant_email_notification"),
            sms_notification=configs.get("tenant_sms_notification"),
            api_access=configs.get("tenant_api_access"),
            file_upload=configs.get("tenant_file_upload"),
            subdomain=tenant.code,
            subdomain_url=subdomain_url,
        ),
        message=_("common.success"),
    )


@router.get("/domain-verification", summary="获取域名验证信息")
@public
async def get_domain_verification_info(
    request: Request,
    domain: str,
):
    """
    获取域名验证信息
    
    用于指导用户配置 DNS 记录，将自定义域名解析到租户子域名。
    
    **参数:**
    - `domain`: 待绑定的域名（如 `app.example.com`）
    
    **返回:**
    - CNAME 解析目标
    - TXT 验证记录（可选）
    - 配置说明
    
    此接口无需认证。
    """
    tenant_ctx = get_tenant_context(request)
    
    if not tenant_ctx or not tenant_ctx.is_resolved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_("tenant.not_found"),
        )
    
    tenant = tenant_ctx.tenant
    
    # CNAME 目标
    cname_target = f"{tenant.code}{settings.TENANT_DOMAIN_SUFFIX}"
    
    # TXT 验证记录
    txt_name = f"{settings.DOMAIN_VERIFICATION_PREFIX}.{domain}"
    txt_value = f"novusai-verification={tenant.code}"
    
    # 配置说明
    instructions = f"""请在您的 DNS 服务商处添加以下记录：

1. CNAME 记录（必需）:
   - 主机记录: @ 或您的子域名
   - 记录类型: CNAME
   - 记录值: {cname_target}

2. TXT 记录（用于验证所有权）:
   - 主机记录: {settings.DOMAIN_VERIFICATION_PREFIX}
   - 记录类型: TXT
   - 记录值: {txt_value}

DNS 记录生效可能需要几分钟到几小时，请耐心等待。
"""
    
    return success(
        data=DomainVerificationInfo(
            domain=domain,
            cname_target=cname_target,
            cname_name="@",
            txt_name=txt_name,
            txt_value=txt_value,
            is_verified=False,
            instructions=instructions,
        ),
        message=_("common.success"),
    )


__all__ = ["router"]
