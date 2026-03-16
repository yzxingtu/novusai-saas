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
from sqlalchemy.ext.asyncio import AsyncSession
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
from app.enums.role import DataScope, RoleType
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

            # Super admin has all permissions (and ALL data scope) / 超级管理员拥有所有权限及全部数据
            if admin.is_super:
                request.state.user_permissions = {"*"}
                await self._set_data_permission_ctx(
                    request,
                    admin_id,
                    max_data_scope=DataScope.ALL.value,
                    all_visible_dept_ids=[],
                    primary_department_id=None,
                    custom_dept_ids=[],
                )
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

            # 平台管理员默认 ALL 数据范围 / Platform admin defaults to ALL data scope
            await self._set_data_permission_ctx(
                request,
                admin_id,
                max_data_scope=DataScope.ALL.value,
                all_visible_dept_ids=[],
                primary_department_id=None,
                custom_dept_ids=[],
            )

    async def _load_tenant_admin_permissions(
        self, request: Request, tenant_admin_id: int
    ) -> None:
        """Load tenant admin permissions / 加载企业管理员权限"""
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
                # Tenant has no plan, deny all feature access / 企业未分配套餐
                return

            # Tenant owner has all plan permissions (and ALL data scope) / 企业所有者拥有套餐内全部权限及全部数据
            if tenant_admin.is_owner:
                request.state.user_permissions = {"*"}
                await self._set_data_permission_ctx(
                    request,
                    tenant_admin_id,
                    max_data_scope=DataScope.ALL.value,
                    all_visible_dept_ids=[],
                    primary_department_id=None,
                    custom_dept_ids=[],
                )
                return

            # No role means no permissions / 无角色则无权限
            if tenant_admin.role_id is None:
                await self._set_data_permission_ctx(
                    request,
                    tenant_admin_id,
                    max_data_scope=DataScope.SELF_ONLY.value,
                    all_visible_dept_ids=[],
                    primary_department_id=None,
                    custom_dept_ids=[],
                )
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

            # 企业管理员：从角色加载 data_scope，预计算可见部门 / Tenant admin: load data_scope from role, precompute visible depts
            max_scope, all_dept_ids, primary_dept_id, custom_ids = (
                await self._compute_tenant_admin_data_permission(db, tenant_admin, role)
            )
            await self._set_data_permission_ctx(
                request,
                tenant_admin_id,
                max_data_scope=max_scope,
                all_visible_dept_ids=all_dept_ids,
                primary_department_id=primary_dept_id,
                custom_dept_ids=custom_ids,
            )

    async def _load_tenant_user_permissions(
        self, request: Request, tenant_user_id: int
    ) -> None:
        """Load tenant business user permissions / 加载企业业务用户权限"""
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
                await self._set_data_permission_ctx(
                    request,
                    tenant_user_id,
                    max_data_scope=DataScope.SELF_ONLY.value,
                    all_visible_dept_ids=[],
                    primary_department_id=None,
                    custom_dept_ids=[],
                )
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

            # 企业业务用户默认 SELF_ONLY（TenantUserRole 无 data_scope 字段）/ Tenant user defaults to SELF_ONLY
            await self._set_data_permission_ctx(
                request,
                tenant_user_id,
                max_data_scope=DataScope.SELF_ONLY.value,
                all_visible_dept_ids=[],
                primary_department_id=None,
                custom_dept_ids=[],
            )

    async def _set_data_permission_ctx(
        self,
        request: Request,
        current_user_id: int,
        *,
        max_data_scope: str,
        all_visible_dept_ids: list[int],
        primary_department_id: int | None,
        custom_dept_ids: list[int],
    ) -> None:
        """
        设置数据权限上下文到 ContextVar（供 DataPermissionFilter 使用）
        Set data permission context to ContextVar (for DataPermissionFilter).

        Args:
            request: 当前请求 / Current request
            current_user_id: 当前用户 ID / Current user ID
            max_data_scope: 最宽数据范围 / Max data scope
            all_visible_dept_ids: 可见部门 ID 列表 / Visible department IDs
            primary_department_id: 主部门 ID / Primary department ID
            custom_dept_ids: 自定义部门 ID 列表 / Custom department IDs
        """
        from app.core.data_permission import data_permission_ctx

        ctx = {
            "current_user_id": current_user_id,
            "max_data_scope": max_data_scope,
            "all_visible_dept_ids": all_visible_dept_ids,
            "primary_department_id": primary_department_id,
            "custom_dept_ids": custom_dept_ids,
        }
        data_permission_ctx.set(ctx)
        request.state.data_permission = ctx

    async def _compute_tenant_admin_data_permission(
        self,
        db: AsyncSession,
        tenant_admin: TenantAdmin,
        role: TenantAdminRole | None,
    ) -> tuple[str, list[int], int | None, list[int]]:
        """
        计算企业管理员的数据权限范围
        Compute tenant admin's data permission scope.

        Returns:
            (max_data_scope, all_visible_dept_ids, primary_department_id, custom_dept_ids)
        """
        if role is None or not role.is_active:
            return (
                DataScope.SELF_ONLY.value,
                [],
                None,
                [],
            )

        data_scope = getattr(role, "data_scope", DataScope.SELF_ONLY.value) or DataScope.SELF_ONLY.value
        custom_dept_ids: list[int] = list(role.custom_dept_ids) if role.custom_dept_ids else []

        if data_scope == DataScope.ALL.value:
            return (DataScope.ALL.value, [], None, [])

        if data_scope == DataScope.CUSTOM.value:
            return (DataScope.CUSTOM.value, [], None, custom_dept_ids)

        if data_scope == DataScope.SELF_ONLY.value:
            return (DataScope.SELF_ONLY.value, [], None, [])

        # DEPT_ONLY 或 DEPT_AND_CHILDREN：计算 primary_department_id 和 all_visible_dept_ids
        primary_dept_id: int | None = None
        if role.type == RoleType.DEPARTMENT.value:
            primary_dept_id = role.id
        elif role.type == RoleType.POSITION.value and role.parent_id:
            # 岗位的父节点可能是部门 / Position's parent may be department
            parent_result = await db.execute(
                select(TenantAdminRole).where(TenantAdminRole.id == role.parent_id)
            )
            parent = parent_result.scalar_one_or_none()
            if parent and parent.type == RoleType.DEPARTMENT.value:
                primary_dept_id = parent.id

        if primary_dept_id is None:
            return (DataScope.SELF_ONLY.value, [], None, [])

        if data_scope == DataScope.DEPT_ONLY.value:
            return (DataScope.DEPT_ONLY.value, [primary_dept_id], primary_dept_id, [])

        # DEPT_AND_CHILDREN：当前部门 + 所有子部门（path 前缀匹配）/ Self dept + all children (path prefix match)
        path_result = await db.execute(
            select(TenantAdminRole.path).where(TenantAdminRole.id == primary_dept_id)
        )
        path_row = path_result.scalar_one_or_none()
        my_path = path_row[0] if path_row and path_row[0] else f"/{primary_dept_id}/"
        if not my_path.endswith("/"):
            my_path = my_path + "/"
        children_result = await db.execute(
            select(TenantAdminRole.id).where(
                TenantAdminRole.tenant_id == tenant_admin.tenant_id,
                TenantAdminRole.type == RoleType.DEPARTMENT.value,
                TenantAdminRole.path.startswith(my_path),
                TenantAdminRole.is_deleted.is_(False),
            )
        )
        child_ids = [r[0] for r in children_result.scalars().all()]
        all_visible = list(dict.fromkeys([primary_dept_id] + child_ids))
        return (DataScope.DEPT_AND_CHILDREN.value, all_visible, primary_dept_id, [])
