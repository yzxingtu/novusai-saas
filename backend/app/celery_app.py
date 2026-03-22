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
# app.conf.beat_schedule is reserved for static/in-memory entries only.
# DB-driven periodic tasks are loaded by ReloadingPersistentScheduler so Beat
# can recover automatically after transient DB outages.
# app.conf.beat_schedule 仅保留静态/内存型调度项。
# 数据库定时任务由 ReloadingPersistentScheduler 动态加载，避免 Beat 在数据库短暂不可用时永久空跑。
celery_app.conf.beat_schedule = {}
celery_app.conf.beat_scheduler = "app.tasks.scheduler:ReloadingPersistentScheduler"
