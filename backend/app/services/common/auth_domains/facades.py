"""Compatibility facades for AuthService responsibilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.models import Admin, TenantAdmin, TenantUser

if TYPE_CHECKING:
    from app.services.common.auth_service import AuthService


class TokenSessionFacade:
    """Token/session lifecycle facade."""

    def __init__(self, service: AuthService) -> None:
        self._service = service

    async def revoke_on_logout(
        self,
        access_token: str,
        user_type: str,
        user_id: str,
    ) -> None:
        await self._service.revoke_on_logout(access_token, user_type, user_id)

    async def force_logout(
        self,
        user_type: str,
        user_id: int,
        tenant_id: int | None = None,
    ) -> None:
        await self._service.force_logout(user_type, user_id, tenant_id)


class AdminAuthFacade:
    """Platform admin auth facade."""

    def __init__(self, service: AuthService) -> None:
        self._service = service

    async def authenticate(
        self,
        username: str,
        password: str,
        client_ip: str | None = None,
        captcha_challenge_id: str | None = None,
        captcha_solution: str | None = None,
        captcha_provider_code: str | None = None,
    ) -> dict[str, Any]:
        return await self._service.authenticate_admin(
            username=username,
            password=password,
            client_ip=client_ip,
            captcha_challenge_id=captcha_challenge_id,
            captcha_solution=captcha_solution,
            captcha_provider_code=captcha_provider_code,
        )

    async def authenticate_by_dev_bootstrap(
        self,
        bootstrap_secret: str,
        request_host: str | None,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        return await self._service.authenticate_admin_by_dev_bootstrap(
            bootstrap_secret=bootstrap_secret,
            request_host=request_host,
            client_ip=client_ip,
        )

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        return await self._service.refresh_admin_token(refresh_token)

    async def change_password(
        self,
        admin: Admin,
        old_password: str,
        new_password: str,
    ) -> None:
        await self._service.change_admin_password(admin, old_password, new_password)


class TenantAdminAuthFacade:
    """Tenant admin auth facade."""

    def __init__(self, service: AuthService) -> None:
        self._service = service

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
        return await self._service.authenticate_tenant_admin(
            username=username,
            password=password,
            tenant_code=tenant_code,
            tenant_id_from_ctx=tenant_id_from_ctx,
            client_ip=client_ip,
            captcha_challenge_id=captcha_challenge_id,
            captcha_solution=captcha_solution,
            captcha_provider_code=captcha_provider_code,
        )

    async def authenticate_by_dev_bootstrap(
        self,
        bootstrap_secret: str,
        request_host: str | None,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        return await self._service.authenticate_tenant_admin_by_dev_bootstrap(
            bootstrap_secret=bootstrap_secret,
            request_host=request_host,
            client_ip=client_ip,
        )

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        return await self._service.refresh_tenant_admin_token(refresh_token)

    async def change_password(
        self,
        tenant_admin: TenantAdmin,
        old_password: str,
        new_password: str,
    ) -> None:
        await self._service.change_tenant_admin_password(
            tenant_admin,
            old_password,
            new_password,
        )

    async def impersonate(self, impersonate_token: str) -> tuple[dict[str, Any], dict]:
        return await self._service.impersonate_tenant_admin(impersonate_token)

    async def get_profile_flags(self, tenant_admin: TenantAdmin) -> dict[str, Any]:
        return await self._service.get_tenant_admin_profile_flags(tenant_admin)

    async def update_profile(
        self,
        tenant_admin: TenantAdmin,
        profile_data: dict[str, Any],
    ) -> TenantAdmin:
        return await self._service.update_tenant_admin_profile(
            tenant_admin,
            profile_data,
        )


class TenantUserAuthFacade:
    """Tenant user auth facade."""

    def __init__(self, service: AuthService) -> None:
        self._service = service

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
        return await self._service.authenticate_tenant_user(
            username=username,
            password=password,
            tenant_code=tenant_code,
            tenant_id_from_ctx=tenant_id_from_ctx,
            client_ip=client_ip,
            captcha_challenge_id=captcha_challenge_id,
            captcha_solution=captcha_solution,
            captcha_provider_code=captcha_provider_code,
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
        return await self._service.authenticate_tenant_user_by_dev_bootstrap(
            bootstrap_secret=bootstrap_secret,
            request_host=request_host,
            username=username,
            tenant_code=tenant_code,
            client_ip=client_ip,
        )

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        return await self._service.refresh_tenant_user_token(refresh_token)

    async def change_password(
        self,
        tenant_user: TenantUser,
        old_password: str,
        new_password: str,
    ) -> None:
        await self._service.change_tenant_user_password(
            tenant_user,
            old_password,
            new_password,
        )

    async def send_login_code(self, **kwargs: Any) -> dict[str, Any]:
        return await self._service.send_tenant_user_login_code(**kwargs)

    async def authenticate_by_code(self, **kwargs: Any) -> dict[str, Any]:
        return await self._service.authenticate_tenant_user_by_code(**kwargs)

    async def register(self, **kwargs: Any) -> dict[str, Any]:
        return await self._service.register_tenant_user(**kwargs)

    async def update_profile(self, user: TenantUser, **kwargs: Any) -> TenantUser:
        return await self._service.update_tenant_user_profile(user, **kwargs)

    async def request_password_reset(self, **kwargs: Any) -> dict[str, Any]:
        return await self._service.request_password_reset(**kwargs)

    async def reset_password(self, **kwargs: Any) -> None:
        await self._service.reset_tenant_user_password(**kwargs)


__all__ = [
    "AdminAuthFacade",
    "TenantAdminAuthFacade",
    "TenantUserAuthFacade",
    "TokenSessionFacade",
]
