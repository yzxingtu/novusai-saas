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
# 任务自动发现
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

# 强制导入任务模块（确保 Windows --pool=solo 模式下也能注册）
def _import_task_modules():
    for module in celery_app.conf.include:
        try:
            __import__(module)
        except ImportError as e:
            pass  # 某些模块可能依赖未安装的包（如 acme）

_import_task_modules()

# ========================================
# 结果配置
# ========================================
celery_app.conf.result_expires = 3600
celery_app.conf.task_ignore_result = False

# ========================================
# Beat 调度（由数据库 periodic_tasks 表驱动）
# ========================================
# 所有定时任务通过 periodic_tasks 表管理，不再硬编码任何调度条目。
#
# 重要：必须在模块级别加载调度，不能用 beat_init 信号。
# 原因：Celery 5.x beat.Service.start() 中，self.scheduler 在
# beat_init.send() 之前就被访问（debug 日志行），触发
# PersistentScheduler 初始化并读取 conf.beat_schedule。
# 如果此时 beat_schedule 为空，调度器不会安装任何条目。
# beat_init 信号中再更新 conf.beat_schedule 已经太晚。
try:
    from app.tasks.scheduler import load_periodic_tasks_from_db
    celery_app.conf.beat_schedule = load_periodic_tasks_from_db()
except Exception:
    celery_app.conf.beat_schedule = {}
