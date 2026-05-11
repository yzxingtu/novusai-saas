"""
FastAPI Application Entry Point. / FastAPI 应用入口。

Configures application instance, middleware, routes, exception handlers, etc.
配置应用实例、中间件、路由、异常处理器等
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.cors import (
    get_cors_headers_for_origin,
    refresh_verified_custom_domain_cache,
)
from app.core.database import (
    check_database_connection,
    close_database,
    get_last_db_init_failure_reason,
    init_database,
)
from app.core.i18n import _, reload_translations
from app.core.logging import get_logger, init_logging
from app.core.response import build_exception_debug, error, validation_error
from app.core.runtime_identity import get_runtime_identity_tag
from app.exceptions import AppException
from app.middleware.access_control import AccessControlMiddleware
from app.middleware.audit_log import AuditLogMiddleware
from app.middleware.dynamic_cors import DynamicCORSMiddleware
from app.middleware.i18n import I18nMiddleware
from app.middleware.permission import PermissionMiddleware
from app.middleware.prometheus_metrics import (
    PrometheusMetricsMiddleware,
    metrics_response,
    set_component_health,
)
from app.middleware.tenant import TenantMiddleware
from app.middleware.trace import TraceIdMiddleware
from app.rbac.decorators import public

_METRICS_COMPONENT_HEALTH_REFRESH_TTL_SECONDS = 15.0
_METRICS_COMPONENT_HEALTH_REFRESH_TIMEOUT_SECONDS = 2.0
_metrics_component_health_last_refresh = 0.0
_metrics_component_health_lock: asyncio.Lock | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifecycle management
    应用生命周期管理

    - startup: Executes on application startup / 应用启动时执行
    - shutdown: Executes on application shutdown / 应用关闭时执行
    """
    # ========== Startup / 启动 ==========
    # Initialize logging system / 初始化日志系统
    init_logging()
    logger = get_logger(__name__)

    # Clear translation cache to ensure latest translation files are loaded / 清除翻译缓存，确保加载最新的翻译文件
    reload_translations()

    try:
        logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
        logger.info(f"Environment: {settings.APP_ENV}")
        logger.info(f"Debug mode: {settings.DEBUG}")
        logger.info("Runtime identity: {}", get_runtime_identity_tag())
        if settings.APP_ENV == "production":
            weak_secret_prefixes = ("change-me", "please-replace")
            secret_key = str(settings.SECRET_KEY or "").strip()
            if (
                not secret_key
                or secret_key == "your-secret-key-change-in-production"
                or secret_key.startswith(weak_secret_prefixes)
            ):
                raise RuntimeError(
                    "Production SECRET_KEY must be replaced before startup"
                )

        if settings.RUN_MIGRATIONS_ON_STARTUP:
            # Initialize database (check/create database + run migrations) / 初始化数据库（检查/创建数据库 + 运行迁移）
            if not await init_database():
                detail = get_last_db_init_failure_reason()
                raise RuntimeError(
                    "Database initialization failed"
                    + (f": {detail}" if detail else "")
                    + " — 亦可手动执行: cd backend && alembic upgrade heads",
                )
            logger.info("Database initialized")
        else:
            # 中文: 生产 compose 通过 backend-migrate 服务执行迁移，API 启动只验证连接。
            # EN: Production compose runs migrations through backend-migrate; API startup only verifies connectivity.
            if not await check_database_connection():
                detail = get_last_db_init_failure_reason()
                raise RuntimeError(
                    "Database connectivity check failed"
                    + (f": {detail}" if detail else "")
                )
            logger.info("Database connectivity verified; startup migrations disabled")

        # Early Redis initialization (subsequent startup steps depend on Redis for distributed locks) / 提前初始化 Redis（后续启动步骤的分布式锁依赖 Redis）
        from app.core.redis import RedisManager as _RedisManager

        try:
            await _RedisManager.init()
            logger.info("Redis initialized (early, for startup locks)")
        except Exception as _redis_early_err:
            logger.error(f"Redis early initialization failed: {_redis_early_err}")
            raise RuntimeError(
                "Redis initialization failed; startup distributed locks are required"
            ) from _redis_early_err

        # Sync permissions to database (sync decorator-defined permissions to DB)
        # 同步权限到数据库（将装饰器定义的权限同步到 DB）
        # Use distributed lock to prevent multi-worker concurrent sync, avoiding Permission INSERT IntegrityError
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
                _perm_lock_key,
                _perm_owner,
                nx=True,
                ex=60,
            )
        except Exception as lock_err:
            raise RuntimeError("Permission sync startup lock unavailable") from lock_err

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
                        from app.plugins.lifecycle_support import _UNLOCK_IF_OWNER_LUA

                        await _perm_redis.eval(
                            _UNLOCK_IF_OWNER_LUA, 1, _perm_lock_key, _perm_owner
                        )
                    except Exception as exc:
                        logger.debug("Redis perm_sync lock release failed: {}", exc)
        else:
            logger.debug("Permission sync: skipped (another worker is syncing)")

        # Sync configs to database (sync code-defined config items to DB)
        # 同步配置到数据库（将代码定义的配置项同步到 DB）
        # Use distributed lock to prevent multi-worker concurrent INSERT of config items/groups
        # 使用分布式锁防止多 worker 并发 INSERT 配置项/分组
        # Import config definition modules (triggers config registration to registry)
        # 导入配置定义模块（触发配置注册到 registry）
        # NOTE: Use from...import instead of import app.xxx to avoid shadowing lifespan's app param
        # NOTE: 使用 from...import 而非 import app.xxx，避免遮蔽 lifespan 的 app 参数
        from app.configs import definitions as _configs_definitions  # noqa: F401
        from app.configs.sync import sync_configs_on_startup

        _cfg_owner = str(__import__("uuid").uuid4())
        _cfg_redis = None
        _cfg_locked = False
        try:
            from app.core.redis import get_redis_client as _get_rc2

            _cfg_redis = _get_rc2()
            _cfg_locked = await _cfg_redis.set(
                "plugin:startup:config_sync_lock", _cfg_owner, nx=True, ex=60
            )
        except Exception as lock_err:
            raise RuntimeError("Config sync startup lock unavailable") from lock_err

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
                        from app.plugins.lifecycle_support import _UNLOCK_IF_OWNER_LUA

                        await _cfg_redis.eval(
                            _UNLOCK_IF_OWNER_LUA,
                            1,
                            "plugin:startup:config_sync_lock",
                            _cfg_owner,
                        )
                    except Exception as exc:
                        logger.debug("Redis lock release failed: {}", exc)

        # Initialize Redis connection / 初始化 Redis 连接
        from app.core.redis import RedisManager

        try:
            await RedisManager.init()
            logger.info("Redis initialized")
        except Exception as redis_err:
            logger.warning(f"Redis initialization failed: {redis_err}")

        await refresh_verified_custom_domain_cache()
        logger.info("Verified custom-domain CORS cache refreshed")

        # Register core AI adapters (hardcoded, not dependent on plugin system) / 注册核心 AI 适配器（硬编码，不依赖插件系统）
        from app.ai.adapters import register_core_adapters

        register_core_adapters()

        # Clean up residual online presence data (old connections already disconnected after server restart) / 清理残留的在线状态数据（服务器重启后旧连接已断开）
        try:
            from app.sio.presence import PresenceManager

            await PresenceManager.clear_all()
        except Exception as presence_err:
            logger.warning(f"Presence cleanup failed: {presence_err}")

        # Apply WebSocket platform config (ping_interval / ping_timeout) / 应用 WebSocket 平台配置（ping_interval / ping_timeout）
        try:
            from app.core.socketio_server import apply_ws_config

            await apply_ws_config()
        except Exception as ws_cfg_err:
            logger.warning(f"WS config apply failed: {ws_cfg_err}")

        # Seed data: notification templates / 种子数据：通知模板
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

        # Verify Celery broker connectivity / 验证 Celery broker 连通性
        try:
            from app.celery_app import celery_app

            conn = celery_app.connection()
            conn.ensure_connection(max_retries=1, timeout=3)
            conn.close()
            logger.info("Celery broker connected")
        except Exception as celery_err:
            logger.warning(f"Celery broker connection failed: {celery_err}")

        # Plugin auto-discovery + restore
        # 插件自动发现 + 恢复
        # Note: When multiple workers start concurrently, discover_and_register runs concurrently.
        # 注意：多 worker 并发启动时，discover_and_register 会并发执行。
        # Use Redis distributed lock to ensure only one worker runs discover (includes alembic migrations).
        # 使用 Redis 分布式锁确保只有一个 worker 执行 discover（含 alembic 迁移）。
        # restore uses two phases:
        # restore 采用双阶段：
        # 1) owner worker runs heavy restore (migration/dependency install/status writeback)
        # 1) owner worker 执行重恢复（迁移/依赖补装/状态写回）
        # 2) other workers wait for owner to complete, then only do in-process extension registration (no DB writes)
        # 2) 其他 worker 等待 owner 完成后，仅做进程内扩展注册（不写库）
        try:
            from app.plugins.startup import (
                discover_and_register,
                restore_enabled_plugins,
            )

            # Phase 1: Auto-discovery (distributed lock protection, avoiding multi-worker concurrent migration race)
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
                logger.warning(
                    f"Plugin discover lock unavailable (Redis error): {_redis_err}"
                )
                raise RuntimeError(
                    "Plugin discovery startup lock unavailable"
                ) from _redis_err

            if _discover_locked:
                try:
                    async with async_session_factory() as db:
                        discover_result = await discover_and_register(db)
                        await db.commit()
                        if (
                            discover_result["discovered"] > 0
                            or discover_result["sync_required"] > 0
                            or discover_result["upgrade_required"] > 0
                            or discover_result["missing"] > 0
                        ):
                            logger.info(
                                f"Plugin discover: "
                                f"discovered={discover_result['discovered']}, "
                                f"sync_required={discover_result['sync_required']}, "
                                f"upgrade_required={discover_result['upgrade_required']}, "
                                f"missing={discover_result['missing']}, "
                                f"failed={discover_result['failed']}"
                            )
                finally:
                    if _redis_client and _discover_locked is True:
                        try:
                            from app.plugins.lifecycle_support import (
                                _UNLOCK_IF_OWNER_LUA,
                            )

                            await _redis_client.eval(
                                _UNLOCK_IF_OWNER_LUA,
                                1,
                                _discover_lock_key,
                                _discover_owner,
                            )
                        except Exception as exc:
                            logger.debug(
                                "Redis plugin discover lock release failed: {}", exc
                            )
            else:
                logger.info(
                    "Plugin discover: skipped (another worker is running discovery)"
                )

            # Phase 2: Restore (owner heavy restore + other workers in-process registration only)
            # Phase 2: 恢复（owner 重恢复 + 其他 worker 仅本进程注册）
            _restore_lock_key = "plugin:startup:restore_lock"
            _restore_lock_ttl = 900  # 覆盖迁移/依赖补装的最长路径 / Max seconds for migrations or dep reinstall
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
                logger.warning(
                    f"Plugin restore lock unavailable (Redis error): {_redis_err}"
                )
                raise RuntimeError(
                    "Plugin restore startup lock unavailable"
                ) from _redis_err

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
                            from app.plugins.lifecycle_support import (
                                _UNLOCK_IF_OWNER_LUA,
                            )

                            await _restore_redis.eval(
                                _UNLOCK_IF_OWNER_LUA,
                                1,
                                _restore_lock_key,
                                _restore_owner,
                            )
                        except Exception as exc:
                            logger.debug(
                                "Redis plugin restore lock release failed: {}", exc
                            )
            else:
                # Non-owner worker waits for owner heavy restore to complete, then does in-process registration
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
                        "Plugin restore(non-owner): owner lock wait timeout ({}s), continuing with register-only mode",
                        wait_limit,
                    )
                else:
                    logger.info(
                        "Plugin restore(non-owner): owner completed after waiting {}s",
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

        # Reload translations after plugin restore (plugins may have their own locales files) / 插件恢复后重新加载翻译（插件可能有自己的 locales 文件）
        reload_translations()

        # Check if configured storage driver is available / 检查配置的存储驱动是否可用
        try:
            from app.configs.service import ConfigService
            from app.storage.manager import storage_manager

            async with async_session_factory() as db:
                config_svc = ConfigService(db)
                configured_driver = await config_svc.get_platform_config(
                    "platform_storage_driver", default="local"
                )
                configured_driver = str(configured_driver)
                if configured_driver != "local" and not storage_manager.has_driver(
                    configured_driver
                ):
                    logger.warning(
                        "Platform storage driver '{}' is configured but not available. "
                        "The corresponding plugin may not be installed or enabled. "
                        "File operations will fail until the driver is available.",
                        configured_driver,
                    )
        except Exception as driver_check_err:
            logger.warning(f"Storage driver check failed: {driver_check_err}")

    except Exception as e:
        # Ensure startup phase errors are logged and displayed / 确保启动阶段的错误能够被记录和显示
        import traceback

        error_msg = f"Startup failed: {e}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        # Also output to console to ensure visibility even when logging system is abnormal / 同时输出到控制台，确保在日志系统异常时也能看到
        print(error_msg, flush=True)
        traceback.print_exc()
        raise

    yield

    # ========== Shutdown / 关闭 ==========
    logger = get_logger(__name__)
    logger.info(f"Shutting down {settings.APP_NAME}")

    # Close database connections / 关闭数据库连接
    await close_database()
    logger.info("Database connections closed")

    # Close Redis connections / 关闭 Redis 连接
    from app.core.redis import RedisManager

    await RedisManager.close()
    logger.info("Redis connections closed")


async def _check_database_component() -> bool:
    """中文: 执行轻量数据库探活并刷新 Prometheus 组件健康指标。

    EN: Runs a lightweight database probe and refreshes the Prometheus
    component health gauge.
    """
    from sqlalchemy import text

    from app.core.database import async_session_factory

    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
    except Exception as exc:
        set_component_health("database", False)
        logger = get_logger(__name__)
        logger.warning("Readiness check failed (database): {}", exc)
        return False
    set_component_health("database", True)
    return True


def _get_metrics_component_health_lock() -> asyncio.Lock:
    global _metrics_component_health_lock
    if _metrics_component_health_lock is None:
        _metrics_component_health_lock = asyncio.Lock()
    return _metrics_component_health_lock


def _describe_health_probe_exception(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return f"{type(exc).__name__}: {message}"
    return repr(exc)


async def _refresh_metrics_component_health() -> None:
    """中文: Prometheus 抓取前主动刷新组件健康，避免只依赖 /ready 和 /health 副作用。

    EN: Refreshes component health before Prometheus scrapes so DB/Redis gauges
    do not depend only on /ready and /health side effects.
    """
    global _metrics_component_health_last_refresh
    loop = asyncio.get_running_loop()
    now = loop.time()
    if (
        now - _metrics_component_health_last_refresh
        < _METRICS_COMPONENT_HEALTH_REFRESH_TTL_SECONDS
    ):
        return

    async with _get_metrics_component_health_lock():
        now = loop.time()
        if (
            now - _metrics_component_health_last_refresh
            < _METRICS_COMPONENT_HEALTH_REFRESH_TTL_SECONDS
        ):
            return

        try:
            await asyncio.wait_for(
                _check_database_component(),
                timeout=_METRICS_COMPONENT_HEALTH_REFRESH_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            set_component_health("database", False)
            logger = get_logger(__name__)
            logger.warning(
                "Metrics component refresh failed (database): {}",
                _describe_health_probe_exception(exc),
            )

        try:
            from app.core.redis import RedisManager

            redis_ok = await asyncio.wait_for(
                RedisManager.health_check(),
                timeout=_METRICS_COMPONENT_HEALTH_REFRESH_TIMEOUT_SECONDS,
            )
            set_component_health("redis", redis_ok)
        except Exception as exc:
            set_component_health("redis", False)
            logger = get_logger(__name__)
            logger.warning(
                "Metrics component refresh failed (redis): {}",
                _describe_health_probe_exception(exc),
            )

        _metrics_component_health_last_refresh = loop.time()


async def readiness_check():
    """
    Kubernetes readiness: verifies database and Redis connectivity.
    / K8s 就绪探针：校验数据库与 Redis 可连（与 /health 区分，/health 可仅表示进程存活）。
    """
    readiness = {
        "ready": True,
        "database": "ok",
        "redis": "ok",
    }
    if not await _check_database_component():
        readiness["ready"] = False
        readiness["database"] = "unavailable"
    try:
        from app.core.redis import RedisManager

        if not await RedisManager.health_check():
            readiness["ready"] = False
            readiness["redis"] = "unavailable"
    except Exception:
        readiness["ready"] = False
        readiness["redis"] = "unavailable"

    if not readiness["ready"]:
        return JSONResponse(
            status_code=503,
            content={
                "code": 5030,
                "message": "not_ready",
                "data": readiness,
            },
        )
    return {
        "code": 0,
        "message": _("common.success"),
        "data": readiness,
    }


def create_application() -> FastAPI:
    """
    Create FastAPI application instance. / 创建 FastAPI 应用实例。
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Modern AI-integrated SaaS development framework / 现代化 AI 集成 SaaS 开发框架",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        default_response_class=JSONResponse,
        lifespan=lifespan,
    )

    # ========================================
    # Register middleware / 注册中间件
    # ========================================

    # API response browser cache prevention middleware
    # API 响应禁止浏览器缓存中间件
    # Only adds no-store to JSON responses without Cache-Control set,
    # preventing browser from caching GET causing stale data after save
    # 仅对未设置 Cache-Control 的 JSON 响应添加 no-store，
    # 避免浏览器缓存 GET 导致保存后数据不更新
    from app.middleware.nocache import NoCacheAPIMiddleware

    app.add_middleware(NoCacheAPIMiddleware)

    # i18n internationalization middleware (pure ASGI implementation, registered via add_middleware)
    # i18n 国际化中间件（纯 ASGI 实现，使用 add_middleware 注册）
    app.add_middleware(I18nMiddleware)

    # Maintenance mode middleware (intercepts non-admin requests with 503 when enabled)
    # 维护模式中间件（开启时拦截非管理端请求返回 503）
    from app.middleware.maintenance import MaintenanceMiddleware

    app.add_middleware(MaintenanceMiddleware)

    # RBAC permission preload middleware (loads user permissions into request.state)
    # RBAC 权限预加载中间件（加载用户权限到 request.state）
    app.add_middleware(PermissionMiddleware)

    # Audit log middleware (records all API calls)
    # 审计日志中间件（记录所有 API 调用）
    # Note: Must be registered after PermissionMiddleware to access user info from state
    # 注意：必须在 PermissionMiddleware 之后注册，这样才能从 state 获取用户信息
    app.add_middleware(AuditLogMiddleware)

    # Access control middleware (enforces "deny by default" security policy)
    # 访问控制中间件（实施“默认拒绝”安全策略）
    app.add_middleware(AccessControlMiddleware)

    # Tenant identification middleware (resolves tenant from Host header)
    # 企业识别中间件（基于 Host 头解析企业）
    app.add_middleware(TenantMiddleware)

    # Dynamic CORS middleware — validates allowed origins and reflects the exact Origin.
    # / 动态 CORS 中间件：校验允许的 Origin，并精确回写请求来源。
    app.add_middleware(DynamicCORSMiddleware)

    # Prometheus metrics middleware / Prometheus 指标中间件
    app.add_middleware(PrometheusMetricsMiddleware)

    # Trace ID middleware (outermost = runs first; propagates X-Trace-ID for request correlation)
    # 追踪 ID 中间件（最外层 = 最先执行；传播 X-Trace-ID 用于请求关联）
    app.add_middleware(TraceIdMiddleware)

    # ========================================
    # Register exception handlers / 注册异常处理器
    # ========================================

    async def _get_cors_headers(request: Request) -> dict[str, str]:
        """Get CORS response headers / 获取 CORS 响应头"""
        return await get_cors_headers_for_origin(request.headers.get("origin"))

    async def _get_error_response_headers(request: Request) -> dict[str, str]:
        """Get CORS headers for error responses / 获取错误响应所需的 CORS 头"""
        return await _get_cors_headers(request)

    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request, exc: AppException
    ) -> JSONResponse:
        """Application exception handler / 应用异常处理器"""
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.to_dict(),
            headers=await _get_error_response_headers(request),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Request validation exception handler / 请求验证异常处理器"""
        errors = [
            {
                "field": ".".join(str(loc) for loc in err.get("loc", [])),
                "message": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        # validation_error() returns JSONResponse / validation_error() 返回 JSONResponse
        response = validation_error(errors=errors)
        response.headers.update(await _get_error_response_headers(request))
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """HTTP exception handler / HTTP 异常处理器"""
        # Map common HTTP status codes to business error codes / 映射常见 HTTP 状态码到业务错误码
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
        detail_text = str(exc.detail) if exc.detail else None
        public_message = (
            detail_text if exc.status_code < 500 else _("common.server_error")
        )
        debug_payload = (
            build_exception_debug(exc, detail=detail_text, include_traceback=False)
            if exc.status_code >= 500 and detail_text
            else None
        )
        response = error(
            message=public_message,
            code=code,
            status_code=exc.status_code,
            debug=debug_payload,
        )
        response.headers.update(await _get_error_response_headers(request))
        return response

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """Global exception handler - catches unhandled exceptions / 全局异常处理器 - 捕获未处理的异常"""
        # Log exception / 记录异常日志
        logger = get_logger(__name__)
        logger.exception(f"Unhandled exception: {exc}")

        response = error(
            message=_("common.server_error"),
            code=5000,
            status_code=500,
            debug=build_exception_debug(exc),
        )
        response.headers.update(await _get_error_response_headers(request))
        return response

    # ========================================
    # Register routes / 注册路由
    # ========================================

    @app.get("/", tags=["Root"])
    async def root() -> dict:
        """Root route - health check / 根路由 - 健康检查"""
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
        """Health check endpoint / 健康检查端点"""
        from app.core.redis import RedisManager

        redis_ok = await RedisManager.health_check()
        set_component_health("redis", redis_ok)
        return {
            "code": 0,
            "message": _("common.success"),
            "data": {
                "status": "healthy" if redis_ok else "degraded",
                "env": settings.APP_ENV,
                "redis_status": "connected" if redis_ok else "disconnected",
            },
        }

    app.get("/ready", tags=["Health"], response_model=None)(readiness_check)

    @app.get("/metrics", tags=["Health"])
    @public
    async def prometheus_metrics() -> Response:
        """Prometheus metrics endpoint / Prometheus 指标端点。"""
        await _refresh_metrics_component_health()
        return metrics_response()

    # Register directory menus (must be before controller imports to ensure parent menus are registered first)
    # 注册目录型菜单（必须在控制器导入之前，确保父菜单先注册）
    from app.rbac.menus import register_directory_menus

    register_directory_menus()

    # Register platform admin routes (/admin/*) / 注册平台管理后台路由 (/admin/*)
    from app.api.admin import admin_router

    app.include_router(admin_router, prefix="/admin")

    # Register plugin API dispatcher / 注册插件 API 分发器
    from app.plugins.api_dispatcher import (
        plugin_api_router,
        plugin_public_api_router,
        plugin_tenant_api_router,
    )

    app.include_router(
        plugin_api_router, prefix="/admin"
    )  # /admin/plugins/{name}/api/* / 平台端插件 API 路径模板
    app.include_router(
        plugin_tenant_api_router, prefix="/tenant"
    )  # /tenant/plugins/{name}/api/* / 企业端插件 API 路径模板
    app.include_router(
        plugin_public_api_router, prefix="/api/public"
    )  # /api/public/plugins/{name}/api/* / 公开插件 API 路径模板

    # Register plugin Webhook dispatcher (/webhooks/plugins/{name}/{path}) — bypasses auth middleware
    # 注册插件 Webhook 分发器 (/webhooks/plugins/{name}/{path}) — 不走认证中间件
    from app.plugins.webhook_dispatcher import webhook_router

    app.include_router(webhook_router)

    # Register tenant admin routes (/tenant/*) / 注册企业管理后台路由 (/tenant/*)
    from app.api.tenant import tenant_router

    app.include_router(tenant_router, prefix="/tenant")

    # Register user API routes (/api/user/*) / 注册用户端 API 路由 (/api/user/*)
    from app.api.user import user_router

    app.include_router(user_router, prefix="/api/user")

    # Register public API routes (/api/public/*) - no auth required, for tenant login page config
    # 注册公共 API 路由 (/api/public/*) - 无需认证，用于企业登录页获取配置
    from app.api.public import public_router

    app.include_router(public_router, prefix="/api/public")

    # ========================================
    # Mount plugin frontend static assets directory / 挂载插件前端静态资源目录
    # ========================================
    from pathlib import Path as _Path
    from pathlib import PurePosixPath

    from fastapi.responses import Response as FastAPIResponse
    from fastapi.staticfiles import StaticFiles

    PLUGINS_ROOT = _Path(__file__).resolve().parent.parent / "plugins"

    @app.api_route(
        "/plugin-public-assets/{public_endpoint}/{plugin_name}/{file_path:path}",
        methods=["GET", "HEAD"],
        include_in_schema=False,
    )
    async def serve_public_captcha_plugin_asset(
        public_endpoint: str,
        plugin_name: str,
        file_path: str,
        request: Request,
    ):
        """
        Public captcha plugin asset service for login pages.
        / 登录页公开验证码插件静态资源服务。

        URL: /plugin-public-assets/{public_endpoint}/{plugin_name}/{file_path}
        Filesystem: plugins/{plugin_name}/frontend/dist/{file_path}
        """
        import mimetypes as _mimetypes

        from app.core.database import async_session_factory
        from app.plugins.asset_resolver import resolve_plugin_asset_file
        from app.plugins.asset_runtime import (
            authorize_public_captcha_asset_request,
            clear_plugin_asset_access_cookie,
        )

        def _build_public_not_found_response():
            response = error(
                message="Plugin asset not found",
                code=4040,
                status_code=404,
            )
            response.headers.update(
                {
                    "Cache-Control": "private, no-store, max-age=0",
                    "Vary": "Host, Authorization, Cookie",
                    "X-Content-Type-Options": "nosniff",
                }
            )
            clear_plugin_asset_access_cookie(response, request)
            return response

        _normalized = PurePosixPath(file_path.replace("\\", "/").lstrip("/"))
        if str(_normalized) in {"", "."}:
            return _build_public_not_found_response()

        async with async_session_factory() as db:
            access = await authorize_public_captcha_asset_request(
                db,
                request,
                plugin_name,
                public_endpoint,
            )
            if not access.allowed:
                return _build_public_not_found_response()

        asset_file = resolve_plugin_asset_file(PLUGINS_ROOT, plugin_name, file_path)
        if asset_file is None:
            return _build_public_not_found_response()

        content_type = (
            _mimetypes.guess_type(str(asset_file))[0] or "application/octet-stream"
        )
        headers = {
            "Cache-Control": "public, max-age=300, must-revalidate",
            "Vary": "Host, Authorization, Cookie",
            "X-Content-Type-Options": "nosniff",
        }

        if request.method == "HEAD":
            response = FastAPIResponse(
                content=b"",
                media_type=content_type,
                headers={
                    **headers,
                    "Content-Length": str(asset_file.stat().st_size),
                },
            )
            clear_plugin_asset_access_cookie(response, request)
            return response

        response = FastAPIResponse(
            content=asset_file.read_bytes(),
            media_type=content_type,
            headers=headers,
        )
        clear_plugin_asset_access_cookie(response, request)
        return response

    @app.api_route(
        "/plugin-assets/{plugin_name}/{file_path:path}",
        methods=["GET", "HEAD"],
        include_in_schema=False,
    )
    async def serve_plugin_asset(
        plugin_name: str,
        file_path: str,
        request: Request,
    ):
        """
        Plugin frontend static asset service
        插件前端静态资源服务

        URL: /plugin-assets/{plugin_name}/{file_path}
        Filesystem: plugins/{plugin_name}/frontend/dist/{file_path}
        文件系统: plugins/{plugin_name}/frontend/dist/{file_path}
        """
        import mimetypes as _mimetypes

        from app.core.database import async_session_factory
        from app.plugins.asset_resolver import resolve_plugin_asset_file
        from app.plugins.asset_runtime import authorize_plugin_asset_request

        def _build_cache_headers(
            *, content_length: int | None = None
        ) -> dict[str, str]:
            headers = {
                "Cache-Control": "private, max-age=300, must-revalidate",
                "Vary": "Authorization, Cookie",
                "X-Content-Type-Options": "nosniff",
            }
            if content_length is not None:
                headers["Content-Length"] = str(content_length)
            return headers

        _normalized = PurePosixPath(file_path.replace("\\", "/").lstrip("/"))
        if str(_normalized) in {"", "."}:
            return error(
                message="Plugin asset not found",
                code=4040,
                status_code=404,
            )

        async with async_session_factory() as db:
            access = await authorize_plugin_asset_request(
                db,
                request,
                plugin_name,
                require_enabled=True,
            )
            if not access.allowed:
                return error(
                    message="Plugin asset not found",
                    code=4040,
                    status_code=404,
                )

        asset_file = resolve_plugin_asset_file(PLUGINS_ROOT, plugin_name, file_path)
        if asset_file is None:
            return error(
                message="Plugin asset not found",
                code=4040,
                status_code=404,
            )

        content_type = (
            _mimetypes.guess_type(str(asset_file))[0] or "application/octet-stream"
        )

        if request.method == "HEAD":
            # HEAD returns metadata only, avoiding unnecessary reading of large file contents
            # HEAD 仅返回元信息，避免无意义读取大文件内容
            file_size = asset_file.stat().st_size
            return FastAPIResponse(
                content=b"",
                media_type=content_type,
                headers=_build_cache_headers(content_length=file_size),
            )

        content = asset_file.read_bytes()
        return FastAPIResponse(
            content=content,
            media_type=content_type,
            headers=_build_cache_headers(),
        )

    @app.api_route(
        "/plugin-icons/{plugin_name}/{file_path:path}",
        methods=["GET", "HEAD"],
        include_in_schema=False,
    )
    async def serve_plugin_icon(
        plugin_name: str,
        file_path: str,
        request: Request,
    ):
        """
        Plugin metadata icon service for admin surfaces.
        / 管理态插件元数据图标服务。

        URL: /plugin-icons/{plugin_name}/{file_path}
        Filesystem: plugins/{plugin_name}/{file_path}
        """
        import mimetypes as _mimetypes

        from app.core.database import async_session_factory
        from app.plugins.asset_resolver import resolve_plugin_icon_file
        from app.plugins.asset_runtime import authorize_plugin_icon_request

        _normalized = PurePosixPath(file_path.replace("\\", "/").lstrip("/"))
        if str(_normalized) in {"", "."}:
            return error(
                message="Plugin icon not found",
                code=4040,
                status_code=404,
            )

        async with async_session_factory() as db:
            access = await authorize_plugin_icon_request(db, request, plugin_name)
            if not access.allowed:
                return error(
                    message="Plugin icon not found",
                    code=4040,
                    status_code=404,
                )

        asset_file = resolve_plugin_icon_file(PLUGINS_ROOT, plugin_name, file_path)
        if asset_file is None:
            return error(
                message="Plugin icon not found",
                code=4040,
                status_code=404,
            )

        content_type = (
            _mimetypes.guess_type(str(asset_file))[0] or "application/octet-stream"
        )
        headers = {
            "Cache-Control": "private, max-age=300, must-revalidate",
            "Vary": "Authorization, Cookie",
            "X-Content-Type-Options": "nosniff",
        }

        if request.method == "HEAD":
            return FastAPIResponse(
                content=b"",
                media_type=content_type,
                headers={
                    **headers,
                    "Content-Length": str(asset_file.stat().st_size),
                },
            )

        return FastAPIResponse(
            content=asset_file.read_bytes(),
            media_type=content_type,
            headers=headers,
        )

    # ========================================
    # Mount local storage static files directory / 挂载本地存储静态文件目录
    # ========================================
    from app.storage import LOCAL_STORAGE_ROOT

    # Ensure storage directory exists / 确保存储目录存在
    LOCAL_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

    # Mount static files directory
    # 挂载静态文件目录
    # URL path: /files/platform/2026/01/25/xxx.png
    # URL 路径: /files/platform/2026/01/25/xxx.png
    # Filesystem path: backend/storage/uploads/platform/2026/01/25/xxx.png
    # 文件系统路径: backend/storage/uploads/platform/2026/01/25/xxx.png
    app.mount(
        "/files",
        StaticFiles(directory=str(LOCAL_STORAGE_ROOT)),
        name="local_storage",
    )

    # ========================================
    # Socket.IO Integration / Socket.IO 集成
    # ========================================
    import socketio as _socketio

    from app.core.socketio_server import sio
    from app.sio import register_namespaces

    register_namespaces(sio)

    # Wrap FastAPI with ASGIApp, Socket.IO path is /sio
    # 用 ASGIApp 包装 FastAPI，Socket.IO 路径为 /sio
    sio_app = _socketio.ASGIApp(
        sio,
        other_asgi_app=app,
        socketio_path="/sio",
    )

    return sio_app


# Create application instance / 创建应用实例
app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        # 中文: 直接运行 main.py 是本地/容器启动入口，公网暴露由部署层控制。
        # EN: Running main.py directly is a local/container entrypoint; public exposure is controlled by deployment.
        host="0.0.0.0",  # nosec B104
        port=8000,
        reload=settings.DEBUG,
        reload_dirs=["app"],
        reload_excludes=["plugins/.backups/*"],
    )
