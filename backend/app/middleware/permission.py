"""
RBAC Permission Check Middleware / RBAC 权限检查中间件

Pre-loads current user's permissions into request.state before route handler.
在请求到达路由处理函数之前，预加载当前用户的权限到 request.state。
Decorators can read permissions from request.state.user_permissions directly.
装饰器可以直接从 request.state.user_permissions 读取权限。
Data permission context (max_data_scope, all_visible_dept_ids, etc.) is also set for DataPermissionFilter.
数据权限上下文（max_data_scope、all_visible_dept_ids 等）供 DataPermissionFilter 使用。
"""

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.database import async_session_factory
from app.core.org_authority import OrgAuthorityResolver
from app.core.security import (
    TOKEN_SCOPE_ADMIN,
    TOKEN_SCOPE_TENANT_ADMIN,
    TOKEN_SCOPE_TENANT_USER,
    TOKEN_TYPE_ACCESS,
)
from app.models import Admin, TenantAdmin, TenantUser
from app.models.auth.admin_role import AdminRole
from app.models.auth.tenant_user_role import TenantUserRole
from app.models.org.admin_org_node import AdminOrgNode


class PermissionMiddleware:
    """
    Permission Pre-load Middleware (ASGI implementation).
    权限预加载中间件（ASGI 实现）。
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from app.core.data_permission import data_permission_ctx

        request = Request(scope, receive, send)
        request.state.user_permissions = set()
        request.state.user = None
        request.state.data_permission = {}

        ctx_token = data_permission_ctx.set({})
        try:
            token = self._get_token_from_headers(scope)
            if token:
                await self._load_permissions(request, token)

            await self.app(scope, receive, send)
        finally:
            data_permission_ctx.reset(ctx_token)

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

        payload = await decode_token(token)
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

    async def _load_admin_permissions(self, request: Request, admin_id: int) -> None:
        """Load platform admin permissions / 加载平台管理员权限"""
        async with async_session_factory() as db:
            result = await db.execute(
                select(Admin)
                .where(Admin.id == admin_id)
                .options(
                    selectinload(Admin.org_node).selectinload(AdminOrgNode.permissions),
                    selectinload(Admin.role).selectinload(AdminRole.permissions),
                )
            )
            admin = result.scalar_one_or_none()

            if admin is None or not admin.is_active:
                return

            request.state.user = admin

            if admin.is_super:
                request.state.user_permissions = {"*"}
                authority = await OrgAuthorityResolver(db).resolve_admin(admin)
                await self._set_data_permission_ctx(
                    request,
                    current_user_id=admin_id,
                    current_user_scope=TOKEN_SCOPE_ADMIN,
                    current_tenant_id=None,
                    authority=authority,
                )
                return

            if admin.org_node_id is None and admin.role_id is None:
                authority = await OrgAuthorityResolver(db).resolve_admin(admin)
                await self._set_data_permission_ctx(
                    request,
                    current_user_id=admin_id,
                    current_user_scope=TOKEN_SCOPE_ADMIN,
                    current_tenant_id=None,
                    authority=authority,
                )
                return

            permissions: set[str] = set()
            if admin.org_node and not admin.org_node.is_deleted:
                for permission in admin.org_node.permissions:
                    if permission.is_enabled and not permission.is_deleted:
                        permissions.add(permission.code)
            elif admin.role and admin.role.is_active:
                for permission in admin.role.permissions:
                    if permission.is_enabled and not permission.is_deleted:
                        permissions.add(permission.code)

            request.state.user_permissions = permissions

            authority = await OrgAuthorityResolver(db).resolve_admin(admin)
            await self._set_data_permission_ctx(
                request,
                current_user_id=admin_id,
                current_user_scope=TOKEN_SCOPE_ADMIN,
                current_tenant_id=None,
                authority=authority,
            )

    async def _load_tenant_admin_permissions(
        self,
        request: Request,
        tenant_admin_id: int,
    ) -> None:
        """Load tenant admin permissions / 加载企业管理员权限"""
        from app.rbac.services.permission_service import PermissionService

        async with async_session_factory() as db:
            result = await db.execute(
                select(TenantAdmin).where(TenantAdmin.id == tenant_admin_id)
            )
            tenant_admin = result.scalar_one_or_none()

            if tenant_admin is None or not tenant_admin.is_active:
                return

            request.state.user = tenant_admin

            request.state.user_permissions = await PermissionService(
                db
            ).get_tenant_admin_permissions(tenant_admin)

            authority = await OrgAuthorityResolver(db).resolve_tenant_admin(
                tenant_admin
            )
            await self._set_data_permission_ctx(
                request,
                current_user_id=tenant_admin_id,
                current_user_scope=TOKEN_SCOPE_TENANT_ADMIN,
                current_tenant_id=tenant_admin.tenant_id,
                authority=authority,
            )

    async def _load_tenant_user_permissions(
        self,
        request: Request,
        tenant_user_id: int,
    ) -> None:
        """Load tenant business user permissions / 加载企业业务用户权限"""
        async with async_session_factory() as db:
            result = await db.execute(
                select(TenantUser).where(TenantUser.id == tenant_user_id)
            )
            tenant_user = result.scalar_one_or_none()

            if tenant_user is None or not tenant_user.is_active:
                return

            request.state.user = tenant_user

            if tenant_user.role_id is None:
                authority = await OrgAuthorityResolver(db).resolve_tenant_user(
                    tenant_user
                )
                await self._set_data_permission_ctx(
                    request,
                    current_user_id=tenant_user_id,
                    current_user_scope=TOKEN_SCOPE_TENANT_USER,
                    current_tenant_id=tenant_user.tenant_id,
                    authority=authority,
                )
                return

            permissions: set[str] = set()
            result = await db.execute(
                select(TenantUserRole)
                .where(TenantUserRole.id == tenant_user.role_id)
                .options(selectinload(TenantUserRole.permissions))
            )
            role = result.scalar_one_or_none()

            if role and role.is_active:
                for permission in role.permissions:
                    if permission.is_enabled and not permission.is_deleted:
                        permissions.add(permission.code)

            request.state.user_permissions = permissions

            authority = await OrgAuthorityResolver(db).resolve_tenant_user(tenant_user)
            await self._set_data_permission_ctx(
                request,
                current_user_id=tenant_user_id,
                current_user_scope=TOKEN_SCOPE_TENANT_USER,
                current_tenant_id=tenant_user.tenant_id,
                authority=authority,
            )

    async def _set_data_permission_ctx(
        self,
        request: Request,
        current_user_id: int,
        current_user_scope: str,
        current_tenant_id: int | None,
        authority,
    ) -> None:
        """
        设置数据权限上下文到 ContextVar（供 DataPermissionFilter 使用）
        Set data permission context to ContextVar (for DataPermissionFilter).
        """
        from app.core.data_permission import data_permission_ctx

        ctx = {
            "current_user_id": current_user_id,
            "current_user_scope": current_user_scope,
            "current_tenant_id": current_tenant_id,
            "scope_mode": authority.scope_mode,
            "max_data_scope": authority.scope_mode,
            "visible_org_ids": authority.visible_org_ids,
            "manageable_org_ids": authority.manageable_org_ids,
            "scope_root_ids": authority.scope_root_ids,
            "effective_scope_org_ids": authority.effective_scope_org_ids,
            "primary_org_id": authority.primary_org_id,
            "custom_org_ids": authority.custom_org_ids,
            "all_visible_dept_ids": authority.effective_scope_org_ids,
            "primary_department_id": authority.primary_org_id,
            "custom_dept_ids": authority.custom_org_ids,
        }
        data_permission_ctx.set(ctx)
        request.state.data_permission = ctx
