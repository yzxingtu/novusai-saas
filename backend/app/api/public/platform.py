from fastapi import APIRouter

from app.configs.service import ConfigService
from app.captcha.runtime import resolve_public_captcha_plugin_bundle
from app.core.config import settings
from app.core.deps import DbSession
from app.core.i18n import _
from app.core.response import success
from app.rbac.decorators import public
from app.schemas.public import PlatformPublicConfig
from app.schemas.public.platform import RuntimeLimitsPublicConfig, StoragePublicConfig
from app.services.ai.page_context_limits import get_page_context_max_bytes

router = APIRouter(prefix="/platform", tags=["平台公开接口 / Platform Public API"])


@router.get("/config", summary="获取平台公开配置 / Get platform public config")
@public
async def get_platform_public_config(db: DbSession):
    config_service = ConfigService(db)
    general_config = await config_service.get_platform_configs_by_group(
        group_code="platform_general",
    )
    security_config = await config_service.get_platform_configs_by_group(
        group_code="platform_security",
    )
    ai_toolkit_config = await config_service.get_platform_configs_by_group(
        group_code="platform_ai_toolkit",
    )
    storage_config = await config_service.get_platform_configs_by_group(
        group_code="platform_storage",
    )
    configs = {**general_config, **security_config, **ai_toolkit_config, **storage_config}

    captcha_plugin = await resolve_public_captcha_plugin_bundle(
        db,
        None,
        configs.get("captcha_provider"),
        "admin",
    )

    return success(
        data=PlatformPublicConfig(
            platform_domains=settings.platform_domains_list,
            site_name=configs.get("site_name"),
            site_description=configs.get("site_description"),
            site_logo=configs.get("site_logo"),
            site_favicon=configs.get("site_favicon"),
            site_copyright=configs.get("site_copyright"),
            site_icp=configs.get("site_icp"),
            tenant_domain_suffix=configs.get("tenant_domain_suffix"),
            domain_verification_prefix=configs.get("domain_verification_prefix"),
            maintenance_mode=configs.get("maintenance_mode"),
            maintenance_message=configs.get("maintenance_message"),
            login_captcha_enabled=configs.get("login_captcha_enabled"),
            captcha_provider=configs.get("captcha_provider"),
            captcha_plugin=(
                captcha_plugin.to_public_payload() if captcha_plugin else None
            ),
            captcha_difficulty=configs.get("captcha_difficulty"),
            captcha_enable_threshold_admin=configs.get("captcha_enable_threshold_admin"),
            login_max_attempts=configs.get("login_max_attempts"),
            login_lockout_minutes=configs.get("login_lockout_minutes"),
            password_min_length=configs.get("password_min_length"),
            password_complexity=configs.get("password_complexity"),
            password_expiry_days=configs.get("password_expiry_days"),
            session_timeout_minutes=configs.get("session_timeout_minutes"),
            session_max_devices=configs.get("session_max_devices"),
            storage=StoragePublicConfig(
                driver=configs.get("platform_storage_driver"),
                base_url=configs.get("platform_storage_base_url"),
                chunk_size_mb=configs.get("platform_storage_chunk_size_mb"),
                max_file_size_mb=configs.get("platform_storage_max_file_size_mb"),
                allowed_extensions=configs.get("platform_storage_allowed_extensions"),
            ),
            runtime_limits=RuntimeLimitsPublicConfig(
                page_context_max_bytes=await get_page_context_max_bytes(db),
            ),
        ),
        message=_("common.success"),
    )


__all__ = ["router"]
