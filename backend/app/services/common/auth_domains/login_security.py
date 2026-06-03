"""Login attempt tracking and lockout domain."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import or_, select

from app.models import Admin, TenantAdmin, TenantUser

if TYPE_CHECKING:
    from app.services.common.auth_service import AuthService


class AuthLoginSecurityDomain:
    """Stable domain for login failure counters and lockout checks."""

    def __init__(self, service: AuthService) -> None:
        self._service = service

    async def record_login_failure(
        self,
        username: str,
        client_ip: str | None,
        user_type: str = "admin",
        tenant_id: int | None = None,
    ) -> None:
        _ = client_ip
        from datetime import timedelta

        if tenant_id and user_type in ("tenant_admin", "tenant_user"):
            max_attempts = await self._service._config_service.get_tenant_config(
                tenant_id, "tenant_login_max_attempts", default=5
            )
            lockout_minutes = await self._service._config_service.get_tenant_config(
                tenant_id, "tenant_login_lockout_minutes", default=30
            )
        else:
            max_attempts = await self._service._config_service.get_platform_config(
                "login_max_attempts", default=5
            )
            lockout_minutes = await self._service._config_service.get_platform_config(
                "login_lockout_minutes", default=30
            )

        now = self._service._utc_now_aware()

        if user_type == "admin":
            result = await self._service.db.execute(
                select(Admin).where(
                    or_(Admin.username == username, Admin.email == username),
                    Admin.is_deleted.is_(False),
                )
            )
            user = result.scalar_one_or_none()
        elif user_type == "tenant_admin":
            result = await self._service.db.execute(
                select(TenantAdmin).where(
                    or_(
                        TenantAdmin.username == username,
                        TenantAdmin.email == username,
                    ),
                    TenantAdmin.is_deleted.is_(False),
                )
            )
            user = result.scalar_one_or_none()
        elif user_type == "tenant_user":
            result = await self._service.db.execute(
                select(TenantUser).where(
                    or_(TenantUser.username == username, TenantUser.email == username),
                    TenantUser.is_deleted.is_(False),
                )
            )
            user = result.scalar_one_or_none()
        else:
            return

        if user:
            user.login_fail_count = (user.login_fail_count or 0) + 1
            user.last_fail_at = now
            if user.login_fail_count >= max_attempts:
                user.locked_until = now + timedelta(minutes=lockout_minutes)
            await self._service.db.commit()

    async def record_admin_login_failure(
        self,
        username: str,
        client_ip: str | None,
    ) -> None:
        await self.record_login_failure(
            username=username,
            client_ip=client_ip,
            user_type="admin",
        )

    async def is_account_locked(
        self,
        user_id: int,
        user_type: str = "admin",
    ) -> bool:
        if user_type == "admin":
            result = await self._service.db.execute(
                select(Admin.locked_until).where(Admin.id == user_id)
            )
        elif user_type == "tenant_admin":
            result = await self._service.db.execute(
                select(TenantAdmin.locked_until).where(TenantAdmin.id == user_id)
            )
        elif user_type == "tenant_user":
            result = await self._service.db.execute(
                select(TenantUser.locked_until).where(TenantUser.id == user_id)
            )
        else:
            return False

        locked_until = result.scalar_one_or_none()
        if locked_until is None:
            return False
        return (
            self._service._normalize_utc(locked_until) > self._service._utc_now_aware()
        )

    async def reset_login_failures(
        self,
        user_id: int,
        user_type: str = "admin",
    ) -> None:
        if user_type == "admin":
            result = await self._service.db.execute(
                select(Admin).where(Admin.id == user_id)
            )
        elif user_type == "tenant_admin":
            result = await self._service.db.execute(
                select(TenantAdmin).where(TenantAdmin.id == user_id)
            )
        elif user_type == "tenant_user":
            result = await self._service.db.execute(
                select(TenantUser).where(TenantUser.id == user_id)
            )
        else:
            return

        user = result.scalar_one_or_none()
        if user:
            user.login_fail_count = 0
            user.last_fail_at = None
            user.locked_until = None
            await self._service.db.commit()

    async def reset_admin_login_failures(self, admin_id: int) -> None:
        await self.reset_login_failures(admin_id, "admin")
