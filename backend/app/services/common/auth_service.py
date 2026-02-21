"""
认证服务

提供平台管理员、租户管理员、租户用户的认证逻辑
"""

from typing import Any

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.configs.service import ConfigService
from app.core.i18n import _
from app.captcha.service import captcha_service
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    create_token_pair,
    verify_token_with_scope,
    verify_impersonate_token,
    TOKEN_TYPE_REFRESH,
    TOKEN_SCOPE_ADMIN,
    TOKEN_SCOPE_TENANT_ADMIN,
    TOKEN_SCOPE_TENANT_USER,
)
from app.exceptions import AuthenticationException, BusinessException, NotFoundException
from app.models import Admin, TenantAdmin, TenantUser, Tenant
from app.core.base_model import utc_now


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

    async def _validate_password_policy(self, password: str) -> None:
        """
        验证密码是否符合平台安全策略

        Args:
            password: 待验证的密码

        Raises:
            BusinessException: 密码不符合策略要求
        """
        # 获取密码策略配置
        min_length = await self._config_service.get_platform_config(
            "password_min_length", default=8
        )
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

    async def _record_login_failure(self, username: str, client_ip: str | None, user_type: str = "admin") -> None:
        """
        记录登录失败

        Args:
            username: 登录用户名
            client_ip: 客户端IP
            user_type: 用户类型 (admin/tenant_admin/tenant_user)
        """
        from datetime import timedelta

        # 获取登录失败配置
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
            client_ip: 客户端 IP
            captcha_challenge_id: 验证码挑战ID
            captcha_solution: 验证码解决方案
            captcha_provider_code: 验证码提供程序代码
        
        Returns:
            包含 tokens 的字典
        
        Raises:
            AuthenticationException: 认证失败
        """
        # 查询租户管理员
        result = await self.db.execute(
            select(TenantAdmin).where(
                or_(
                    TenantAdmin.username == username,
                    TenantAdmin.email == username,
                ),
                TenantAdmin.is_deleted.is_(False),
            )
        )
        tenant_admin = result.scalar_one_or_none()

        # 检查账户是否存在
        if tenant_admin is None:
            await self._record_login_failure(username, client_ip, "tenant_admin")
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
            await self._record_login_failure(username, client_ip, "tenant_admin")
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

        # 生成 Token（应用会话配置）
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
        await self._validate_password_policy(new_password)

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
            client_ip: 客户端 IP
        
        Returns:
            包含 tokens 的字典
        
        Raises:
            AuthenticationException: 认证失败
        """
        # 查询用户
        result = await self.db.execute(
            select(TenantUser).where(
                or_(
                    TenantUser.username == username,
                    TenantUser.email == username,
                    TenantUser.phone == username,
                ),
                TenantUser.is_deleted.is_(False),
            )
        )
        user = result.scalar_one_or_none()

        # 检查账户是否存在
        if user is None:
            await self._record_login_failure(username, client_ip, "tenant_user")
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
            await self._record_login_failure(username, client_ip, "tenant_user")
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

        # 生成 Token（应用会话配置）
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
        await self._validate_password_policy(new_password)

        user.password_hash = get_password_hash(new_password)


__all__ = ["AuthService"]
