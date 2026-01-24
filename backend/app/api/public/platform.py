from fastapi import APIRouter

from app.core.deps import DbSession
from app.core.i18n import _
from app.core.response import success
from app.configs.service import ConfigService
from app.schemas.public import PlatformPublicConfig
from app.rbac.decorators import public


router = APIRouter(prefix="/platform", tags=["平台公开接口"])


@router.get("/config", summary="获取平台公开配置")
@public
async def get_platform_public_config(db: DbSession):
    config_service = ConfigService(db)
    general_config = await config_service.get_platform_configs_by_group(
        group_code="platform_general",
    )
    security_config = await config_service.get_platform_configs_by_group(
        group_code="platform_security",
    )
    configs = {**general_config, **security_config}

    return success(
        data=PlatformPublicConfig(
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
            captcha_difficulty=configs.get("captcha_difficulty"),
            captcha_enable_threshold_admin=configs.get("captcha_enable_threshold_admin"),
            login_max_attempts=configs.get("login_max_attempts"),
            login_lockout_minutes=configs.get("login_lockout_minutes"),
            password_min_length=configs.get("password_min_length"),
            password_complexity=configs.get("password_complexity"),
            password_expiry_days=configs.get("password_expiry_days"),
            session_timeout_minutes=configs.get("session_timeout_minutes"),
            session_max_devices=configs.get("session_max_devices"),
        ),
        message=_("common.success"),
    )


__all__ = ["router"]
