"""
Celery 应用配置模块

配置 Celery Worker、Broker(Redis)、Result Backend，支持多队列路由和优先级
"""

from celery import Celery
from kombu import Exchange, Queue

from app.core.config import settings

celery_app = Celery("novusai")

# ========================================
# Broker & Backend
# ========================================
celery_app.conf.broker_url = settings.celery_broker_url
celery_app.conf.result_backend = settings.celery_result_backend

# ========================================
# 序列化
# ========================================
celery_app.conf.task_serializer = settings.CELERY_TASK_SERIALIZER
celery_app.conf.result_serializer = settings.CELERY_RESULT_SERIALIZER
celery_app.conf.accept_content = settings.CELERY_ACCEPT_CONTENT

# ========================================
# 时区
# ========================================
celery_app.conf.timezone = settings.TIMEZONE
celery_app.conf.enable_utc = True

# ========================================
# 任务执行
# ========================================
celery_app.conf.task_track_started = settings.CELERY_TASK_TRACK_STARTED
celery_app.conf.task_time_limit = settings.CELERY_TASK_TIME_LIMIT
celery_app.conf.task_soft_time_limit = settings.CELERY_TASK_SOFT_TIME_LIMIT
celery_app.conf.worker_prefetch_multiplier = settings.CELERY_WORKER_PREFETCH_MULTIPLIER
celery_app.conf.worker_concurrency = settings.CELERY_WORKER_CONCURRENCY

# ========================================
# 多队列路由
# ========================================
default_exchange = Exchange("default", type="direct")
high_priority_exchange = Exchange("high_priority", type="direct")

celery_app.conf.task_queues = (
    Queue("default", default_exchange, routing_key="default"),
    Queue("high_priority", high_priority_exchange, routing_key="high_priority"),
    Queue("ai_gateway", default_exchange, routing_key="ai_gateway"),
    Queue("scheduled", default_exchange, routing_key="scheduled"),
)

celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "default"
celery_app.conf.task_default_routing_key = "default"

celery_app.conf.task_routes = {
    "app.tasks.ai.*": {"queue": "ai_gateway"},
    "app.tasks.scheduled.*": {"queue": "scheduled"},
    "app.tasks.high_priority.*": {"queue": "high_priority"},
}

# ========================================
# 任务自动发现
# ========================================
celery_app.conf.task_modules = [
    "app.tasks",
    "app.tasks.scheduled",
    "app.tasks.recycle_bin",
    "app.tasks.ai_health_check",
    "app.tasks.agent_batch",
    "app.ai.rag.processor",
]

# ========================================
# 结果配置
# ========================================
celery_app.conf.result_expires = 3600
celery_app.conf.task_ignore_result = False

# ========================================
# 默认 Beat 调度（可被数据库配置覆盖）
# ========================================
celery_app.conf.beat_schedule = {
    "system-health-check": {
        "task": "app.tasks.scheduled.system_health_check",
        "schedule": 300.0,
        "options": {"queue": "scheduled"},
    },
    "clean-expired-captchas": {
        "task": "app.tasks.scheduled.clean_expired_captchas",
        "schedule": 3600.0,
        "options": {"queue": "scheduled"},
    },
    "clean-expired-task-logs": {
        "task": "app.tasks.scheduled.clean_expired_task_logs",
        "schedule": 86400.0,
        "options": {"queue": "scheduled"},
    },
    "ai-provider-health-check": {
        "task": "app.tasks.ai_health_check.ai_provider_health_check",
        "schedule": 300.0,
        "options": {"queue": "scheduled"},
    },
    "reset-agent-daily-quotas": {
        "task": "app.tasks.scheduled.reset_agent_daily_quotas",
        "schedule": 86400.0,
        "options": {"queue": "scheduled"},
    },
    "reset-agent-daily-stats": {
        "task": "app.tasks.scheduled.reset_agent_daily_stats",
        "schedule": 86400.0,
        "options": {"queue": "scheduled"},
    },
    "cleanup-recycle-bin": {
        "task": "app.tasks.recycle_bin.cleanup_recycle_bin",
        "schedule": 86400.0,
        "kwargs": {"retention_days": 30},
        "options": {"queue": "scheduled"},
    },
}
