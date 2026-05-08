"""
认证服务 / Authentication Service

提供平台管理员、企业管理员、企业用户的认证逻辑
Provides authentication logic for platform admins, tenant admins and tenant users.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import ConfigService
from app.core.logging import LogManager
from app.core.redis import cache_delete, cache_get, cache_set
from app.core.security import (
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    get_password_hash,
    verify_impersonate_token,
    verify_password,
    verify_token_with_scope,
)
from app.models import Admin, TenantAdmin, TenantUser
from app.services.common.auth_domains import (
    AdminAuthFacade,
    AuthAdminDomain,
    AuthCaptchaVerificationMixin,
    AuthLoggingBootstrapDomain,
    AuthLoginSecurityDomain,
    AuthSessionPasswordDomain,
    AuthTenantAdminDomain,
    AuthTenantUserDomain,
    TenantAdminAuthFacade,
    TenantUserAuthFacade,
    TokenSessionFacade,
)

logger = LogManager.get_logger("auth")


class AuthService(AuthCaptchaVerificationMixin):
    """
    认证服务 / Authentication service.

    提供：
    - 平台管理员认证 (Admin)
    - 企业管理员认证 (TenantAdmin)
    - 企业用户认证 (TenantUser)
    - Token 刷新
    - 密码修改
    """

    LOGIN_CODE_TTL = 600
    LOGIN_CODE_RATE_LIMIT_TTL = 60
    RESET_CODE_TTL = 600
    RESET_RATE_LIMIT_TTL = 60

    def __init__(self, db: AsyncSession):
        self.db = db
        self._config_service = ConfigService(db)

        self.token_sessions = TokenSessionFacade(self)
        self.token_session = self.token_sessions
        self.admin_auth = AdminAuthFacade(self)
        self.tenant_admin_auth = TenantAdminAuthFacade(self)
        self.tenant_user_auth = TenantUserAuthFacade(self)

        self._logging_domain = AuthLoggingBootstrapDomain(self)
        self._session_domain = AuthSessionPasswordDomain(self)
        self._login_security_domain = AuthLoginSecurityDomain(self)
        self._admin_domain = AuthAdminDomain(self)
        self._tenant_admin_domain = AuthTenantAdminDomain(self)
        self._tenant_user_domain = AuthTenantUserDomain(self)

    @staticmethod
    def _mask_identifier(identifier: str | None) -> str:
        return AuthLoggingBootstrapDomain.mask_identifier(identifier)

    @staticmethod
    def _format_auth_fields(**fields: Any) -> str:
        return AuthLoggingBootstrapDomain.format_auth_fields(**fields)

    @classmethod
    def _log_auth_info(cls, event: str, **fields: Any) -> None:
        AuthLoggingBootstrapDomain.format_auth_fields(**fields)
        details = cls._format_auth_fields(**fields)
        logger.info(f"{event} | {details}" if details else event)

    @classmethod
    def _log_auth_warning(cls, event: str, **fields: Any) -> None:
        AuthLoggingBootstrapDomain.format_auth_fields(**fields)
        details = cls._format_auth_fields(**fields)
        logger.warning(f"{event} | {details}" if details else event)

    @staticmethod
    def _utc_now_aware() -> datetime:
        return AuthLoggingBootstrapDomain.utc_now_aware()

    @staticmethod
    def _normalize_utc(value: datetime) -> datetime:
        return AuthLoggingBootstrapDomain.normalize_utc(value)

    @staticmethod
    def _normalize_request_host(host: str | None) -> str:
        return AuthLoggingBootstrapDomain.normalize_request_host(host)

    @classmethod
    def _host_matches_rule(cls, host: str, rule: str) -> bool:
        return AuthLoggingBootstrapDomain.host_matches_rule(host, rule)

    def _assert_dev_bootstrap_enabled(
        self,
        scope: str,
        request_host: str | None,
    ) -> str:
        return self._logging_domain.assert_dev_bootstrap_enabled(scope, request_host)

    def _assert_dev_bootstrap_secret(
        self,
        *,
        scope: str,
        provided_secret: str,
        expected_secret: str,
        request_host: str,
    ) -> None:
        self._logging_domain.assert_dev_bootstrap_secret(
            scope=scope,
            provided_secret=provided_secret,
            expected_secret=expected_secret,
            request_host=request_host,
        )

    async def _record_active_tokens(
        self,
        user_type: str,
        user_id: str,
        access_jti: str,
        refresh_jti: str,
    ) -> None:
        await self._session_domain.record_active_tokens(
            user_type,
            user_id,
            access_jti,
            refresh_jti,
        )

    async def revoke_on_logout(
        self,
        access_token: str,
        user_type: str,
        user_id: str,
    ) -> None:
        await self._session_domain.revoke_on_logout(access_token, user_type, user_id)

    async def force_logout(
        self,
        user_type: str,
        user_id: int,
        tenant_id: int | None = None,
    ) -> None:
        await self._session_domain.force_logout(user_type, user_id, tenant_id)

    async def _validate_password_policy(
        self,
        password: str,
        tenant_id: int | None = None,
    ) -> None:
        await self._session_domain.validate_password_policy(password, tenant_id)

    async def _record_login_failure(
        self,
        username: str,
        client_ip: str | None,
        user_type: str = "admin",
        tenant_id: int | None = None,
    ) -> None:
        await self._login_security_domain.record_login_failure(
            username,
            client_ip,
            user_type,
            tenant_id,
        )

    async def _record_admin_login_failure(
        self,
        username: str,
        client_ip: str | None,
    ) -> None:
        await self._login_security_domain.record_admin_login_failure(
            username, client_ip
        )

    async def _is_account_locked(
        self,
        user_id: int,
        user_type: str = "admin",
    ) -> bool:
        return await self._login_security_domain.is_account_locked(user_id, user_type)

    async def _reset_login_failures(
        self,
        user_id: int,
        user_type: str = "admin",
    ) -> None:
        await self._login_security_domain.reset_login_failures(user_id, user_type)

    async def _reset_admin_login_failures(self, admin_id: int) -> None:
        await self._login_security_domain.reset_admin_login_failures(admin_id)

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        return verify_password(password, password_hash)

    @staticmethod
    def _get_password_hash(password: str) -> str:
        return get_password_hash(password)

    @staticmethod
    async def _verify_impersonate_token(
        token: str,
        expected_target_scope: str,
    ) -> dict[str, Any] | None:
        return await verify_impersonate_token(token, expected_target_scope)

    @staticmethod
    async def _verify_token_with_scope(
        token: str,
        scope: str,
        token_type: str = TOKEN_TYPE_REFRESH,
    ) -> tuple[str | None, str | None]:
        return await verify_token_with_scope(token, scope, token_type)

    @staticmethod
    def _create_access_token(
        subject: int | str,
        *,
        scope: str,
        expires_delta: Any | None = None,
        extra_claims: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        return create_access_token(
            subject=subject,
            scope=scope,
            expires_delta=expires_delta,
            extra_claims=extra_claims,
        )

    @staticmethod
    def _create_refresh_token(
        subject: int | str,
        *,
        scope: str,
        extra_claims: dict[str, Any] | None = None,
    ) -> tuple[str, str]:
        return create_refresh_token(
            subject=subject,
            scope=scope,
            extra_claims=extra_claims,
        )

    @staticmethod
    def _create_token_pair(
        subject: int | str,
        *,
        scope: str,
        extra_claims: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return create_token_pair(
            subject=subject,
            scope=scope,
            extra_claims=extra_claims,
        )

    async def _cache_get(self, key: str) -> Any:
        return await cache_get(key)

    async def _cache_set(self, key: str, value: Any, ttl: int) -> None:
        await cache_set(key, value, ttl=ttl)

    async def _cache_delete(self, key: str) -> None:
        await cache_delete(key)

    async def _issue_admin_login_tokens(
        self,
        admin: Admin,
        *,
        client_ip: str | None = None,
        log_event: str = "admin.login.success",
    ) -> dict[str, Any]:
        return await self._admin_domain.issue_login_tokens(
            admin,
            client_ip=client_ip,
            log_event=log_event,
        )

    async def authenticate_admin(
        self,
        username: str,
        password: str,
        client_ip: str | None = None,
        captcha_challenge_id: str | None = None,
        captcha_solution: str | None = None,
        captcha_provider_code: str | None = None,
    ) -> dict[str, Any]:
        return await self._admin_domain.authenticate(
            username,
            password,
            client_ip=client_ip,
            captcha_challenge_id=captcha_challenge_id,
            captcha_solution=captcha_solution,
            captcha_provider_code=captcha_provider_code,
        )

    async def authenticate_admin_by_dev_bootstrap(
        self,
        bootstrap_secret: str,
        request_host: str | None,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        return await self._admin_domain.authenticate_by_dev_bootstrap(
            bootstrap_secret,
            request_host=request_host,
            client_ip=client_ip,
        )

    async def refresh_admin_token(self, refresh_token: str) -> dict[str, Any]:
        return await self._admin_domain.refresh_token(refresh_token)

    async def change_admin_password(
        self,
        admin: Admin,
        old_password: str,
        new_password: str,
    ) -> None:
        await self._admin_domain.change_password(admin, old_password, new_password)

    async def _issue_tenant_admin_login_tokens(
        self,
        tenant_admin: TenantAdmin,
        *,
        tenant_code: str | None = None,
        client_ip: str | None = None,
        log_event: str = "tenant_admin.login.success",
    ) -> dict[str, Any]:
        return await self._tenant_admin_domain.issue_login_tokens(
            tenant_admin,
            tenant_code=tenant_code,
            client_ip=client_ip,
            log_event=log_event,
        )

    async def authenticate_tenant_admin(
        self,
        username: str,
        password: str,
        tenant_code: str | None = None,
        client_ip: str | None = None,
        captcha_challenge_id: str | None = None,
        captcha_solution: str | None = None,
        captcha_provider_code: str | None = None,
    ) -> dict[str, Any]:
        return await self._tenant_admin_domain.authenticate(
            username,
            password,
            tenant_code=tenant_code,
            client_ip=client_ip,
            captcha_challenge_id=captcha_challenge_id,
            captcha_solution=captcha_solution,
            captcha_provider_code=captcha_provider_code,
        )

    async def authenticate_tenant_admin_by_dev_bootstrap(
        self,
        bootstrap_secret: str,
        request_host: str | None,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        return await self._tenant_admin_domain.authenticate_by_dev_bootstrap(
            bootstrap_secret,
            request_host=request_host,
            client_ip=client_ip,
        )

    async def refresh_tenant_admin_token(self, refresh_token: str) -> dict[str, Any]:
        return await self._tenant_admin_domain.refresh_token(refresh_token)

    async def change_tenant_admin_password(
        self,
        tenant_admin: TenantAdmin,
        old_password: str,
        new_password: str,
    ) -> None:
        await self._tenant_admin_domain.change_password(
            tenant_admin,
            old_password,
            new_password,
        )

    async def impersonate_tenant_admin(
        self,
        impersonate_token: str,
    ) -> tuple[dict[str, Any], dict]:
        return await self._tenant_admin_domain.impersonate(impersonate_token)

    async def get_tenant_admin_profile_flags(
        self,
        tenant_admin: TenantAdmin,
    ) -> dict[str, Any]:
        return await self._tenant_admin_domain.get_profile_flags(tenant_admin)

    async def update_tenant_admin_profile(
        self,
        tenant_admin: TenantAdmin,
        profile_data: dict[str, Any],
    ) -> TenantAdmin:
        return await self._tenant_admin_domain.update_profile(
            tenant_admin,
            profile_data,
        )

    async def authenticate_tenant_user(
        self,
        username: str,
        password: str,
        tenant_code: str | None = None,
        client_ip: str | None = None,
        captcha_challenge_id: str | None = None,
        captcha_solution: str | None = None,
        captcha_provider_code: str | None = None,
    ) -> dict[str, Any]:
        return await self._tenant_user_domain.authenticate(
            username,
            password,
            tenant_code=tenant_code,
            client_ip=client_ip,
            captcha_challenge_id=captcha_challenge_id,
            captcha_solution=captcha_solution,
            captcha_provider_code=captcha_provider_code,
        )

    async def authenticate_tenant_user_by_dev_bootstrap(
        self,
        bootstrap_secret: str,
        *,
        request_host: str | None,
        username: str,
        tenant_code: str,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        return await self._tenant_user_domain.authenticate_by_dev_bootstrap(
            bootstrap_secret=bootstrap_secret,
            request_host=request_host,
            username=username,
            tenant_code=tenant_code,
            client_ip=client_ip,
        )

    async def _issue_tenant_user_tokens(
        self,
        user: TenantUser,
        *,
        client_ip: str | None,
        tenant_code: str | None = None,
        event: str = "tenant_user.login.success",
    ) -> dict[str, Any]:
        return await self._tenant_user_domain.issue_tokens(
            user=user,
            client_ip=client_ip,
            tenant_code=tenant_code,
            event=event,
        )

    async def send_tenant_user_login_code(self, **kwargs: Any) -> dict[str, Any]:
        return await self._tenant_user_domain.send_login_code(**kwargs)

    async def authenticate_tenant_user_by_code(self, **kwargs: Any) -> dict[str, Any]:
        return await self._tenant_user_domain.authenticate_by_code(**kwargs)

    async def refresh_tenant_user_token(self, refresh_token: str) -> dict[str, Any]:
        return await self._tenant_user_domain.refresh_token(refresh_token)

    async def change_tenant_user_password(
        self,
        tenant_user: TenantUser,
        old_password: str,
        new_password: str,
    ) -> None:
        await self._tenant_user_domain.change_password(
            tenant_user,
            old_password,
            new_password,
        )

    async def register_tenant_user(self, **kwargs: Any) -> dict[str, Any]:
        return await self._tenant_user_domain.register(**kwargs)

    async def notify_tenant_admins_pending(
        self,
        tenant_id: int,
        username: str,
        email: str,
    ) -> None:
        await self._tenant_user_domain.notify_tenant_admins_pending(
            tenant_id,
            username,
            email,
        )

    async def update_tenant_user_profile(
        self,
        user: TenantUser,
        **kwargs: Any,
    ) -> TenantUser:
        return await self._tenant_user_domain.update_profile(user, **kwargs)

    async def request_password_reset(self, **kwargs: Any) -> dict[str, Any]:
        return await self._tenant_user_domain.request_password_reset(**kwargs)

    async def reset_tenant_user_password(self, **kwargs: Any) -> None:
        await self._tenant_user_domain.reset_password(**kwargs)
