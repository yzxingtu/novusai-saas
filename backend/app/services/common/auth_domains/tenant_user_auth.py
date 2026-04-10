"""Tenant-user authentication domain for AuthService."""

from __future__ import annotations

import secrets
import string
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, or_, select

from app.core.i18n import _
from app.core.logging import LogManager
from app.core.security import TOKEN_SCOPE_TENANT_USER, TOKEN_TYPE_REFRESH
from app.enums import ErrorCode
from app.enums.common import ApprovalStatusEnum
from app.exceptions import AuthenticationException, BusinessException, ValidationException
from app.models import Tenant, TenantAdmin, TenantUser

if TYPE_CHECKING:
    from app.services.common.auth_service import AuthService

logger = LogManager.get_logger("auth")


class AuthTenantUserDomain:
    """Stable domain for tenant-user auth, registration, and password reset flows."""

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
        if not tenant_code and not tenant_id_from_ctx:
            self._service._log_auth_warning(
                "tenant_user.login.failed",
                identifier=self._service._mask_identifier(username),
                client_ip=client_ip,
                reason="tenant_domain_required",
            )
            raise AuthenticationException(message=_("auth.tenant_domain_required"))

        query = select(TenantUser).where(
            or_(
                TenantUser.username == username,
                TenantUser.email == username,
                TenantUser.phone == username,
            ),
            TenantUser.is_deleted.is_(False),
        )
        if tenant_code:
            query = query.join(Tenant, TenantUser.tenant_id == Tenant.id).where(
                Tenant.code == tenant_code,
                Tenant.is_active.is_(True),
                Tenant.is_deleted.is_(False),
            )
        elif tenant_id_from_ctx:
            query = query.where(TenantUser.tenant_id == tenant_id_from_ctx)

        result = await self._service.db.execute(query)
        results = result.scalars().all()

        if len(results) > 1:
            self._service._log_auth_warning(
                "tenant_user.login.failed",
                identifier=self._service._mask_identifier(username),
                tenant_code=tenant_code,
                client_ip=client_ip,
                reason="tenant_code_required",
            )
            raise AuthenticationException(
                message=_("auth.tenant_code_required"),
                data={"tenant_code_required": True},
            )

        user = results[0] if results else None
        if user is None:
            await self._service._record_login_failure(
                username,
                client_ip,
                "tenant_user",
                tenant_id=None,
            )
            self._service._log_auth_warning(
                "tenant_user.login.failed",
                identifier=self._service._mask_identifier(username),
                tenant_code=tenant_code,
                client_ip=client_ip,
                reason="user_not_found",
            )
            raise AuthenticationException(
                message=_("auth.credentials_invalid"),
                data={"captcha_required": False},
            )

        if await self._service._is_account_locked(user.id, "tenant_user"):
            self._service._log_auth_warning(
                "tenant_user.login.failed",
                user_id=user.id,
                username=user.username,
                tenant_id=user.tenant_id,
                client_ip=client_ip,
                reason="account_locked",
            )
            raise AuthenticationException(message=_("auth.account_locked"))

        if not user.is_active:
            self._service._log_auth_warning(
                "tenant_user.login.failed",
                user_id=user.id,
                username=user.username,
                tenant_id=user.tenant_id,
                client_ip=client_ip,
                reason="account_disabled",
            )
            raise AuthenticationException(message=_("auth.credentials_invalid"))

        captcha_enabled = await self._service._config_service.get_tenant_config(
            user.tenant_id,
            "user_login_captcha_enabled",
            default=True,
        )
        threshold = await self._service._config_service.get_tenant_config(
            user.tenant_id,
            "user_login_captcha_enable_threshold",
            default=0,
        )
        fail_count = user.login_fail_count or 0
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
                    "endpoint": "user",
                    "action": "login",
                    "identifier": self._service._mask_identifier(username),
                    "tenant_id": user.tenant_id,
                },
            )

        if not self._service._verify_password(password, user.password_hash):
            await self._service._record_login_failure(
                username,
                client_ip,
                "tenant_user",
                tenant_id=user.tenant_id,
            )
            self._service._log_auth_warning(
                "tenant_user.login.failed",
                user_id=user.id,
                username=user.username,
                tenant_id=user.tenant_id,
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

        await self._service._reset_login_failures(user.id, "tenant_user")
        return await self.issue_tokens(
            user=user,
            client_ip=client_ip,
            tenant_code=tenant_code,
            event="tenant_user.login.success",
        )

    async def issue_tokens(
        self,
        *,
        user: TenantUser,
        client_ip: str | None,
        tenant_code: str | None = None,
        event: str = "tenant_user.login.success",
    ) -> dict[str, Any]:
        user.last_login_at = self._service._utc_now_aware()
        user.last_login_ip = client_ip

        tokens = self._service._create_token_pair(
            user.id,
            scope=TOKEN_SCOPE_TENANT_USER,
            extra_claims={"tenant_id": user.tenant_id},
        )
        await self._service._record_active_tokens(
            "tenant_user",
            str(user.id),
            tokens["access_jti"],
            tokens["refresh_jti"],
        )
        self._service._log_auth_info(
            event,
            user_id=user.id,
            username=user.username,
            tenant_id=user.tenant_id,
            tenant_code=tenant_code,
            client_ip=client_ip,
        )
        return tokens

    async def resolve_login_tenant_id(
        self,
        *,
        tenant_code: str | None,
        tenant_id_from_ctx: int | None,
        identifier: str | None = None,
        client_ip: str | None = None,
        log_reason: str = "tenant_domain_required",
    ) -> int:
        if not tenant_code and not tenant_id_from_ctx:
            self._service._log_auth_warning(
                "tenant_user.login_code.failed",
                identifier=self._service._mask_identifier(identifier),
                client_ip=client_ip,
                reason=log_reason,
            )
            raise AuthenticationException(message=_("auth.tenant_domain_required"))

        tenant_id = tenant_id_from_ctx
        if not tenant_id and tenant_code:
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
            tenant_id = tenant.id

        if tenant_id is None:
            raise BusinessException(message=_("tenant.not_found"))
        return int(tenant_id)

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
        tenant_id_from_ctx: int | None = None,
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
            tenant_id_from_ctx=tenant_id_from_ctx,
            identifier=identifier,
            client_ip=client_ip,
        )
        await self.ensure_login_code_channel_enabled(tenant_id=tenant_id, channel=channel)

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
        tenant_id_from_ctx: int | None = None,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        normalized_email = (email or "").strip().lower() or None
        normalized_phone = (phone or "").strip() or None
        identifier = normalized_email or normalized_phone
        tenant_id = await self.resolve_login_tenant_id(
            tenant_code=tenant_code,
            tenant_id_from_ctx=tenant_id_from_ctx,
            identifier=identifier,
            client_ip=client_ip,
        )
        await self.ensure_login_code_channel_enabled(tenant_id=tenant_id, channel=channel)

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

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        user_id, _scope = await self._service._verify_token_with_scope(
            refresh_token,
            TOKEN_SCOPE_TENANT_USER,
            TOKEN_TYPE_REFRESH,
        )
        if user_id is None:
            self._service._log_auth_warning(
                "tenant_user.token.refresh.failed",
                reason="invalid_token",
            )
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        result = await self._service.db.execute(
            select(TenantUser).where(
                TenantUser.id == int(user_id),
                TenantUser.is_deleted.is_(False),
            )
        )
        user = result.scalar_one_or_none()

        if user is None:
            self._service._log_auth_warning(
                "tenant_user.token.refresh.failed",
                user_id=user_id,
                reason="user_not_found",
            )
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        if not user.is_active:
            self._service._log_auth_warning(
                "tenant_user.token.refresh.failed",
                user_id=user.id,
                username=user.username,
                tenant_id=user.tenant_id,
                reason="account_disabled",
            )
            raise AuthenticationException(message=_("auth.account_disabled"))

        tokens = self._service._create_token_pair(
            user.id,
            scope=TOKEN_SCOPE_TENANT_USER,
            extra_claims={"tenant_id": user.tenant_id},
        )
        await self._service._record_active_tokens(
            "tenant_user",
            str(user.id),
            tokens["access_jti"],
            tokens["refresh_jti"],
        )
        self._service._log_auth_info(
            "tenant_user.token.refresh.success",
            user_id=user.id,
            username=user.username,
            tenant_id=user.tenant_id,
        )
        return tokens

    async def change_password(
        self,
        user: TenantUser,
        old_password: str,
        new_password: str,
    ) -> None:
        if not self._service._verify_password(old_password, user.password_hash):
            raise BusinessException(
                message=_("auth.password_mismatch"),
                code=ErrorCode.OLD_PASSWORD_INCORRECT,
            )

        await self._service._validate_password_policy(
            new_password,
            tenant_id=user.tenant_id,
        )
        user.password_hash = self._service._get_password_hash(new_password)

    async def register(
        self,
        username: str,
        email: str,
        password: str,
        tenant_code: str | None = None,
        tenant_id_from_ctx: int | None = None,
        phone: str | None = None,
        nickname: str | None = None,
        client_ip: str | None = None,
        captcha_challenge_id: str | None = None,
        captcha_solution: str | None = None,
        captcha_provider_code: str | None = None,
    ) -> dict[str, Any]:
        tenant_id = tenant_id_from_ctx
        if not tenant_id and tenant_code:
            result = await self._service.db.execute(
                select(Tenant).where(
                    Tenant.code == tenant_code,
                    Tenant.is_deleted.is_(False),
                )
            )
            tenant = result.scalar_one_or_none()
            if tenant is None or not tenant.is_active:
                raise BusinessException(message=_("tenant.not_found"))
            tenant_id = tenant.id
        elif tenant_id:
            result = await self._service.db.execute(
                select(Tenant).where(
                    Tenant.id == tenant_id,
                    Tenant.is_deleted.is_(False),
                )
            )
            tenant = result.scalar_one_or_none()
            if tenant is None or not tenant.is_active:
                raise BusinessException(message=_("tenant.disabled"))

        if not tenant_id:
            raise BusinessException(
                message=_("tenant.not_found"),
                data={"tenant_code_required": True},
            )

        registration_enabled = await self._service._config_service.get_tenant_config(
            tenant_id,
            "tenant_allow_registration",
            default=False,
        )
        if not registration_enabled:
            raise BusinessException(message=_("auth.registration_disabled"))

        captcha_enabled = await self._service._config_service.get_tenant_config(
            tenant_id,
            "user_registration_captcha_enabled",
            default=True,
        )
        if captcha_enabled:
            try:
                await self._service._verify_captcha(
                    captcha_challenge_id,
                    captcha_solution,
                    captcha_provider_code,
                    {"ip": client_ip, "endpoint": "user", "action": "register"},
                )
            except AuthenticationException as exc:
                raise ValidationException(
                    message=exc.message,
                    errors=[exc.data] if exc.data else None,
                ) from exc

        from sqlalchemy.orm import selectinload as _selectinload

        from app.services.tenant.quota_service import QuotaService

        tenant_for_quota = (
            await self._service.db.execute(
                select(Tenant)
                .options(_selectinload(Tenant.tenant_plan))
                .where(Tenant.id == tenant_id)
            )
        ).scalar_one_or_none()
        if tenant_for_quota:
            quota_svc = QuotaService(self._service.db, tenant_for_quota)
            quota_check = await quota_svc.check_user_quota()
            if not quota_check.allowed:
                raise BusinessException(
                    message=quota_check.message or _("quota.users_exceeded"),
                )

        await self._service._validate_password_policy(password, tenant_id=tenant_id)

        existing = await self._service.db.execute(
            select(TenantUser).where(
                and_(
                    TenantUser.tenant_id == tenant_id,
                    TenantUser.username == username,
                    TenantUser.is_deleted.is_(False),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise BusinessException(message=_("auth.username_taken"))

        existing = await self._service.db.execute(
            select(TenantUser).where(
                and_(
                    TenantUser.tenant_id == tenant_id,
                    TenantUser.email == email,
                    TenantUser.is_deleted.is_(False),
                )
            )
        )
        if existing.scalar_one_or_none():
            raise BusinessException(message=_("auth.email_taken"))

        if phone:
            existing = await self._service.db.execute(
                select(TenantUser).where(
                    and_(
                        TenantUser.tenant_id == tenant_id,
                        TenantUser.phone == phone,
                        TenantUser.is_deleted.is_(False),
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise BusinessException(message=_("auth.phone_taken"))

        require_approval = await self._service._config_service.get_tenant_config(
            tenant_id,
            "tenant_registration_approval",
            default=False,
        )
        default_active = await self._service._config_service.get_tenant_config(
            tenant_id,
            "user_default_active",
            default=True,
        )
        default_role_id = await self._service._config_service.get_tenant_config(
            tenant_id,
            "user_default_role_id",
            default=0,
        )
        default_role_id = int(default_role_id) if default_role_id else 0

        if require_approval:
            approval_status = ApprovalStatusEnum.PENDING.value
            is_active = False
        else:
            approval_status = ApprovalStatusEnum.APPROVED.value
            is_active = default_active

        user = TenantUser(
            tenant_id=tenant_id,
            username=username,
            email=email,
            password_hash=self._service._get_password_hash(password),
            phone=phone,
            nickname=nickname or username,
            is_active=is_active,
            approval_status=approval_status,
            role_id=default_role_id if default_role_id > 0 else None,
        )
        self._service.db.add(user)
        await self._service.db.flush()

        logger.info(
            f"User registered: {username} (tenant={tenant_id}, "
            f"approval={approval_status}, active={is_active})"
        )

        if approval_status == ApprovalStatusEnum.PENDING.value:
            await self.notify_tenant_admins_pending(
                tenant_id=tenant_id,
                username=username,
                email=email,
            )

        result_data: dict[str, Any] = {
            "user_id": user.id,
            "username": user.username,
            "approval_status": approval_status,
            "is_active": is_active,
        }

        if approval_status == ApprovalStatusEnum.APPROVED.value and is_active:
            tokens = self._service._create_token_pair(
                user.id,
                scope=TOKEN_SCOPE_TENANT_USER,
                extra_claims={"tenant_id": tenant_id},
            )
            await self._service._record_active_tokens(
                "tenant_user",
                str(user.id),
                tokens["access_jti"],
                tokens["refresh_jti"],
            )
            result_data["tokens"] = tokens
        return result_data

    async def notify_tenant_admins_pending(
        self,
        tenant_id: int,
        username: str,
        email: str,
    ) -> None:
        from app.services.common.notification_service import notify

        admins = (
            (
                await self._service.db.execute(
                    select(TenantAdmin).where(
                        and_(
                            TenantAdmin.tenant_id == tenant_id,
                            TenantAdmin.is_active.is_(True),
                            TenantAdmin.is_deleted.is_(False),
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
        if not admins:
            return

        recipients = [("tenant_admin", admin.id) for admin in admins]
        await notify(
            self._service.db,
            template_code="biz.user_registration_pending",
            recipients=recipients,
            data={"username": username, "email": email},
            tenant_id=tenant_id,
        )

    async def update_profile(
        self,
        user: TenantUser,
        nickname: str | None = None,
        avatar: str | None = None,
        gender: int | None = None,
        phone: str | None = None,
        email: str | None = None,
    ) -> TenantUser:
        if email and email != user.email:
            existing = await self._service.db.execute(
                select(TenantUser).where(
                    and_(
                        TenantUser.tenant_id == user.tenant_id,
                        TenantUser.email == email,
                        TenantUser.id != user.id,
                        TenantUser.is_deleted.is_(False),
                    )
                )
            )
            if existing.scalar_one_or_none():
                raise BusinessException(message=_("auth.email_taken"))
            user.email = email

        if phone is not None and phone != user.phone:
            if phone:
                existing = await self._service.db.execute(
                    select(TenantUser).where(
                        and_(
                            TenantUser.tenant_id == user.tenant_id,
                            TenantUser.phone == phone,
                            TenantUser.id != user.id,
                            TenantUser.is_deleted.is_(False),
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    raise BusinessException(message=_("auth.phone_taken"))
            user.phone = phone

        if nickname is not None:
            user.nickname = nickname
        if avatar is not None:
            user.avatar = avatar
        if gender is not None:
            user.gender = gender

        return user

    async def request_password_reset(
        self,
        email: str,
        tenant_code: str | None = None,
        tenant_id_from_ctx: int | None = None,
    ) -> dict[str, Any]:
        tenant_id = tenant_id_from_ctx
        if not tenant_id and tenant_code:
            result = await self._service.db.execute(
                select(Tenant).where(
                    Tenant.code == tenant_code,
                    Tenant.is_deleted.is_(False),
                )
            )
            tenant = result.scalar_one_or_none()
            if tenant is None or not tenant.is_active:
                raise BusinessException(message=_("tenant.not_found"))
            tenant_id = tenant.id

        if not tenant_id:
            raise BusinessException(
                message=_("tenant.not_found"),
                data={"tenant_code_required": True},
            )

        rate_key = f"password_reset_rate:{tenant_id}:{email}"
        if await self._service._cache_get(rate_key):
            raise BusinessException(message=_("auth.reset_rate_limited"))

        result = await self._service.db.execute(
            select(TenantUser).where(
                and_(
                    TenantUser.tenant_id == tenant_id,
                    TenantUser.email == email,
                    TenantUser.is_deleted.is_(False),
                )
            )
        )
        user = result.scalar_one_or_none()
        if user is None:
            logger.warning(
                f"Password reset requested for non-existent email: {email}"
            )
            return {"message": _("auth.reset_code_sent")}

        code = "".join(secrets.choice(string.digits) for _ in range(6))
        code_key = f"password_reset:{tenant_id}:{email}"
        await self._service._cache_set(
            code_key,
            {"code": code, "user_id": user.id},
            ttl=self._service.RESET_CODE_TTL,
        )
        await self._service._cache_set(
            rate_key,
            True,
            ttl=self._service.RESET_RATE_LIMIT_TTL,
        )

        expire_minutes = self._service.RESET_CODE_TTL // 60
        try:
            from app.services.common.email_templates import (
                render_verification_code_email,
            )
            from app.tasks.email import send_email_task

            user_name = (user.nickname or user.username or "").strip()
            subject, html_body, text_body = render_verification_code_email(
                user_name=user_name or email,
                code=code,
                expire_minutes=expire_minutes,
            )
            send_email_task.delay(
                to=[email],
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                triggered_by="password_reset",
                tenant_id=tenant_id,
            )
        except Exception as exc:
            logger.warning(
                "Failed to queue verification code email: user_id={} tenant_id={} error={}",
                user.id,
                tenant_id,
                str(exc),
            )

        logger.info(
            f"Password reset code generated for user {user.id} (tenant={tenant_id})"
        )
        return {"message": _("auth.reset_code_sent")}

    async def reset_password(
        self,
        email: str,
        code: str,
        new_password: str,
        tenant_code: str | None = None,
        tenant_id_from_ctx: int | None = None,
    ) -> None:
        tenant_id = tenant_id_from_ctx
        if not tenant_id and tenant_code:
            result = await self._service.db.execute(
                select(Tenant).where(
                    Tenant.code == tenant_code,
                    Tenant.is_deleted.is_(False),
                )
            )
            tenant = result.scalar_one_or_none()
            if tenant is None or not tenant.is_active:
                raise BusinessException(message=_("tenant.not_found"))
            tenant_id = tenant.id

        if not tenant_id:
            raise BusinessException(
                message=_("tenant.not_found"),
                data={"tenant_code_required": True},
            )

        code_key = f"password_reset:{tenant_id}:{email}"
        stored = await self._service._cache_get(code_key)
        if not stored or not isinstance(stored, dict):
            raise BusinessException(message=_("auth.reset_code_invalid"))
        if stored.get("code") != code:
            raise BusinessException(message=_("auth.reset_code_invalid"))

        user_id = stored.get("user_id")
        if not user_id:
            raise BusinessException(message=_("auth.reset_code_invalid"))

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
            raise BusinessException(message=_("auth.reset_code_invalid"))

        await self._service._validate_password_policy(
            new_password,
            tenant_id=tenant_id,
        )
        user.password_hash = self._service._get_password_hash(new_password)
        await self._service._cache_delete(code_key)

        logger.info(f"Password reset completed for user {user.id} (tenant={tenant_id})")
