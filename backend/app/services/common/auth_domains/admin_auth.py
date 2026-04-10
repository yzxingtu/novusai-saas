"""Platform-admin authentication domain for AuthService."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import or_, select

from app.core.config import settings
from app.core.i18n import _
from app.core.security import TOKEN_SCOPE_ADMIN, TOKEN_TYPE_REFRESH
from app.enums import ErrorCode
from app.exceptions import AuthenticationException, BusinessException, NotFoundException
from app.models import Admin

if TYPE_CHECKING:
    from app.services.common.auth_service import AuthService


class AuthAdminDomain:
    """Stable domain for platform-admin auth flows."""

    def __init__(self, service: AuthService) -> None:
        self._service = service

    async def issue_login_tokens(
        self,
        admin: Admin,
        *,
        client_ip: str | None = None,
        log_event: str = "admin.login.success",
    ) -> dict[str, Any]:
        admin.last_login_at = self._service._utc_now_aware()
        admin.last_login_ip = client_ip

        session_timeout = await self._service._config_service.get_platform_config(
            "session_timeout_minutes",
            default=120,
        )
        access_token, access_jti = self._service._create_access_token(
            admin.id,
            scope=TOKEN_SCOPE_ADMIN,
            expires_delta=timedelta(minutes=session_timeout),
        )
        refresh_token, refresh_jti = self._service._create_refresh_token(
            admin.id,
            scope=TOKEN_SCOPE_ADMIN,
        )

        await self._service._record_active_tokens(
            "admin",
            str(admin.id),
            access_jti,
            refresh_jti,
        )

        self._service._log_auth_info(
            log_event,
            user_id=admin.id,
            username=admin.username,
            client_ip=client_ip,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    async def authenticate(
        self,
        username: str,
        password: str,
        client_ip: str | None = None,
        captcha_challenge_id: str | None = None,
        captcha_solution: str | None = None,
        captcha_provider_code: str | None = None,
    ) -> dict[str, Any]:
        result = await self._service.db.execute(
            select(Admin).where(
                or_(Admin.username == username, Admin.email == username),
                Admin.is_deleted.is_(False),
            )
        )
        admin = result.scalar_one_or_none()

        if admin is None:
            await self._service._record_admin_login_failure(username, client_ip)
            self._service._log_auth_warning(
                "admin.login.failed",
                identifier=self._service._mask_identifier(username),
                client_ip=client_ip,
                reason="user_not_found",
            )
            captcha_enabled = await self._service._config_service.get_platform_config(
                "login_captcha_enabled",
                default=True,
            )
            threshold = await self._service._config_service.get_platform_config(
                "captcha_enable_threshold_admin",
                default=2,
            )
            captcha_required = captcha_enabled and threshold == 0
            raise AuthenticationException(
                message=_("auth.credentials_invalid"),
                data={"captcha_required": captcha_required},
            )

        if await self._service._is_account_locked(admin.id, "admin"):
            self._service._log_auth_warning(
                "admin.login.failed",
                user_id=admin.id,
                username=admin.username,
                client_ip=client_ip,
                reason="account_locked",
            )
            raise AuthenticationException(message=_("auth.account_locked"))

        if not admin.is_active:
            self._service._log_auth_warning(
                "admin.login.failed",
                user_id=admin.id,
                username=admin.username,
                client_ip=client_ip,
                reason="account_disabled",
            )
            raise AuthenticationException(message=_("auth.credentials_invalid"))

        captcha_enabled = await self._service._config_service.get_platform_config(
            "login_captcha_enabled",
            default=True,
        )
        threshold = await self._service._config_service.get_platform_config(
            "captcha_enable_threshold_admin",
            default=2,
        )
        fail_count = admin.login_fail_count or 0
        captcha_required = captcha_enabled and (
            threshold == 0 or fail_count >= threshold
        )
        if captcha_required:
            await self._service._verify_captcha(
                captcha_challenge_id,
                captcha_solution,
                captcha_provider_code,
                {
                    "ip": client_ip,
                    "endpoint": "admin",
                    "action": "login",
                    "identifier": self._service._mask_identifier(username),
                },
            )

        if not self._service._verify_password(password, admin.password_hash):
            await self._service._record_admin_login_failure(username, client_ip)
            self._service._log_auth_warning(
                "admin.login.failed",
                user_id=admin.id,
                username=admin.username,
                client_ip=client_ip,
                reason="password_mismatch",
            )
            next_fail_count = fail_count + 1
            captcha_required_after = captcha_enabled and (
                threshold == 0 or next_fail_count >= threshold
            )
            raise AuthenticationException(
                message=_("auth.credentials_invalid"),
                data={"captcha_required": captcha_required_after},
            )

        await self._service._reset_admin_login_failures(admin.id)
        return await self.issue_login_tokens(admin, client_ip=client_ip)

    async def authenticate_by_dev_bootstrap(
        self,
        bootstrap_secret: str,
        *,
        request_host: str | None,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        normalized_host = self._service._assert_dev_bootstrap_enabled(
            "admin",
            request_host,
        )
        self._service._assert_dev_bootstrap_secret(
            scope="admin",
            provided_secret=bootstrap_secret,
            expected_secret=settings.DEV_ADMIN_BOOTSTRAP_SECRET,
            request_host=normalized_host,
        )

        identifier = settings.DEV_ADMIN_BOOTSTRAP_USERNAME.strip()
        if not identifier:
            self._service._log_auth_warning(
                "admin.dev_bootstrap.failed",
                reason="username_not_configured",
                request_host=normalized_host,
            )
            raise NotFoundException()

        result = await self._service.db.execute(
            select(Admin).where(
                or_(Admin.username == identifier, Admin.email == identifier),
                Admin.is_deleted.is_(False),
            )
        )
        admin = result.scalar_one_or_none()

        if admin is None:
            self._service._log_auth_warning(
                "admin.dev_bootstrap.failed",
                identifier=self._service._mask_identifier(identifier),
                request_host=normalized_host,
                reason="user_not_found",
            )
            raise AuthenticationException(message=_("auth.credentials_invalid"))

        if not admin.is_active:
            self._service._log_auth_warning(
                "admin.dev_bootstrap.failed",
                user_id=admin.id,
                username=admin.username,
                request_host=normalized_host,
                reason="account_disabled",
            )
            raise AuthenticationException(message=_("auth.account_disabled"))

        return await self.issue_login_tokens(
            admin,
            client_ip=client_ip,
            log_event="admin.dev_bootstrap.success",
        )

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        admin_id, _scope = await self._service._verify_token_with_scope(
            refresh_token,
            TOKEN_SCOPE_ADMIN,
            TOKEN_TYPE_REFRESH,
        )
        if admin_id is None:
            self._service._log_auth_warning(
                "admin.token.refresh.failed",
                reason="invalid_token",
            )
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        result = await self._service.db.execute(
            select(Admin).where(
                Admin.id == int(admin_id),
                Admin.is_deleted.is_(False),
            )
        )
        admin = result.scalar_one_or_none()

        if admin is None:
            self._service._log_auth_warning(
                "admin.token.refresh.failed",
                user_id=admin_id,
                reason="user_not_found",
            )
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        if not admin.is_active:
            self._service._log_auth_warning(
                "admin.token.refresh.failed",
                user_id=admin.id,
                username=admin.username,
                reason="account_disabled",
            )
            raise AuthenticationException(message=_("auth.account_disabled"))

        tokens = self._service._create_token_pair(admin.id, scope=TOKEN_SCOPE_ADMIN)
        await self._service._record_active_tokens(
            "admin",
            str(admin.id),
            tokens["access_jti"],
            tokens["refresh_jti"],
        )
        self._service._log_auth_info(
            "admin.token.refresh.success",
            user_id=admin.id,
            username=admin.username,
        )
        return tokens

    async def change_password(
        self,
        admin: Admin,
        old_password: str,
        new_password: str,
    ) -> None:
        if not self._service._verify_password(old_password, admin.password_hash):
            raise BusinessException(
                message=_("auth.password_mismatch"),
                code=ErrorCode.OLD_PASSWORD_INCORRECT,
            )

        await self._service._validate_password_policy(new_password)
        admin.password_hash = self._service._get_password_hash(new_password)
