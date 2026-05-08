"""Tenant-user auth facade for AuthService."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.models import TenantUser
from app.services.common.auth_domains.tenant_user_login import (
    TenantUserAccountDomain,
    TenantUserLoginDomain,
    TenantUserTokenDomain,
)
from app.services.common.auth_domains.tenant_user_login_code import (
    TenantUserLoginCodeDomain,
)

if TYPE_CHECKING:
    from app.services.common.auth_service import AuthService


class AuthTenantUserDomain:
    """Stable facade for tenant-user auth flows."""

    def __init__(self, service: AuthService) -> None:
        self._service = service
        self._login_domain = TenantUserLoginDomain(service)
        self._login_code_domain = TenantUserLoginCodeDomain(service)
        self._token_domain = TenantUserTokenDomain(service)
        self._account_domain = TenantUserAccountDomain(service)

    async def authenticate(
        self,
        username: str,
        password: str,
        tenant_code: str | None = None,
        tenant_id_from_ctx: int | None = None,
        client_ip: str | None = None,
        captcha_challenge_id: str | None = None,
        captcha_solution: str | None = None,
        captcha_provider_code: str | None = None,
    ) -> dict[str, Any]:
        return await self._login_domain.authenticate(
            username=username,
            password=password,
            tenant_code=tenant_code,
            tenant_id_from_ctx=tenant_id_from_ctx,
            client_ip=client_ip,
            captcha_challenge_id=captcha_challenge_id,
            captcha_solution=captcha_solution,
            captcha_provider_code=captcha_provider_code,
        )

    async def issue_tokens(
        self,
        *,
        user: TenantUser,
        client_ip: str | None,
        tenant_code: str | None = None,
        event: str = "tenant_user.login.success",
    ) -> dict[str, Any]:
        return await self._login_domain.issue_tokens(
            user=user,
            client_ip=client_ip,
            tenant_code=tenant_code,
            event=event,
        )

    async def authenticate_by_dev_bootstrap(
        self,
        bootstrap_secret: str,
        *,
        request_host: str | None,
        username: str,
        tenant_code: str,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        return await self._login_domain.authenticate_by_dev_bootstrap(
            bootstrap_secret=bootstrap_secret,
            request_host=request_host,
            username=username,
            tenant_code=tenant_code,
            client_ip=client_ip,
        )

    async def resolve_login_tenant_id(
        self,
        *,
        tenant_code: str | None,
        tenant_id_from_ctx: int | None,
        identifier: str | None = None,
        client_ip: str | None = None,
        log_reason: str = "tenant_domain_required",
    ) -> int:
        return await self._login_code_domain.resolve_login_tenant_id(
            tenant_code=tenant_code,
            tenant_id_from_ctx=tenant_id_from_ctx,
            identifier=identifier,
            client_ip=client_ip,
            log_reason=log_reason,
        )

    async def ensure_login_code_channel_enabled(
        self,
        *,
        tenant_id: int,
        channel: str,
    ) -> None:
        await self._login_code_domain.ensure_login_code_channel_enabled(
            tenant_id=tenant_id,
            channel=channel,
        )

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
        await self._login_code_domain.maybe_verify_code_login_captcha(
            tenant_id=tenant_id,
            identifier=identifier,
            client_ip=client_ip,
            captcha_challenge_id=captcha_challenge_id,
            captcha_solution=captcha_solution,
            captcha_provider_code=captcha_provider_code,
        )

    @staticmethod
    def build_login_code_key(
        *,
        channel: str,
        identifier: str,
        tenant_id: int,
    ) -> str:
        return TenantUserLoginCodeDomain.build_login_code_key(
            channel=channel,
            identifier=identifier,
            tenant_id=tenant_id,
        )

    @staticmethod
    def build_login_code_rate_key(
        *,
        channel: str,
        identifier: str,
        tenant_id: int,
    ) -> str:
        return TenantUserLoginCodeDomain.build_login_code_rate_key(
            channel=channel,
            identifier=identifier,
            tenant_id=tenant_id,
        )

    async def send_login_code(self, **kwargs: Any) -> dict[str, Any]:
        return await self._login_code_domain.send_login_code(**kwargs)

    async def authenticate_by_code(self, **kwargs: Any) -> dict[str, Any]:
        return await self._login_code_domain.authenticate_by_code(**kwargs)

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        return await self._token_domain.refresh_token(refresh_token)

    async def change_password(
        self,
        user: TenantUser,
        old_password: str,
        new_password: str,
    ) -> None:
        await self._account_domain.change_password(user, old_password, new_password)

    async def register(self, **kwargs: Any) -> dict[str, Any]:
        return await self._account_domain.register(**kwargs)

    async def notify_tenant_admins_pending(
        self,
        tenant_id: int,
        username: str,
        email: str,
    ) -> None:
        await self._account_domain.notify_tenant_admins_pending(
            tenant_id=tenant_id,
            username=username,
            email=email,
        )

    async def update_profile(self, user: TenantUser, **kwargs: Any) -> TenantUser:
        return await self._account_domain.update_profile(user, **kwargs)

    async def request_password_reset(self, **kwargs: Any) -> dict[str, Any]:
        return await self._account_domain.request_password_reset(**kwargs)

    async def reset_password(self, **kwargs: Any) -> None:
        await self._account_domain.reset_password(**kwargs)
