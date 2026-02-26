"""插件 API 路由分发器

统一的插件 API 入口，根据插件名和路径分发到插件注册的 handler。
所有插件 API 走此 dispatcher，无需动态增删 FastAPI 路由。
禁用插件后请求自动 404（通过 DB 状态检查）。

路径约定:
  /admin/plugins/{plugin_name}/api/{path}
  /tenant/plugins/{plugin_name}/api/{path}
"""

from __future__ import annotations

import asyncio
import inspect
import re
from functools import lru_cache
from typing import TYPE_CHECKING, Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import DbSession, ActiveAdmin, ActiveTenantAdmin
from app.core.logging import get_logger
from app.core.response import success
from app.core.scope import ScopeChecker
from app.core.security import (
    TOKEN_SCOPE_ADMIN,
    TOKEN_SCOPE_TENANT_ADMIN,
)
from app.enums.plugin import PluginStatusEnum
from app.models.system.plugin import Plugin
from app.plugins.module_loader import load_plugin_handler
from app.rbac.decorators import auth_only, public

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

plugin_api_router = APIRouter(tags=["插件 API"])
plugin_tenant_api_router = APIRouter(tags=["插件 API (租户)"])
plugin_public_api_router = APIRouter(tags=["插件 API (公开)"])


async def _dispatch_plugin_api(
    plugin_name: str,
    path: str,
    request: Request,
    db: DbSession,
    tenant_id: int | None = None,
    user_id: int | None = None,
    user_role: str = "",
    allow_public_only: bool = False,
) -> JSONResponse:
    """插件 API 核心分发逻辑（admin/tenant 共用）"""
    # 检查插件是否存在且已启用
    result = await db.execute(
        select(
            Plugin.id, Plugin.status, Plugin.scope,
            Plugin.manifest, Plugin.granted_capabilities,
        ).where(
            Plugin.name == plugin_name,
            Plugin.is_deleted.is_(False),
        )
    )
    row = result.one_or_none()
    if not row or row[1] != PluginStatusEnum.ENABLED.value:
        return JSONResponse(
            status_code=404,
            content={"code": 4040, "message": "Plugin not found or disabled"},
        )

    plugin_id: int = row[0]
    plugin_scope: str = row[2]

    # C1: 租户端 Scope 可见性校验 — 防止越权访问 admin_only / 未分配插件
    if tenant_id is not None:
        visible = await ScopeChecker.is_visible_to_tenant(
            scope=plugin_scope,
            resource_type="plugin",
            resource_id=plugin_id,
            tenant_id=tenant_id,
            db=db,
        )
        if not visible:
            return JSONResponse(
                status_code=404,
                content={"code": 4040, "message": "Plugin not found or disabled"},
            )

    manifest_data = row[3] or {}
    granted_capabilities = row[4] or []

    # 开发模式：从磁盘 plugin.yaml 实时读取路由（改了 yaml 不需要重新禁用/启用）
    # 生产模式：从 DB manifest 快照读取（性能更好）
    if settings.DEBUG:
        try:
            live_manifest = _get_plugin_loader().load_manifest(plugin_name)
            api_config = live_manifest.extensions.api.model_dump() if live_manifest.extensions.api else {}
        except Exception:
            api_config = manifest_data.get("extensions", {}).get("api", {})
    else:
        api_config = manifest_data.get("extensions", {}).get("api", {})

    # 查找匹配的路由
    # 安全规则：
    # 1) allow_public_only=True 时仅允许 public_routes，并且 route.auth 必须为 none
    # 2) tenant 端只匹配 tenant_routes + public_routes，不回退到 admin_routes
    # 3) admin 端匹配 admin_routes + tenant_routes + public_routes（admin 权限 ⊇ tenant）
    method = request.method.upper()
    matched_route = None
    public_routes = api_config.get("public_routes", [])

    if allow_public_only:
        candidate_routes = public_routes
    else:
        request_path = str(request.url.path)
        is_tenant_side = request_path.startswith("/tenant")
        side = "tenant" if is_tenant_side else "admin"
        primary_routes = api_config.get(f"{side}_routes", [])
        # admin 端额外回退到 tenant_routes（admin 是 tenant 的超集）
        fallback_routes = api_config.get("tenant_routes", []) if side == "admin" else []
        candidate_routes = [*primary_routes, *fallback_routes, *public_routes]

    path_params: dict[str, str] = {}
    for route in candidate_routes:
        if allow_public_only and route.get("auth", "required") != "none":
            continue
        route_path = route.get("path", "").strip("/")
        route_method = route.get("method", "GET").upper()
        if route_method != method:
            continue
        matched, params = _match_route_path(route_path, path)
        if matched:
            matched_route = route
            path_params = params
            break

    if not matched_route:
        return JSONResponse(
            status_code=404,
            content={"code": 4040, "message": "Route not found"},
        )

    # 注入提取到的路径参数（如 {doc_id}=123）到 request.path_params
    # 这样 handler 可以通过 request.path_params.get("doc_id") 访问
    if path_params:
        existing = dict(request.path_params)
        existing.update(path_params)
        request.scope["path_params"] = existing

    # 权限动作门控：若路由声明了 permission 字段，校验用户是否拥有该动作权限
    route_permission = matched_route.get("permission", "")
    if route_permission and not allow_public_only:
        has_perm = await _check_plugin_permission(
            db, plugin_name, route_permission, user_id, user_role, tenant_id,
        )
        if not has_perm:
            logger.warning(
                "Plugin permission denied: %s/%s requires '%s' (user=%s role=%s)",
                plugin_name, path, route_permission, user_id, user_role,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "code": 4030,
                    "message": f"Permission denied: action '{route_permission}' required",
                },
            )

    # 加载并执行 handler
    handler_path = matched_route.get("handler", "")
    handler = load_plugin_handler(plugin_name, handler_path)
    if not handler:
        logger.error("Handler '%s' failed to load for plugin '%s'", handler_path, plugin_name)
        return JSONResponse(
            status_code=500,
            content={"code": 5000, "message": "Plugin handler failed to load"},
        )

    # 创建 PluginContext（含 RequestContext）
    ctx = _build_plugin_context(
        plugin_name=plugin_name,
        manifest_data=manifest_data,
        granted_capabilities=granted_capabilities,
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        user_role=user_role,
        request_id=request.headers.get("x-request-id", ""),
    )

    try:
        # 根据 handler 签名自动注入（严格沙箱）：
        # - request: Request
        # - ctx: PluginContext
        # - db: PluginDbProxy（仅声明且具备 db:own_tables 能力时）
        handler_kwargs: dict[str, object] = {}
        if _handler_accepts_param(handler, "request"):
            handler_kwargs["request"] = request
        if _handler_accepts_param(handler, "ctx"):
            handler_kwargs["ctx"] = ctx
        if _handler_accepts_param(handler, "db"):
            if not _context_has_db_capability(ctx):
                return JSONResponse(
                    status_code=403,
                    content={
                        "code": 4030,
                        "message": "Plugin requires granted capability 'db:own_tables' to use db",
                    },
                )
            handler_kwargs["db"] = ctx.get_db()

        if asyncio.iscoroutinefunction(handler):
            result = await handler(**handler_kwargs)
        else:
            result = handler(**handler_kwargs)

        # handler 返回 Response 对象时直接透传（JSONResponse / StreamingResponse 等）
        from starlette.responses import Response as StarletteResponse
        if isinstance(result, StarletteResponse):
            return result
        # handler 返回含 error 的 dict 时转为错误响应
        if isinstance(result, dict) and "error" in result:
            status_code = result.get("status_code", 422)
            return JSONResponse(
                status_code=status_code,
                content={
                    "code": result.get("code", 4220),
                    "message": result["error"],
                },
            )
        # 正常 dict 包装为 success 响应
        if isinstance(result, dict):
            return success(data=result)
        # M4: 非 dict/JSONResponse 兜底 — 包装为 success
        return success(data=result)
    except Exception as exc:
        logger.error(
            "Plugin API handler error: %s/%s: %s",
            plugin_name, path, exc, exc_info=True,
        )
        err_message = str(exc) if settings.DEBUG else "Internal server error"
        return JSONResponse(
            status_code=500,
            content={"code": 5000, "message": err_message},
        )


