"""
插件 API 路由分发器

统一的插件 API 入口，根据插件名和路径分发到插件注册的 handler。
所有插件 API 走此 dispatcher，无需动态增删 FastAPI 路由。
禁用插件后请求自动 404（通过 DB 状态检查）。

路径约定:
  /admin/plugins/{plugin_name}/api/{path}
  /tenant/plugins/{plugin_name}/api/{path}
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.deps import DbSession, ActiveAdmin, ActiveTenantAdmin
from app.core.logging import get_logger
from app.core.response import success
from app.rbac.decorators import auth_only

logger = get_logger(__name__)

plugin_api_router = APIRouter(tags=["插件 API"])
plugin_tenant_api_router = APIRouter(tags=["插件 API (租户)"])


async def _dispatch_plugin_api(
    plugin_name: str,
    path: str,
    request: Request,
    db: DbSession,
) -> JSONResponse:
    """插件 API 核心分发逻辑（admin/tenant 共用）"""
    from sqlalchemy import select

    from app.models.system.plugin import Plugin

    # 检查插件是否存在且已启用
    result = await db.execute(
        select(Plugin.status, Plugin.manifest).where(
            Plugin.name == plugin_name,
            Plugin.is_deleted.is_(False),
        )
    )
    row = result.one_or_none()
    from app.enums.plugin import PluginStatusEnum
    if not row or row[0] != PluginStatusEnum.ENABLED.value:
        return JSONResponse(
            status_code=404,
            content={"code": 4040, "message": f"Plugin '{plugin_name}' not found or disabled"},
        )

    # 开发模式：从磁盘 plugin.yaml 实时读取路由（改了 yaml 不需要重新禁用/启用）
    # 生产模式：从 DB manifest 快照读取（性能更好）
    from app.core.config import settings
    if settings.DEBUG:
        try:
            from app.plugins.loader import PluginLoader
            live_manifest = PluginLoader().load_manifest(plugin_name)
            api_config = live_manifest.extensions.api.model_dump() if live_manifest.extensions.api else {}
        except Exception:
            manifest_data = row[1] or {}
            api_config = manifest_data.get("extensions", {}).get("api", {})
    else:
        manifest_data = row[1] or {}
        api_config = manifest_data.get("extensions", {}).get("api", {})

    # 确定是哪个 side 的路由（从请求路径判断）
    request_path = str(request.url.path)
    if request_path.startswith("/tenant"):
        side = "tenant"
    else:
        side = "admin"

    # 查找匹配的路由（优先当前 side，再 fallback 其他 side）
    method = request.method.upper()
    matched_route = None
    primary_routes = api_config.get(f"{side}_routes", [])
    fallback_side = "tenant" if side == "admin" else "admin"
    fallback_routes = api_config.get(f"{fallback_side}_routes", [])

    for route in [*primary_routes, *fallback_routes]:
        route_path = route.get("path", "").strip("/")
        route_method = route.get("method", "GET").upper()
        if route_path == path and route_method == method:
            matched_route = route
            break

    if not matched_route:
        return JSONResponse(
            status_code=404,
            content={"code": 4040, "message": f"Route {method} /{path} not found in plugin '{plugin_name}'"},
        )

    # 加载并执行 handler
    handler_path = matched_route.get("handler", "")
    handler = _load_plugin_handler(plugin_name, handler_path)
    if not handler:
        return JSONResponse(
            status_code=500,
            content={"code": 5000, "message": f"Handler '{handler_path}' failed to load"},
        )

    try:
        # 传递 request 和 db 给 handler
        if _is_async(handler):
            result = await handler(request=request, db=db)
        else:
            result = handler(request=request, db=db)

        # handler 返回 JSONResponse 时直接透传
        if isinstance(result, JSONResponse):
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
        return result
    except Exception as exc:
        logger.error(
            "Plugin API handler error: %s/%s: %s",
            plugin_name, path, exc, exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={"code": 5000, "message": str(exc)},
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
    return await _dispatch_plugin_api(plugin_name, path, request, db)


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
    return await _dispatch_plugin_api(plugin_name, path, request, db)


def _load_plugin_handler(plugin_name: str, handler_path: str):
    """加载插件 API handler — 委托给统一加载器"""
    from app.plugins.module_loader import load_plugin_handler
    return load_plugin_handler(plugin_name, handler_path)


def _is_async(func) -> bool:
    """检查函数是否为异步"""
    import asyncio
    return asyncio.iscoroutinefunction(func)
