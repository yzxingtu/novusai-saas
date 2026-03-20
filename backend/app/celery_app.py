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

celery_app = Celery("novusai")

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

_import_task_modules()

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
# All scheduled tasks are managed via the periodic_tasks table, no hardcoded schedule entries.
# 所有定时任务通过 periodic_tasks 表管理，不再硬编码任何调度条目。
#
# Important: Schedule must be loaded at module level for the **beat** process only,
# cannot use beat_init signal (Celery 5.x reads beat_schedule before beat_init).
# 重要：仅 **celery beat** 进程在模块级加载；Uvicorn/FastAPI 导入本模块时不应查库，
# 否则会在 init_database()/迁移之前访问 periodic_tasks，列未迁移时会报错且误导排障。
#
# Worker 进程不需要 DB 里的 beat_schedule（由 Beat 下发）；空 dict 即可。
try:
    import sys

    _argv_lower = [str(a).lower() for a in sys.argv]
    _is_beat = "beat" in _argv_lower
    if _is_beat:
        from app.tasks.scheduler import load_periodic_tasks_from_db

        celery_app.conf.beat_schedule = load_periodic_tasks_from_db()
    else:
        celery_app.conf.beat_schedule = {}
except Exception:
    celery_app.conf.beat_schedule = {}
