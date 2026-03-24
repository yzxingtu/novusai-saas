"""Plugin API route dispatcher / 插件 API 路由分发器

Unified plugin API entry point — dispatches to plugin-registered handlers by plugin name and path.
All plugin APIs go through this dispatcher; no dynamic FastAPI route add/remove needed.
Disabled plugins automatically return 404 (via DB status check).
/
统一的插件 API 入口，根据插件名和路径分发到插件注册的 handler。
所有插件 API 走此 dispatcher，无需动态增删 FastAPI 路由。
禁用插件后请求自动 404（通过 DB 状态检查）。

Path convention / 路径约定:
  /admin/plugins/{plugin_name}/api/{path}
  /tenant/plugins/{plugin_name}/api/{path}
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
from collections.abc import Callable
from functools import lru_cache
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from starlette.responses import Response as StarletteResponse

from app.core.config import settings
from app.core.deps import ActiveAdmin, ActiveTenantAdmin, DbSession
from app.core.i18n import _
from app.core.logging import get_logger
from app.core.response import (
    build_exception_debug,
    error,
    resolve_public_error_message,
    success,
)
from app.core.security import (
    TOKEN_SCOPE_ADMIN,
    TOKEN_SCOPE_TENANT_ADMIN,
)
from app.middleware.trace import normalize_trace_id, trace_id_var
from app.exceptions.base import AppException
from app.plugins.module_loader import load_plugin_handler
from app.plugins.runtime_gate import evaluate_plugin_runtime_gate
from app.rbac.decorators import auth_only, public

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

plugin_api_router = APIRouter(tags=["插件 API"])
plugin_tenant_api_router = APIRouter(tags=["插件 API (企业)"])
plugin_public_api_router = APIRouter(tags=["插件 API (公开)"])
_SAFE_PLUGIN_ERROR_CODES = {4001, 4010, 4030, 4031, 4040}


def _default_plugin_error_code(status_code: int) -> int:
    return {
        400: 4001,
        401: 4010,
        403: 4030,
        404: 4040,
        409: 4090,
        422: 4220,
        429: 4290,
        502: 5020,
        503: 5030,
    }.get(status_code, 5000 if status_code >= 500 else 4220)


def _default_plugin_status_code(code: int) -> int:
    return {
        4001: 400,
        4010: 401,
        4030: 403,
        4031: 403,
        4040: 404,
        4090: 409,
        4220: 422,
        4221: 422,
        4290: 429,
        5000: 500,
        5001: 500,
        5020: 502,
        5030: 503,
    }.get(code, 500 if code >= 5000 else 422)


def _normalize_plugin_error_code(code: Any, status_code: int) -> int:
    try:
        return int(code)
    except (TypeError, ValueError):
        return _default_plugin_error_code(status_code)


def _resolve_plugin_error_message(
    error_message: str | None,
    *,
    code: int,
    status_code: int,
) -> str:
    raw_message = str(error_message or "").strip()
    if code >= 5000 or status_code >= 500:
        return resolve_public_error_message(
            raw_message,
            fallback_message=_("common.server_error"),
        )
    if code not in _SAFE_PLUGIN_ERROR_CODES:
        return resolve_public_error_message(
            raw_message,
            fallback_message=_("common.invalid_request"),
        )
    return raw_message or _("common.invalid_request")


def _extract_json_response_payload(response: StarletteResponse) -> dict[str, Any] | None:
    content_type = response.headers.get("content-type", "")
    body = getattr(response, "body", None)
    if not body or "json" not in content_type.lower():
        return None
    try:
        payload = json.loads(body)
    except (TypeError, ValueError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _raise_plugin_response_error(response: StarletteResponse) -> None:
    status_code = int(getattr(response, "status_code", 500) or 500)
    payload = _extract_json_response_payload(response) or {}
    code = _normalize_plugin_error_code(payload.get("code"), status_code)
    data = payload.get("data")
    extra = {
        key: value
        for key, value in payload.items()
        if key not in {"code", "message", "data", "trace_id", "debug", "error"}
    }
    raise AppException(
        message=_resolve_plugin_error_message(
            payload.get("message") or payload.get("error"),
            code=code,
            status_code=status_code,
        ),
        code=code,
        status_code=status_code,
        data=data,
        extra=extra or None,
    )


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
    """Core plugin API dispatch logic (shared by admin/tenant) / 插件 API 核心分发逻辑（admin/tenant 共用）"""
    gate = await evaluate_plugin_runtime_gate(
        db,
        plugin_name,
        tenant_id=tenant_id,
        require_enabled=True,
        enforce_scope=True,
    )
    if not gate.allowed:
        return error(
            message="Plugin not found or disabled",
            code=4040,
            status_code=404,
        )

    manifest_data = gate.manifest or {}
    granted_capabilities = gate.granted_capabilities or []

    # Dev mode: read routes from disk plugin.yaml in real-time (no need to re-disable/enable after yaml changes) / 开发模式：从磁盘 plugin.yaml 实时读取路由（改了 yaml 不需要重新禁用/启用）
    # Prod mode: read from DB manifest snapshot (better performance) / 生产模式：从 DB manifest 快照读取（性能更好）
    if settings.DEBUG:
        try:
            live_manifest = _get_plugin_loader().load_manifest(plugin_name)
            api_config = live_manifest.extensions.api.model_dump() if live_manifest.extensions.api else {}
        except Exception:
            api_config = manifest_data.get("extensions", {}).get("api", {})
    else:
        api_config = manifest_data.get("extensions", {}).get("api", {})

    # Find matching route / 查找匹配的路由
    # Security rules / 安全规则：
    # 1) When allow_public_only=True, only public_routes allowed, and route.auth must be none
    #    / allow_public_only=True 时仅允许 public_routes，并且 route.auth 必须为 none
    # 2) Tenant side only matches tenant_routes + public_routes, no fallback to admin_routes
    #    / tenant 端只匹配 tenant_routes + public_routes，不回退到 admin_routes
    # 3) Admin side matches admin_routes + public_routes only, no implicit tenant fallback
    #    / admin 端仅匹配 admin_routes + public_routes，不允许隐式回退 tenant_routes
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
        candidate_routes = [*primary_routes, *public_routes]

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
        return error(
            message="Route not found",
            code=4040,
            status_code=404,
        )

    # Inject extracted path params (e.g. {doc_id}=123) into request.path_params so handler can access via request.path_params.get("doc_id") / 注入提取到的路径参数到 request.path_params，供 handler 访问
    if path_params:
        existing = dict(request.path_params)
        existing.update(path_params)
        request.scope["path_params"] = existing

    # Permission action gating: if route declares a permission field, check user has that action permission / 权限动作门控：若路由声明了 permission 字段，校验用户是否拥有该动作权限
    route_permission = matched_route.get("permission", "")
    if route_permission and not allow_public_only:
        has_perm = await _check_plugin_permission(
            db, plugin_name, route_permission, user_id, user_role, tenant_id,
        )
        if not has_perm:
            logger.warning(
                "Plugin permission denied: {}/{} requires '{}' (user={} role={})",
                plugin_name, path, route_permission, user_id, user_role,
            )
            return error(
                message=f"Permission denied: action '{route_permission}' required",
                code=4030,
                status_code=403,
            )

    # Load and execute handler / 加载并执行 handler
    handler_path = matched_route.get("handler", "")
    handler = load_plugin_handler(plugin_name, handler_path)
    if not handler:
        logger.error("Handler '{}' failed to load for plugin '{}'", handler_path, plugin_name)
        return error(
            message="Plugin handler failed to load",
            code=5000,
            status_code=500,
        )

    # Create PluginContext (including RequestContext) / 创建 PluginContext（含 RequestContext）
    request_trace_id = normalize_trace_id(
        getattr(request.state, "trace_id", None)
        or trace_id_var.get()
        or request.headers.get("x-trace-id", "")
        or request.headers.get("x-request-id", ""),
    )
    ctx = _build_plugin_context(
        plugin_name=plugin_name,
        manifest_data=manifest_data,
        granted_capabilities=granted_capabilities,
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        user_role=user_role,
        request_id=request_trace_id,
    )

    try:
        # Auto-inject based on handler signature (strict sandbox) / 根据 handler 签名自动注入（严格沙箱）：
        # - request: Request
        # - ctx: PluginContext
        # - db: PluginDbProxy (only when declared and has db:own_tables capability)
        #   / db: PluginDbProxy（仅声明且具备 db:own_tables 能力时）
        handler_kwargs: dict[str, object] = {}
        if _handler_accepts_param(handler, "request"):
            handler_kwargs["request"] = request
        if _handler_accepts_param(handler, "ctx"):
            handler_kwargs["ctx"] = ctx
        if _handler_accepts_param(handler, "db"):
            if not _context_has_db_capability(ctx):
                return error(
                    message="Plugin requires granted capability 'db:own_tables' to use db",
                    code=4030,
                    status_code=403,
                )
            handler_kwargs["db"] = ctx.get_db()

        if asyncio.iscoroutinefunction(handler):
            result = await handler(**handler_kwargs)
        else:
            result = handler(**handler_kwargs)

        # Pass through directly when handler returns a Response object (JSONResponse / StreamingResponse, etc.)
        # / handler 返回 Response 对象时直接透传（JSONResponse / StreamingResponse 等）
        if isinstance(result, StarletteResponse):
            if int(getattr(result, "status_code", 200) or 200) >= 400:
                _raise_plugin_response_error(result)
            return result
        # Convert to error response when handler returns dict containing 'error'
        # / handler 返回含 error 的 dict 时转为错误响应
        if isinstance(result, dict) and "error" in result:
            code = _normalize_plugin_error_code(
                result.get("code"),
                int(result.get("status_code") or 422),
            )
            status_code = result.get("status_code")
            if status_code is None:
                status_code = _default_plugin_status_code(code)
            error_message = _resolve_plugin_error_message(
                str(result["error"]),
                code=code,
                status_code=int(status_code),
            )
            # Raise exception to ensure get_db triggers rollback, preventing commit after plugin write failure
            # / 以异常返回错误，确保 get_db 触发 rollback，避免插件写入后逻辑失败仍被 commit
            raise AppException(
                message=error_message,
                code=code,
                status_code=status_code,
            )
        # Wrap normal dict as success response / 正常 dict 包装为 success 响应
        if isinstance(result, dict):
            return success(data=result)
        # M4: Fallback for non-dict/JSONResponse — wrap as success / 非 dict/JSONResponse 兜底 — 包装为 success
        return success(data=result)
    except AppException:
        raise
    except Exception as exc:
        logger.error(
            "Plugin API handler error: {}/{}: {}",
            plugin_name, path, exc, exc_info=True,
        )
        raise AppException(
            message=_("common.server_error"),
            code=5000,
            status_code=500,
            debug=build_exception_debug(exc),
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
    """Plugin API dispatcher (admin side) / 插件 API 分发器（管理端）"""
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
    """Plugin API dispatcher (tenant side) / 插件 API 分发器（企业端）"""
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
    """Plugin API dispatcher (public routes, public_routes only) / 插件 API 分发器（公开路由，仅 public_routes）"""
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
    """Compile and cache route pattern regex (call cache_clear on enable/disable in DEBUG mode) / 编译并缓存路由模式的正则表达式（DEBUG 模式下 enable/disable 时需调用 cache_clear）"""
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
    将路由模式与实际请求路径匹配并提取路径参数 / Match a route pattern against an actual request path, extracting path parameters.

    Pattern: 'docs/{doc_id}/ai/continue'
    Path:    'docs/123/ai/continue'
    Returns: (True, {'doc_id': '123'})

    Pattern: 'folders/{id}'
    Path:    'folders/42'
    Returns: (True, {'id': '42'})
    """
    if "{" not in route_pattern:
        # No parameters — exact match / 无参数时精确匹配
        return (route_pattern == actual_path, {})

    m = _compile_route_regex(route_pattern).match(actual_path)
    if m:
        return (True, m.groupdict())
    return (False, {})


