from __future__ import annotations

from fastapi import APIRouter, Request

from app.captcha.runtime import resolve_public_captcha_plugin_bundle
from app.captcha.service import captcha_service
from app.core.deps import DbSession
from app.core.i18n import _
from app.core.response import success
from app.enums.error_code import ErrorCode
from app.exceptions import (
    BusinessException,
    RateLimitException,
    ServiceUnavailableException,
)
from app.rbac.decorators import public
from app.schemas.common.captcha import (
    CaptchaChallengeRequest,
    CaptchaChallengeResponse,
    CaptchaVerifyRequest,
    CaptchaVerifyResponse,
)

router = APIRouter(prefix="/captcha", tags=["验证码 / Captcha"])


@router.post("/challenge", summary="获取验证码挑战 / Get captcha challenge")
@public
async def create_challenge(
    request: Request,
    data: CaptchaChallengeRequest,
    db: DbSession,
):
    ctx = {
        "ip": request.client.host if request.client else None,
        "endpoint": data.endpoint,
        "action": data.action,
        "difficulty": data.difficulty,
    }
    captcha_plugin = await resolve_public_captcha_plugin_bundle(
        db,
        request,
        data.provider_code,
        data.endpoint,
    )
    if data.provider_code and data.provider_code != "image" and captcha_plugin is None:
        raise BusinessException(
            message=_(ErrorCode.INVALID_PARAMETER.message_key),
            code=ErrorCode.INVALID_PARAMETER,
        )
    if captcha_plugin is not None:
        ctx["plugin_config"] = captcha_plugin.plugin_config

    if not captcha_service.check_rate_limit(ctx, "challenge"):
        raise RateLimitException()
    try:
        challenge = await captcha_service.generate_challenge(data.provider_code, ctx)
    except ValueError:
        raise BusinessException(
            message=_(ErrorCode.INVALID_PARAMETER.message_key),
            code=ErrorCode.INVALID_PARAMETER,
        )
    except RuntimeError as exc:
        if str(exc) == "captcha_library_missing":
            raise ServiceUnavailableException()
        raise
    return success(
        data=CaptchaChallengeResponse(**challenge.model_dump()),
        message=_("common.success"),
    )


@router.post("/verify", summary="校验验证码 / Verify captcha")
@public
async def verify_captcha(
    request: Request,
    data: CaptchaVerifyRequest,
):
    ctx = {
        "ip": request.client.host if request.client else None,
        "endpoint": data.endpoint,
        "action": data.action,
    }
    if not captcha_service.check_rate_limit(ctx, "verify"):
        raise RateLimitException()
    result = await captcha_service.verify(
        data.provider_code,
        data.challenge_id,
        data.solution,
        ctx,
    )
    return success(
        data=CaptchaVerifyResponse(**result.model_dump()),
        message=_("common.success"),
    )
