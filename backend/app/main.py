"""
FastAPI 应用入口

配置应用实例、中间件、路由、异常处理器等
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, ORJSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.i18n import _, reload_translations
from app.core.database import init_database, close_database
from app.core.response import error, validation_error
from app.core.logging import init_logging, get_logger
from app.exceptions import AppException
from app.middleware.i18n import I18nMiddleware
from app.middleware.permission import PermissionMiddleware
from app.middleware.access_control import AccessControlMiddleware
from app.middleware.tenant import TenantMiddleware
from app.middleware.audit_log import AuditLogMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理
    
    - startup: 应用启动时执行
    - shutdown: 应用关闭时执行
    """
    # ========== Startup ==========
    # 初始化日志系统
    init_logging()
    logger = get_logger(__name__)
    
    # 清除翻译缓存，确保加载最新的翻译文件
    reload_translations()
    
    try:
        logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
        logger.info(f"Environment: {settings.APP_ENV}")
        logger.info(f"Debug mode: {settings.DEBUG}")

        # 初始化数据库（检查/创建数据库 + 运行迁移）
        await init_database()
        logger.info("Database initialized")
        
        # 同步权限到数据库（将装饰器定义的权限同步到 DB）
        from app.core.database import async_session_factory
        from app.rbac.sync import sync_permissions_on_startup
        
        async with async_session_factory() as db:
            sync_result = await sync_permissions_on_startup(db)
            logger.info(
                f"Permissions synced: "
                f"created={sync_result['created']}, "
                f"updated={sync_result['updated']}, "
                f"disabled={sync_result['disabled']}"
            )
        
        # 同步配置到数据库（将代码定义的配置项同步到 DB）
        # 导入配置定义模块（触发配置注册到 registry）
        import app.configs.definitions  # noqa: F401
        from app.configs.sync import sync_configs_on_startup
        
        async with async_session_factory() as db:
            config_sync_result = await sync_configs_on_startup(db)
            logger.info(
                f"Configs synced: "
                f"groups={config_sync_result['groups']}, "
                f"configs={config_sync_result['configs']}"
            )

        # 同步 AI 表策略（自动发现新表并创建默认策略）
        from app.services.ai.table_policy_sync_service import sync_table_policies
        
        async with async_session_factory() as db:
            policy_sync_result = await sync_table_policies(db)
            logger.info(
                f"Table policies synced: "
                f"new={policy_sync_result['new']}, "
                f"existing={policy_sync_result['existing']}, "
                f"blocked={policy_sync_result['blocked']}"
            )

        # 初始化 Redis 连接
        from app.core.redis import RedisManager
        try:
            await RedisManager.init()
            logger.info("Redis initialized")
        except Exception as redis_err:
            logger.warning(f"Redis initialization failed: {redis_err}")

        # 注册核心 AI 适配器（硬编码，不依赖插件系统）
        from app.ai.adapters import AdapterRegistry
        from app.ai.adapters.openai_adapter import OpenAIAdapter
        AdapterRegistry.register("openai_compatible", OpenAIAdapter)

        # 加载插件系统
        from app.plugins.discovery import (
            register_builtin_plugins,
            load_enabled_plugins,
            auto_install_local_plugins,
        )
        from app.plugins.manager import get_plugin_manager
        get_plugin_manager().set_app(app)
        try:
            async with async_session_factory() as db:
                # 注册内置插件（首次启动时自动安装并启用）
                await register_builtin_plugins(db)

                # 开发模式：自动安装本地发现的插件
                if settings.APP_ENV == "development":
                    auto_result = await auto_install_local_plugins(db)
                    if auto_result["installed"] or auto_result["errors"]:
                        logger.info(
                            f"Auto-install local plugins: "
                            f"installed={auto_result['installed']}, "
                            f"skipped={auto_result['skipped']}, "
                            f"errors={len(auto_result['errors'])}"
                        )

                # 加载所有已启用的插件
                plugin_result = await load_enabled_plugins(db)
                if plugin_result["loaded"] or plugin_result["failed"]:
                    logger.info(
                        f"Plugins loaded: "
                        f"loaded={plugin_result['loaded']}, "
                        f"failed={plugin_result['failed']}"
                    )
        except Exception as plugin_err:
            logger.warning(f"Plugin loading failed: {plugin_err}")

        # 清理残留的在线状态数据（服务器重启后旧连接已断开）
        try:
            from app.sio.presence import PresenceManager
            await PresenceManager.clear_all()
        except Exception as presence_err:
            logger.warning(f"Presence cleanup failed: {presence_err}")

        # 应用 WebSocket 平台配置（ping_interval / ping_timeout）
        try:
            from app.core.socketio_server import apply_ws_config
            await apply_ws_config()
        except Exception as ws_cfg_err:
            logger.warning(f"WS config apply failed: {ws_cfg_err}")

        # 种子数据：通知模板
        try:
            from app.sio.notification_seeds import seed_notification_templates
            async with async_session_factory() as db:
                seed_result = await seed_notification_templates(db)
                if seed_result["created"] > 0:
                    logger.info(
                        f"Notification templates seeded: "
                        f"created={seed_result['created']}, "
                        f"existing={seed_result['existing']}"
                    )
        except Exception as seed_err:
            logger.warning(f"Notification template seed failed: {seed_err}")

        # 验证 Celery broker 连通性
        try:
            from app.celery_app import celery_app
            conn = celery_app.connection()
            conn.ensure_connection(max_retries=1, timeout=3)
            conn.close()
            logger.info("Celery broker connected")
        except Exception as celery_err:
            logger.warning(f"Celery broker connection failed: {celery_err}")
        
    except Exception as e:
        # 确保启动阶段的错误能够被记录和显示
        import traceback
        error_msg = f"Startup failed: {e}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        # 同时输出到控制台，确保在日志系统异常时也能看到
        print(error_msg, flush=True)
        traceback.print_exc()
        raise

    yield

    # ========== Shutdown ==========
    logger = get_logger(__name__)
    logger.info(f"Shutting down {settings.APP_NAME}")

    # 关闭数据库连接
    await close_database()
    logger.info("Database connections closed")

    # 关闭 Redis 连接
    from app.core.redis import RedisManager
    await RedisManager.close()
    logger.info("Redis connections closed")


