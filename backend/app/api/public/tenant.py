"""
租户公开 API / Tenant Public API

提供登录前可访问的租户公开信息接口
Provides pre-login accessible tenant public information endpoints
"""

from fastapi import APIRouter, HTTPException, Request, status

from app.configs.service import ConfigService
from app.core.config import settings
from app.core.deps import DbSession
from app.core.i18n import _
from app.core.response import success
from app.middleware.tenant import get_tenant_context
from app.rbac.decorators import public
from app.schemas.public import DomainVerificationInfo, TenantPublicConfig
from app.schemas.public.platform import StoragePublicConfig

router = APIRouter(prefix="/tenant", tags=["租户公开接口 / Tenant Public API"])


@router.get("/config", summary="获取当前租户公开配置 / Get current tenant public config")
@public
async def get_tenant_public_config(request: Request, db: DbSession):
    """
    获取当前租户的公开配置
    Get current tenant's public configuration

    根据请求的域名自动识别租户，返回该租户的公开配置信息。
    Automatically identifies tenant by request domain and returns public config.

    **域名识别规则 / Domain identification rules:**
    - 子域名模式 / Subdomain mode: `{tenant_code}.app.novusai.com`
    - 自定义域名模式 / Custom domain mode: 用户绑定的独立域名 / User-bound independent domain

    **返回内容 / Response content:**
    - 租户基本信息（名称、logo 等） / Tenant basic info (name, logo, etc.)
    - 登录配置（验证码、登录方式等） / Login config (captcha, login methods, etc.)
    - 品牌设置（Logo、登录页定制等） / Brand settings (logo, login page customization, etc.)

    此接口无需认证，用于前端登录页面获取租户信息。
    This endpoint requires no authentication, used by frontend login page to get tenant info.
    """
    tenant_ctx = get_tenant_context(request)

    tenant = None
    if tenant_ctx and tenant_ctx.is_resolved:
        tenant = tenant_ctx.tenant

    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_("tenant.not_found"),
        )

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
    storage_config = await config_service.get_tenant_configs_by_group(
        tenant_id=tenant.id,
        group_code="tenant_storage",
    )
    configs = {**general_config, **appearance_config, **feature_config, **storage_config}

    # 加载平台品牌配置（用于租户未设置时的 fallback） / Load platform brand config (fallback when tenant not configured)
    platform_general_config = await config_service.get_platform_configs_by_group(
        group_code="platform_general",
    )

    # 确定存储配置：如果租户使用平台托管存储，则使用平台的配置 / Determine storage config: use platform config if tenant uses platform-managed storage
    platform_storage_config = await config_service.get_platform_configs_by_group(
        group_code="platform_storage",
    )

    if configs.get("tenant_storage_mode") == "custom":
        storage_base_url = configs.get("tenant_storage_base_url")
        # 租户自定义 allowed_extensions，如果未设置则使用平台配置 / Tenant custom allowed_extensions, falls back to platform config
        allowed_extensions = configs.get("tenant_storage_allowed_extensions") or platform_storage_config.get("platform_storage_allowed_extensions")
    else:
        # 平台托管模式，全部使用平台配置 / Platform managed mode, use all platform configs
        storage_base_url = platform_storage_config.get("platform_storage_base_url")
        allowed_extensions = platform_storage_config.get("platform_storage_allowed_extensions")

    # chunk_size 和 max_file_size 始终使用平台配置 / chunk_size and max_file_size always use platform config
    # driver: 自定义模式使用租户配置，平台托管模式使用平台配置 / driver: custom mode uses tenant config, platform managed mode uses platform config
    if configs.get("tenant_storage_mode") == "custom":
        storage_driver = configs.get("tenant_storage_driver")
    else:
        storage_driver = platform_storage_config.get("platform_storage_driver")

    storage_config_obj = StoragePublicConfig(
        driver=storage_driver,
        base_url=storage_base_url,
        chunk_size_mb=platform_storage_config.get("platform_storage_chunk_size_mb"),
        max_file_size_mb=platform_storage_config.get("platform_storage_max_file_size_mb"),
        allowed_extensions=allowed_extensions,
    )

    scheme = request.url.scheme
    subdomain_url = f"{scheme}://{tenant.code}{settings.TENANT_DOMAIN_SUFFIX}"

    # 品牌 fallback：租户未设置 → 平台默认 / Brand fallback: tenant not set → platform default
    logo_url = configs.get("tenant_logo") or platform_general_config.get("site_logo") or ""
    favicon_url = configs.get("tenant_favicon") or platform_general_config.get("site_favicon") or ""
    login_title = configs.get("tenant_login_title") or platform_general_config.get("site_name") or ""
    login_subtitle = configs.get("tenant_login_subtitle") or platform_general_config.get("site_description") or ""
    footer_copyright = configs.get("tenant_footer_copyright") or platform_general_config.get("site_copyright") or ""
    login_bg = configs.get("tenant_login_bg") or ""

    return success(
        data=TenantPublicConfig(
            tenant_id=tenant.id,
            tenant_code=tenant.code,
            tenant_name=tenant.name,
            logo_url=logo_url,
            favicon_url=favicon_url,
            login_bg=login_bg,
            login_title=login_title,
            login_subtitle=login_subtitle,
            footer_copyright=footer_copyright,
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
            privacy_policy_url=configs.get("user_privacy_policy_url") or None,
            terms_url=configs.get("user_terms_url") or None,
            subdomain=tenant.code,
            subdomain_url=subdomain_url,
            storage=storage_config_obj,
        ),
        message=_("common.success"),
    )


@router.get("/domain-verification", summary="获取域名验证信息 / Get domain verification info")
@public
async def get_domain_verification_info(
    request: Request,
    domain: str,
):
    """
    获取域名验证信息
    Get domain verification info

    用于指导用户配置 DNS 记录，将自定义域名解析到租户子域名。
    Used to guide users in configuring DNS records to resolve custom domains to tenant subdomains.

    **参数 / Parameters:**
    - `domain`: 待绑定的域名 / Domain to bind (e.g. `app.example.com`)

    **返回 / Returns:**
    - CNAME 解析目标 / CNAME resolution target
    - TXT 验证记录（可选） / TXT verification record (optional)
    - 配置说明 / Configuration instructions

    此接口无需认证。 / This endpoint requires no authentication.
    """
    tenant_ctx = get_tenant_context(request)

    if not tenant_ctx or not tenant_ctx.is_resolved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_("tenant.not_found"),
        )

    tenant = tenant_ctx.tenant

    # CNAME 目标 / CNAME target
    cname_target = f"{tenant.code}{settings.TENANT_DOMAIN_SUFFIX}"

    # TXT 验证记录 / TXT verification record
    txt_name = f"{settings.DOMAIN_VERIFICATION_PREFIX}.{domain}"
    txt_value = f"novusai-verification={tenant.code}"

    # 配置说明 / Configuration instructions
    instructions = (
        f"{_('domain.instructions_header')}\n\n"
        f"1. {_('domain.cname_record_required')}:\n"
        f"   - {_('domain.host_record')}: @ {_('domain.or_subdomain')}\n"
        f"   - {_('domain.record_type')}: CNAME\n"
        f"   - {_('domain.record_value')}: {cname_target}\n\n"
        f"2. {_('domain.txt_record_verify')}:\n"
        f"   - {_('domain.host_record')}: {settings.DOMAIN_VERIFICATION_PREFIX}\n"
        f"   - {_('domain.record_type')}: TXT\n"
        f"   - {_('domain.record_value')}: {txt_value}\n\n"
        f"{_('domain.dns_propagation_note')}\n"
    )

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
