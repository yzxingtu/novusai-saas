"""
Celery Application Configuration Module / Celery 应用配置模块

Configures Celery Worker, Broker (Redis), Result Backend with multi-queue routing and priority support.
配置 Celery Worker、Broker(Redis)、Result Backend，支持多队列路由和优先级
"""

from contextlib import suppress

from celery import Celery
from kombu import Exchange, Queue

from app.ai.adapters import AdapterRegistry
from app.ai.adapters.openai_adapter import OpenAIAdapter
from app.core.config import settings
from app.core.logging import LogManager
from app.middleware.trace import trace_id_var

celery_app = Celery("novusai")
logger = LogManager.get_logger("queue")

_original_send_task = celery_app.send_task


def _send_task_with_trace(*args, **kwargs):
    headers = dict(kwargs.get("headers") or {})
    trace_id = trace_id_var.get()
    if trace_id and not headers.get("trace_id"):
        headers["trace_id"] = trace_id
        kwargs = {**kwargs, "headers": headers}
    return _original_send_task(*args, **kwargs)


celery_app.send_task = _send_task_with_trace  # type: ignore[method-assign]

# ========================================
# Broker & Backend
# ========================================
celery_app.conf.broker_url = settings.celery_broker_url
celery_app.conf.result_backend = settings.celery_result_backend

# ========================================
# Serialization / 序列化
# ========================================
celery_app.conf.task_serializer = settings.CELERY_TASK_SERIALIZER
celery_app.conf.result_serializer = settings.CELERY_RESULT_SERIALIZER
celery_app.conf.accept_content = settings.CELERY_ACCEPT_CONTENT

# ========================================
# Timezone / 时区
# ========================================
celery_app.conf.timezone = settings.TIMEZONE
celery_app.conf.enable_utc = True

# ========================================
# Task Execution / 任务执行
# ========================================
celery_app.conf.task_track_started = settings.CELERY_TASK_TRACK_STARTED
celery_app.conf.task_time_limit = settings.CELERY_TASK_TIME_LIMIT
celery_app.conf.task_soft_time_limit = settings.CELERY_TASK_SOFT_TIME_LIMIT
celery_app.conf.worker_prefetch_multiplier = settings.CELERY_WORKER_PREFETCH_MULTIPLIER
celery_app.conf.worker_concurrency = settings.CELERY_WORKER_CONCURRENCY

# ========================================
# Multi-queue Routing / 多队列路由
# ========================================
default_exchange = Exchange("default", type="direct")
high_priority_exchange = Exchange("high_priority", type="direct")

celery_app.conf.task_queues = (
    Queue("default", default_exchange, routing_key="default"),
    Queue("high_priority", high_priority_exchange, routing_key="high_priority"),
    Queue("ai_gateway", default_exchange, routing_key="ai_gateway"),
    Queue("scheduled", default_exchange, routing_key="scheduled"),
    Queue("notification", default_exchange, routing_key="notification"),
)

celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "default"
celery_app.conf.task_default_routing_key = "default"

celery_app.conf.task_routes = {
    "app.tasks.ai.*": {"queue": "ai_gateway"},
    "app.tasks.scheduled.*": {"queue": "scheduled"},
    "app.tasks.high_priority.*": {"queue": "high_priority"},
    "app.tasks.notification.*": {"queue": "notification"},
}

# ========================================
# Task Auto-discovery / 任务自动发现
# ========================================
celery_app.conf.include = [
    "app.tasks.scheduled",
    "app.tasks.recycle_bin",
    "app.tasks.upload_cleanup",
    "app.tasks.ai_health_check",
    "app.tasks.agent_batch",
    "app.tasks.ssl_tasks",
    "app.tasks.email",
    "app.tasks.notification",
    "app.tasks.ai",
    "app.tasks.notification_cleanup",
    "app.ai.rag.processor",
]


# Force import task modules (ensure registration even in Windows --pool=solo mode)
# 强制导入任务模块（确保 Windows --pool=solo 模式下也能注册）
def _import_task_modules():
    for module in celery_app.conf.include:
        with suppress(ImportError):
            __import__(module)


def _bootstrap_enabled_plugin_queue_extensions() -> None:
    """
    Register enabled plugin tasks/consumers for worker and beat processes.
    / 为 worker 与 beat 进程注册已启用插件的任务与消费者。

    Celery processes do not go through FastAPI lifespan startup, so plugin queue
    extensions must be restored separately here. Only queue-executable
    extensions are registered; beat schedule remains DB-driven.
    / Celery 进程不经过 FastAPI lifespan，因此需要在这里单独恢复插件队列扩展。
    这里只注册可执行队列扩展，不向 in-memory beat_schedule 注入插件周期任务。
    """
    try:
        from sqlalchemy import select

        from app.core.database import sync_session_factory
        from app.enums.plugin import PluginStatusEnum
        from app.models.system.plugin import Plugin
        from app.plugins._extension_registrar import register_queue_extensions
        from app.plugins.loader import PluginLoader
        from app.plugins.registry import ExtensionRegistry

        session = sync_session_factory()
        try:
            result = session.execute(
                select(Plugin.name).where(
                    Plugin.status == PluginStatusEnum.ENABLED.value,
                    Plugin.is_deleted.is_(False),
                )
            )
            plugin_names = [str(row[0]) for row in result.all() if row and row[0]]
        finally:
            session.close()

        if not plugin_names:
            return

        loader = PluginLoader()
        registry = ExtensionRegistry.get_instance()
        restored_count = 0

        for plugin_name in plugin_names:
            try:
                manifest = loader.load_manifest(plugin_name)
                if not manifest.extensions.tasks and not manifest.extensions.consumers:
                    continue
                register_queue_extensions(
                    registry,
                    manifest,
                    plugin_name,
                    register_schedule=False,
                    record_failures=False,
                )
                restored_count += 1
            except Exception as exc:
                logger.warning(
                    "Celery plugin queue bootstrap skipped {}: {}",
                    plugin_name,
                    exc,
                )

        if restored_count:
            logger.info(
                "Celery plugin queue bootstrap restored {} plugin(s)",
                restored_count,
            )
    except Exception as exc:
        logger.warning("Celery plugin queue bootstrap failed: {}", exc)


_import_task_modules()
_bootstrap_enabled_plugin_queue_extensions()

# ========================================
# AI Adapter Registration (Worker process doesn't go through main.py lifespan)
# AI 适配器注册（Worker 进程不走 main.py lifespan）
# ========================================
AdapterRegistry.register("openai_compatible", OpenAIAdapter)

# ========================================
# Result Configuration / 结果配置
# ========================================
celery_app.conf.result_expires = 3600
celery_app.conf.task_ignore_result = False

# ========================================
# Beat Scheduling (driven by database periodic_tasks table)
# Beat 调度（由数据库 periodic_tasks 表驱动）
# ========================================
# app.conf.beat_schedule is reserved for static/in-memory entries only.
# DB-driven periodic tasks are loaded by ReloadingPersistentScheduler so Beat
# can recover automatically after transient DB outages.
# app.conf.beat_schedule 仅保留静态/内存型调度项。
# 数据库定时任务由 ReloadingPersistentScheduler 动态加载，避免 Beat 在数据库短暂不可用时永久空跑。
celery_app.conf.beat_schedule = {}
celery_app.conf.beat_scheduler = "app.tasks.scheduler:ReloadingPersistentScheduler"
