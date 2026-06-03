"""Tenant-user login code flows."""

from __future__ import annotations

import secrets
import string
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, select

from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import (
    AuthenticationException,
    BusinessException,
    ValidationException,
)
from app.models import Tenant, TenantUser

if TYPE_CHECKING:
    from app.services.common.auth_service import AuthService

logger = LogManager.get_logger("auth")


class TenantUserLoginCodeDomain:
    """Login code issuance and validation for tenant users."""

    def __init__(self, service: AuthService) -> None:
        self._service = service

    async def resolve_login_tenant_id(
        self,
        *,
        tenant_code: str | None,
        identifier: str | None = None,
        client_ip: str | None = None,
        log_reason: str = "tenant_domain_required",
    ) -> int:
        if not tenant_code:
            self._service._log_auth_warning(
                "tenant_user.login_code.failed",
                identifier=self._service._mask_identifier(identifier),
                client_ip=client_ip,
                reason=log_reason,
            )
            raise AuthenticationException(message=_("auth.tenant_domain_required"))

        result = await self._service.db.execute(
            select(Tenant).where(
                Tenant.code == tenant_code,
                Tenant.is_active.is_(True),
                Tenant.is_deleted.is_(False),
            )
        )
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise BusinessException(message=_("tenant.not_found"))
        return int(tenant.id)

    async def ensure_login_code_channel_enabled(
        self,
        *,
        tenant_id: int,
        channel: str,
    ) -> None:
        methods = await self._service._config_service.get_tenant_config(
            tenant_id,
            "tenant_login_methods",
            default=["password", "email"],
        )
        allowed_methods = {
            str(item).strip().lower() for item in (methods or []) if str(item).strip()
        }
        if channel not in {"email", "sms"}:
            raise ValidationException(message=_("auth.login_code_channel_invalid"))
        if channel not in allowed_methods:
            if channel == "sms":
                raise BusinessException(message=_("auth.login_code_sms_not_enabled"))
            raise BusinessException(message=_("auth.login_code_email_not_enabled"))

    async def maybe_verify_code_login_captcha(
        self,
        *,
        tenant_id: int,
        identifier: str,
        client_ip: str | None,
        captcha_challenge_id: str | None,
        captcha_solution: str | None,
        captcha_provider_code: str | None,
    ) -> None:
        enabled = await self._service._config_service.get_tenant_config(
            tenant_id,
            "user_login_captcha_enabled",
            default=True,
        )
        threshold = await self._service._config_service.get_tenant_config(
            tenant_id,
            "user_login_captcha_enable_threshold",
            default=0,
        )
        if not enabled or (isinstance(threshold, int) and threshold > 0):
            return

        await self._service._verify_captcha(
            captcha_challenge_id,
            captcha_solution,
            captcha_provider_code,
            {
                "action": "login_code_send",
                "endpoint": "user",
                "identifier": self._service._mask_identifier(identifier),
                "ip": client_ip,
                "tenant_id": tenant_id,
            },
        )

    @staticmethod
    def build_login_code_key(
        *,
        channel: str,
        identifier: str,
        tenant_id: int,
    ) -> str:
        return f"tenant_user_login_code:{channel}:{tenant_id}:{identifier}"

    @staticmethod
    def build_login_code_rate_key(
        *,
        channel: str,
        identifier: str,
        tenant_id: int,
    ) -> str:
        return f"tenant_user_login_code_rate:{channel}:{tenant_id}:{identifier}"

    async def send_login_code(
        self,
        *,
        channel: str,
        email: str | None = None,
        phone: str | None = None,
        tenant_code: str | None = None,
        client_ip: str | None = None,
        captcha_challenge_id: str | None = None,
        captcha_solution: str | None = None,
        captcha_provider_code: str | None = None,
    ) -> dict[str, Any]:
        normalized_email = (email or "").strip().lower() or None
        normalized_phone = (phone or "").strip() or None
        identifier = normalized_email or normalized_phone
        tenant_id = await self.resolve_login_tenant_id(
            tenant_code=tenant_code,
            identifier=identifier,
            client_ip=client_ip,
        )
        await self.ensure_login_code_channel_enabled(
            tenant_id=tenant_id, channel=channel
        )

        if channel == "email":
            if not normalized_email:
                raise ValidationException(message=_("auth.login_code_email_required"))
            identifier = normalized_email
        elif channel == "sms":
            if not normalized_phone:
                raise ValidationException(message=_("auth.login_code_phone_required"))
            raise BusinessException(message=_("auth.login_code_sms_not_enabled"))

        await self.maybe_verify_code_login_captcha(
            tenant_id=tenant_id,
            identifier=identifier or "",
            client_ip=client_ip,
            captcha_challenge_id=captcha_challenge_id,
            captcha_solution=captcha_solution,
            captcha_provider_code=captcha_provider_code,
        )

        rate_key = self.build_login_code_rate_key(
            channel=channel,
            identifier=identifier or "",
            tenant_id=tenant_id,
        )
        if await self._service._cache_get(rate_key):
            raise BusinessException(message=_("auth.reset_rate_limited"))

        if channel != "email":
            raise BusinessException(message=_("auth.login_code_channel_invalid"))

        result = await self._service.db.execute(
            select(TenantUser).where(
                and_(
                    TenantUser.tenant_id == tenant_id,
                    TenantUser.email == identifier,
                    TenantUser.is_deleted.is_(False),
                )
            )
        )
        user = result.scalar_one_or_none()

        await self._service._cache_set(
            rate_key,
            True,
            ttl=self._service.LOGIN_CODE_RATE_LIMIT_TTL,
        )
        if user is None:
            self._service._log_auth_warning(
                "tenant_user.login_code.send.skipped",
                identifier=self._service._mask_identifier(identifier),
                tenant_id=tenant_id,
                tenant_code=tenant_code,
                client_ip=client_ip,
                reason="user_not_found",
            )
            return {"message": _("auth.login_code_sent")}

        code = "".join(secrets.choice(string.digits) for _ in range(6))
        code_key = self.build_login_code_key(
            channel=channel,
            identifier=identifier or "",
            tenant_id=tenant_id,
        )
        await self._service._cache_set(
            code_key,
            {"code": code, "user_id": user.id},
            ttl=self._service.LOGIN_CODE_TTL,
        )

        expire_minutes = self._service.LOGIN_CODE_TTL // 60
        try:
            from app.services.common.email_templates import render_login_code_email
            from app.tasks.email import send_email_task

            user_name = (user.nickname or user.username or "").strip()
            subject, html_body, text_body = render_login_code_email(
                user_name=user_name or identifier or "",
                code=code,
                expire_minutes=expire_minutes,
            )
            send_email_task.delay(
                to=[identifier],
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                triggered_by="login_code",
                tenant_id=tenant_id,
            )
        except Exception as exc:
            logger.warning(
                "Failed to queue login code email: user_id={} tenant_id={} error={}",
                user.id,
                tenant_id,
                str(exc),
            )

        self._service._log_auth_info(
            "tenant_user.login_code.send.success",
            user_id=user.id,
            username=user.username,
            tenant_id=tenant_id,
            tenant_code=tenant_code,
            client_ip=client_ip,
        )
        return {"message": _("auth.login_code_sent")}

    async def authenticate_by_code(
        self,
        *,
        channel: str,
        code: str,
        email: str | None = None,
        phone: str | None = None,
        tenant_code: str | None = None,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        normalized_email = (email or "").strip().lower() or None
        normalized_phone = (phone or "").strip() or None
        identifier = normalized_email or normalized_phone
        tenant_id = await self.resolve_login_tenant_id(
            tenant_code=tenant_code,
            identifier=identifier,
            client_ip=client_ip,
        )
        await self.ensure_login_code_channel_enabled(
            tenant_id=tenant_id, channel=channel
        )

        if channel == "email":
            if not normalized_email:
                raise ValidationException(message=_("auth.login_code_email_required"))
            identifier = normalized_email
        elif channel == "sms":
            if not normalized_phone:
                raise ValidationException(message=_("auth.login_code_phone_required"))
            raise BusinessException(message=_("auth.login_code_sms_not_enabled"))

        code_key = self.build_login_code_key(
            channel=channel,
            identifier=identifier or "",
            tenant_id=tenant_id,
        )
        stored = await self._service._cache_get(code_key)
        if not stored or not isinstance(stored, dict):
            raise AuthenticationException(message=_("auth.login_code_invalid"))
        if stored.get("code") != code:
            raise AuthenticationException(message=_("auth.login_code_invalid"))

        user_id = stored.get("user_id")
        if not user_id:
            raise AuthenticationException(message=_("auth.login_code_invalid"))

        result = await self._service.db.execute(
            select(TenantUser).where(
                and_(
                    TenantUser.id == int(user_id),
                    TenantUser.tenant_id == tenant_id,
                    TenantUser.is_deleted.is_(False),
                )
            )
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise AuthenticationException(message=_("auth.login_code_invalid"))

        if await self._service._is_account_locked(user.id, "tenant_user"):
            raise AuthenticationException(message=_("auth.account_locked"))
        if not user.is_active:
            raise AuthenticationException(message=_("auth.account_disabled"))

        await self._service._reset_login_failures(user.id, "tenant_user")
        await self._service._cache_delete(code_key)
        return await self._service._issue_tenant_user_tokens(
            user,
            client_ip=client_ip,
            tenant_code=tenant_code,
            event="tenant_user.login_code.success",
        )
