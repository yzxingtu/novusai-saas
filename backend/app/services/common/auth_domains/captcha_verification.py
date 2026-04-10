"""Captcha verification mixin for AuthService."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.captcha.service import captcha_service
from app.core.i18n import _
from app.exceptions import AuthenticationException

if TYPE_CHECKING:
    from app.services.common.auth_service import AuthService


class AuthCaptchaVerificationMixin:
    """Shared CAPTCHA verification behavior for auth flows."""

    async def _verify_captcha(
        self: "AuthService",
        challenge_id: str | None,
        solution: str | None,
        provider_code: str | None,
        ctx: dict[str, Any],
    ) -> None:
        log_fields = {
            "endpoint": ctx.get("endpoint"),
            "action": ctx.get("action"),
            "identifier": ctx.get("identifier"),
            "tenant_id": ctx.get("tenant_id"),
            "client_ip": ctx.get("ip"),
            "provider": provider_code,
        }
        if not provider_code:
            self._log_auth_warning(
                "captcha.verify.failed",
                **log_fields,
                reason="provider_required",
            )
            raise AuthenticationException(
                message=_("auth.captcha_provider_required"),
                data={"captcha_required": True},
            )
        if not challenge_id or not solution:
            self._log_auth_warning(
                "captcha.verify.failed",
                **log_fields,
                reason="challenge_required",
            )
            raise AuthenticationException(
                message=_("auth.captcha_required"),
                data={"captcha_required": True},
            )
        result = await captcha_service.verify(
            provider_code, challenge_id, solution, ctx
        )
        if not result.ok:
            self._log_auth_warning(
                "captcha.verify.failed",
                **log_fields,
                reason="invalid",
            )
            raise AuthenticationException(
                message=_("auth.captcha_invalid"),
                data={"captcha_required": True},
            )