def create_application() -> FastAPI:
    """
    创建 FastAPI 应用实例
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="现代化 AI 集成 SaaS 开发框架",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )
    
    # ========================================
    # 注册中间件
    # ========================================
    
    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # i18n 国际化中间件（纯 ASGI 实现，使用 add_middleware 注册）
    app.add_middleware(I18nMiddleware)
    
    # 维护模式中间件（开启时拦截非管理端请求返回 503）
    from app.middleware.maintenance import MaintenanceMiddleware
    app.add_middleware(MaintenanceMiddleware)
    
    # RBAC 权限预加载中间件（加载用户权限到 request.state）
    app.add_middleware(PermissionMiddleware)
    
    # 审计日志中间件（记录所有 API 调用）
    # 注意：必须在 PermissionMiddleware 之后注册，这样才能从 state 获取用户信息
    app.add_middleware(AuditLogMiddleware)
    
    # 访问控制中间件（实施“默认拒绝”安全策略）
    app.add_middleware(AccessControlMiddleware)
    
    # 租户识别中间件（基于 Host 头解析租户）
    app.add_middleware(TenantMiddleware)
    
    # ========================================
    # 注册异常处理器
    # ========================================
    
    def _get_cors_headers(request: Request) -> dict[str, str]:
        """获取 CORS 响应头"""
        origin = request.headers.get("origin", "")
        # 检查 origin 是否在允许列表中
        if "*" in settings.CORS_ORIGINS or origin in settings.CORS_ORIGINS:
            return {
                "Access-Control-Allow-Origin": origin or "*",
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
            }
        return {}
    
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        """应用异常处理器"""
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
            headers=_get_cors_headers(request),
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """请求验证异常处理器"""
        errors = [
            {
                "field": ".".join(str(loc) for loc in err.get("loc", [])),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        # validation_error() 返回 JSONResponse
        response = validation_error(errors=errors)
        response.headers.update(_get_cors_headers(request))
        return response
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """HTTP 异常处理器"""
        # 映射常见 HTTP 状态码到业务错误码
        status_code_map = {
            400: 4000,
            401: 4010,
            403: 4030,
            404: 4040,
            405: 4050,
            409: 4090,
            422: 4220,
            429: 4290,
            500: 5000,
            502: 5020,
            503: 5030,
        }
        code = status_code_map.get(exc.status_code, exc.status_code * 10)
        # error() 返回 JSONResponse，但需要指定正确的 status_code
        response = error(
            message=str(exc.detail) if exc.detail else None,
            code=code,
            status_code=exc.status_code,
        )
        response.headers.update(_get_cors_headers(request))
        return response
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """全局异常处理器 - 捕获未处理的异常"""
        import traceback
        
        # 记录异常日志
        logger = get_logger(__name__)
        logger.exception(f"Unhandled exception: {exc}")
        
        # DEBUG 模式下返回堆栈跟踪信息
        error_data = None
        if settings.DEBUG:
            error_data = {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        
        response = error(
            message=_("common.server_error"),
            code=5000,
            status_code=500,
            data=error_data,
        )
        response.headers.update(_get_cors_headers(request))
        return response
    
    # ========================================  
    # 注册路由
    # ========================================
    
    @app.get("/", tags=["Root"])
    async def root() -> dict:
        """根路由 - 健康检查"""
        return {
            "code": 0,
            "message": _("common.success"),
            "data": {
                "name": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "status": "healthy",
            },
        }
    
    @app.get("/health", tags=["Health"])
    async def health_check() -> dict:
        """健康检查端点"""
        from app.core.redis import RedisManager
        redis_ok = await RedisManager.health_check()
        return {
            "code": 0,
            "message": _("common.success"),
            "data": {
                "status": "healthy" if redis_ok else "degraded",
                "env": settings.APP_ENV,
                "redis_status": "connected" if redis_ok else "disconnected",
            },
        }
    
    # 注册目录型菜单（必须在控制器导入之前，确保父菜单先注册）
    from app.rbac.menus import register_directory_menus
    register_directory_menus()
    
    # 注册平台管理后台路由 (/admin/*)
    from app.api.admin import admin_router

    # CRUD Generator routes removed — now provided by plugin (novusai-crud-generator)

    app.include_router(admin_router, prefix="/admin")
    
    # 注册租户管理后台路由 (/tenant/*)
    from app.api.tenant import tenant_router
    app.include_router(tenant_router, prefix="/tenant")
    
    # 注册租户业务用户 API v1 路由 (/api/v1/*)
    from app.api.v1 import api_router
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    
    # 注册公共 API 路由 (/api/public/*) - 无需认证，用于租户登录页获取配置
    from app.api.public import public_router
    app.include_router(public_router, prefix="/api/public")

    # ========================================
    # 挂载本地存储静态文件目录
    # ========================================
    from fastapi.staticfiles import StaticFiles
    from app.storage import LOCAL_STORAGE_ROOT
    
    # 确保存储目录存在
    LOCAL_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    
    # 挂载静态文件目录
    # URL 路径: /files/platform/2026/01/25/xxx.png
    # 文件系统路径: backend/storage/uploads/platform/2026/01/25/xxx.png
    app.mount(
        "/files",
        StaticFiles(directory=str(LOCAL_STORAGE_ROOT)),
        name="local_storage",
    )
    
    # ========================================
    # Socket.IO 集成
    # ========================================
    import socketio as _socketio
    from app.core.socketio_server import sio
    from app.sio import register_namespaces

    register_namespaces(sio)

    # 用 ASGIApp 包装 FastAPI，Socket.IO 路径为 /sio
    sio_app = _socketio.ASGIApp(
        sio,
        other_asgi_app=app,
        socketio_path="/sio",
    )

    return sio_app


# 创建应用实例
app = create_application()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