@plugin_api_router.api_route(
    "/plugins/{plugin_name}/api/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
@auth_only
async def admin_plugin_api(
    plugin_name: str,
    path: str,
    request: Request,
    db: DbSession,
    admin: ActiveAdmin,
):
    """插件 API 分发器（管理端）"""
    return await _dispatch_plugin_api(
        plugin_name, path, request, db,
        tenant_id=None,
        user_id=admin.id,
        user_role=TOKEN_SCOPE_ADMIN,
    )


@plugin_tenant_api_router.api_route(
    "/plugins/{plugin_name}/api/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
@auth_only
async def tenant_plugin_api(
    plugin_name: str,
    path: str,
    request: Request,
    db: DbSession,
    tenant_admin: ActiveTenantAdmin,
):
    """插件 API 分发器（租户端）"""
    return await _dispatch_plugin_api(
        plugin_name, path, request, db,
        tenant_id=tenant_admin.tenant_id,
        user_id=tenant_admin.id,
        user_role=TOKEN_SCOPE_TENANT_ADMIN,
    )


@plugin_public_api_router.api_route(
    "/plugins/{plugin_name}/api/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
@public
async def public_plugin_api(
    plugin_name: str,
    path: str,
    request: Request,
    db: DbSession,
):
    """插件 API 分发器（公开路由，仅 public_routes）"""
    return await _dispatch_plugin_api(
        plugin_name,
        path,
        request,
        db,
        tenant_id=None,
        user_id=None,
        user_role="",
        allow_public_only=True,
    )


@lru_cache(maxsize=256)
def _compile_route_regex(route_pattern: str) -> re.Pattern[str]:
    """编译并缓存路由模式的正则表达式（DEBUG 模式下 enable/disable 时需调用 cache_clear）"""
    regex_parts = []
    for segment in route_pattern.split("/"):
        if segment.startswith("{") and segment.endswith("}"):
            param_name = segment[1:-1]
            regex_parts.append(f"(?P<{param_name}>[^/]+)")
        else:
            regex_parts.append(re.escape(segment))
    return re.compile("^" + "/".join(regex_parts) + "$")


def _match_route_path(route_pattern: str, actual_path: str) -> tuple[bool, dict[str, str]]:
    """
    Match a route pattern against an actual request path, extracting path parameters.

    Pattern: 'docs/{doc_id}/ai/continue'
    Path:    'docs/123/ai/continue'
    Returns: (True, {'doc_id': '123'})

    Pattern: 'folders/{id}'
    Path:    'folders/42'
    Returns: (True, {'id': '42'})
    """
    if "{" not in route_pattern:
        # No parameters — exact match
        return (route_pattern == actual_path, {})

    m = _compile_route_regex(route_pattern).match(actual_path)
    if m:
        return (True, m.groupdict())
    return (False, {})


def _get_plugin_loader():
    """获取模块级缓存的 PluginLoader 实例（避免每次请求新建）"""
    from app.plugins.loader import PluginLoader

    if not hasattr(_get_plugin_loader, "_instance"):
        _get_plugin_loader._instance = PluginLoader()  # type: ignore[attr-defined]
    return _get_plugin_loader._instance  # type: ignore[attr-defined]


def _handler_accepts_param(handler: Callable[..., object], param_name: str) -> bool:
    """检查 handler 是否接受指定参数（含 **kwargs 兼容）。"""
    try:
        sig = inspect.signature(handler)
        if param_name in sig.parameters:
            return True
        return any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in sig.parameters.values()
        )
    except (ValueError, TypeError):
        return False


def _handler_accepts_ctx(handler: Callable[..., object]) -> bool:
    """向后兼容 helper：仅检查显式 ctx 参数（不匹配 **kwargs）。"""
    try:
        sig = inspect.signature(handler)
        return "ctx" in sig.parameters
    except (ValueError, TypeError):
        return False


def _context_has_db_capability(ctx: object) -> bool:
    """检查 PluginContext 是否被授予 db:own_tables 能力。"""
    checker = getattr(ctx, "has_capability", None)
    if not callable(checker):
        return False
    try:
        return bool(checker("db:own_tables"))
    except Exception:
        return False


async def _check_plugin_permission(
    db: AsyncSession,
    plugin_name: str,
    route_permission: str,
    user_id: int | None,
    user_role: str,
    tenant_id: int | None,
) -> bool:
    """
    检查用户是否拥有插件路由要求的权限动作。

    route_permission 格式: "permission_code:action"（如 "novusdoc-pro:comment"）
    - admin 用户默认拥有所有插件权限（超集）
    - tenant_admin 通过 RBAC 权限检查

    Returns:
        True = 允许, False = 拒绝
    """
    if not route_permission or not user_id:
        return False

    # admin 角色默认拥有所有插件权限
    if user_role == TOKEN_SCOPE_ADMIN:
        return True

    # 解析 permission_code:action
    parts = route_permission.split(":")
    if len(parts) != 2:
        logger.warning(
            "Invalid plugin permission format '%s' (expected 'code:action')",
            route_permission,
        )
        return False

    perm_code, action = parts
    full_perm_code = f"plugin.{plugin_name}.{perm_code}"

    # 查询插件注册的权限元数据，校验 action 是否在声明列表中
    from app.plugins.registry import ExtensionRegistry
    registry = ExtensionRegistry.get_instance()
    plugin_perms = registry.get_plugin_permissions(plugin_name)

    declared_actions: set[str] = set()
    for perm in plugin_perms:
        if perm.get("code") == full_perm_code:
            declared_actions = set(perm.get("actions", []))
            break

    if action not in declared_actions:
        # C2: Fail-close — 未声明的 action 默认拒绝
        logger.warning(
            "Plugin permission action '%s' not declared in '%s' actions %s — denying",
            action, full_perm_code, declared_actions,
        )
        return False

    # tenant_admin: 检查 RBAC 权限
    if user_role == TOKEN_SCOPE_TENANT_ADMIN and tenant_id:
        try:
            from app.rbac.services.permission_service import PermissionService
            perm_service = PermissionService(db)

            from app.models import TenantAdmin
            result = await db.execute(
                select(TenantAdmin).where(
                    TenantAdmin.id == user_id,
                    TenantAdmin.tenant_id == tenant_id,
                    TenantAdmin.is_deleted.is_(False),
                )
            )
            ta = result.scalar_one_or_none()
            if not ta:
                return False

            # 租户所有者拥有全部权限
            if ta.is_owner:
                return True

            user_perms = await perm_service.get_tenant_admin_permissions(ta)
            # 检查 full_perm_code:action 格式的权限
            return perm_service.check_permission(user_perms, f"{full_perm_code}:{action}")
        except Exception as exc:
            logger.error("Plugin permission check failed: %s", exc)
            return False

    # 其他角色（如 tenant_user）暂不支持插件权限，拒绝
    return False


def _build_plugin_context(
    plugin_name: str,
    manifest_data: dict[str, object],
    granted_capabilities: list[str],
    db: AsyncSession,
    tenant_id: int | None = None,
    user_id: int | None = None,
    user_role: str = "",
    request_id: str = "",
) -> object:
    """为插件 API handler 创建 PluginContext（含 RequestContext）"""
    from app.plugins.context import RequestContext
    from app.plugins.context_factory import create_plugin_context
    from app.plugins.manifest import PluginManifest

    # 生产模式：以 DB manifest 快照为准，避免磁盘变更突破授权边界
    # DEBUG 模式：允许热加载磁盘 manifest，提升开发体验
    if settings.DEBUG:
        try:
            manifest = _get_plugin_loader().load_manifest(plugin_name)
        except Exception:
            manifest = PluginManifest(**manifest_data)
    else:
        manifest = PluginManifest(**manifest_data)

    req_ctx = RequestContext(
        tenant_id=tenant_id,
        user_id=user_id,
        user_role=user_role,
        request_id=request_id,
    )

    return create_plugin_context(
        plugin_name=plugin_name,
        manifest=manifest,
        db=db,
        granted_capabilities=granted_capabilities,
        request_context=req_ctx,
    )
