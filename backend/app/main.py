"""
FastAPI 应用入口

配置应用实例、中间件、路由、异常处理器等
"""

import asyncio
import warnings
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.database import close_database, init_database
from app.core.i18n import _, reload_translations
from app.core.logging import get_logger, init_logging
from app.core.response import error, validation_error
from app.exceptions import AppException
from app.middleware.access_control import AccessControlMiddleware
from app.middleware.audit_log import AuditLogMiddleware
from app.middleware.i18n import I18nMiddleware
from app.middleware.permission import PermissionMiddleware
from app.middleware.tenant import TenantMiddleware

# 抑制 requests 库的版本兼容性噪音警告（urllib3/charset_normalizer 版本超出其预设测试范围，但实际兼容）
warnings.filterwarnings("ignore", message=".*urllib3.*doesn't match a supported version.*")
warnings.filterwarnings("ignore", message=".*chardet.*doesn't match a supported version.*")
warnings.filterwarnings("ignore", message=".*charset_normalizer.*doesn't match a supported version.*")


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
        if not await init_database():
            raise RuntimeError("Database initialization failed")
        logger.info("Database initialized")

        # 提前初始化 Redis（后续启动步骤的分布式锁依赖 Redis）
        from app.core.redis import RedisManager as _RedisManager
        try:
            await _RedisManager.init()
            logger.info("Redis initialized (early, for startup locks)")
        except Exception as _redis_early_err:
            logger.warning(f"Redis early initialization failed: {_redis_early_err}")

        # 同步权限到数据库（将装饰器定义的权限同步到 DB）
        # 使用分布式锁防止多 worker 并发同步，避免 Permission INSERT IntegrityError
        from app.core.database import async_session_factory
        from app.rbac.sync import sync_permissions_on_startup

        _perm_lock_key = "plugin:startup:perm_sync_lock"
        _perm_owner = str(__import__("uuid").uuid4())
        _perm_redis = None
        _perm_locked = False
        try:
            from app.core.redis import get_redis_client
            _perm_redis = get_redis_client()
            _perm_locked = await _perm_redis.set(
                _perm_lock_key, _perm_owner, nx=True, ex=60,
            )
        except Exception:
            _perm_locked = True  # Redis 不可用时降级为无锁

        if _perm_locked:
            try:
                async with async_session_factory() as db:
                    sync_result = await sync_permissions_on_startup(db)
                    logger.info(
                        f"Permissions synced: "
                        f"created={sync_result['created']}, "
                        f"updated={sync_result['updated']}, "
                        f"disabled={sync_result['disabled']}"
                    )
            finally:
                if _perm_redis and _perm_locked is True:
                    try:
                        from app.plugins.lifecycle import _UNLOCK_IF_OWNER_LUA
                        await _perm_redis.eval(_UNLOCK_IF_OWNER_LUA, 1, _perm_lock_key, _perm_owner)
                    except Exception:
                        pass
        else:
            logger.debug("Permission sync: skipped (another worker is syncing)")

        # 同步配置到数据库（将代码定义的配置项同步到 DB）
        # 使用分布式锁防止多 worker 并发 INSERT 配置项/分组
        # 导入配置定义模块（触发配置注册到 registry）
        # NOTE: 使用 from...import 而非 import app.xxx，避免遮蔽 lifespan 的 app 参数
        from app.configs import definitions as _configs_definitions  # noqa: F401
        from app.configs.sync import sync_configs_on_startup

        _cfg_owner = str(__import__("uuid").uuid4())
        _cfg_redis = None
        _cfg_locked = False
        try:
            from app.core.redis import get_redis_client as _get_rc2
            _cfg_redis = _get_rc2()
            _cfg_locked = await _cfg_redis.set("plugin:startup:config_sync_lock", _cfg_owner, nx=True, ex=60)
        except Exception:
            _cfg_locked = True

        if _cfg_locked:
            try:
                async with async_session_factory() as db:
                    config_sync_result = await sync_configs_on_startup(db)
                    logger.info(
                        f"Configs synced: "
                        f"groups={config_sync_result['groups']}, "
                        f"configs={config_sync_result['configs']}"
                    )
            finally:
                if _cfg_redis and _cfg_locked is True:
                    try:
                        from app.plugins.lifecycle import _UNLOCK_IF_OWNER_LUA
                        await _cfg_redis.eval(_UNLOCK_IF_OWNER_LUA, 1, "plugin:startup:config_sync_lock", _cfg_owner)
                    except Exception:
                        pass

        # 同步 AI 表策略（自动发现新表并创建默认策略）
        # 使用分布式锁防止多 worker 并发 INSERT 策略记录
        from app.services.ai.table_policy_sync_service import sync_table_policies

        _tp_owner = str(__import__("uuid").uuid4())
        _tp_redis = None
        _tp_locked = False
        try:
            from app.core.redis import get_redis_client as _get_rc3
            _tp_redis = _get_rc3()
            _tp_locked = await _tp_redis.set("plugin:startup:table_policy_lock", _tp_owner, nx=True, ex=60)
        except Exception:
            _tp_locked = True

        if _tp_locked:
            try:
                async with async_session_factory() as db:
                    policy_sync_result = await sync_table_policies(db)
                    logger.info(
                        f"Table policies synced: "
                        f"new={policy_sync_result['new']}, "
                        f"existing={policy_sync_result['existing']}, "
                        f"blocked={policy_sync_result['blocked']}"
                    )
            finally:
                if _tp_redis and _tp_locked is True:
                    try:
                        from app.plugins.lifecycle import _UNLOCK_IF_OWNER_LUA
                        await _tp_redis.eval(_UNLOCK_IF_OWNER_LUA, 1, "plugin:startup:table_policy_lock", _tp_owner)
                    except Exception:
                        pass

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

        # 插件自动发现 + 恢复
        # 注意：多 worker 并发启动时，discover_and_register 会并发执行。
        # 使用 Redis 分布式锁确保只有一个 worker 执行 discover（含 alembic 迁移）。
        # restore 采用双阶段：
        # 1) owner worker 执行重恢复（迁移/依赖补装/状态写回）
        # 2) 其他 worker 等待 owner 完成后，仅做进程内扩展注册（不写库）
        try:
            from app.plugins.startup import (
                discover_and_register,
                restore_enabled_plugins,
            )

            # Phase 1: 自动发现（分布式锁保护，避免多 worker 并发迁移竞争）
            _discover_lock_key = "plugin:startup:discover_lock"
            _discover_lock_ttl = 120  # 秒
            _discover_owner = str(__import__("uuid").uuid4())
            _redis_client = None
            _discover_locked = False
            try:
                from app.core.redis import get_redis_client

                _redis_client = get_redis_client()
                _discover_locked = await _redis_client.set(
                    _discover_lock_key, _discover_owner, nx=True, ex=_discover_lock_ttl
                )
            except Exception as _redis_err:
                logger.warning(f"Plugin discover lock unavailable (Redis error): {_redis_err}")
                _discover_locked = True  # Redis 不可用时降级为无锁（保持原有行为）

            if _discover_locked:
                try:
                    async with async_session_factory() as db:
                        discover_result = await discover_and_register(db)
                        await db.commit()
                        if discover_result["discovered"] > 0 or discover_result["missing"] > 0:
                            logger.info(
                                f"Plugin discover: "
                                f"discovered={discover_result['discovered']}, "
                                f"synced={discover_result['synced']}, "
                                f"missing={discover_result['missing']}, "
                                f"failed={discover_result['failed']}"
                            )
                finally:
                    if _redis_client and _discover_locked is True:
                        try:
                            from app.plugins.lifecycle import _UNLOCK_IF_OWNER_LUA

                            await _redis_client.eval(_UNLOCK_IF_OWNER_LUA, 1, _discover_lock_key, _discover_owner)
                        except Exception:
                            pass
            else:
                logger.info("Plugin discover: skipped (another worker is running discovery)")

            # Phase 2: 恢复（owner 重恢复 + 其他 worker 仅本进程注册）
            _restore_lock_key = "plugin:startup:restore_lock"
            _restore_lock_ttl = 900  # 覆盖迁移/依赖补装的最长路径
            _restore_owner = str(__import__("uuid").uuid4())
            _restore_redis = None
            _restore_locked = False
            try:
                from app.core.redis import get_redis_client

                _restore_redis = get_redis_client()
                _restore_locked = await _restore_redis.set(
                    _restore_lock_key, _restore_owner, nx=True, ex=_restore_lock_ttl
                )
            except Exception as _redis_err:
                logger.warning(f"Plugin restore lock unavailable (Redis error): {_redis_err}")
                _restore_locked = True  # Redis 不可用时降级为旧行为（每 worker 重恢复）

            if _restore_locked:
                try:
                    async with async_session_factory() as db:
                        plugin_result = await restore_enabled_plugins(
                            db,
                            run_heavy=True,
                            mutate_db_status=True,
                        )
                        await db.commit()
                        if plugin_result["total"] > 0:
                            logger.info(
                                f"Plugin restore(owner): "
                                f"restored={plugin_result['restored']}, "
                                f"failed={plugin_result['failed']}, "
                                f"total={plugin_result['total']}"
                            )
                finally:
                    if _restore_redis and _restore_locked is True:
                        try:
                            from app.plugins.lifecycle import _UNLOCK_IF_OWNER_LUA

                            await _restore_redis.eval(_UNLOCK_IF_OWNER_LUA, 1, _restore_lock_key, _restore_owner)
                        except Exception:
                            pass
            else:
                # 非 owner worker 等待 owner 重恢复完成，再进行本 worker 进程内注册
                wait_seconds = 0
                wait_limit = 180
                if _restore_redis:
                    while wait_seconds < wait_limit:
                        lock_holder = await _restore_redis.get(_restore_lock_key)
                        if not lock_holder:
                            break
                        await asyncio.sleep(1)
                        wait_seconds += 1

                if wait_seconds >= wait_limit:
                    logger.warning(
                        "Plugin restore(non-owner): owner lock wait timeout (%ss), continuing with register-only mode",
                        wait_limit,
                    )
                else:
                    logger.info(
                        "Plugin restore(non-owner): owner completed after waiting %ss",
                        wait_seconds,
                    )

                async with async_session_factory() as db:
                    plugin_result = await restore_enabled_plugins(
                        db,
                        run_heavy=False,
                        mutate_db_status=False,
                    )
                    await db.commit()
                    if plugin_result["total"] > 0:
                        logger.info(
                            f"Plugin restore(non-owner): "
                            f"restored={plugin_result['restored']}, "
                            f"failed={plugin_result['failed']}, "
                            f"total={plugin_result['total']}"
                        )
        except Exception as plugin_err:
            logger.warning(f"Plugin startup failed: {plugin_err}")

        # 插件恢复后重新加载翻译（插件可能有自己的 locales 文件）
        reload_translations()

        # 插件恢复后再次同步权限（插件可能注册了菜单到 permission_registry）
        # 同样需要分布式锁防止多 worker 并发 INSERT
        _plugin_perm_owner = str(__import__("uuid").uuid4())
        _plugin_perm_redis = None
        _plugin_perm_locked = False
        try:
            from app.core.redis import get_redis_client as _get_rc
            _plugin_perm_redis = _get_rc()
            _plugin_perm_locked = await _plugin_perm_redis.set(
                "plugin:startup:plugin_perm_sync_lock", _plugin_perm_owner, nx=True, ex=60,
            )
        except Exception:
            _plugin_perm_locked = True

        if _plugin_perm_locked:
            try:
                async with async_session_factory() as db:
                    plugin_perm_result = await sync_permissions_on_startup(db)
                    if plugin_perm_result["created"] > 0:
                        logger.info(
                            f"Plugin permissions synced: "
                            f"created={plugin_perm_result['created']}, "
                            f"updated={plugin_perm_result['updated']}"
                        )
            finally:
                if _plugin_perm_redis and _plugin_perm_locked is True:
                    try:
                        from app.plugins.lifecycle import _UNLOCK_IF_OWNER_LUA
                        await _plugin_perm_redis.eval(
                            _UNLOCK_IF_OWNER_LUA, 1,
                            "plugin:startup:plugin_perm_sync_lock", _plugin_perm_owner,
                        )
                    except Exception:
                        pass

        # Check if configured storage driver is available
        try:
            from app.configs.service import ConfigService
            from app.storage.manager import storage_manager
            async with async_session_factory() as db:
                config_svc = ConfigService(db)
                configured_driver = await config_svc.get_platform_config(
                    "platform_storage_driver", default="local"
                )
                configured_driver = str(configured_driver)
                if configured_driver != "local" and not storage_manager.has_driver(configured_driver):
                    logger.warning(
                        "Platform storage driver '%s' is configured but not available. "
                        "The corresponding plugin may not be installed or enabled. "
                        "File operations will fail until the driver is available.",
                        configured_driver,
                    )
        except Exception as driver_check_err:
            logger.warning(f"Storage driver check failed: {driver_check_err}")

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
        default_response_class=JSONResponse,
        lifespan=lifespan,
    )

    # ========================================
    # 注册中间件
    # ========================================

    # API 响应禁止浏览器缓存中间件
    # 仅对未设置 Cache-Control 的 JSON 响应添加 no-store，
    # 避免浏览器缓存 GET 导致保存后数据不更新
    from starlette.middleware.base import BaseHTTPMiddleware

    class NoCacheAPIMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            response = await call_next(request)
            if "Cache-Control" not in response.headers:
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
                    response.headers["Pragma"] = "no-cache"
            return response

    app.add_middleware(NoCacheAPIMiddleware)

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

    # CORS 中间件 — 必须最后注册（= 最外层），
    # 确保所有中间件（包括 AccessControlMiddleware 的 403）返回的响应都带 CORS headers
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
    app.include_router(admin_router, prefix="/admin")

    # 注册插件 API 分发器
    from app.plugins.api_dispatcher import (
        plugin_api_router,
        plugin_public_api_router,
        plugin_tenant_api_router,
    )
    app.include_router(plugin_api_router, prefix="/admin")          # /admin/plugins/{name}/api/*
    app.include_router(plugin_tenant_api_router, prefix="/tenant")  # /tenant/plugins/{name}/api/*
    app.include_router(plugin_public_api_router, prefix="/api/public")  # /api/public/plugins/{name}/api/*

    # 注册插件 Webhook 分发器 (/webhooks/plugins/{name}/{path}) — 不走认证中间件
    from app.plugins.webhook_dispatcher import webhook_router
    app.include_router(webhook_router)

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
    # 挂载插件前端静态资源目录
    # ========================================
    from pathlib import Path as _Path
    from pathlib import PurePosixPath

    from fastapi.responses import Response as FastAPIResponse
    from fastapi.staticfiles import StaticFiles

    PLUGINS_ROOT = _Path(__file__).resolve().parent.parent / "plugins"

    @app.api_route(
        "/plugin-assets/{plugin_name}/{file_path:path}",
        methods=["GET", "HEAD"],
    )
    async def serve_plugin_asset(
        plugin_name: str,
        file_path: str,
        request: Request,
    ):
        """
        插件前端静态资源服务

        URL: /plugin-assets/{plugin_name}/{file_path}
        文件系统: plugins/{plugin_name}/frontend/dist/{file_path}
        """
        import mimetypes as _mimetypes

        from sqlalchemy import select as _select

        from app.core.database import async_session_factory
        from app.enums.plugin import PluginStatusEnum as _PluginStatusEnum
        from app.models.system.plugin import Plugin as _Plugin
        from app.plugins.asset_resolver import resolve_plugin_asset_file

        # 图标文件（顶层 icon.*）允许任何状态访问；其他资源仅允许已启用插件
        _icon_exts = frozenset({".png", ".jpg", ".jpeg", ".svg", ".webp", ".ico"})
        _normalized = PurePosixPath(file_path.replace("\\", "/").lstrip("/"))
        _is_icon = len(_normalized.parts) == 1 and _normalized.suffix.lower() in _icon_exts

        if not _is_icon:
            async with async_session_factory() as db:
                status_result = await db.execute(
                    _select(_Plugin.status).where(
                        _Plugin.name == plugin_name,
                        _Plugin.is_deleted.is_(False),
                    )
                )
                plugin_status = status_result.scalar_one_or_none()
                if plugin_status != _PluginStatusEnum.ENABLED.value:
                    return JSONResponse(
                        status_code=404,
                        content={"code": 4040, "message": "Plugin asset not found"},
                    )

        asset_file = resolve_plugin_asset_file(PLUGINS_ROOT, plugin_name, file_path)
        if asset_file is None:
            return JSONResponse(
                status_code=404,
                content={"code": 4040, "message": "Plugin asset not found"},
            )

        content_type = _mimetypes.guess_type(str(asset_file))[0] or "application/octet-stream"
        cache_header = "no-cache" if settings.DEBUG else "public, max-age=3600"

        if request.method == "HEAD":
            # HEAD 仅返回元信息，避免无意义读取大文件内容
            file_size = asset_file.stat().st_size
            return FastAPIResponse(
                content=b"",
                media_type=content_type,
                headers={
                    "Cache-Control": cache_header,
                    "Content-Length": str(file_size),
                },
            )

        content = asset_file.read_bytes()
        return FastAPIResponse(
            content=content,
            media_type=content_type,
            headers={"Cache-Control": cache_header},
        )

    # ========================================
    # 挂载本地存储静态文件目录
    # ========================================
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
        reload_dirs=["app"],
        reload_excludes=["plugins/.backups/*"],
    )
