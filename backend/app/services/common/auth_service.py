"""
认证服务

提供平台管理员、租户管理员、租户用户的认证逻辑
"""

import secrets
import string
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.captcha.service import captcha_service
from app.configs.service import ConfigService
from app.core.base_model import utc_now
from app.core.i18n import _
from app.core.security import (
    TOKEN_SCOPE_ADMIN,
    TOKEN_SCOPE_TENANT_ADMIN,
    TOKEN_SCOPE_TENANT_USER,
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    get_password_hash,
    verify_impersonate_token,
    verify_password,
    verify_token_with_scope,
)
from app.core.logging import LogManager
from app.core.redis import cache_delete, cache_get, cache_set
from app.enums.common import ApprovalStatusEnum
from app.exceptions import AuthenticationException, BusinessException, NotFoundException, ValidationException
from app.models import Admin, Tenant, TenantAdmin, TenantUser

logger = LogManager.get_logger("auth")


class AuthService:
    """
    认证服务

    提供：
    - 平台管理员认证 (Admin)
    - 租户管理员认证 (TenantAdmin)
    - 租户用户认证 (TenantUser)
    - Token 刷新
    - 密码修改
    """

    def __init__(self, db: AsyncSession):
        """
        初始化服务

        Args:
            db: 异步数据库会话
        """
        self.db = db
        self._config_service = ConfigService(db)

    # ==================== 密码策略验证 ====================

    async def _validate_password_policy(
        self, password: str, tenant_id: int | None = None,
    ) -> None:
        """
        验证密码是否符合安全策略

        Args:
            password: 待验证的密码
            tenant_id: 租户 ID（租户端优先使用租户配置，回退到平台配置）

        Raises:
            BusinessException: 密码不符合策略要求
        """
        # 获取密码策略配置（租户端优先使用租户配置）
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
        # 回退到平台配置
        if not min_length:
            min_length = await self._config_service.get_platform_config(
                "password_min_length", default=8
            )
        if not complexity:
            complexity = await self._config_service.get_platform_config(
                "password_complexity", default="medium"
            )

        # 验证密码长度
        if len(password) < min_length:
            raise BusinessException(
                message=_("auth.password_too_short", min_length=min_length)
            )

        # 验证密码复杂度
        if complexity == "low":
            # 仅检查长度（已在上面检查）
            pass
        elif complexity == "medium":
            # 必须包含字母和数字
            has_letter = any(c.isalpha() for c in password)
            has_digit = any(c.isdigit() for c in password)
            if not (has_letter and has_digit):
                raise BusinessException(message=_("auth.password_complexity_medium"))
        elif complexity == "high":
            # 必须包含字母、数字和特殊字符
            has_letter = any(c.isalpha() for c in password)
            has_digit = any(c.isdigit() for c in password)
            has_special = any(not c.isalnum() for c in password)
            if not (has_letter and has_digit and has_special):
                raise BusinessException(message=_("auth.password_complexity_high"))

    # ==================== 平台管理员认证 ====================

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
        平台管理员认证

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
        # 查询管理员
        result = await self.db.execute(
            select(Admin).where(
                or_(Admin.username == username, Admin.email == username),
                Admin.is_deleted.is_(False),
            )
        )
        admin = result.scalar_one_or_none()

        # 检查账户是否存在
        if admin is None:
            await self._record_admin_login_failure(username, client_ip)
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

        # 检查账户锁定状态
        if await self._is_account_locked(admin.id, "admin"):
            raise AuthenticationException(message=_("auth.account_locked"))

        # 检查账户状态（在密码验证之前，防止通过不同错误消息泄漏密码正确性）
        if not admin.is_active:
            raise AuthenticationException(message=_("auth.credentials_invalid"))

        captcha_enabled = await self._config_service.get_platform_config(
            "login_captcha_enabled", default=True
        )
        threshold = await self._config_service.get_platform_config(
            "captcha_enable_threshold_admin", default=2
        )
        fail_count = admin.login_fail_count or 0
        captcha_required = captcha_enabled and (threshold == 0 or fail_count >= threshold)
        if captcha_required:
            await self._verify_captcha(
                captcha_challenge_id,
                captcha_solution,
                captcha_provider_code,
                {"ip": client_ip, "endpoint": "admin", "action": "login"},
            )

        # 验证密码
        if not verify_password(password, admin.password_hash):
            # 记录登录失败
            await self._record_admin_login_failure(username, client_ip)
            next_fail_count = fail_count + 1
            captcha_required_after = captcha_enabled and (
                threshold == 0 or next_fail_count >= threshold
            )
            raise AuthenticationException(
                message=_("auth.credentials_invalid"),
                data={"captcha_required": captcha_required_after},
            )

        # 登录成功，重置失败计数
        await self._reset_admin_login_failures(admin.id)

        # 更新登录信息
        admin.last_login_at = utc_now()
        admin.last_login_ip = client_ip

        # 生成 Token（应用会话配置）
        from datetime import timedelta

        session_timeout = await self._config_service.get_platform_config(
            "session_timeout_minutes", default=120
        )
        access_token = create_access_token(
            admin.id,
            scope=TOKEN_SCOPE_ADMIN,
            expires_delta=timedelta(minutes=session_timeout)
        )
        refresh_token = create_refresh_token(admin.id, scope=TOKEN_SCOPE_ADMIN)

        tokens = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

        return tokens

    # ==================== 登录安全辅助方法 ====================

    async def _record_login_failure(
        self, username: str, client_ip: str | None,
        user_type: str = "admin", tenant_id: int | None = None,
    ) -> None:
        """
        记录登录失败

        Args:
            username: 登录用户名
            client_ip: 客户端IP
            user_type: 用户类型 (admin/tenant_admin/tenant_user)
            tenant_id: 租户 ID（租户端使用租户配置）
        """
        _ = client_ip
        from datetime import timedelta

        # 获取登录失败配置（租户端优先使用租户配置，回退到平台配置）
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

        now = utc_now()

        if user_type == "admin":
            # 处理平台管理员
            result = await self.db.execute(
                select(Admin).where(
                    or_(Admin.username == username, Admin.email == username),
                    Admin.is_deleted.is_(False),
                )
            )
            user = result.scalar_one_or_none()
        elif user_type == "tenant_admin":
            # 处理租户管理员
            result = await self.db.execute(
                select(TenantAdmin).where(
                    or_(TenantAdmin.username == username, TenantAdmin.email == username),
                    TenantAdmin.is_deleted.is_(False),
                )
            )
            user = result.scalar_one_or_none()
        elif user_type == "tenant_user":
            # 处理租户用户
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
            # 增加失败次数
            user.login_fail_count = (user.login_fail_count or 0) + 1
            user.last_fail_at = now

            # 检查是否需要锁定账户
            if user.login_fail_count >= max_attempts:
                user.locked_until = now + timedelta(minutes=lockout_minutes)

            await self.db.commit()

    async def _record_admin_login_failure(self, username: str, client_ip: str | None) -> None:
        """记录平台管理员登录失败"""
        await self._record_login_failure(username, client_ip, "admin")

    async def _is_account_locked(self, user_id: int, user_type: str = "admin") -> bool:
        """
        检查账户是否被锁定

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

        # 检查锁定是否已过期
        now = utc_now()
        return locked_until > now

    async def _reset_login_failures(self, user_id: int, user_type: str = "admin") -> None:
        """
        重置登录失败计数

        Args:
            user_id: 用户ID
            user_type: 用户类型 (admin/tenant_admin/tenant_user)
        """
        if user_type == "admin":
            result = await self.db.execute(
                select(Admin).where(Admin.id == user_id)
            )
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
        """重置平台管理员登录失败计数"""
        await self._reset_login_failures(admin_id, "admin")

    async def _verify_captcha(
        self,
        challenge_id: str | None,
        solution: str | None,
        provider_code: str | None,
        ctx: dict[str, Any],
    ) -> None:
        """
        验证验证码

        Args:
            challenge_id: 验证码挑战ID
            solution: 验证码解决方案
            provider_code: 验证码提供程序代码
            ctx: 上下文信息

        Raises:
            AuthenticationException: 验证码无效
        """
        if not provider_code:
            raise AuthenticationException(
                message=_("auth.captcha_provider_required"),
                data={"captcha_required": True},
            )
        if not challenge_id or not solution:
            raise AuthenticationException(
                message=_("auth.captcha_required"),
                data={"captcha_required": True},
            )
        result = await captcha_service.verify(provider_code, challenge_id, solution, ctx)
        if not result.ok:
            raise AuthenticationException(
                message=_("auth.captcha_invalid"),
                data={"captcha_required": True},
            )

    async def refresh_admin_token(self, refresh_token: str) -> dict[str, Any]:
        """
        刷新平台管理员 Token

        Args:
            refresh_token: 刷新令牌

        Returns:
            新的 tokens

        Raises:
            AuthenticationException: Token 无效
        """
        admin_id, scope = verify_token_with_scope(
            refresh_token, TOKEN_SCOPE_ADMIN, TOKEN_TYPE_REFRESH
        )
        if admin_id is None:
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        # 查询管理员
        result = await self.db.execute(
            select(Admin).where(
                Admin.id == int(admin_id),
                Admin.is_deleted.is_(False),
            )
        )
        admin = result.scalar_one_or_none()

        if admin is None:
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        if not admin.is_active:
            raise AuthenticationException(message=_("auth.account_disabled"))

        return create_token_pair(admin.id, scope=TOKEN_SCOPE_ADMIN)

    async def change_admin_password(
        self,
        admin: Admin,
        old_password: str,
        new_password: str,
    ) -> None:
        """
        修改平台管理员密码

        Args:
            admin: 管理员实例
            old_password: 旧密码
            new_password: 新密码

        Raises:
            BusinessException: 旧密码不正确或新密码不符合策略
        """
        if not verify_password(old_password, admin.password_hash):
            raise BusinessException(message=_("auth.password_mismatch"))

        # 验证新密码符合策略
        await self._validate_password_policy(new_password)

        admin.password_hash = get_password_hash(new_password)

    # ==================== 租户管理员认证 ====================

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
        租户管理员认证

        Args:
            username: 用户名或邮箱
            password: 密码
            tenant_code: 租户编码（优先级最高）
            tenant_id_from_ctx: 来自域名中间件的租户 ID（回退）
            client_ip: 客户端 IP
            captcha_challenge_id: 验证码挑战ID
            captcha_solution: 验证码解决方案
            captcha_provider_code: 验证码提供程序代码

        Returns:
            包含 tokens 的字典

        Raises:
            AuthenticationException: 认证失败
        """
        # 租户域名隔离：必须通过租户域名或显式指定 tenant_code 访问
        if not tenant_code and not tenant_id_from_ctx:
            raise AuthenticationException(
                message=_("auth.tenant_domain_required"),
            )

        # 查询租户管理员
        query = select(TenantAdmin).where(
            or_(
                TenantAdmin.username == username,
                TenantAdmin.email == username,
            ),
            TenantAdmin.is_deleted.is_(False),
        )

        # 按优先级限定租户范围
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
            raise AuthenticationException(
                message=_("auth.tenant_code_required"),
                data={"tenant_code_required": True},
            )

        tenant_admin = results[0] if results else None

        # 检查账户是否存在
        if tenant_admin is None:
            await self._record_login_failure(username, client_ip, "tenant_admin", tenant_id=None)
            raise AuthenticationException(
                message=_("auth.credentials_invalid"),
                data={"captcha_required": False},
            )

        # 检查账户锁定状态
        if await self._is_account_locked(tenant_admin.id, "tenant_admin"):
            raise AuthenticationException(message=_("auth.account_locked"))

        # 检查账户状态（在密码验证之前，防止通过不同错误消息泄漏密码正确性）
        if not tenant_admin.is_active:
            raise AuthenticationException(message=_("auth.credentials_invalid"))

        captcha_enabled = await self._config_service.get_tenant_config(
            tenant_admin.tenant_id, "tenant_captcha_enabled", default=True
        )
        threshold = await self._config_service.get_tenant_config(
            tenant_admin.tenant_id, "tenant_captcha_enable_threshold", default=2
        )
        fail_count = tenant_admin.login_fail_count or 0
        captcha_required = captcha_enabled and (threshold == 0 or fail_count >= threshold)
        if captcha_required:
            await self._verify_captcha(
                captcha_challenge_id,
                captcha_solution,
                captcha_provider_code,
                {"ip": client_ip, "endpoint": "tenant", "action": "login"},
            )

        # 验证密码
        if not verify_password(password, tenant_admin.password_hash):
            await self._record_login_failure(username, client_ip, "tenant_admin", tenant_id=tenant_admin.tenant_id)
            next_fail_count = fail_count + 1
            captcha_required_after = captcha_enabled and (
                threshold == 0 or next_fail_count >= threshold
            )
            raise AuthenticationException(
                message=_("auth.credentials_invalid"),
                data={"captcha_required": captcha_required_after},
            )

        # 检查租户状态
        tenant_result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_admin.tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()

        if tenant is None or not tenant.is_active:
            raise AuthenticationException(message=_("tenant.disabled"))

        # 登录成功，重置失败计数
        await self._reset_login_failures(tenant_admin.id, "tenant_admin")

        # 更新登录信息
        tenant_admin.last_login_at = utc_now()
        tenant_admin.last_login_ip = client_ip

        # 生成 Token（优先使用租户会话配置，回退到平台配置）
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

        return tokens

    async def refresh_tenant_admin_token(self, refresh_token: str) -> dict[str, Any]:
        """
        刷新租户管理员 Token

        Args:
            refresh_token: 刷新令牌

        Returns:
            新的 tokens

        Raises:
            AuthenticationException: Token 无效
        """
        admin_id, scope = verify_token_with_scope(
            refresh_token, TOKEN_SCOPE_TENANT_ADMIN, TOKEN_TYPE_REFRESH
        )
        if admin_id is None:
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        # 查询租户管理员
        result = await self.db.execute(
            select(TenantAdmin).where(
                TenantAdmin.id == int(admin_id),
                TenantAdmin.is_deleted.is_(False),
            )
        )
        tenant_admin = result.scalar_one_or_none()

        if tenant_admin is None:
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        if not tenant_admin.is_active:
            raise AuthenticationException(message=_("auth.account_disabled"))

        return create_token_pair(
            tenant_admin.id,
            scope=TOKEN_SCOPE_TENANT_ADMIN,
            extra_claims={"tenant_id": tenant_admin.tenant_id},
        )

    async def change_tenant_admin_password(
        self,
        tenant_admin: TenantAdmin,
        old_password: str,
        new_password: str,
    ) -> None:
        """
        修改租户管理员密码

        Args:
            tenant_admin: 租户管理员实例
            old_password: 旧密码
            new_password: 新密码

        Raises:
            BusinessException: 旧密码不正确或新密码不符合策略
        """
        if not verify_password(old_password, tenant_admin.password_hash):
            raise BusinessException(message=_("auth.password_mismatch"))

        # 验证新密码符合策略
        await self._validate_password_policy(new_password, tenant_id=tenant_admin.tenant_id)

        tenant_admin.password_hash = get_password_hash(new_password)

    async def impersonate_tenant_admin(
        self,
        impersonate_token: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        验证平台管理员的 impersonate token 并换取正式 Token

        Args:
            impersonate_token: 一键登录令牌

        Returns:
            (tokens, audit_info) 元组

        Raises:
            AuthenticationException: Token 无效
            NotFoundException: 租户或所有者不存在
        """
        # 验证 impersonate token
        payload = verify_impersonate_token(impersonate_token, TOKEN_SCOPE_TENANT_ADMIN)

        if payload is None:
            raise AuthenticationException(message=_("auth.impersonate_token_invalid"))

        admin_id = int(payload["sub"]) if payload.get("sub") else None
        target_tenant_id = payload.get("target_tenant_id")
        target_role_id = payload.get("target_role_id")

        if admin_id is None:
            raise AuthenticationException(message=_("auth.impersonate_token_invalid"))

        # 验证租户状态
        tenant_result = await self.db.execute(
            select(Tenant).where(
                Tenant.id == target_tenant_id,
                Tenant.is_deleted.is_(False),
            )
        )
        tenant = tenant_result.scalar_one_or_none()

        if tenant is None or not tenant.is_active:
            raise AuthenticationException(message=_("tenant.disabled"))

        # 获取租户的所有者信息
        owner_result = await self.db.execute(
            select(TenantAdmin).where(
                TenantAdmin.tenant_id == target_tenant_id,
                TenantAdmin.is_owner.is_(True),
                TenantAdmin.is_deleted.is_(False),
            )
        )
        tenant_owner = owner_result.scalar_one_or_none()

        if tenant_owner is None:
            raise NotFoundException(message=_("tenant.owner_not_found"))

        # 获取执行 impersonate 的平台管理员信息
        platform_admin_result = await self.db.execute(
            select(Admin).where(
                Admin.id == admin_id,
                Admin.is_deleted.is_(False),
            )
        )
        platform_admin = platform_admin_result.scalar_one_or_none()
        platform_admin_username = platform_admin.username if platform_admin else "unknown"

        # 生成正式 Token
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

        # 返回审计信息
        audit_info = {
            "admin_id": admin_id,
            "admin_username": platform_admin_username,
            "target_tenant_id": target_tenant_id,
            "target_tenant_code": tenant.code,
            "tenant_owner_id": tenant_owner.id,
            "target_role_id": target_role_id,
        }

        return tokens, audit_info

    # ==================== 租户用户认证 ====================

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
        租户用户认证

        Args:
            username: 用户名、邮箱或手机号
            password: 密码
            tenant_code: 租户编码（优先级最高）
            tenant_id_from_ctx: 来自域名中间件的租户 ID（回退）
            client_ip: 客户端 IP

        Returns:
            包含 tokens 的字典

        Raises:
            AuthenticationException: 认证失败
        """
        # 租户域名隔离：必须通过租户域名或显式指定 tenant_code 访问
        if not tenant_code and not tenant_id_from_ctx:
            raise AuthenticationException(
                message=_("auth.tenant_domain_required"),
            )

        # 查询用户
        query = select(TenantUser).where(
            or_(
                TenantUser.username == username,
                TenantUser.email == username,
                TenantUser.phone == username,
            ),
            TenantUser.is_deleted.is_(False),
        )

        # 按优先级限定租户范围
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

        # 多条匹配 → 要求指定 tenant_code
        if len(results) > 1:
            raise AuthenticationException(
                message=_("auth.tenant_code_required"),
                data={"tenant_code_required": True},
            )

        user = results[0] if results else None

        # 检查账户是否存在
        if user is None:
            await self._record_login_failure(username, client_ip, "tenant_user", tenant_id=None)
            raise AuthenticationException(
                message=_("auth.credentials_invalid"),
                data={"captcha_required": False},
            )

        # 检查账户锁定状态
        if await self._is_account_locked(user.id, "tenant_user"):
            raise AuthenticationException(message=_("auth.account_locked"))

        # 检查账户状态（在密码验证之前，防止通过不同错误消息泄漏密码正确性）
        if not user.is_active:
            raise AuthenticationException(message=_("auth.credentials_invalid"))

        captcha_enabled = await self._config_service.get_tenant_config(
            user.tenant_id, "tenant_captcha_enabled", default=True
        )
        threshold = await self._config_service.get_tenant_config(
            user.tenant_id, "tenant_captcha_enable_threshold", default=2
        )
        fail_count = user.login_fail_count or 0
        captcha_required = captcha_enabled and (threshold == 0 or fail_count >= threshold)
        if captcha_required:
            await self._verify_captcha(
                captcha_challenge_id,
                captcha_solution,
                captcha_provider_code,
                {"ip": client_ip, "endpoint": "user", "action": "login"},
            )

        # 验证密码
        if not verify_password(password, user.password_hash):
            await self._record_login_failure(username, client_ip, "tenant_user", tenant_id=user.tenant_id)
            next_fail_count = fail_count + 1
            captcha_required_after = captcha_enabled and (
                threshold == 0 or next_fail_count >= threshold
            )
            raise AuthenticationException(
                message=_("auth.credentials_invalid"),
                data={"captcha_required": captcha_required_after},
            )

        # 登录成功，重置失败计数
        await self._reset_login_failures(user.id, "tenant_user")

        # 更新登录信息
        user.last_login_at = utc_now()
        user.last_login_ip = client_ip

        # 生成 Token（优先使用租户会话配置，回退到平台配置）
        session_timeout = await self._config_service.get_tenant_config(
            user.tenant_id, "tenant_session_timeout", default=None
        )
        if not session_timeout:
            session_timeout = await self._config_service.get_platform_config(
                "session_timeout_minutes", default=120
            )
        tokens = create_token_pair(
            user.id,
            scope=TOKEN_SCOPE_TENANT_USER,
            extra_claims={"tenant_id": user.tenant_id},
        )

        return tokens

    async def refresh_tenant_user_token(self, refresh_token: str) -> dict[str, Any]:
        """
        刷新租户用户 Token

        Args:
            refresh_token: 刷新令牌

        Returns:
            新的 tokens

        Raises:
            AuthenticationException: Token 无效
        """
        user_id, scope = verify_token_with_scope(
            refresh_token, TOKEN_SCOPE_TENANT_USER, TOKEN_TYPE_REFRESH
        )
        if user_id is None:
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        # 查询用户
        result = await self.db.execute(
            select(TenantUser).where(
                TenantUser.id == int(user_id),
                TenantUser.is_deleted.is_(False),
            )
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise AuthenticationException(message=_("auth.refresh_token_invalid"))

        if not user.is_active:
            raise AuthenticationException(message=_("auth.account_disabled"))

        return create_token_pair(
            user.id,
            scope=TOKEN_SCOPE_TENANT_USER,
            extra_claims={"tenant_id": user.tenant_id},
        )

    async def change_tenant_user_password(
        self,
        user: TenantUser,
        old_password: str,
        new_password: str,
    ) -> None:
        """
        修改租户用户密码

        Args:
            user: 用户实例
            old_password: 旧密码
            new_password: 新密码

        Raises:
            BusinessException: 旧密码不正确或新密码不符合策略
        """
        if not verify_password(old_password, user.password_hash):
            raise BusinessException(message=_("auth.password_mismatch"))

        # 验证新密码符合策略
        await self._validate_password_policy(new_password, tenant_id=user.tenant_id)

        user.password_hash = get_password_hash(new_password)

    # ==================== 租户用户注册 ====================

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
        租户用户自助注册

        Args:
            username: 用户名
            email: 邮箱
            password: 密码
            tenant_code: 租户编码
            tenant_id_from_ctx: 来自中间件的租户 ID
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
        # 确定租户
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

        # 检查注册是否开放（与前端功能设置 tenant_allow_registration 一致）
        registration_enabled = await self._config_service.get_tenant_config(
            tenant_id, "tenant_allow_registration", default=False
        )
        if not registration_enabled:
            raise BusinessException(message=_("auth.registration_disabled"))

        # 检查注册验证码（注册属于表单验证，验证码错误返回 422 而非 401）
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
                )

        # 检查用户数配额
        from sqlalchemy.orm import selectinload as _selectinload
        from app.services.tenant.quota_service import QuotaService
        tenant_for_quota = (await self.db.execute(
            select(Tenant)
            .options(_selectinload(Tenant.tenant_plan))
            .where(Tenant.id == tenant_id)
        )).scalar_one_or_none()
        if tenant_for_quota:
            quota_svc = QuotaService(self.db, tenant_for_quota)
            quota_check = await quota_svc.check_user_quota()
            if not quota_check.allowed:
                raise BusinessException(
                    message=quota_check.message or _("quota.users_exceeded"),
                )

        # 验证密码策略
        await self._validate_password_policy(password, tenant_id=tenant_id)

        # 检查用户名唯一性
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

        # 检查邮箱唯一性
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

        # 检查手机号唯一性
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

        # 获取审批和激活配置（与前端功能设置 tenant_registration_approval 一致）
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

        # 根据配置决定初始状态
        if require_approval:
            approval_status = ApprovalStatusEnum.PENDING.value
            is_active = False
        else:
            approval_status = ApprovalStatusEnum.APPROVED.value
            is_active = default_active

        # 创建用户
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

        # 需要审批时通知租户管理员
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

        # 如果不需要审批且默认激活，直接返回 token
        if approval_status == ApprovalStatusEnum.APPROVED.value and is_active:
            tokens = create_token_pair(
                user.id,
                scope=TOKEN_SCOPE_TENANT_USER,
                extra_claims={"tenant_id": tenant_id},
            )
            result_data["tokens"] = tokens

        return result_data

    async def _notify_tenant_admins_pending(
        self,
        tenant_id: int,
        username: str,
        email: str,
    ) -> None:
        """注册待审批时通知租户管理员"""
        from app.services.common.notification_service import notify

        # 获取租户所有活跃管理员
        admins = (await self.db.execute(
            select(TenantAdmin).where(
                and_(
                    TenantAdmin.tenant_id == tenant_id,
                    TenantAdmin.is_active.is_(True),
                    TenantAdmin.is_deleted.is_(False),
                )
            )
        )).scalars().all()

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

    # ==================== 用户资料更新 ====================

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
        更新租户用户个人资料

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
        # 检查邮箱唯一性
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

        # 检查手机号唯一性
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

    # ==================== 忘记密码 / 重置密码 ====================

    RESET_CODE_TTL = 600  # 10 分钟
    RESET_RATE_LIMIT_TTL = 60  # 1 分钟内只能发一次

    async def request_password_reset(
        self,
        email: str,
        tenant_code: str | None = None,
        tenant_id_from_ctx: int | None = None,
    ) -> dict[str, Any]:
        """
        请求密码重置

        生成重置验证码并通过邮件发送

        Args:
            email: 邮箱
            tenant_code: 租户编码
            tenant_id_from_ctx: 来自中间件的租户 ID

        Returns:
            结果信息

        Raises:
            BusinessException: 频率限制或用户不存在
        """
        # 确定租户
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

        # 频率限制检查
        rate_key = f"password_reset_rate:{tenant_id}:{email}"
        if await cache_get(rate_key):
            raise BusinessException(message=_("auth.reset_rate_limited"))

        # 查找用户
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

        # 无论用户是否存在，都返回成功（防止枚举攻击）
        if user is None:
            logger.warning(f"Password reset requested for non-existent email: {email}")
            return {"message": _("auth.reset_code_sent")}

        # 生成 6 位数验证码
        code = "".join(secrets.choice(string.digits) for _ in range(6))

        # 存储到 Redis
        code_key = f"password_reset:{tenant_id}:{email}"
        await cache_set(code_key, {"code": code, "user_id": user.id}, ttl=self.RESET_CODE_TTL)

        # 设置频率限制
        await cache_set(rate_key, True, ttl=self.RESET_RATE_LIMIT_TTL)

        # TODO: 通过邮件发送验证码（集成邮件服务后实现）
        logger.info(f"Password reset code generated for user {user.id} (tenant={tenant_id})")

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
        重置租户用户密码

        Args:
            email: 邮箱
            code: 验证码
            new_password: 新密码
            tenant_code: 租户编码
            tenant_id_from_ctx: 来自中间件的租户 ID

        Raises:
            BusinessException: 验证码无效或已过期
        """
        # 确定租户
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

        # 从 Redis 获取验证码
        code_key = f"password_reset:{tenant_id}:{email}"
        stored = await cache_get(code_key)

        if not stored or not isinstance(stored, dict):
            raise BusinessException(message=_("auth.reset_code_invalid"))

        if stored.get("code") != code:
            raise BusinessException(message=_("auth.reset_code_invalid"))

        user_id = stored.get("user_id")
        if not user_id:
            raise BusinessException(message=_("auth.reset_code_invalid"))

        # 查找用户
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

        # 验证新密码策略
        await self._validate_password_policy(new_password, tenant_id=tenant_id)

        # 更新密码
        user.password_hash = get_password_hash(new_password)

        # 删除验证码
        await cache_delete(code_key)

        logger.info(f"Password reset completed for user {user.id} (tenant={tenant_id})")


__all__ = ["AuthService"]
