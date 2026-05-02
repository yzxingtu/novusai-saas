"""Tenant-admin authentication domain for AuthService."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.i18n import _
from app.core.security import (
    TOKEN_SCOPE_TENANT_ADMIN,
    TOKEN_TYPE_REFRESH,
)
from app.enums import ErrorCode
from app.exceptions import AuthenticationException, BusinessException, NotFoundException
from app.models import Admin, Tenant, TenantAdmin

if TYPE_CHECKING:
    from app.services.common.auth_service import AuthService


class AuthTenantAdminDomain:
    """Stable domain for tenant-admin auth and impersonation flows."""

    def __init__(self, service: AuthService) -> None:
        self._service = service

    async def get_profile_flags(
        self,
        tenant_admin: TenantAdmin,
    ) -> dict[str, Any]:
        tenant_result = await self._service.db.execute(
            select(Tenant)
            .where(Tenant.id == tenant_admin.tenant_id)
            .options(selectinload(Tenant.tenant_plan))
        )
        tenant = tenant_result.scalar_one_or_none()
        plan = tenant.tenant_plan if tenant is not None else None
        has_plan = (
            tenant is not None
            and bool(getattr(tenant, "is_active", False))
            and tenant.plan_id is not None
            and plan is not None
            and bool(getattr(plan, "is_active", False))
        )
        plan_name = None
        if has_plan and plan:
            plan_name = plan.name
        return {"has_plan": has_plan, "plan_name": plan_name}

    async def issue_login_tokens(
        self,
        tenant_admin: TenantAdmin,
        *,
        tenant_code: str | None = None,
        client_ip: str | None = None,
        log_event: str = "tenant_admin.login.success",
    ) -> dict[str, Any]:
        tenant_admin.last_login_at = self._service._utc_now_aware()
        tenant_admin.last_login_ip = client_ip

        tenant_result = await self._service.db.execute(
            select(Tenant).where(Tenant.id == tenant_admin.tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()

        if tenant is None or not tenant.is_active:
            self._service._log_auth_warning(
                log_event.replace(".success", ".failed"),
                user_id=tenant_admin.id,
                username=tenant_admin.username,
                tenant_id=tenant_admin.tenant_id,
                client_ip=client_ip,
                reason="tenant_disabled",
            )
            raise AuthenticationException(message=_("tenant.disabled"))

        session_timeout = await self._service._config_service.get_tenant_config(
            tenant_admin.tenant_id,
            "tenant_session_timeout",
            default=None,
        )
        if not session_timeout:
            session_timeout = await self._service._config_service.get_platform_config(
                "session_timeout_minutes",
                default=120,
            )

        extra_claims = {"tenant_id": tenant_admin.tenant_id}
        access_token, access_jti = self._service._create_access_token(
            tenant_admin.id,
            scope=TOKEN_SCOPE_TENANT_ADMIN,
            expires_delta=timedelta(minutes=session_timeout),
            extra_claims=extra_claims,
        )
        refresh_token, refresh_jti = self._service._create_refresh_token(
            tenant_admin.id,
            scope=TOKEN_SCOPE_TENANT_ADMIN,
            extra_claims=extra_claims,
        )
        await self._service._record_active_tokens(
            "tenant_admin",
            str(tenant_admin.id),
            access_jti,
            refresh_jti,
        )

        self._service._log_auth_info(
            log_event,
            user_id=tenant_admin.id,
            username=tenant_admin.username,
            tenant_id=tenant_admin.tenant_id,
            tenant_code=tenant.code if tenant else tenant_code,
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
        tenant_code: str | None = None,
        tenant_id_from_ctx: int | None = None,
        client_ip: str | None = None,
        captcha_challenge_id: str | None = None,
        captcha_solution: str | None = None,
        captcha_provider_code: str | None = None,
    ) -> dict[str, Any]:
        if not tenant_code and not tenant_id_from_ctx:
            self._service._log_auth_warning(
                "tenant_admin.login.failed",
                identifier=self._service._mask_identifier(username),
                client_ip=client_ip,
                reason="tenant_domain_required",
            )
            raise AuthenticationException(message=_("auth.tenant_domain_required"))

        query = select(TenantAdmin).where(
            or_(
                TenantAdmin.username == username,
                TenantAdmin.email == username,
            ),
            TenantAdmin.is_deleted.is_(False),
        )

        if tenant_code:
            query = query.join(Tenant, TenantAdmin.tenant_id == Tenant.id).where(
                Tenant.code == tenant_code,
                Tenant.is_active.is_(True),
                Tenant.is_deleted.is_(False),
            )
        elif tenant_id_from_ctx:
            query = query.where(TenantAdmin.tenant_id == tenant_id_from_ctx)

        result = await self._service.db.execute(query)
        results = result.scalars().all()

        if len(results) > 1:
            self._service._log_auth_warning(
                "tenant_admin.login.failed",
                identifier=self._service._mask_identifier(username),
                tenant_code=tenant_code,
                client_ip=client_ip,
                reason="tenant_code_required",
            )
            raise AuthenticationException(
                message=_("auth.tenant_code_required"),
                data={"tenant_code_required": True},
            )

        tenant_admin = results[0] if results else None
        if tenant_admin is None:
            await self._service._record_login_failure(
                username,
                client_ip,
                "tenant_admin",
                tenant_id=None,
            )
            self._service._log_auth_warning(
                "tenant_admin.login.failed",
                identifier=self._service._mask_identifier(username),
                tenant_code=tenant_code,
                client_ip=client_ip,
                reason="user_not_found",
            )
            raise AuthenticationException(
                message=_("auth.credentials_invalid"),
                data={"captcha_required": False},
            )

        if await self._service._is_account_locked(tenant_admin.id, "tenant_admin"):
            self._service._log_auth_warning(
                "tenant_admin.login.failed",
                user_id=tenant_admin.id,
                username=tenant_admin.username,
                tenant_id=tenant_admin.tenant_id,
                client_ip=client_ip,
                reason="account_locked",
            )
            raise AuthenticationException(message=_("auth.account_locked"))

        if not tenant_admin.is_active:
            self._service._log_auth_warning(
                "tenant_admin.login.failed",
                user_id=tenant_admin.id,
                username=tenant_admin.username,
                tenant_id=tenant_admin.tenant_id,
                client_ip=client_ip,
                reason="account_disabled",
            )
            raise AuthenticationException(message=_("auth.credentials_invalid"))

        captcha_enabled = await self._service._config_service.get_tenant_config(
            tenant_admin.tenant_id,
            "tenant_captcha_enabled",
            default=True,
        )
        threshold = await self._service._config_service.get_tenant_config(
            tenant_admin.tenant_id,
            "tenant_captcha_enable_threshold",
            default=2,
        )
        fail_count = tenant_admin.login_fail_count or 0
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
                    "endpoint": "tenant",
                    "action": "login",
                    "identifier": self._service._mask_identifier(username),
                    "tenant_id": tenant_admin.tenant_id,
                },
            )

        if not self._service._verify_password(password, tenant_admin.password_hash):
            await self._service._record_login_failure(
                username,
                client_ip,
                "tenant_admin",
                tenant_id=tenant_admin.tenant_id,
            )
            self._service._log_auth_warning(
                "tenant_admin.login.failed",
                user_id=tenant_admin.id,
                username=tenant_admin.username,
                tenant_id=tenant_admin.tenant_id,
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

        await self._service._reset_login_failures(tenant_admin.id, "tenant_admin")
        return await self.issue_login_tokens(
            tenant_admin,
            tenant_code=tenant_code,
            client_ip=client_ip,
        )

    async def authenticate_by_dev_bootstrap(
        self,
        bootstrap_secret: str,
        *,
        request_host: str | None,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        normalized_host = self._service._assert_dev_bootstrap_enabled(
            "tenant_admin",
            request_host,
        )
        self._service._assert_dev_bootstrap_secret(
            scope="tenant_admin",
            provided_secret=bootstrap_secret,
            expected_secret=settings.DEV_TENANT_BOOTSTRAP_SECRET,
            request_host=normalized_host,
        )

        identifier = settings.DEV_TENANT_BOOTSTRAP_USERNAME.strip()
        tenant_code = settings.DEV_TENANT_BOOTSTRAP_TENANT_CODE.strip()
        if not identifier or not tenant_code:
            self._service._log_auth_warning(
                "tenant_admin.dev_bootstrap.failed",
                reason="target_not_configured",
                has_identifier=bool(identifier),
                has_tenant_code=bool(tenant_code),
                request_host=normalized_host,
            )
            raise NotFoundException()

        tenant_result = await self._service.db.execute(
            select(Tenant).where(
                Tenant.code == tenant_code,
                Tenant.is_deleted.is_(False),
            )
        )
        tenant = tenant_result.scalar_one_or_none()
        if tenant is None or not tenant.is_active:
            self._service._log_auth_warning(
                "tenant_admin.dev_bootstrap.failed",
                tenant_code=tenant_code,
                request_host=normalized_host,
                reason="tenant_disabled",
            )
            raise AuthenticationException(message=_("tenant.disabled"))

        result = await self._service.db.execute(
            select(TenantAdmin).where(
                or_(
                    TenantAdmin.username == identifier,
                    TenantAdmin.email == identifier,
                ),
                TenantAdmin.tenant_id == tenant.id,
                TenantAdmin.is_deleted.is_(False),
            )
        )
        tenant_admin = result.scalar_one_or_none()
        if tenant_admin is None:
            self._service._log_auth_warning(
                "tenant_admin.dev_bootstrap.failed",
                identifier=self._service._mask_identifier(identifier),
                tenant_code=tenant_code,
                request_host=normalized_host,
                reason="user_not_found",
            )
            raise AuthenticationException(message=_("auth.credentials_invalid"))

        if not tenant_admin.is_active:
            self._service._log_auth_warning(
                "tenant_admin.dev_bootstrap.failed",
                user_id=tenant_admin.id,
                username=tenant_admin.username,
                tenant_id=tenant_admin.tenant_id,
                tenant_code=tenant_code,
                request_host=normalized_host,
                reason="account_disabled",
            )
            raise AuthenticationException(message=_("auth.account_disabled"))

        return await self.issue_login_tokens(
            tenant_admin,
            tenant_code=tenant_code,
            client_ip=client_ip,
            log_event="tenant_admin.dev_bootstrap.success",
        )

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        admin_id, _scope = await self._service._verify_token_with_scope(
            refresh_token,
            TOKEN_SCOPE_TENANT_ADMIN,
            TOKEN_TYPE_REFRESH,
        )
        if admin_id is None:
            self._service._log_auth_warning(
                "tenant_admin.token.refresh.failed",
                reason="invalid_token",
            )
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        result = await self._service.db.execute(
            select(TenantAdmin).where(
                TenantAdmin.id == int(admin_id),
                TenantAdmin.is_deleted.is_(False),
            )
        )
        tenant_admin = result.scalar_one_or_none()

        if tenant_admin is None:
            self._service._log_auth_warning(
                "tenant_admin.token.refresh.failed",
                user_id=admin_id,
                reason="user_not_found",
            )
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        if not tenant_admin.is_active:
            self._service._log_auth_warning(
                "tenant_admin.token.refresh.failed",
                user_id=tenant_admin.id,
                username=tenant_admin.username,
                tenant_id=tenant_admin.tenant_id,
                reason="account_disabled",
            )
            raise AuthenticationException(message=_("auth.account_disabled"))

        tokens = self._service._create_token_pair(
            tenant_admin.id,
            scope=TOKEN_SCOPE_TENANT_ADMIN,
            extra_claims={"tenant_id": tenant_admin.tenant_id},
        )
        await self._service._record_active_tokens(
            "tenant_admin",
            str(tenant_admin.id),
            tokens["access_jti"],
            tokens["refresh_jti"],
        )
        self._service._log_auth_info(
            "tenant_admin.token.refresh.success",
            user_id=tenant_admin.id,
            username=tenant_admin.username,
            tenant_id=tenant_admin.tenant_id,
        )
        return tokens

    async def change_password(
        self,
        tenant_admin: TenantAdmin,
        old_password: str,
        new_password: str,
    ) -> None:
        if not self._service._verify_password(old_password, tenant_admin.password_hash):
            raise BusinessException(
                message=_("auth.password_mismatch"),
                code=ErrorCode.OLD_PASSWORD_INCORRECT,
            )

        await self._service._validate_password_policy(
            new_password,
            tenant_id=tenant_admin.tenant_id,
        )
        tenant_admin.password_hash = self._service._get_password_hash(new_password)

    async def update_profile(
        self,
        tenant_admin: TenantAdmin,
        profile_data: dict[str, Any],
    ) -> TenantAdmin:
        for field, value in profile_data.items():
            setattr(tenant_admin, field, value)

        try:
            await self._service.db.flush()
        except Exception as exc:
            await self._service.db.rollback()
            err_msg = str(exc).lower()
            if "unique" in err_msg and "email" in err_msg:
                raise BusinessException(message=_("auth.email_already_exists")) from exc
            raise

        await self._service.db.refresh(tenant_admin)
        return tenant_admin

    async def impersonate(
        self,
        impersonate_token: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        payload = await self._service._verify_impersonate_token(
            impersonate_token,
            TOKEN_SCOPE_TENANT_ADMIN,
        )
        if payload is None:
            self._service._log_auth_warning(
                "tenant_admin.impersonate.failed",
                reason="invalid_token",
            )
            raise AuthenticationException(message=_("auth.impersonate_token_invalid"))

        admin_id = int(payload["sub"]) if payload.get("sub") else None
        target_tenant_id = payload.get("target_tenant_id")
        target_role_id = payload.get("target_role_id")

        if admin_id is None:
            self._service._log_auth_warning(
                "tenant_admin.impersonate.failed",
                reason="missing_admin_id",
            )
            raise AuthenticationException(message=_("auth.impersonate_token_invalid"))

        tenant_result = await self._service.db.execute(
            select(Tenant).where(
                Tenant.id == target_tenant_id,
                Tenant.is_deleted.is_(False),
            )
        )
        tenant = tenant_result.scalar_one_or_none()
        if tenant is None or not tenant.is_active:
            self._service._log_auth_warning(
                "tenant_admin.impersonate.failed",
                admin_id=admin_id,
                target_tenant_id=target_tenant_id,
                reason="tenant_disabled",
            )
            raise AuthenticationException(message=_("tenant.disabled"))

        owner_result = await self._service.db.execute(
            select(TenantAdmin).where(
                TenantAdmin.tenant_id == target_tenant_id,
                TenantAdmin.is_owner.is_(True),
                TenantAdmin.is_deleted.is_(False),
            )
        )
        tenant_owner = owner_result.scalar_one_or_none()
        if tenant_owner is None:
            self._service._log_auth_warning(
                "tenant_admin.impersonate.failed",
                admin_id=admin_id,
                target_tenant_id=target_tenant_id,
                reason="tenant_owner_not_found",
            )
            raise NotFoundException(message=_("tenant.owner_not_found"))

        platform_admin_result = await self._service.db.execute(
            select(Admin).where(
                Admin.id == admin_id,
                Admin.is_deleted.is_(False),
            )
        )
        platform_admin = platform_admin_result.scalar_one_or_none()
        platform_admin_username = (
            platform_admin.username if platform_admin else "unknown"
        )

        extra_claims: dict[str, Any] = {
            "tenant_id": target_tenant_id,
            "impersonated_by": admin_id,
        }
        if target_role_id:
            extra_claims["impersonate_role_id"] = target_role_id

        tokens = self._service._create_token_pair(
            tenant_owner.id,
            scope=TOKEN_SCOPE_TENANT_ADMIN,
            extra_claims=extra_claims,
        )
        await self._service._record_active_tokens(
            "tenant_admin",
            str(tenant_owner.id),
            tokens["access_jti"],
            tokens["refresh_jti"],
        )

        audit_info = {
            "admin_id": admin_id,
            "admin_username": platform_admin_username,
            "target_tenant_id": target_tenant_id,
            "target_tenant_code": tenant.code,
            "tenant_owner_id": tenant_owner.id,
            "target_role_id": target_role_id,
        }

        self._service._log_auth_info(
            "tenant_admin.impersonate.success",
            admin_id=admin_id,
            admin_username=platform_admin_username,
            target_tenant_id=target_tenant_id,
            target_tenant_code=tenant.code,
            tenant_owner_id=tenant_owner.id,
            target_role_id=target_role_id,
        )
        return tokens, audit_info
