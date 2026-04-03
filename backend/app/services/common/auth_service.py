"""
认证服务 / Authentication Service

提供平台管理员、企业管理员、企业用户的认证逻辑
Provides authentication logic for platform admins, tenant admins and tenant users.
"""

import secrets
import string
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.captcha.service import captcha_service
from app.configs.service import ConfigService
from app.core.config import settings
from app.core.i18n import _
from app.core.logging import LogManager
from app.core.redis import cache_delete, cache_get, cache_set, get_redis_client
from app.core.security import (
    ACTIVE_TOKENS_PREFIX,
    TOKEN_SCOPE_ADMIN,
    TOKEN_SCOPE_TENANT_ADMIN,
    TOKEN_SCOPE_TENANT_USER,
    TOKEN_TYPE_REFRESH,
    _decode_token_no_blacklist,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    get_password_hash,
    revoke_token,
    verify_impersonate_token,
    verify_password,
    verify_token_with_scope,
)
from app.enums import ErrorCode
from app.enums.common import ApprovalStatusEnum
from app.exceptions import (
    AuthenticationException,
    BusinessException,
    NotFoundException,
    ValidationException,
)
from app.models import Admin, Tenant, TenantAdmin, TenantUser

logger = LogManager.get_logger("auth")


class AuthService:
    """
    认证服务 / Authentication service.

    提供：
    - 平台管理员认证 (Admin)
    - 企业管理员认证 (TenantAdmin)
    - 企业用户认证 (TenantUser)
    - Token 刷新
    - 密码修改
    """

    def __init__(self, db: AsyncSession):
        """
        初始化服务 / Initialize service.

        Args:
            db: 异步数据库会话
        """
        self.db = db
        self._config_service = ConfigService(db)

    @staticmethod
    def _mask_identifier(identifier: str | None) -> str:
        if not identifier:
            return ""
        value = identifier.strip()
        if len(value) <= 2:
            return "*" * len(value)
        if len(value) <= 6:
            return f"{value[:1]}***{value[-1:]}"
        return f"{value[:2]}***{value[-2:]}"

    @staticmethod
    def _format_auth_fields(**fields: Any) -> str:
        parts: list[str] = []
        for key, value in fields.items():
            if value is None or value == "":
                continue
            normalized = str(value).replace("\r", r"\r").replace("\n", r"\n")
            parts.append(f"{key}={normalized}")
        return " | ".join(parts)

    @classmethod
    def _log_auth_info(cls, event: str, **fields: Any) -> None:
        details = cls._format_auth_fields(**fields)
        logger.info(f"{event} | {details}" if details else event)

    @classmethod
    def _log_auth_warning(cls, event: str, **fields: Any) -> None:
        details = cls._format_auth_fields(**fields)
        logger.warning(f"{event} | {details}" if details else event)

    @staticmethod
    def _utc_now_aware() -> datetime:
        """返回认证安全字段使用的带时区 UTC 时间 / Return an aware UTC datetime for auth security fields."""
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_utc(value: datetime) -> datetime:
        """比较前统一归一化为带时区 UTC 时间 / Normalize naive or aware datetimes to aware UTC before comparison."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    async def _record_active_tokens(
        self,
        user_type: str,
        user_id: str,
        access_jti: str,
        refresh_jti: str,
    ) -> None:
        """
        记录活跃 Token 到 Redis（用于登出/强制下线时吊销） / Record active tokens for logout/force-logout revoke.
        Key: active_tokens:{user_type}:{user_id}, Hash: {access_jti: refresh_jti}, TTL=7d
        """
        try:
            client = get_redis_client()
            key = f"{ACTIVE_TOKENS_PREFIX}{user_type}:{user_id}"
            await client.hset(key, access_jti, refresh_jti)
            ttl_days = settings.REFRESH_TOKEN_EXPIRE_DAYS
            await client.expire(key, ttl_days * 24 * 3600)
        except Exception:
            pass  # Redis 不可用时静默失败

    async def revoke_on_logout(
        self,
        access_token: str,
        user_type: str,
        user_id: str,
    ) -> None:
        """
        登出时吊销 Token / Revoke tokens on logout.
        从 active_tokens 获取 refresh_jti，吊销 access 和 refresh，并从 Hash 中移除。
        """
        payload = _decode_token_no_blacklist(access_token)
        if not payload or not payload.get("jti"):
            self._log_auth_warning(
                "auth.logout.skipped",
                user_type=user_type,
                user_id=user_id,
                reason="missing_jti",
            )
            return  # 旧 Token 无 jti，跳过
        access_jti = payload["jti"]
        exp = payload.get("exp")
        from time import time

        access_ttl = max(1, int(exp - time())) if exp else 86400

        try:
            client = get_redis_client()
            key = f"{ACTIVE_TOKENS_PREFIX}{user_type}:{user_id}"
            refresh_jti = await client.hget(key, access_jti)
            await revoke_token(access_jti, access_ttl)
            if refresh_jti:
                refresh_ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
                await revoke_token(refresh_jti, refresh_ttl)
            await client.hdel(key, access_jti)
            self._log_auth_info(
                "auth.logout.success",
                user_type=user_type,
                user_id=user_id,
                revoked_refresh=bool(refresh_jti),
            )
        except Exception as exc:
            self._log_auth_warning(
                "auth.logout.failed",
                user_type=user_type,
                user_id=user_id,
                reason="token_revoke_error",
                error_type=type(exc).__name__,
            )

    async def force_logout(
        self,
        user_type: str,
        user_id: int,
        tenant_id: int | None = None,
    ) -> None:
        """
        强制下线用户：吊销所有 Token、清除 Presence、发送 Socket.IO 事件
        Force logout user: revoke all tokens, clear presence, emit Socket.IO event.

        Args:
            user_type: admin / tenant_admin / tenant_user
            user_id: 用户 ID / User ID
            tenant_id: 企业 ID（admin 为 None；tenant_admin/tenant_user 必填）
        """
        from app.core.redis import get_redis_client
        from app.core.sio_bridge import emit_force_logout
        from app.sio.presence import PresenceManager

        user_id_str = str(user_id)
        key = f"{ACTIVE_TOKENS_PREFIX}{user_type}:{user_id_str}"
        revoked_sessions = 0
        try:
            client = get_redis_client()
            pairs = await client.hgetall(key)
            if pairs:
                revoked_sessions = len(pairs)
                for access_jti, refresh_jti in pairs.items():
                    # 使用剩余 TTL 作为吊销 TTL（简化：用 refresh 的 7 天）
                    access_ttl = 86400  # access 最多 24h
                    refresh_ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
                    await revoke_token(access_jti, access_ttl)
                    if refresh_jti:
                        await revoke_token(refresh_jti, refresh_ttl)
                await client.delete(key)
        except Exception as exc:
            self._log_auth_warning(
                "auth.force_logout.revoke_failed",
                user_type=user_type,
                user_id=user_id,
                tenant_id=tenant_id,
                reason="token_revoke_error",
                error_type=type(exc).__name__,
            )

        # 清除在线状态 / Clear presence
        try:
            await PresenceManager.set_offline(user_type, user_id, tenant_id=tenant_id)
        except Exception as exc:
            self._log_auth_warning(
                "auth.force_logout.presence_cleanup_failed",
                user_type=user_type,
                user_id=user_id,
                tenant_id=tenant_id,
                error_type=type(exc).__name__,
            )

        # 向对应用户类型所在 namespace 发送 force_logout / Emit to user's namespace only
        try:
            await emit_force_logout(user_id, user_type)
        except Exception as exc:
            self._log_auth_warning(
                "auth.force_logout.emit_failed",
                user_type=user_type,
                user_id=user_id,
                tenant_id=tenant_id,
                error_type=type(exc).__name__,
            )
            raise

        self._log_auth_info(
            "auth.force_logout.success",
            user_type=user_type,
            user_id=user_id,
            tenant_id=tenant_id,
            revoked_sessions=revoked_sessions,
        )

    # ==================== 密码策略验证 / Password policy validation ====================

    async def _validate_password_policy(
        self,
        password: str,
        tenant_id: int | None = None,
    ) -> None:
        """
        验证密码是否符合安全策略 / Validate password against security policy.

        Args:
            password: 待验证的密码
            tenant_id: 企业 ID（企业端优先使用企业配置，回退到平台配置）

        Raises:
            BusinessException: 密码不符合策略要求
        """
        # 获取密码策略配置（企业端优先使用企业配置） / Load policy: tenant overrides first
        if tenant_id:
            min_length = await self._config_service.get_tenant_config(
                tenant_id, "tenant_password_min_length", default=None
            )
            complexity = await self._config_service.get_tenant_config(
                tenant_id, "tenant_password_complexity", default=None
            )
        else:
            min_length = None
            complexity = None
        # 回退到平台配置 / Fallback to platform config
        if not min_length:
            min_length = await self._config_service.get_platform_config(
                "password_min_length", default=8
            )
        if not complexity:
            complexity = await self._config_service.get_platform_config(
                "password_complexity", default="medium"
            )

        # 验证密码长度 / Validate min length
        if len(password) < min_length:
            raise BusinessException(
                message=_("auth.password_too_short", min_length=min_length)
            )

        # 验证密码复杂度 / Validate complexity tier
        if complexity == "low":
            # 仅检查长度（已在上面检查） / Length only (already enforced)
            pass
        elif complexity == "medium":
            # 必须包含字母和数字 / Require letters and digits
            has_letter = any(c.isalpha() for c in password)
            has_digit = any(c.isdigit() for c in password)
            if not (has_letter and has_digit):
                raise BusinessException(message=_("auth.password_complexity_medium"))
        elif complexity == "high":
            # 必须包含字母、数字和特殊字符 / Require letters, digits, special chars
            has_letter = any(c.isalpha() for c in password)
            has_digit = any(c.isdigit() for c in password)
            has_special = any(not c.isalnum() for c in password)
            if not (has_letter and has_digit and has_special):
                raise BusinessException(message=_("auth.password_complexity_high"))

    # ==================== 平台管理员认证 / Platform admin authentication ====================

    async def authenticate_admin(
        self,
        username: str,
        password: str,
        client_ip: str | None = None,
        captcha_challenge_id: str | None = None,
        captcha_solution: str | None = None,
        captcha_provider_code: str | None = None,
    ) -> dict[str, Any]:
        """
        平台管理员认证 / Platform admin authentication.

        Args:
            username: 用户名或邮箱
            password: 密码
            client_ip: 客户端 IP
            captcha_challenge_id: 验证码挑战ID
            captcha_solution: 验证码解决方案
            captcha_provider_code: 验证码提供程序代码

        Returns:
            包含 tokens 的字典

        Raises:
            AuthenticationException: 认证失败
        """
        # 查询管理员 / Load admin by identifier
        result = await self.db.execute(
            select(Admin).where(
                or_(Admin.username == username, Admin.email == username),
                Admin.is_deleted.is_(False),
            )
        )
        admin = result.scalar_one_or_none()

        # 检查账户是否存在 / Check account exists
        if admin is None:
            await self._record_admin_login_failure(username, client_ip)
            self._log_auth_warning(
                "admin.login.failed",
                identifier=self._mask_identifier(username),
                client_ip=client_ip,
                reason="user_not_found",
            )
            captcha_enabled = await self._config_service.get_platform_config(
                "login_captcha_enabled", default=True
            )
            threshold = await self._config_service.get_platform_config(
                "captcha_enable_threshold_admin", default=2
            )
            captcha_required = captcha_enabled and threshold == 0
            raise AuthenticationException(
                message=_("auth.credentials_invalid"),
                data={"captcha_required": captcha_required},
            )

        # 检查账户锁定状态 / Check lockout window
        if await self._is_account_locked(admin.id, "admin"):
            self._log_auth_warning(
                "admin.login.failed",
                user_id=admin.id,
                username=admin.username,
                client_ip=client_ip,
                reason="account_locked",
            )
            raise AuthenticationException(message=_("auth.account_locked"))

        # 检查账户状态（在密码验证之前，防止通过不同错误消息泄漏密码正确性） / Check active before pwd (avoid oracle)
        if not admin.is_active:
            self._log_auth_warning(
                "admin.login.failed",
                user_id=admin.id,
                username=admin.username,
                client_ip=client_ip,
                reason="account_disabled",
            )
            raise AuthenticationException(message=_("auth.credentials_invalid"))

        captcha_enabled = await self._config_service.get_platform_config(
            "login_captcha_enabled", default=True
        )
        threshold = await self._config_service.get_platform_config(
            "captcha_enable_threshold_admin", default=2
        )
        fail_count = admin.login_fail_count or 0
        captcha_required = captcha_enabled and (
            threshold == 0 or fail_count >= threshold
        )
        if captcha_required:
            await self._verify_captcha(
                captcha_challenge_id,
                captcha_solution,
                captcha_provider_code,
                {
                    "ip": client_ip,
                    "endpoint": "admin",
                    "action": "login",
                    "identifier": self._mask_identifier(username),
                },
            )

        # 验证密码 / Verify password hash
        if not verify_password(password, admin.password_hash):
            # 记录登录失败 / Record failed attempt
            await self._record_admin_login_failure(username, client_ip)
            self._log_auth_warning(
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

        # 登录成功，重置失败计数 / Success: reset fail counter
        await self._reset_admin_login_failures(admin.id)

        # 更新登录信息 / Update last login fields
        admin.last_login_at = self._utc_now_aware()
        admin.last_login_ip = client_ip

        # 生成 Token（应用会话配置）
        from datetime import timedelta

        session_timeout = await self._config_service.get_platform_config(
            "session_timeout_minutes", default=120
        )
        access_token, access_jti = create_access_token(
            admin.id,
            scope=TOKEN_SCOPE_ADMIN,
            expires_delta=timedelta(minutes=session_timeout),
        )
        refresh_token, refresh_jti = create_refresh_token(
            admin.id, scope=TOKEN_SCOPE_ADMIN
        )

        await self._record_active_tokens(
            "admin", str(admin.id), access_jti, refresh_jti
        )

        self._log_auth_info(
            "admin.login.success",
            user_id=admin.id,
            username=admin.username,
            client_ip=client_ip,
        )

        tokens = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

        return tokens

    # ==================== 登录安全辅助方法 / Login security helpers ====================

    async def _record_login_failure(
        self,
        username: str,
        client_ip: str | None,
        user_type: str = "admin",
        tenant_id: int | None = None,
    ) -> None:
        """
        记录登录失败 / Record login failure.

        Args:
            username: 登录用户名
            client_ip: 客户端IP
            user_type: 用户类型 (admin/tenant_admin/tenant_user)
            tenant_id: 企业 ID（企业端使用企业配置）
        """
        _ = client_ip
        from datetime import timedelta

        # 获取登录失败配置（企业端优先使用企业配置，回退到平台配置） / Lockout config: tenant first, else platform
        if tenant_id and user_type in ("tenant_admin", "tenant_user"):
            max_attempts = await self._config_service.get_tenant_config(
                tenant_id, "tenant_login_max_attempts", default=5
            )
            lockout_minutes = await self._config_service.get_tenant_config(
                tenant_id, "tenant_login_lockout_minutes", default=30
            )
        else:
            max_attempts = await self._config_service.get_platform_config(
                "login_max_attempts", default=5
            )
            lockout_minutes = await self._config_service.get_platform_config(
                "login_lockout_minutes", default=30
            )

        now = self._utc_now_aware()

        if user_type == "admin":
            # 处理平台管理员 / Branch: platform admin
            result = await self.db.execute(
                select(Admin).where(
                    or_(Admin.username == username, Admin.email == username),
                    Admin.is_deleted.is_(False),
                )
            )
            user = result.scalar_one_or_none()
        elif user_type == "tenant_admin":
            # 处理企业管理员 / Branch: tenant admin
            result = await self.db.execute(
                select(TenantAdmin).where(
                    or_(
                        TenantAdmin.username == username, TenantAdmin.email == username
                    ),
                    TenantAdmin.is_deleted.is_(False),
                )
            )
            user = result.scalar_one_or_none()
        elif user_type == "tenant_user":
            # 处理企业用户 / Branch: tenant end-user
            result = await self.db.execute(
                select(TenantUser).where(
                    or_(TenantUser.username == username, TenantUser.email == username),
                    TenantUser.is_deleted.is_(False),
                )
            )
            user = result.scalar_one_or_none()
        else:
            return

        if user:
            # 增加失败次数 / Increment failure count
            user.login_fail_count = (user.login_fail_count or 0) + 1
            user.last_fail_at = now

            # 检查是否需要锁定账户 / Lock if max attempts exceeded
            if user.login_fail_count >= max_attempts:
                user.locked_until = now + timedelta(minutes=lockout_minutes)

            await self.db.commit()

    async def _record_admin_login_failure(
        self, username: str, client_ip: str | None
    ) -> None:
        """记录平台管理员登录失败 / Record admin login failure."""
        await self._record_login_failure(username, client_ip, "admin")

    async def _is_account_locked(self, user_id: int, user_type: str = "admin") -> bool:
        """
        检查账户是否被锁定 / Check if account is locked.

        Args:
            user_id: 用户ID
            user_type: 用户类型 (admin/tenant_admin/tenant_user)

        Returns:
            是否被锁定
        """

        if user_type == "admin":
            result = await self.db.execute(
                select(Admin.locked_until).where(Admin.id == user_id)
            )
        elif user_type == "tenant_admin":
            result = await self.db.execute(
                select(TenantAdmin.locked_until).where(TenantAdmin.id == user_id)
            )
        elif user_type == "tenant_user":
            result = await self.db.execute(
                select(TenantUser.locked_until).where(TenantUser.id == user_id)
            )
        else:
            return False

        locked_until = result.scalar_one_or_none()

        if locked_until is None:
            return False

        # 检查锁定是否已过期 / Treat expired lock as unlocked
        return self._normalize_utc(locked_until) > self._utc_now_aware()

    async def _reset_login_failures(
        self, user_id: int, user_type: str = "admin"
    ) -> None:
        """
        重置登录失败计数 / Reset login failure count.

        Args:
            user_id: 用户ID
            user_type: 用户类型 (admin/tenant_admin/tenant_user)
        """
        if user_type == "admin":
            result = await self.db.execute(select(Admin).where(Admin.id == user_id))
        elif user_type == "tenant_admin":
            result = await self.db.execute(
                select(TenantAdmin).where(TenantAdmin.id == user_id)
            )
        elif user_type == "tenant_user":
            result = await self.db.execute(
                select(TenantUser).where(TenantUser.id == user_id)
            )
        else:
            return

        user = result.scalar_one_or_none()

        if user:
            user.login_fail_count = 0
            user.last_fail_at = None
            user.locked_until = None
            await self.db.commit()

    async def _reset_admin_login_failures(self, admin_id: int) -> None:
        """重置平台管理员登录失败计数 / Reset admin login failure count."""
        await self._reset_login_failures(admin_id, "admin")

    async def _verify_captcha(
        self,
        challenge_id: str | None,
        solution: str | None,
        provider_code: str | None,
        ctx: dict[str, Any],
    ) -> None:
        """
        验证验证码 / Verify captcha.

        Args:
            challenge_id: 验证码挑战ID
            solution: 验证码解决方案
            provider_code: 验证码提供程序代码
            ctx: 上下文信息

        Raises:
            AuthenticationException: 验证码无效
        """
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

    async def refresh_admin_token(self, refresh_token: str) -> dict[str, Any]:
        """
        刷新平台管理员 Token / Refresh platform admin token.

        Args:
            refresh_token: 刷新令牌

        Returns:
            新的 tokens

        Raises:
            AuthenticationException: Token 无效
        """
        admin_id, scope = await verify_token_with_scope(
            refresh_token, TOKEN_SCOPE_ADMIN, TOKEN_TYPE_REFRESH
        )
        if admin_id is None:
            self._log_auth_warning(
                "admin.token.refresh.failed",
                reason="invalid_token",
            )
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        # 查询管理员 / Load admin by id
        result = await self.db.execute(
            select(Admin).where(
                Admin.id == int(admin_id),
                Admin.is_deleted.is_(False),
            )
        )
        admin = result.scalar_one_or_none()

        if admin is None:
            self._log_auth_warning(
                "admin.token.refresh.failed",
                user_id=admin_id,
                reason="user_not_found",
            )
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        if not admin.is_active:
            self._log_auth_warning(
                "admin.token.refresh.failed",
                user_id=admin.id,
                username=admin.username,
                reason="account_disabled",
            )
            raise AuthenticationException(message=_("auth.account_disabled"))

        tokens = create_token_pair(admin.id, scope=TOKEN_SCOPE_ADMIN)
        await self._record_active_tokens(
            "admin",
            str(admin.id),
            tokens["access_jti"],
            tokens["refresh_jti"],
        )
        self._log_auth_info(
            "admin.token.refresh.success",
            user_id=admin.id,
            username=admin.username,
        )
        return tokens

    async def change_admin_password(
        self,
        admin: Admin,
        old_password: str,
        new_password: str,
    ) -> None:
        """
        修改平台管理员密码 / Change platform admin password.

        Args:
            admin: 管理员实例
            old_password: 旧密码
            new_password: 新密码

        Raises:
            BusinessException: 旧密码不正确或新密码不符合策略
        """
        if not verify_password(old_password, admin.password_hash):
            raise BusinessException(
                message=_("auth.password_mismatch"),
                code=ErrorCode.OLD_PASSWORD_INCORRECT,
            )

        # 验证新密码符合策略 / Validate new password policy
        await self._validate_password_policy(new_password)

        admin.password_hash = get_password_hash(new_password)

    # ==================== 企业管理员认证 / Tenant admin authentication ====================

    async def authenticate_tenant_admin(
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
        """
        企业管理员认证 / Tenant admin authentication.

        Args:
            username: 用户名或邮箱
            password: 密码
            tenant_code: 企业编码（优先级最高）
            tenant_id_from_ctx: 来自域名中间件的企业 ID（回退）
            client_ip: 客户端 IP
            captcha_challenge_id: 验证码挑战ID
            captcha_solution: 验证码解决方案
            captcha_provider_code: 验证码提供程序代码

        Returns:
            包含 tokens 的字典

        Raises:
            AuthenticationException: 认证失败
        """
        # 企业域名隔离：必须通过企业域名或显式指定 tenant_code 访问 / Tenant host isolation: require tenant_code or ctx
        if not tenant_code and not tenant_id_from_ctx:
            self._log_auth_warning(
                "tenant_admin.login.failed",
                identifier=self._mask_identifier(username),
                client_ip=client_ip,
                reason="tenant_domain_required",
            )
            raise AuthenticationException(
                message=_("auth.tenant_domain_required"),
            )

        # 查询企业管理员 / Build tenant admin query
        query = select(TenantAdmin).where(
            or_(
                TenantAdmin.username == username,
                TenantAdmin.email == username,
            ),
            TenantAdmin.is_deleted.is_(False),
        )

        # 按优先级限定企业范围 / Scope tenant by code or middleware id
        if tenant_code:
            query = query.join(Tenant, TenantAdmin.tenant_id == Tenant.id).where(
                Tenant.code == tenant_code,
                Tenant.is_active.is_(True),
                Tenant.is_deleted.is_(False),
            )
        elif tenant_id_from_ctx:
            query = query.where(TenantAdmin.tenant_id == tenant_id_from_ctx)

        result = await self.db.execute(query)
        results = result.scalars().all()

        # 多条匹配 → 要求指定 tenant_code
        if len(results) > 1:
            self._log_auth_warning(
                "tenant_admin.login.failed",
                identifier=self._mask_identifier(username),
                tenant_code=tenant_code,
                client_ip=client_ip,
                reason="tenant_code_required",
            )
            raise AuthenticationException(
                message=_("auth.tenant_code_required"),
                data={"tenant_code_required": True},
            )

        tenant_admin = results[0] if results else None

        # 检查账户是否存在 / Check tenant admin exists
        if tenant_admin is None:
            await self._record_login_failure(
                username, client_ip, "tenant_admin", tenant_id=None
            )
            self._log_auth_warning(
                "tenant_admin.login.failed",
                identifier=self._mask_identifier(username),
                tenant_code=tenant_code,
                client_ip=client_ip,
                reason="user_not_found",
            )
            raise AuthenticationException(
                message=_("auth.credentials_invalid"),
                data={"captcha_required": False},
            )

        # 检查账户锁定状态 / Check lockout
        if await self._is_account_locked(tenant_admin.id, "tenant_admin"):
            self._log_auth_warning(
                "tenant_admin.login.failed",
                user_id=tenant_admin.id,
                username=tenant_admin.username,
                tenant_id=tenant_admin.tenant_id,
                client_ip=client_ip,
                reason="account_locked",
            )
            raise AuthenticationException(message=_("auth.account_locked"))

        # 检查账户状态（在密码验证之前，防止通过不同错误消息泄漏密码正确性） / Active check before pwd (avoid oracle)
        if not tenant_admin.is_active:
            self._log_auth_warning(
                "tenant_admin.login.failed",
                user_id=tenant_admin.id,
                username=tenant_admin.username,
                tenant_id=tenant_admin.tenant_id,
                client_ip=client_ip,
                reason="account_disabled",
            )
            raise AuthenticationException(message=_("auth.credentials_invalid"))

        captcha_enabled = await self._config_service.get_tenant_config(
            tenant_admin.tenant_id, "tenant_captcha_enabled", default=True
        )
        threshold = await self._config_service.get_tenant_config(
            tenant_admin.tenant_id, "tenant_captcha_enable_threshold", default=2
        )
        fail_count = tenant_admin.login_fail_count or 0
        captcha_required = captcha_enabled and (
            threshold == 0 or fail_count >= threshold
        )
        if captcha_required:
            await self._verify_captcha(
                captcha_challenge_id,
                captcha_solution,
                captcha_provider_code,
                {
                    "ip": client_ip,
                    "endpoint": "tenant",
                    "action": "login",
                    "identifier": self._mask_identifier(username),
                    "tenant_id": tenant_admin.tenant_id,
                },
            )

        # 验证密码 / Verify password
        if not verify_password(password, tenant_admin.password_hash):
            await self._record_login_failure(
                username, client_ip, "tenant_admin", tenant_id=tenant_admin.tenant_id
            )
            self._log_auth_warning(
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

        # 检查企业状态 / Ensure tenant active
        tenant_result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_admin.tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()

        if tenant is None or not tenant.is_active:
            self._log_auth_warning(
                "tenant_admin.login.failed",
                user_id=tenant_admin.id,
                username=tenant_admin.username,
                tenant_id=tenant_admin.tenant_id,
                client_ip=client_ip,
                reason="tenant_disabled",
            )
            raise AuthenticationException(message=_("tenant.disabled"))

        # 登录成功，重置失败计数 / Success: reset failures
        await self._reset_login_failures(tenant_admin.id, "tenant_admin")

        # 更新登录信息 / Update last login
        tenant_admin.last_login_at = self._utc_now_aware()
        tenant_admin.last_login_ip = client_ip

        # 生成 Token（优先使用企业会话配置，回退到平台配置） / Session TTL: tenant config then platform
        session_timeout = await self._config_service.get_tenant_config(
            tenant_admin.tenant_id, "tenant_session_timeout", default=None
        )
        if not session_timeout:
            session_timeout = await self._config_service.get_platform_config(
                "session_timeout_minutes", default=120
            )
        tokens = create_token_pair(
            tenant_admin.id,
            scope=TOKEN_SCOPE_TENANT_ADMIN,
            extra_claims={"tenant_id": tenant_admin.tenant_id},
        )
        await self._record_active_tokens(
            "tenant_admin",
            str(tenant_admin.id),
            tokens["access_jti"],
            tokens["refresh_jti"],
        )

        self._log_auth_info(
            "tenant_admin.login.success",
            user_id=tenant_admin.id,
            username=tenant_admin.username,
            tenant_id=tenant_admin.tenant_id,
            tenant_code=tenant.code if tenant else tenant_code,
            client_ip=client_ip,
        )

        return tokens

    async def refresh_tenant_admin_token(self, refresh_token: str) -> dict[str, Any]:
        """
        刷新企业管理员 Token / Refresh tenant admin token.

        Args:
            refresh_token: 刷新令牌

        Returns:
            新的 tokens

        Raises:
            AuthenticationException: Token 无效
        """
        admin_id, scope = await verify_token_with_scope(
            refresh_token, TOKEN_SCOPE_TENANT_ADMIN, TOKEN_TYPE_REFRESH
        )
        if admin_id is None:
            self._log_auth_warning(
                "tenant_admin.token.refresh.failed",
                reason="invalid_token",
            )
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        # 查询企业管理员 / Load tenant admin
        result = await self.db.execute(
            select(TenantAdmin).where(
                TenantAdmin.id == int(admin_id),
                TenantAdmin.is_deleted.is_(False),
            )
        )
        tenant_admin = result.scalar_one_or_none()

        if tenant_admin is None:
            self._log_auth_warning(
                "tenant_admin.token.refresh.failed",
                user_id=admin_id,
                reason="user_not_found",
            )
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        if not tenant_admin.is_active:
            self._log_auth_warning(
                "tenant_admin.token.refresh.failed",
                user_id=tenant_admin.id,
                username=tenant_admin.username,
                tenant_id=tenant_admin.tenant_id,
                reason="account_disabled",
            )
            raise AuthenticationException(message=_("auth.account_disabled"))

        tokens = create_token_pair(
            tenant_admin.id,
            scope=TOKEN_SCOPE_TENANT_ADMIN,
            extra_claims={"tenant_id": tenant_admin.tenant_id},
        )
        await self._record_active_tokens(
            "tenant_admin",
            str(tenant_admin.id),
            tokens["access_jti"],
            tokens["refresh_jti"],
        )
        self._log_auth_info(
            "tenant_admin.token.refresh.success",
            user_id=tenant_admin.id,
            username=tenant_admin.username,
            tenant_id=tenant_admin.tenant_id,
        )
        return tokens

    async def change_tenant_admin_password(
        self,
        tenant_admin: TenantAdmin,
        old_password: str,
        new_password: str,
    ) -> None:
        """
        修改企业管理员密码 / Change tenant admin password.

        Args:
            tenant_admin: 企业管理员实例
            old_password: 旧密码
            new_password: 新密码

        Raises:
            BusinessException: 旧密码不正确或新密码不符合策略
        """
        if not verify_password(old_password, tenant_admin.password_hash):
            raise BusinessException(
                message=_("auth.password_mismatch"),
                code=ErrorCode.OLD_PASSWORD_INCORRECT,
            )

        # 验证新密码符合策略 / Validate new password policy
        await self._validate_password_policy(
            new_password, tenant_id=tenant_admin.tenant_id
        )

        tenant_admin.password_hash = get_password_hash(new_password)

    async def impersonate_tenant_admin(
        self,
        impersonate_token: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        验证平台管理员的 impersonate token 并换取正式 Token / Verify impersonate token and exchange for real token.

        Args:
            impersonate_token: 一键登录令牌

        Returns:
            (tokens, audit_info) 元组

        Raises:
            AuthenticationException: Token 无效
            NotFoundException: 企业或所有者不存在
        """
        # 验证 impersonate token / Verify impersonate JWT
        payload = await verify_impersonate_token(
            impersonate_token, TOKEN_SCOPE_TENANT_ADMIN
        )

        if payload is None:
            self._log_auth_warning(
                "tenant_admin.impersonate.failed",
                reason="invalid_token",
            )
            raise AuthenticationException(message=_("auth.impersonate_token_invalid"))

        admin_id = int(payload["sub"]) if payload.get("sub") else None
        target_tenant_id = payload.get("target_tenant_id")
        target_role_id = payload.get("target_role_id")

        if admin_id is None:
            self._log_auth_warning(
                "tenant_admin.impersonate.failed",
                reason="missing_admin_id",
            )
            raise AuthenticationException(message=_("auth.impersonate_token_invalid"))

        # 验证企业状态 / Validate tenant active
        tenant_result = await self.db.execute(
            select(Tenant).where(
                Tenant.id == target_tenant_id,
                Tenant.is_deleted.is_(False),
            )
        )
        tenant = tenant_result.scalar_one_or_none()

        if tenant is None or not tenant.is_active:
            self._log_auth_warning(
                "tenant_admin.impersonate.failed",
                admin_id=admin_id,
                target_tenant_id=target_tenant_id,
                reason="tenant_disabled",
            )
            raise AuthenticationException(message=_("tenant.disabled"))

        # 获取企业的所有者信息 / Resolve tenant owner account
        owner_result = await self.db.execute(
            select(TenantAdmin).where(
                TenantAdmin.tenant_id == target_tenant_id,
                TenantAdmin.is_owner.is_(True),
                TenantAdmin.is_deleted.is_(False),
            )
        )
        tenant_owner = owner_result.scalar_one_or_none()

        if tenant_owner is None:
            self._log_auth_warning(
                "tenant_admin.impersonate.failed",
                admin_id=admin_id,
                target_tenant_id=target_tenant_id,
                reason="tenant_owner_not_found",
            )
            raise NotFoundException(message=_("tenant.owner_not_found"))

        # 获取执行 impersonate 的平台管理员信息 / Load platform admin who triggered impersonation
        platform_admin_result = await self.db.execute(
            select(Admin).where(
                Admin.id == admin_id,
                Admin.is_deleted.is_(False),
            )
        )
        platform_admin = platform_admin_result.scalar_one_or_none()
        platform_admin_username = (
            platform_admin.username if platform_admin else "unknown"
        )

        # 生成正式 Token / Issue real session tokens
        extra_claims = {
            "tenant_id": target_tenant_id,
            "impersonated_by": admin_id,
        }

        if target_role_id:
            extra_claims["impersonate_role_id"] = target_role_id

        tokens = create_token_pair(
            tenant_owner.id,
            scope=TOKEN_SCOPE_TENANT_ADMIN,
            extra_claims=extra_claims,
        )
        await self._record_active_tokens(
            "tenant_admin",
            str(tenant_owner.id),
            tokens["access_jti"],
            tokens["refresh_jti"],
        )

        # 返回审计信息 / Return audit payload
        audit_info = {
            "admin_id": admin_id,
            "admin_username": platform_admin_username,
            "target_tenant_id": target_tenant_id,
            "target_tenant_code": tenant.code,
            "tenant_owner_id": tenant_owner.id,
            "target_role_id": target_role_id,
        }

        self._log_auth_info(
            "tenant_admin.impersonate.success",
            admin_id=admin_id,
            admin_username=platform_admin_username,
            target_tenant_id=target_tenant_id,
            target_tenant_code=tenant.code,
            tenant_owner_id=tenant_owner.id,
            target_role_id=target_role_id,
        )

        return tokens, audit_info

    # ==================== 企业用户认证 / Tenant user authentication ====================

    async def authenticate_tenant_user(
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
        """
        企业用户认证 / Tenant user authentication.

        Args:
            username: 用户名、邮箱或手机号
            password: 密码
            tenant_code: 企业编码（优先级最高）
            tenant_id_from_ctx: 来自域名中间件的企业 ID（回退）
            client_ip: 客户端 IP

        Returns:
            包含 tokens 的字典

        Raises:
            AuthenticationException: 认证失败
        """
        # 企业域名隔离：必须通过企业域名或显式指定 tenant_code 访问 / Tenant host isolation: require tenant_code or ctx
        if not tenant_code and not tenant_id_from_ctx:
            self._log_auth_warning(
                "tenant_user.login.failed",
                identifier=self._mask_identifier(username),
                client_ip=client_ip,
                reason="tenant_domain_required",
            )
            raise AuthenticationException(
                message=_("auth.tenant_domain_required"),
            )

        # 查询用户 / Build tenant user query
        query = select(TenantUser).where(
            or_(
                TenantUser.username == username,
                TenantUser.email == username,
                TenantUser.phone == username,
            ),
            TenantUser.is_deleted.is_(False),
        )

        # 按优先级限定企业范围 / Scope tenant by code or middleware id
        if tenant_code:
            query = query.join(Tenant, TenantUser.tenant_id == Tenant.id).where(
                Tenant.code == tenant_code,
                Tenant.is_active.is_(True),
                Tenant.is_deleted.is_(False),
            )
        elif tenant_id_from_ctx:
            query = query.where(TenantUser.tenant_id == tenant_id_from_ctx)

        result = await self.db.execute(query)
        results = result.scalars().all()

        # 多条匹配 → 要求指定 tenant_code / Ambiguous → require tenant_code
        if len(results) > 1:
            self._log_auth_warning(
                "tenant_user.login.failed",
                identifier=self._mask_identifier(username),
                tenant_code=tenant_code,
                client_ip=client_ip,
                reason="tenant_code_required",
            )
            raise AuthenticationException(
                message=_("auth.tenant_code_required"),
                data={"tenant_code_required": True},
            )

        user = results[0] if results else None

        # 检查账户是否存在 / Check user exists
        if user is None:
            await self._record_login_failure(
                username, client_ip, "tenant_user", tenant_id=None
            )
            self._log_auth_warning(
                "tenant_user.login.failed",
                identifier=self._mask_identifier(username),
                tenant_code=tenant_code,
                client_ip=client_ip,
                reason="user_not_found",
            )
            raise AuthenticationException(
                message=_("auth.credentials_invalid"),
                data={"captcha_required": False},
            )

        # 检查账户锁定状态 / Check lockout
        if await self._is_account_locked(user.id, "tenant_user"):
            self._log_auth_warning(
                "tenant_user.login.failed",
                user_id=user.id,
                username=user.username,
                tenant_id=user.tenant_id,
                client_ip=client_ip,
                reason="account_locked",
            )
            raise AuthenticationException(message=_("auth.account_locked"))

        # 检查账户状态（在密码验证之前，防止通过不同错误消息泄漏密码正确性） / Active check before pwd (avoid oracle)
        if not user.is_active:
            self._log_auth_warning(
                "tenant_user.login.failed",
                user_id=user.id,
                username=user.username,
                tenant_id=user.tenant_id,
                client_ip=client_ip,
                reason="account_disabled",
            )
            raise AuthenticationException(message=_("auth.credentials_invalid"))

        captcha_enabled = await self._config_service.get_tenant_config(
            user.tenant_id, "user_login_captcha_enabled", default=True
        )
        threshold = await self._config_service.get_tenant_config(
            user.tenant_id, "user_login_captcha_enable_threshold", default=0
        )
        fail_count = user.login_fail_count or 0
        captcha_required = captcha_enabled and (
            threshold == 0 or fail_count >= threshold
        )
        if captcha_required:
            await self._verify_captcha(
                captcha_challenge_id,
                captcha_solution,
                captcha_provider_code,
                {
                    "ip": client_ip,
                    "endpoint": "user",
                    "action": "login",
                    "identifier": self._mask_identifier(username),
                    "tenant_id": user.tenant_id,
                },
            )

        # 验证密码 / Verify password
        if not verify_password(password, user.password_hash):
            await self._record_login_failure(
                username, client_ip, "tenant_user", tenant_id=user.tenant_id
            )
            self._log_auth_warning(
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

        # 登录成功，重置失败计数 / Success: reset failures
        await self._reset_login_failures(user.id, "tenant_user")
        return await self._issue_tenant_user_tokens(
            user=user,
            client_ip=client_ip,
            tenant_code=tenant_code,
            event="tenant_user.login.success",
        )

    async def _issue_tenant_user_tokens(
        self,
        *,
        user: TenantUser,
        client_ip: str | None,
        tenant_code: str | None = None,
        event: str = "tenant_user.login.success",
    ) -> dict[str, Any]:
        """
        为企业用户签发 Token 并记录登录态 / Issue tenant-user tokens and persist login state.
        """
        user.last_login_at = self._utc_now_aware()
        user.last_login_ip = client_ip

        tokens = create_token_pair(
            user.id,
            scope=TOKEN_SCOPE_TENANT_USER,
            extra_claims={"tenant_id": user.tenant_id},
        )
        await self._record_active_tokens(
            "tenant_user",
            str(user.id),
            tokens["access_jti"],
            tokens["refresh_jti"],
        )

        self._log_auth_info(
            event,
            user_id=user.id,
            username=user.username,
            tenant_id=user.tenant_id,
            tenant_code=tenant_code,
            client_ip=client_ip,
        )

        return tokens

    async def _resolve_tenant_user_login_tenant_id(
        self,
        *,
        tenant_code: str | None,
        tenant_id_from_ctx: int | None,
        identifier: str | None = None,
        client_ip: str | None = None,
        log_reason: str = "tenant_domain_required",
    ) -> int:
        """
        解析企业用户登录链路的企业 ID / Resolve tenant ID for tenant-user login flows.
        """
        if not tenant_code and not tenant_id_from_ctx:
            self._log_auth_warning(
                "tenant_user.login_code.failed",
                identifier=self._mask_identifier(identifier),
                client_ip=client_ip,
                reason=log_reason,
            )
            raise AuthenticationException(message=_("auth.tenant_domain_required"))

        tenant_id = tenant_id_from_ctx
        if not tenant_id and tenant_code:
            result = await self.db.execute(
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

    async def _ensure_tenant_user_login_code_channel_enabled(
        self,
        *,
        tenant_id: int,
        channel: str,
    ) -> None:
        """
        校验验证码登录渠道是否启用 / Validate that the code-login channel is enabled.
        """
        methods = await self._config_service.get_tenant_config(
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

    async def _maybe_verify_tenant_user_code_login_captcha(
        self,
        *,
        tenant_id: int,
        identifier: str,
        client_ip: str | None,
        captcha_challenge_id: str | None,
        captcha_solution: str | None,
        captcha_provider_code: str | None,
    ) -> None:
        """
        按租户配置验证验证码登录发送接口的 CAPTCHA / Verify CAPTCHA for code-login send flow when enabled.
        """
        enabled = await self._config_service.get_tenant_config(
            tenant_id,
            "user_login_captcha_enabled",
            default=True,
        )
        threshold = await self._config_service.get_tenant_config(
            tenant_id,
            "user_login_captcha_enable_threshold",
            default=0,
        )
        if not enabled or (isinstance(threshold, int) and threshold > 0):
            return

        await self._verify_captcha(
            captcha_challenge_id,
            captcha_solution,
            captcha_provider_code,
            {
                "action": "login_code_send",
                "endpoint": "user",
                "identifier": self._mask_identifier(identifier),
                "ip": client_ip,
                "tenant_id": tenant_id,
            },
        )

    @staticmethod
    def _build_tenant_user_login_code_key(
        *,
        channel: str,
        identifier: str,
        tenant_id: int,
    ) -> str:
        return f"tenant_user_login_code:{channel}:{tenant_id}:{identifier}"

    @staticmethod
    def _build_tenant_user_login_code_rate_key(
        *,
        channel: str,
        identifier: str,
        tenant_id: int,
    ) -> str:
        return f"tenant_user_login_code_rate:{channel}:{tenant_id}:{identifier}"

    async def send_tenant_user_login_code(
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
        """
        发送企业用户登录验证码 / Send login verification code for tenant users.
        """
        normalized_email = (email or "").strip().lower() or None
        normalized_phone = (phone or "").strip() or None
        identifier = normalized_email or normalized_phone
        tenant_id = await self._resolve_tenant_user_login_tenant_id(
            tenant_code=tenant_code,
            tenant_id_from_ctx=tenant_id_from_ctx,
            identifier=identifier,
            client_ip=client_ip,
        )
        await self._ensure_tenant_user_login_code_channel_enabled(
            tenant_id=tenant_id,
            channel=channel,
        )

        if channel == "email":
            if not normalized_email:
                raise ValidationException(message=_("auth.login_code_email_required"))
            identifier = normalized_email
        elif channel == "sms":
            if not normalized_phone:
                raise ValidationException(message=_("auth.login_code_phone_required"))
            raise BusinessException(message=_("auth.login_code_sms_not_enabled"))

        await self._maybe_verify_tenant_user_code_login_captcha(
            tenant_id=tenant_id,
            identifier=identifier or "",
            client_ip=client_ip,
            captcha_challenge_id=captcha_challenge_id,
            captcha_solution=captcha_solution,
            captcha_provider_code=captcha_provider_code,
        )

        rate_key = self._build_tenant_user_login_code_rate_key(
            channel=channel,
            identifier=identifier or "",
            tenant_id=tenant_id,
        )
        if await cache_get(rate_key):
            raise BusinessException(message=_("auth.reset_rate_limited"))

        if channel != "email":
            raise BusinessException(message=_("auth.login_code_channel_invalid"))

        result = await self.db.execute(
            select(TenantUser).where(
                and_(
                    TenantUser.tenant_id == tenant_id,
                    TenantUser.email == identifier,
                    TenantUser.is_deleted.is_(False),
                )
            )
        )
        user = result.scalar_one_or_none()

        await cache_set(rate_key, True, ttl=self.LOGIN_CODE_RATE_LIMIT_TTL)
        if user is None:
            self._log_auth_warning(
                "tenant_user.login_code.send.skipped",
                identifier=self._mask_identifier(identifier),
                tenant_id=tenant_id,
                tenant_code=tenant_code,
                client_ip=client_ip,
                reason="user_not_found",
            )
            return {"message": _("auth.login_code_sent")}

        code = "".join(secrets.choice(string.digits) for _ in range(6))
        code_key = self._build_tenant_user_login_code_key(
            channel=channel,
            identifier=identifier or "",
            tenant_id=tenant_id,
        )
        await cache_set(
            code_key,
            {"code": code, "user_id": user.id},
            ttl=self.LOGIN_CODE_TTL,
        )

        expire_minutes = self.LOGIN_CODE_TTL // 60
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

        self._log_auth_info(
            "tenant_user.login_code.send.success",
            user_id=user.id,
            username=user.username,
            tenant_id=tenant_id,
            tenant_code=tenant_code,
            client_ip=client_ip,
        )
        return {"message": _("auth.login_code_sent")}

    async def authenticate_tenant_user_by_code(
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
        """
        企业用户验证码登录 / Authenticate tenant user by verification code.
        """
        normalized_email = (email or "").strip().lower() or None
        normalized_phone = (phone or "").strip() or None
        identifier = normalized_email or normalized_phone
        tenant_id = await self._resolve_tenant_user_login_tenant_id(
            tenant_code=tenant_code,
            tenant_id_from_ctx=tenant_id_from_ctx,
            identifier=identifier,
            client_ip=client_ip,
        )
        await self._ensure_tenant_user_login_code_channel_enabled(
            tenant_id=tenant_id,
            channel=channel,
        )

        if channel == "email":
            if not normalized_email:
                raise ValidationException(message=_("auth.login_code_email_required"))
            identifier = normalized_email
        elif channel == "sms":
            if not normalized_phone:
                raise ValidationException(message=_("auth.login_code_phone_required"))
            raise BusinessException(message=_("auth.login_code_sms_not_enabled"))

        code_key = self._build_tenant_user_login_code_key(
            channel=channel,
            identifier=identifier or "",
            tenant_id=tenant_id,
        )
        stored = await cache_get(code_key)
        if not stored or not isinstance(stored, dict):
            raise AuthenticationException(message=_("auth.login_code_invalid"))
        if stored.get("code") != code:
            raise AuthenticationException(message=_("auth.login_code_invalid"))

        user_id = stored.get("user_id")
        if not user_id:
            raise AuthenticationException(message=_("auth.login_code_invalid"))

        result = await self.db.execute(
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

        if await self._is_account_locked(user.id, "tenant_user"):
            raise AuthenticationException(message=_("auth.account_locked"))
        if not user.is_active:
            raise AuthenticationException(message=_("auth.account_disabled"))

        await self._reset_login_failures(user.id, "tenant_user")
        await cache_delete(code_key)
        return await self._issue_tenant_user_tokens(
            user=user,
            client_ip=client_ip,
            tenant_code=tenant_code,
            event="tenant_user.login_code.success",
        )

    async def refresh_tenant_user_token(self, refresh_token: str) -> dict[str, Any]:
        """
        刷新企业用户 Token / Refresh tenant user token.

        Args:
            refresh_token: 刷新令牌

        Returns:
            新的 tokens

        Raises:
            AuthenticationException: Token 无效
        """
        user_id, scope = await verify_token_with_scope(
            refresh_token, TOKEN_SCOPE_TENANT_USER, TOKEN_TYPE_REFRESH
        )
        if user_id is None:
            self._log_auth_warning(
                "tenant_user.token.refresh.failed",
                reason="invalid_token",
            )
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        # 查询用户 / Load tenant user by id
        result = await self.db.execute(
            select(TenantUser).where(
                TenantUser.id == int(user_id),
                TenantUser.is_deleted.is_(False),
            )
        )
        user = result.scalar_one_or_none()

        if user is None:
            self._log_auth_warning(
                "tenant_user.token.refresh.failed",
                user_id=user_id,
                reason="user_not_found",
            )
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        if not user.is_active:
            self._log_auth_warning(
                "tenant_user.token.refresh.failed",
                user_id=user.id,
                username=user.username,
                tenant_id=user.tenant_id,
                reason="account_disabled",
            )
            raise AuthenticationException(message=_("auth.account_disabled"))

        tokens = create_token_pair(
            user.id,
            scope=TOKEN_SCOPE_TENANT_USER,
            extra_claims={"tenant_id": user.tenant_id},
        )
        await self._record_active_tokens(
            "tenant_user",
            str(user.id),
            tokens["access_jti"],
            tokens["refresh_jti"],
        )
        self._log_auth_info(
            "tenant_user.token.refresh.success",
            user_id=user.id,
            username=user.username,
            tenant_id=user.tenant_id,
        )
        return tokens

    async def change_tenant_user_password(
        self,
        user: TenantUser,
        old_password: str,
        new_password: str,
    ) -> None:
        """
        修改企业用户密码 / Change tenant user password.

        Args:
            user: 用户实例
            old_password: 旧密码
            new_password: 新密码

        Raises:
            BusinessException: 旧密码不正确或新密码不符合策略
        """
        if not verify_password(old_password, user.password_hash):
            raise BusinessException(
                message=_("auth.password_mismatch"),
                code=ErrorCode.OLD_PASSWORD_INCORRECT,
            )

        # 验证新密码符合策略 / Validate new password policy
        await self._validate_password_policy(new_password, tenant_id=user.tenant_id)

        user.password_hash = get_password_hash(new_password)

    # ==================== 企业用户注册 / Tenant user registration ====================

    async def register_tenant_user(
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
        """
        企业用户自助注册 / Tenant user self-registration.

        Args:
            username: 用户名
            email: 邮箱
            password: 密码
            tenant_code: 企业编码
            tenant_id_from_ctx: 来自中间件的企业 ID
            phone: 手机号
            nickname: 昵称
            client_ip: 客户端 IP
            captcha_challenge_id: 验证码挑战 ID
            captcha_solution: 验证码答案
            captcha_provider_code: 验证码提供方标识

        Returns:
            注册结果信息

        Raises:
            BusinessException: 注册未开放或参数错误
        """
        # 确定企业 / Resolve tenant id
        tenant_id = tenant_id_from_ctx
        if not tenant_id and tenant_code:
            result = await self.db.execute(
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
            result = await self.db.execute(
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

        # 检查注册是否开放（与前端功能设置 tenant_allow_registration 一致） / Registration toggle (matches UI)
        registration_enabled = await self._config_service.get_tenant_config(
            tenant_id, "tenant_allow_registration", default=False
        )
        if not registration_enabled:
            raise BusinessException(message=_("auth.registration_disabled"))

        # 检查注册验证码（注册属于表单验证，验证码错误返回 422 而非 401） / Captcha: map auth error to 422 for forms
        captcha_enabled = await self._config_service.get_tenant_config(
            tenant_id, "user_registration_captcha_enabled", default=True
        )
        if captcha_enabled:
            try:
                await self._verify_captcha(
                    captcha_challenge_id,
                    captcha_solution,
                    captcha_provider_code,
                    {"ip": client_ip, "endpoint": "user", "action": "register"},
                )
            except AuthenticationException as e:
                raise ValidationException(
                    message=e.message,
                    errors=[e.data] if e.data else None,
                ) from e

        # 检查用户数配额 / Enforce user quota
        from sqlalchemy.orm import selectinload as _selectinload

        from app.services.tenant.quota_service import QuotaService

        tenant_for_quota = (
            await self.db.execute(
                select(Tenant)
                .options(_selectinload(Tenant.tenant_plan))
                .where(Tenant.id == tenant_id)
            )
        ).scalar_one_or_none()
        if tenant_for_quota:
            quota_svc = QuotaService(self.db, tenant_for_quota)
            quota_check = await quota_svc.check_user_quota()
            if not quota_check.allowed:
                raise BusinessException(
                    message=quota_check.message or _("quota.users_exceeded"),
                )

        # 验证密码策略 / Validate password policy
        await self._validate_password_policy(password, tenant_id=tenant_id)

        # 检查用户名唯一性 / Username unique per tenant
        existing = await self.db.execute(
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

        # 检查邮箱唯一性 / Email unique per tenant
        existing = await self.db.execute(
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

        # 检查手机号唯一性 / Phone unique per tenant
        if phone:
            existing = await self.db.execute(
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

        # 获取审批和激活配置（与前端功能设置 tenant_registration_approval 一致） / Approval + default active flags
        require_approval = await self._config_service.get_tenant_config(
            tenant_id, "tenant_registration_approval", default=False
        )
        default_active = await self._config_service.get_tenant_config(
            tenant_id, "user_default_active", default=True
        )

        # 获取默认用户角色 ID
        default_role_id = await self._config_service.get_tenant_config(
            tenant_id, "user_default_role_id", default=0
        )
        default_role_id = int(default_role_id) if default_role_id else 0

        # 根据配置决定初始状态 / Initial approval_status + is_active
        if require_approval:
            approval_status = ApprovalStatusEnum.PENDING.value
            is_active = False
        else:
            approval_status = ApprovalStatusEnum.APPROVED.value
            is_active = default_active

        # 创建用户 / Insert TenantUser row
        user = TenantUser(
            tenant_id=tenant_id,
            username=username,
            email=email,
            password_hash=get_password_hash(password),
            phone=phone,
            nickname=nickname or username,
            is_active=is_active,
            approval_status=approval_status,
            role_id=default_role_id if default_role_id > 0 else None,
        )
        self.db.add(user)
        await self.db.flush()

        logger.info(
            f"User registered: {username} (tenant={tenant_id}, "
            f"approval={approval_status}, active={is_active})"
        )

        # 需要审批时通知企业管理员 / Notify admins when pending approval
        if approval_status == ApprovalStatusEnum.PENDING.value:
            await self._notify_tenant_admins_pending(
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

        # 如果不需要审批且默认激活，直接返回 token / Auto-issue tokens when active immediately
        if approval_status == ApprovalStatusEnum.APPROVED.value and is_active:
            tokens = create_token_pair(
                user.id,
                scope=TOKEN_SCOPE_TENANT_USER,
                extra_claims={"tenant_id": tenant_id},
            )
            await self._record_active_tokens(
                "tenant_user",
                str(user.id),
                tokens["access_jti"],
                tokens["refresh_jti"],
            )
            result_data["tokens"] = tokens

        return result_data

    async def _notify_tenant_admins_pending(
        self,
        tenant_id: int,
        username: str,
        email: str,
    ) -> None:
        """注册待审批时通知企业管理员 / Notify tenant admins when registration pending approval."""
        from app.services.common.notification_service import notify

        # 获取企业所有活跃管理员 / List active tenant admins
        admins = (
            (
                await self.db.execute(
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
            self.db,
            template_code="biz.user_registration_pending",
            recipients=recipients,
            data={"username": username, "email": email},
            tenant_id=tenant_id,
        )

    # ==================== 用户资料更新 / Profile updates ====================

    async def update_tenant_user_profile(
        self,
        user: TenantUser,
        nickname: str | None = None,
        avatar: str | None = None,
        gender: int | None = None,
        phone: str | None = None,
        email: str | None = None,
    ) -> TenantUser:
        """
        更新企业用户个人资料 / Update tenant user profile.

        Args:
            user: 当前用户实例
            nickname: 昵称
            avatar: 头像 URL
            gender: 性别
            phone: 手机号
            email: 邮箱

        Returns:
            更新后的用户实例

        Raises:
            BusinessException: 邮箱或手机号已被占用
        """
        # 检查邮箱唯一性 / Email uniqueness (excluding self)
        if email and email != user.email:
            existing = await self.db.execute(
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

        # 检查手机号唯一性 / Phone uniqueness (excluding self)
        if phone is not None and phone != user.phone:
            if phone:
                existing = await self.db.execute(
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

    # ==================== 忘记密码 / 重置密码 / Forgot password & reset ====================

    LOGIN_CODE_TTL = 600  # 10 分钟 / 10-minute login-code TTL
    LOGIN_CODE_RATE_LIMIT_TTL = (
        60  # 1 分钟内只能发一次 / One login-code request per minute
    )
    RESET_CODE_TTL = 600  # 10 分钟 / 10-minute code TTL
    RESET_RATE_LIMIT_TTL = 60  # 1 分钟内只能发一次 / One request per minute rate limit

    async def request_password_reset(
        self,
        email: str,
        tenant_code: str | None = None,
        tenant_id_from_ctx: int | None = None,
    ) -> dict[str, Any]:
        """
        请求密码重置 / Request password reset.

        生成重置验证码并通过邮件发送

        Args:
            email: 邮箱
            tenant_code: 企业编码
            tenant_id_from_ctx: 来自中间件的企业 ID

        Returns:
            结果信息

        Raises:
            BusinessException: 频率限制或用户不存在
        """
        # 确定企业 / Resolve tenant
        tenant_id = tenant_id_from_ctx
        if not tenant_id and tenant_code:
            result = await self.db.execute(
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

        # 频率限制检查 / Per-email rate limit
        rate_key = f"password_reset_rate:{tenant_id}:{email}"
        if await cache_get(rate_key):
            raise BusinessException(message=_("auth.reset_rate_limited"))

        # 查找用户 / Lookup user by email
        result = await self.db.execute(
            select(TenantUser).where(
                and_(
                    TenantUser.tenant_id == tenant_id,
                    TenantUser.email == email,
                    TenantUser.is_deleted.is_(False),
                )
            )
        )
        user = result.scalar_one_or_none()

        # 无论用户是否存在，都返回成功（防止枚举攻击） / Uniform response to prevent user enumeration
        if user is None:
            logger.warning(f"Password reset requested for non-existent email: {email}")
            return {"message": _("auth.reset_code_sent")}

        # 生成 6 位数验证码 / Generate 6-digit OTP
        code = "".join(secrets.choice(string.digits) for _ in range(6))

        # 存储到 Redis / Store OTP payload in Redis
        code_key = f"password_reset:{tenant_id}:{email}"
        await cache_set(
            code_key, {"code": code, "user_id": user.id}, ttl=self.RESET_CODE_TTL
        )

        # 设置频率限制 / Set rate-limit marker
        await cache_set(rate_key, True, ttl=self.RESET_RATE_LIMIT_TTL)

        # 通过邮件发送验证码 / Send verification code via email
        expire_minutes = self.RESET_CODE_TTL // 60
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
        except Exception as e:
            logger.warning(
                "Failed to queue verification code email: user_id={} tenant_id={} error={}",
                user.id,
                tenant_id,
                str(e),
            )

        logger.info(
            f"Password reset code generated for user {user.id} (tenant={tenant_id})"
        )
        return {"message": _("auth.reset_code_sent")}

    async def reset_tenant_user_password(
        self,
        email: str,
        code: str,
        new_password: str,
        tenant_code: str | None = None,
        tenant_id_from_ctx: int | None = None,
    ) -> None:
        """
        重置企业用户密码 / Reset tenant user password.

        Args:
            email: 邮箱
            code: 验证码
            new_password: 新密码
            tenant_code: 企业编码
            tenant_id_from_ctx: 来自中间件的企业 ID

        Raises:
            BusinessException: 验证码无效或已过期
        """
        # 确定企业 / Resolve tenant
        tenant_id = tenant_id_from_ctx
        if not tenant_id and tenant_code:
            result = await self.db.execute(
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

        # 从 Redis 获取验证码 / Load OTP payload from Redis
        code_key = f"password_reset:{tenant_id}:{email}"
        stored = await cache_get(code_key)

        if not stored or not isinstance(stored, dict):
            raise BusinessException(message=_("auth.reset_code_invalid"))

        if stored.get("code") != code:
            raise BusinessException(message=_("auth.reset_code_invalid"))

        user_id = stored.get("user_id")
        if not user_id:
            raise BusinessException(message=_("auth.reset_code_invalid"))

        # 查找用户 / Load user for update
        result = await self.db.execute(
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

        # 验证新密码策略 / Validate new password policy
        await self._validate_password_policy(new_password, tenant_id=tenant_id)

        # 更新密码 / Persist new hash
        user.password_hash = get_password_hash(new_password)

        # 删除验证码 / Invalidate OTP
        await cache_delete(code_key)

        logger.info(f"Password reset completed for user {user.id} (tenant={tenant_id})")


__all__ = ["AuthService"]
