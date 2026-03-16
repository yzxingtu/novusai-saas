"""
Celery task base classes and decorators / Celery 任务基类与装饰器

Provides BaseTask, TenantTask base classes and @register_task decorator.
提供 BaseTask、TenantTask 基类和 @register_task 装饰器
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from celery import Task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.middleware.trace import trace_id_var
from app.core.base_model import utc_now
from app.core.database import sync_session_factory
from app.core.logging import LogManager

logger = LogManager.get_logger("queue")

_task_registry: dict[str, dict[str, Any]] = {}


def get_task_registry() -> dict[str, dict[str, Any]]:
    return _task_registry


# Cache periodic_tasks config to avoid DB query on every task execution / 缓存 periodic_tasks 配置，避免每次任务执行都查 DB
_periodic_task_config_cache: dict[str, dict[str, Any]] = {}


def _load_periodic_task_config(task_path: str) -> dict[str, Any]:
    """
    从 periodic_tasks 表加载任务配置 / Load task config from periodic_tasks table.

    Results are cached in memory; DB is queried only once per Worker lifecycle.
    结果缓存在内存中，Worker 生命周期内只查一次 DB。
    """
    if task_path in _periodic_task_config_cache:
        return _periodic_task_config_cache[task_path]

    config: dict[str, Any] = {}
    session = None
    try:
        from app.models.system.periodic_task import PeriodicTask

        session = sync_session_factory()
        task = (
            session.query(PeriodicTask)
            .filter(
                PeriodicTask.task_path == task_path,
                PeriodicTask.is_deleted.is_(False),
            )
            .first()
        )
        if task:
            config = {
                "max_retries": task.max_retries,
                "retry_delay": task.retry_delay,
                "timeout": task.timeout,
                "notify_on_failure": task.notify_on_failure,
                "notify_emails": task.notify_emails,
                "task_name": task.name,
            }
    except Exception as e:
        logger.warning(f"Failed to load periodic task config for {task_path}: {e}")
    finally:
        if session:
            session.close()

    _periodic_task_config_cache[task_path] = config
    return config


class BaseTask(Task):
    """
    Celery task base class / Celery 任务基类

    Automatically logs, handles retries and error callbacks.
    自动记录日志、处理重试和错误回调。
    Dynamically reads max_retries / retry_delay / timeout config from periodic_tasks table.
    动态从 periodic_tasks 表读取 max_retries / retry_delay / timeout 配置。
    """

    abstract = True
    max_retries = 3
    default_retry_delay = 60
    _start_time: float | None = None
    _db_config: dict[str, int] | None = None

    def apply_async(
        self,
        args: tuple | None = None,
        kwargs: dict | None = None,
        **options: Any,
    ) -> Any:
        """
        Override to inject trace_id from context into task headers.
        覆盖以从上下文注入 trace_id 到任务 headers。
        """
        headers = dict(options.get("headers") or {})
        tid = trace_id_var.get()
        if tid:
            headers["trace_id"] = tid
        if headers:
            options = {**options, "headers": headers}
        return super().apply_async(args=args, kwargs=kwargs, **options)

    def before_start(self, task_id: str, args: tuple, kwargs: dict) -> None:
        # Restore trace_id from task headers for log correlation
        # 从任务 headers 恢复 trace_id 用于日志关联
        req_headers = getattr(self.request, "headers", None) or {}
        tid = req_headers.get("trace_id") if isinstance(req_headers, dict) else None
        if tid:
            trace_id_var.set(tid)

        self._start_time = time.monotonic()
        self._apply_db_config()
        logger.info(f"Task started: {self.name} [{task_id}]")
        self._record_task_log_start(task_id, args, kwargs)

    def _apply_db_config(self) -> None:
        """
        从 periodic_tasks 表动态加载配置并覆盖 Celery 参数 / Dynamically load config from periodic_tasks and override Celery params.

        DB config takes priority over @register_task hardcoded values.
        """
        config = _load_periodic_task_config(self.name)
        if not config:
            return
        self._db_config = config
        if config.get("max_retries") is not None:
            self.max_retries = config["max_retries"]
        if config.get("timeout") is not None:
            self.soft_time_limit = config["timeout"]

    def get_retry_countdown(self) -> int:
        """
        获取重试间隔（秒）/ Get retry interval (seconds). Prefers DB config, falls back to default_retry_delay.
        """
        if self._db_config and self._db_config.get("retry_delay"):
            return self._db_config["retry_delay"]
        return self.default_retry_delay

    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        _ = (args, kwargs)
        elapsed = self._get_elapsed()
        logger.info(
            f"Task succeeded: {self.name} [{task_id}] "
            f"elapsed={elapsed:.2f}s"
        )
        self._record_task_log_success(task_id, retval, elapsed)
        self._update_periodic_task_timestamps()

    def on_failure(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        _ = (args, kwargs)
        elapsed = self._get_elapsed()
        logger.error(
            f"Task failed: {self.name} [{task_id}] "
            f"elapsed={elapsed:.2f}s error={exc!r}"
        )
        self._record_task_log_failure(task_id, exc, einfo, elapsed)
        self._update_periodic_task_timestamps()
        self._notify_failure(task_id, exc)

    def on_retry(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        _ = (args, kwargs, einfo)
        logger.warning(
            f"Task retrying: {self.name} [{task_id}] "
            f"retry={self.request.retries}/{self.max_retries} error={exc!r}"
        )
        self._record_task_log_retry(task_id, exc)

    def _notify_failure(self, task_id: str, exc: Exception) -> None:
        """
        Task failure notification hook / 任务失败通知钩子。

        Decides whether to send notification based on periodic_tasks table's notify_on_failure config.
        根据 periodic_tasks 表的 notify_on_failure 配置决定是否发送通知。
        Currently supported: log recording. Reserved: WebSocket push, email notification.
        当前支持：日志记录。预留接口：WebSocket 实时推送、邮件通知
        """
        if not self._db_config or not self._db_config.get("notify_on_failure"):
            return

        task_name = self._db_config.get("task_name", self.name)
        notify_emails = self._db_config.get("notify_emails", "")

        # 1. Record notification log / 记录通知日志
        logger.warning(
            "Task failure notification: task={} task_id={} error={} emails={}",
            task_name, task_id, str(exc)[:200], notify_emails or "(none)",
        )

        # 2. Socket.IO real-time push (via sio_bridge sync publish) / Socket.IO 实时推送（通过 sio_bridge 同步发布）
        try:
            from app.core.sio_bridge import notify_admins_sync
            notify_admins_sync({
                "type": "task.failed",
                "category": "task",
                "title": f"Task failed: {task_name}",
                "body": str(exc)[:500],
                "data": {"task_name": task_name, "task_id": task_id},
                "priority": "high",
            })
        except Exception as ws_err:
            logger.warning("Failed to send WS task failure notification: {}", str(ws_err))

        # 3. Email notification (via unified notification system) / 邮件通知（通过统一通知系统）
        if notify_emails:
            try:
                from app.services.common.email_templates import (
                    render_task_failure_email,
                )
                from app.services.common.notification_service import notify_sync

                subject, html_body, text_body = render_task_failure_email(
                    task_name=task_name,
                    task_id=task_id,
                    error=str(exc)[:1000],
                )
                notify_sync(
                    template_code="system.task_failure",
                    recipients=[("admin", 1)],
                    data={"task_name": task_name, "task_id": task_id, "error": str(exc)[:500]},
                    email_html=html_body,
                    email_subject=subject,
                    email_text=text_body,
                )
            except Exception as mail_err:
                logger.warning(
                    "Failed to send task failure notification: {}", str(mail_err),
                )

    def _get_elapsed(self) -> float:
        if self._start_time is not None:
            return time.monotonic() - self._start_time
        return 0.0

    def get_db_session(self) -> Session:
        return sync_session_factory()

    # ── Task Log Recording (sync) / 任务日志记录（同步） ──────────────────────────

    def _record_task_log_start(
        self, task_id: str, args: tuple, kwargs: dict,
    ) -> None:
        """Insert a TaskLog row when task starts. / 任务启动时插入 TaskLog 记录。"""
        session = None
        try:
            from app.models.system.task_log import TaskLog

            session = sync_session_factory()
            queue = getattr(self, "queue", "default") or "default"
            tenant_id = kwargs.get("tenant_id") if kwargs else None

            # Serialize args/kwargs safely / 安全序列化 args/kwargs
            safe_args = self._safe_json(list(args)) if args else None
            safe_kwargs = self._safe_json(dict(kwargs)) if kwargs else None

            log = TaskLog(
                task_id=task_id,
                task_name=self.name,
                queue=queue,
                status="running",
                args=safe_args,
                kwargs=safe_kwargs,
                started_at=utc_now(),
                tenant_id=tenant_id,
            )
            session.add(log)
            session.commit()
        except Exception as e:
            logger.warning(f"Failed to record task log start: {e}")
            if session:
                session.rollback()
        finally:
            if session:
                session.close()

    def _record_task_log_success(
        self, task_id: str, retval: Any, elapsed: float,
    ) -> None:
        """Update TaskLog to SUCCESS. / 更新 TaskLog 为成功状态。"""
        session = None
        try:
            from app.models.system.task_log import TaskLog

            session = sync_session_factory()
            log = (
                session.query(TaskLog)
                .filter(TaskLog.task_id == task_id)
                .first()
            )
            if log:
                log.status = "success"
                log.result = self._safe_json(retval)
                log.finished_at = utc_now()
                log.duration_ms = int(elapsed * 1000)
                session.commit()
        except Exception as e:
            logger.warning(f"Failed to record task log success: {e}")
            if session:
                session.rollback()
        finally:
            if session:
                session.close()

    def _record_task_log_failure(
        self, task_id: str, exc: Exception, einfo: Any, elapsed: float,
    ) -> None:
        """Update or create TaskLog as FAILED. / 更新或创建失败状态的 TaskLog。"""
        session = None
        try:
            from app.models.system.task_log import TaskLog

            session = sync_session_factory()
            log = (
                session.query(TaskLog)
                .filter(TaskLog.task_id == task_id)
                .first()
            )
            now = utc_now()
            if log:
                log.status = "failed"
                log.error_message = str(exc)[:2000]
                log.traceback = str(einfo)[:5000] if einfo else None
                log.finished_at = now
                log.duration_ms = int(elapsed * 1000)
            else:
                # Create a new failure record if before_start failed to create log / before_start 未能创建日志时，直接新建一条失败记录
                queue = getattr(self, "queue", "default") or "default"
                log = TaskLog(
                    task_id=task_id,
                    task_name=self.name,
                    queue=queue,
                    status="failed",
                    error_message=str(exc)[:2000],
                    traceback=str(einfo)[:5000] if einfo else None,
                    started_at=now,
                    finished_at=now,
                    duration_ms=int(elapsed * 1000),
                )
                session.add(log)
            session.commit()
        except Exception as e:
            logger.warning(f"Failed to record task log failure: {e}")
            if session:
                session.rollback()
        finally:
            if session:
                session.close()

    def _record_task_log_retry(self, task_id: str, exc: Exception) -> None:
        """Update TaskLog to RETRYING. / 更新 TaskLog 为重试状态。"""
        session = None
        try:
            from app.models.system.task_log import TaskLog

            session = sync_session_factory()
            log = (
                session.query(TaskLog)
                .filter(TaskLog.task_id == task_id)
                .first()
            )
            if log:
                log.status = "retrying"
                log.retry_count = getattr(self.request, "retries", 0)
                log.error_message = str(exc)[:2000]
                session.commit()
        except Exception as e:
            logger.warning(f"Failed to record task log retry: {e}")
            if session:
                session.rollback()
        finally:
            if session:
                session.close()

    @staticmethod
    def _safe_json(value: Any) -> Any:
        """Convert value to JSON-serializable form. / 将值转换为 JSON 可序列化格式。"""
        if value is None:
            return None
        if isinstance(value, (dict, list, str, int, float, bool)):
            return value
        try:
            return str(value)
        except Exception:
            return None

    def _update_periodic_task_timestamps(self) -> None:
        """Update last_run_at and next_run_at in periodic_tasks table / 更新 periodic_tasks 表中的 last_run_at 和 next_run_at"""
        session = None
        try:
            from datetime import timedelta

            from app.models.system.periodic_task import PeriodicTask

            session = sync_session_factory()
            task = (
                session.query(PeriodicTask)
                .filter(
                    PeriodicTask.task_path == self.name,
                    PeriodicTask.is_deleted.is_(False),
                )
                .first()
            )
            if not task:
                return

            now = utc_now()
            task.last_run_at = now

            # Calculate next_run_at / 计算 next_run_at
            if task.schedule_type == "cron" and task.cron_expression:
                try:
                    from celery.schedules import crontab
                    parts = task.cron_expression.strip().split()
                    if len(parts) == 5:
                        schedule = crontab(
                            minute=parts[0],
                            hour=parts[1],
                            day_of_month=parts[2],
                            month_of_year=parts[3],
                            day_of_week=parts[4],
                        )
                        remaining = schedule.remaining_estimate(now)
                        task.next_run_at = now + remaining  # remaining is timedelta
                except Exception:
                    pass
            elif task.schedule_type == "interval" and task.interval_seconds:
                task.next_run_at = now + timedelta(seconds=task.interval_seconds)

            session.commit()
            logger.info(f"Updated periodic task timestamps: {self.name}")
        except Exception as e:
            logger.warning(f"Failed to update periodic task timestamps: {e}")
            if session:
                session.rollback()
        finally:
            if session:
                session.close()


class TenantTask(BaseTask):
    """
    Tenant-isolated task base class / 企业隔离任务基类

    Automatically extracts tenant_id from task params and sets it to context.
    自动从任务参数中提取 tenant_id 并设置到上下文
    """

    abstract = True
    _tenant_id: int | None = None

    def before_start(self, task_id: str, args: tuple, kwargs: dict) -> None:
        super().before_start(task_id, args, kwargs)
        self._tenant_id = kwargs.get("tenant_id")
        if self._tenant_id:
            logger.info(f"Task tenant context: tenant_id={self._tenant_id}")

    @property
    def tenant_id(self) -> int | None:
        return self._tenant_id


def register_task(
    *,
    name: str | None = None,
    queue: str = "default",
    description: str = "",
    max_retries: int = 3,
    rate_limit: str | None = None,
    base: type[Task] = BaseTask,
    **task_kwargs: Any,
) -> Callable:
    """
    Task registration decorator / 任务注册装饰器

    Automatically sets base=BaseTask, bind=True, and registers to the global task registry.
    自动设置 base=BaseTask、bind=True，并注册到全局任务注册表
    """

    def decorator(func: Callable) -> Task:
        task_name = name or f"{func.__module__}.{func.__qualname__}"

        task_options: dict[str, Any] = {
            "name": task_name,
            "bind": True,
            "base": base,
            "max_retries": max_retries,
            "queue": queue,
            **task_kwargs,
        }
        if rate_limit:
            task_options["rate_limit"] = rate_limit

        registered_task = celery_app.task(**task_options)(func)

        _task_registry[task_name] = {
            "name": task_name,
            "description": description,
            "queue": queue,
            "max_retries": max_retries,
            "module": func.__module__,
        }

        return registered_task

    return decorator
