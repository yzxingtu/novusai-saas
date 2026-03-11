"""
RBAC Permission Check Middleware / RBAC 权限检查中间件

Pre-loads current user's permissions into request.state before route handler.
在请求到达路由处理函数之前，预加载当前用户的权限到 request.state。
Decorators can read permissions from request.state.user_permissions directly.
装饰器可以直接从 request.state.user_permissions 读取权限。
"""

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.database import async_session_factory
from app.core.security import (
    TOKEN_SCOPE_ADMIN,
    TOKEN_SCOPE_TENANT_ADMIN,
    TOKEN_SCOPE_TENANT_USER,
    TOKEN_TYPE_ACCESS,
)
from app.models import Admin, TenantAdmin, TenantUser
from app.models.auth.admin_role import AdminRole
from app.models.auth.tenant_admin_role import TenantAdminRole
from app.models.auth.tenant_user_role import TenantUserRole


class PermissionMiddleware:
    """
    Permission Pre-load Middleware (ASGI implementation).
    权限预加载中间件（ASGI 实现）。

    Features / 功能：
    1. Parse Bearer Token from request headers / 从请求头解析 Bearer Token
    2. Validate Token and get user / 验证 Token 并获取用户
    3. Load user permissions to request.state.user_permissions / 加载用户权限

    Decorators can read permissions from request.state directly, avoiding duplicate DB queries.
    装饰器可以直接从 request.state 读取权限，避免重复查询数据库。
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Create Request object to access state / 创建 Request 对象来访问 state
        request = Request(scope, receive, send)

        # Initialize user_permissions and user / 初始化 user_permissions 和 user
        request.state.user_permissions = set()
        request.state.user = None

        # Get Token from headers / 从请求头获取 Token
        token = self._get_token_from_headers(scope)

        if token:
            # Try to load permissions / 尝试加载权限
            await self._load_permissions(request, token)

        # Continue processing request / 继续处理请求
        await self.app(scope, receive, send)

    def _get_token_from_headers(self, scope: Scope) -> str | None:
        """Get Bearer Token from request headers / 从请求头获取 Bearer Token"""
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("utf-8")

        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return None

    async def _load_permissions(self, request: Request, token: str) -> None:
        """Load user permissions to request.state / 加载用户权限到 request.state"""
        from app.core.security import decode_token

        payload = decode_token(token)
        if not payload or payload.get("type") != TOKEN_TYPE_ACCESS:
            return

        scope = payload.get("scope")
        user_id = payload.get("sub")
        if not user_id:
            return

        if scope == TOKEN_SCOPE_ADMIN:
            await self._load_admin_permissions(request, int(user_id))
        elif scope == TOKEN_SCOPE_TENANT_ADMIN:
            await self._load_tenant_admin_permissions(request, int(user_id))
        elif scope == TOKEN_SCOPE_TENANT_USER:
            await self._load_tenant_user_permissions(request, int(user_id))

    async def _load_admin_permissions(
        self, request: Request, admin_id: int
    ) -> None:
        """Load platform admin permissions / 加载平台管理员权限"""
        async with async_session_factory() as db:
            result = await db.execute(
                select(Admin).where(Admin.id == admin_id)
            )
            admin = result.scalar_one_or_none()

            if admin is None or not admin.is_active:
                return

            # Store user object in state (for audit log etc.) / 将用户对象存入 state
            request.state.user = admin

            # Super admin has all permissions / 超级管理员拥有所有权限
            if admin.is_super:
                request.state.user_permissions = {"*"}
                return

            # No role means no permissions / 无角色则无权限
            if admin.role_id is None:
                return

            permissions: set[str] = set()

            # Get current role's permissions / 获取当前角色的权限
            result = await db.execute(
                select(AdminRole)
                .where(AdminRole.id == admin.role_id)
                .options(selectinload(AdminRole.permissions))
            )
            role = result.scalar_one_or_none()

            if role and role.is_active:
                for p in role.permissions:
                    if p.is_enabled and not p.is_deleted:
                        permissions.add(p.code)

            request.state.user_permissions = permissions

    async def _load_tenant_admin_permissions(
        self, request: Request, tenant_admin_id: int
    ) -> None:
        """Load tenant admin permissions / 加载租户管理员权限"""
        from app.models.tenant.tenant import Tenant

        async with async_session_factory() as db:
            result = await db.execute(
                select(TenantAdmin).where(TenantAdmin.id == tenant_admin_id)
            )
            tenant_admin = result.scalar_one_or_none()

            if tenant_admin is None or not tenant_admin.is_active:
                return

            # Store user object in state (for audit log etc.) / 将用户对象存入 state
            request.state.user = tenant_admin

            # Strict mode: no plan → no permissions (all tenant admins, including owner) / 严格模式：无套餐 → 无权限
            plan_result = await db.execute(
                select(Tenant.plan_id).where(Tenant.id == tenant_admin.tenant_id)
            )
            plan_id = plan_result.scalar_one_or_none()
            if plan_id is None:
                # Tenant has no plan, deny all feature access / 租户未分配套餐
                return

            # Tenant owner has all plan permissions / 租户所有者拥有套餐内全部权限
            if tenant_admin.is_owner:
                request.state.user_permissions = {"*"}
                return

            # No role means no permissions / 无角色则无权限
            if tenant_admin.role_id is None:
                return

            permissions: set[str] = set()

            # Get current role's permissions / 获取当前角色的权限
            result = await db.execute(
                select(TenantAdminRole)
                .where(TenantAdminRole.id == tenant_admin.role_id)
                .options(selectinload(TenantAdminRole.permissions))
            )
            role = result.scalar_one_or_none()

            if role and role.is_active:
                for p in role.permissions:
                    if p.is_enabled and not p.is_deleted:
                        permissions.add(p.code)

            request.state.user_permissions = permissions

    async def _load_tenant_user_permissions(
        self, request: Request, tenant_user_id: int
    ) -> None:
        """Load tenant business user permissions / 加载租户业务用户权限"""
        async with async_session_factory() as db:
            result = await db.execute(
                select(TenantUser).where(TenantUser.id == tenant_user_id)
            )
            tenant_user = result.scalar_one_or_none()

            if tenant_user is None or not tenant_user.is_active:
                return

            # Store user object in state / 将用户对象存入 state
            request.state.user = tenant_user

            # No role means no permissions / 无角色则无权限
            if tenant_user.role_id is None:
                return

            permissions: set[str] = set()

            # Get current role's permissions / 获取当前角色的权限
            result = await db.execute(
                select(TenantUserRole)
                .where(TenantUserRole.id == tenant_user.role_id)
                .options(selectinload(TenantUserRole.permissions))
            )
            role = result.scalar_one_or_none()

            if role and role.is_active:
                for p in role.permissions:
                    if p.is_enabled and not p.is_deleted:
                        permissions.add(p.code)

            request.state.user_permissions = permissions