def _get_plugin_loader():
    """Get module-level cached PluginLoader instance (avoid creating new one per request) / 获取模块级缓存的 PluginLoader 实例（避免每次请求新建）"""
    from app.plugins.loader import PluginLoader

    if not hasattr(_get_plugin_loader, "_instance"):
        _get_plugin_loader._instance = PluginLoader()  # type: ignore[attr-defined]
    return _get_plugin_loader._instance  # type: ignore[attr-defined]


def _handler_accepts_param(handler: Callable[..., object], param_name: str) -> bool:
    """Check if handler explicitly accepts the specified parameter. / 检查 handler 是否显式接受指定参数。

    Returns True only when param_name is an explicit parameter. **kwargs does NOT
    count—we do not auto-inject ctx into handlers that only have **kwargs.
    """
    try:
        sig = inspect.signature(handler)
        return param_name in sig.parameters
    except (ValueError, TypeError):
        return False


def _context_has_db_capability(ctx: object) -> bool:
    """Check if PluginContext has been granted db:own_tables capability. / 检查 PluginContext 是否被授予 db:own_tables 能力。"""
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
    Check if user has the permission action required by the plugin route.
    / 检查用户是否拥有插件路由要求的权限动作。

    route_permission format / 格式: "permission_code:action" (e.g. "novusdoc:list")
    - admin checked via platform RBAC / admin 通过平台 RBAC 权限检查
    - tenant_admin checked via RBAC / tenant_admin 通过 RBAC 权限检查

    Returns:
        True = allow / 允许, False = deny / 拒绝
    """
    if not route_permission or not user_id:
        return False

    # Parse permission_code:action / 解析 permission_code:action
    parts = route_permission.split(":")
    if len(parts) != 2:
        logger.warning(
            "Invalid plugin permission format '{}' (expected 'code:action')",
            route_permission,
        )
        return False

    perm_code, action = parts
    full_perm_code = f"plugin.{plugin_name}.{perm_code}"

    # Query plugin registered permission metadata, verify action is in declared list
    # / 查询插件注册的权限元数据，校验 action 是否在声明列表中
    from app.plugins.registry import ExtensionRegistry
    registry = ExtensionRegistry.get_instance()
    plugin_perms = registry.get_plugin_permissions(plugin_name)

    declared_actions: set[str] = set()
    for perm in plugin_perms:
        if perm.get("code") == full_perm_code:
            declared_actions = set(perm.get("actions", []))
            break

    if action not in declared_actions:
        # C2: Fail-close — undeclared actions denied by default / 未声明的 action 默认拒绝
        logger.warning(
            "Plugin permission action '{}' not declared in '{}' actions {} — denying",
            action, full_perm_code, declared_actions,
        )
        return False

    if user_role == TOKEN_SCOPE_ADMIN:
        try:
            from app.models import Admin
            from app.rbac.services.permission_service import PermissionService

            perm_service = PermissionService(db)
            result = await db.execute(
                select(Admin).where(
                    Admin.id == user_id,
                    Admin.is_deleted.is_(False),
                )
            )
            admin = result.scalar_one_or_none()
            if not admin:
                return False

            user_perms = await perm_service.get_admin_permissions(admin)
            return perm_service.check_permission(user_perms, f"{full_perm_code}:{action}")
        except Exception as exc:
            logger.error("Plugin permission check failed: {}", exc)
            return False

    # tenant_admin: check RBAC permissions / 检查 RBAC 权限
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

            # Tenant owner has all permissions / 企业所有者拥有全部权限
            if ta.is_owner:
                return True

            user_perms = await perm_service.get_tenant_admin_permissions(ta)
            # Check permission in full_perm_code:action format / 检查 full_perm_code:action 格式的权限
            return perm_service.check_permission(user_perms, f"{full_perm_code}:{action}")
        except Exception as exc:
            logger.error("Plugin permission check failed: {}", exc)
            return False

    # Other roles (e.g. tenant_user) don't support plugin permissions yet, deny / 其他角色（如 tenant_user）暂不支持插件权限，拒绝
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
    """Create PluginContext for plugin API handler (including RequestContext) / 为插件 API handler 创建 PluginContext（含 RequestContext）"""
    from app.plugins.context import RequestContext
    from app.plugins.context_factory import create_plugin_context
    from app.plugins.manifest import PluginManifest

    # Prod mode: use DB manifest snapshot to prevent disk changes from bypassing auth boundaries / 生产模式：以 DB manifest 快照为准，避免磁盘变更突破授权边界
    # DEBUG mode: allow hot-loading disk manifest for better dev experience / DEBUG 模式：允许热加载磁盘 manifest，提升开发体验
    if settings.DEBUG:
        try:
            manifest = _get_plugin_loader().load_manifest(plugin_name)
        except Exception:
            manifest = PluginManifest.model_validate(manifest_data)
    else:
        manifest = PluginManifest.model_validate(manifest_data)

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
