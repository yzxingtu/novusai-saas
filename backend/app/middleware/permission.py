"""
RBAC 权限检查中间件

在请求到达路由处理函数之前，预加载当前用户的权限到 request.state。
装饰器可以直接从 request.state.user_permissions 读取权限进行检查。
"""

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request

from app.core.database import async_session_factory
from app.core.security import (
    verify_token_with_scope,
    TOKEN_TYPE_ACCESS,
    TOKEN_SCOPE_ADMIN,
    TOKEN_SCOPE_TENANT_ADMIN,
)
from app.models import Admin, TenantAdmin
from app.models.auth.admin_role import AdminRole
from app.models.auth.tenant_admin_role import TenantAdminRole


class PermissionMiddleware:
    """
    权限预加载中间件（ASGI 实现）
    
    功能：
    1. 从请求头解析 Bearer Token
    2. 验证 Token 并获取用户
    3. 加载用户权限到 request.state.user_permissions
    
    装饰器可以直接从 request.state 读取权限进行检查，
    避免重复查询数据库。
    """
    
    def __init__(self, app: ASGIApp) -> None:
        self.app = app
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # 创建 Request 对象来访问 state
        request = Request(scope, receive, send)
        
        # 初始化 user_permissions 和 user
        request.state.user_permissions = set()
        request.state.user = None
        
        # 从请求头获取 Token
        token = self._get_token_from_headers(scope)
        
        if token:
            # 尝试加载权限
            await self._load_permissions(request, token)
        
        # 继续处理请求
        await self.app(scope, receive, send)
    
    def _get_token_from_headers(self, scope: Scope) -> str | None:
        """从请求头获取 Bearer Token"""
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("utf-8")
        
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return None
    
    async def _load_permissions(self, request: Request, token: str) -> None:
        """加载用户权限到 request.state"""
        # 尝试验证为平台管理员
        user_id, _ = verify_token_with_scope(
            token, TOKEN_SCOPE_ADMIN, TOKEN_TYPE_ACCESS
        )
        
        if user_id:
            await self._load_admin_permissions(request, int(user_id))
            return
        
        # 尝试验证为租户管理员
        user_id, _ = verify_token_with_scope(
            token, TOKEN_SCOPE_TENANT_ADMIN, TOKEN_TYPE_ACCESS
        )
        
        if user_id:
            await self._load_tenant_admin_permissions(request, int(user_id))
            return
    
    async def _load_admin_permissions(
        self, request: Request, admin_id: int
    ) -> None:
        """加载平台管理员权限"""
        async with async_session_factory() as db:
            result = await db.execute(
                select(Admin).where(Admin.id == admin_id)
            )
            admin = result.scalar_one_or_none()
            
            if admin is None or not admin.is_active:
                return
            
            # 将用户对象存入 state（供审计日志等使用）
            request.state.user = admin
            
            # 超级管理员拥有所有权限
            if admin.is_super:
                request.state.user_permissions = {"*"}
                return
            
            # 无角色则无权限
            if admin.role_id is None:
                return
            
            permissions: set[str] = set()
            
            # 获取当前角色的权限
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
        """加载租户管理员权限"""
        async with async_session_factory() as db:
            result = await db.execute(
                select(TenantAdmin).where(TenantAdmin.id == tenant_admin_id)
            )
            tenant_admin = result.scalar_one_or_none()
            
            if tenant_admin is None or not tenant_admin.is_active:
                return
            
            # 将用户对象存入 state（供审计日志等使用）
            request.state.user = tenant_admin
            
            # 租户所有者拥有所有租户权限
            if tenant_admin.is_owner:
                request.state.user_permissions = {"*"}
                return
            
            # 无角色则无权限
            if tenant_admin.role_id is None:
                return
            
            permissions: set[str] = set()
            
            # 获取当前角色的权限
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
