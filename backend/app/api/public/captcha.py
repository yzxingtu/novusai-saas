from __future__ import annotations
from fastapi import APIRouter, Request
from app.captcha.service import captcha_service
from app.core.i18n import _
from app.core.response import success
from app.enums.error_code import ErrorCode
from app.exceptions import BusinessException, ServiceUnavailableException
from app.rbac.decorators import public
from app.schemas.common.captcha import (
    CaptchaChallengeRequest,
    CaptchaChallengeResponse,
    CaptchaVerifyRequest,
    CaptchaVerifyResponse,
)


router = APIRouter(prefix="/captcha", tags=["验证码"])


@router.post("/challenge", summary="获取验证码挑战")
@public
async def create_challenge(
    request: Request,
    data: CaptchaChallengeRequest,
):
    ctx = {
        "ip": request.client.host if request.client else None,
        "endpoint": data.endpoint,
        "action": data.action,
        "difficulty": data.difficulty,
    }
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


@router.post("/verify", summary="校验验证码")
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
