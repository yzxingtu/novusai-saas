"""
Celery task base classes and decorators / Celery 任务基类与装饰器

Provides BaseTask, TenantTask base classes and @register_task decorator.
提供 BaseTask、TenantTask 基类和 @register_task 装饰器
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from typing import Any

from celery import Task
from celery.exceptions import Ignore
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.base_model import utc_now
from app.core.database import sync_session_factory
from app.core.logging import LogManager
from app.enums.task import TaskStatusEnum
from app.middleware.trace import trace_id_var

logger = LogManager.get_logger("queue")

_task_registry: dict[str, dict[str, Any]] = {}


def get_task_registry() -> dict[str, dict[str, Any]]:
    return _task_registry


def build_task_run_key(
    *,
    task_definition_id: int | None,
    binding_id: int | None,
    owner_tenant_id: int | None,
    effective_tenant_id: int | None,
    trigger_source: str | None,
    trigger_slot: str | None = None,
    trigger_id: str | None = None,
    explicit_run_key: str | None = None,
) -> str | None:
    """中文: 构造不依赖 Celery task id 的业务幂等键。

    EN: Build a business idempotency key that does not depend on the Celery task id.
    """
    if explicit_run_key:
        return str(explicit_run_key)[:255]
    if task_definition_id is None:
        return None
    trigger_token = trigger_slot or trigger_id
    if not trigger_token:
        return None
    if binding_id is not None:
        tenant_token = f"binding:{binding_id}"
    else:
        tenant_id = (
            effective_tenant_id if effective_tenant_id is not None else owner_tenant_id
        )
        tenant_token = f"tenant:{tenant_id}"
    key = (
        f"task_definition:{task_definition_id}|{tenant_token}|"
        f"source:{trigger_source or 'unknown'}|trigger:{trigger_token}"
    )
    return key[:255]


def _load_task_definition_config(
    task_definition_id: int,
    binding_id: int | None = None,
) -> dict[str, Any]:
    config: dict[str, Any] = {}
    session = None
    try:
        from app.models.system.task_definition import TaskDefinition
        from app.models.system.tenant_task_binding import TenantTaskBinding

        session = sync_session_factory()
        definition = (
            session.query(TaskDefinition)
            .filter(
                TaskDefinition.id == task_definition_id,
                TaskDefinition.is_deleted.is_(False),
            )
            .first()
        )
        binding = None
        if binding_id is not None:
            binding = (
                session.query(TenantTaskBinding)
                .filter(
                    TenantTaskBinding.id == binding_id,
                    TenantTaskBinding.is_deleted.is_(False),
                )
                .first()
            )

        if definition:
            config = {
                "max_retries": definition.max_retries,
                "retry_delay": definition.retry_delay,
                "timeout": definition.timeout,
                "notify_on_failure": definition.notify_on_failure,
                "notify_emails": definition.notify_emails,
                "task_name": definition.name,
                "task_definition_id": definition.id,
                "binding_id": binding.id if binding else None,
                "schedule_type": (
                    binding.schedule_type_override
                    if binding and binding.schedule_type_override
                    else definition.default_schedule_type
                ),
                "cron_expression": (
                    binding.cron_expression_override
                    if binding and binding.cron_expression_override
                    else definition.default_cron_expression
                ),
                "interval_seconds": (
                    binding.interval_seconds_override
                    if binding and binding.interval_seconds_override is not None
                    else definition.default_interval_seconds
                ),
            }
    except Exception as e:
        logger.warning(
            f"Failed to load task definition config for {task_definition_id}: {e}"
        )
    finally:
        if session:
            session.close()
    return config


class BaseTask(Task):
    """
    Celery task base class / Celery 任务基类

    Automatically logs, handles retries and error callbacks.
    自动记录日志、处理重试和错误回调。
    Dynamically reads max_retries / retry_delay / timeout config from task_definitions.
    动态从 task_definitions 读取 max_retries / retry_delay / timeout 配置。
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
        if not tid:
            tid = str(uuid.uuid4())
        trace_id_var.set(tid)

        self._start_time = time.monotonic()
        self._apply_db_config()
        self._before_task_run_start(task_id, args, kwargs)
        logger.info(f"Task started: {self.name} [{task_id}]")
        self._record_task_run_start(task_id, args, kwargs)

    def after_return(
        self,
        status: str,
        retval: Any,
        task_id: str,
        args: tuple,
        kwargs: dict,
        einfo: Any,
    ) -> None:
        try:
            super().after_return(status, retval, task_id, args, kwargs, einfo)
        finally:
            trace_id_var.set("")

    def _apply_db_config(self) -> None:
        """
        从 task_definitions 动态加载配置并覆盖 Celery 参数 / Dynamically load config from task_definitions and override Celery params.

        DB config takes priority over @register_task hardcoded values.
        """
        headers = getattr(self.request, "headers", None) or {}
        config: dict[str, Any] = {}
        if isinstance(headers, dict) and headers.get("task_definition_id"):
            try:
                task_definition_id = int(headers["task_definition_id"])
                binding_id = (
                    int(headers["binding_id"])
                    if headers.get("binding_id") not in (None, "", "null")
                    else None
                )
                config = _load_task_definition_config(
                    task_definition_id,
                    binding_id,
                )
            except (TypeError, ValueError):
                config = {}
        if not config:
            return
        self._db_config = config
        if config.get("max_retries") is not None:
            self.max_retries = config["max_retries"]
        if config.get("timeout") is not None:
            self.soft_time_limit = config["timeout"]

    def _before_task_run_start(
        self,
        task_id: str,
        args: tuple,
        kwargs: dict,
    ) -> None:
        """中文: 任务启动前的 fail-closed 扩展点。EN: Fail-closed hook before task execution starts."""
        _ = (task_id, args, kwargs)

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
        logger.info(f"Task succeeded: {self.name} [{task_id}] elapsed={elapsed:.2f}s")
        self._record_task_run_success(task_id, retval, elapsed)
        self._update_periodic_task_timestamps()

    def on_failure(
        self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any
    ) -> None:
        _ = (args, kwargs)
        elapsed = self._get_elapsed()
        logger.error(
            f"Task failed: {self.name} [{task_id}] elapsed={elapsed:.2f}s error={exc!r}"
        )
        self._record_task_run_failure(task_id, exc, einfo, elapsed)
        self._update_periodic_task_timestamps()
        self._notify_failure(task_id, exc)

    def on_retry(
        self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any
    ) -> None:
        _ = (args, kwargs, einfo)
        logger.warning(
            f"Task retrying: {self.name} [{task_id}] "
            f"retry={self.request.retries}/{self.max_retries} error={exc!r}"
        )
        self._record_task_run_retry(task_id, exc)

    def _notify_failure(self, task_id: str, exc: Exception) -> None:
        """
        Task failure notification hook / 任务失败通知钩子。

        Decides whether to send notification based on task_definitions notify_on_failure config.
        根据 task_definitions 的 notify_on_failure 配置决定是否发送通知。
        Currently supported: log recording. Reserved: WebSocket push, email notification.
        当前支持：日志记录。预留接口：WebSocket 实时推送、邮件通知
        """
        if not self._db_config or not self._db_config.get("notify_on_failure"):
            return

        task_name = self._db_config.get("task_name", self.name)
        notify_emails = self._db_config.get("notify_emails", "")

        logger.warning(
            "Task failure notification: task={} task_id={} error={} emails={}",
            task_name,
            task_id,
            str(exc)[:200],
            notify_emails or "(none)",
        )

        try:
            from app.core.sio_bridge import notify_admins_sync
            from app.services.common.notification_service import build_ws_payload_sync

            payload = build_ws_payload_sync(
                template_code="task.failed",
                data={
                    "task_name": task_name,
                    "task_id": task_id,
                    "error": str(exc)[:500],
                },
                fallback_category="task",
                fallback_title=f"Task failed: {task_name}",
                fallback_body=str(exc)[:500],
                fallback_priority="high",
            )
            if payload:
                notify_admins_sync(payload)
        except Exception as ws_err:
            logger.warning(
                "Failed to send WS task failure notification: {}", str(ws_err)
            )

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
                    data={
                        "task_name": task_name,
                        "task_id": task_id,
                        "error": str(exc)[:500],
                    },
                    email_html=html_body,
                    email_subject=subject,
                    email_text=text_body,
                )
            except Exception as mail_err:
                logger.warning(
                    "Failed to send task failure notification: {}",
                    str(mail_err),
                )

    def _get_elapsed(self) -> float:
        if self._start_time is not None:
            return time.monotonic() - self._start_time
        return 0.0

    def get_db_session(self) -> Session:
        return sync_session_factory()

    # ── Task Run Recording (sync) / 任务运行记录（同步） ────────────────────────

    def _get_task_run_context(self) -> dict[str, Any] | None:
        """Extract task-run metadata from Celery headers. / 从 Celery headers 中提取任务运行上下文。"""
        headers = getattr(self.request, "headers", None) or {}
        if not isinstance(headers, dict):
            return None

        task_code = headers.get("task_code_snapshot")
        if not task_code:
            return None

        def _to_int(value: Any) -> int | None:
            if value in (None, "", "null"):
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        return {
            "task_definition_id": _to_int(headers.get("task_definition_id")),
            "binding_id": _to_int(headers.get("binding_id")),
            "run_key": headers.get("run_key"),
            "task_code_snapshot": str(task_code),
            "task_name_snapshot": str(headers.get("task_name_snapshot") or self.name),
            "handler_path_snapshot": str(
                headers.get("handler_path_snapshot") or self.name
            ),
            "trigger_source": str(headers.get("trigger_source") or "scheduler"),
            "run_kind": str(headers.get("run_kind") or "platform"),
            "owner_tenant_id": _to_int(headers.get("owner_tenant_id")),
            "effective_tenant_id": _to_int(headers.get("effective_tenant_id")),
            "trigger_slot": headers.get("trigger_slot"),
            "trigger_id": headers.get("trigger_id"),
            "retry_of_run_id": _to_int(headers.get("retry_of_run_id")),
            "retry_of_task_id": headers.get("retry_of_task_id"),
        }

    def _summarize_payload(self, value: Any) -> str | None:
        """Create a concise summary string for logs. / 为日志生成精简摘要文本。"""
        if value is None:
            return None
        if isinstance(value, dict):
            if "error" in value:
                return str(value["error"])[:500]
            text = str(value)
            return text[:500]
        text = str(value)
        return text[:500] if text else None

    def _build_context_run_key(self, context: dict[str, Any]) -> str | None:
        run_key = build_task_run_key(
            task_definition_id=context["task_definition_id"],
            binding_id=context["binding_id"],
            owner_tenant_id=context["owner_tenant_id"],
            effective_tenant_id=context["effective_tenant_id"],
            trigger_source=context["trigger_source"],
            trigger_slot=(
                str(context["trigger_slot"]) if context.get("trigger_slot") else None
            ),
            trigger_id=str(context["trigger_id"])
            if context.get("trigger_id")
            else None,
            explicit_run_key=str(context["run_key"])
            if context.get("run_key")
            else None,
        )
        if run_key:
            return run_key
        trace_id = trace_id_var.get()
        if not trace_id:
            return None
        return build_task_run_key(
            task_definition_id=context["task_definition_id"],
            binding_id=context["binding_id"],
            owner_tenant_id=context["owner_tenant_id"],
            effective_tenant_id=context["effective_tenant_id"],
            trigger_source=context["trigger_source"],
            trigger_id=f"trace:{trace_id}",
        )

    def _raise_duplicate_task_run(
        self, task_id: str, run_key: str, existing: Any
    ) -> None:
        logger.warning(
            "Deduplicated task run: task={} duplicate_task_id={} run_key={} existing_run_id={}",
            self.name,
            task_id,
            run_key,
            getattr(existing, "id", None),
        )
        raise Ignore()

    def _record_task_run_start(
        self,
        task_id: str,
        args: tuple,
        kwargs: dict,
    ) -> None:
        """Insert a TaskRun row when the actual task starts. / 真实任务启动时插入 TaskRun。"""
        context = self._get_task_run_context()
        if not context:
            return

        session = None
        try:
            from app.models.system.task_run import TaskRun

            session = sync_session_factory()
            queue = getattr(self, "queue", "default") or "default"
            safe_args = self._safe_json(list(args)) if args else None
            safe_kwargs = self._safe_json(dict(kwargs)) if kwargs else None
            args_summary = None
            if safe_args is not None or safe_kwargs is not None:
                args_summary = {"args": safe_args, "kwargs": safe_kwargs}

            run_key = self._build_context_run_key(context)
            if run_key:
                existing = (
                    session.query(TaskRun)
                    .filter(
                        TaskRun.run_key == run_key,
                        TaskRun.is_deleted.is_(False),
                    )
                    .first()
                )
                if existing:
                    self._raise_duplicate_task_run(task_id, run_key, existing)

            run = TaskRun(
                celery_task_id=task_id,
                run_key=run_key,
                task_definition_id=context["task_definition_id"],
                binding_id=context["binding_id"],
                task_code_snapshot=context["task_code_snapshot"],
                task_name_snapshot=context["task_name_snapshot"],
                handler_path_snapshot=context["handler_path_snapshot"],
                trigger_source=context["trigger_source"],
                run_kind=context["run_kind"],
                owner_tenant_id=context["owner_tenant_id"],
                effective_tenant_id=context["effective_tenant_id"],
                queue=queue,
                status=TaskStatusEnum.RUNNING.value,
                args_summary=args_summary,
                trace_id=trace_id_var.get() or None,
                started_at=utc_now(),
            )
            session.add(run)
            session.commit()
        except IntegrityError:
            if session:
                session.rollback()
                try:
                    from app.models.system.task_run import TaskRun

                    run_key = self._build_context_run_key(context)
                    existing = (
                        session.query(TaskRun)
                        .filter(
                            TaskRun.run_key == run_key,
                            TaskRun.is_deleted.is_(False),
                        )
                        .first()
                        if run_key
                        else None
                    )
                    if existing and run_key:
                        self._raise_duplicate_task_run(task_id, run_key, existing)
                except Ignore:
                    raise
            logger.warning("Failed to record task run start due to unique constraint")
        except Ignore:
            raise
        except Exception as e:
            logger.warning(f"Failed to record task run start: {e}")
            if session:
                session.rollback()
        finally:
            if session:
                session.close()

    def _record_task_run_success(
        self,
        task_id: str,
        retval: Any,
        elapsed: float,
    ) -> None:
        """Update TaskRun to SUCCESS. / 更新 TaskRun 为成功状态。"""
        context = self._get_task_run_context()
        if not context:
            return

        session = None
        try:
            from app.models.system.task_run import TaskRun

            session = sync_session_factory()
            run = (
                session.query(TaskRun).filter(TaskRun.celery_task_id == task_id).first()
            )
            if run:
                run.status = TaskStatusEnum.SUCCESS.value
                run.result_summary = self._safe_json(retval)
                run.summary = self._summarize_payload(retval)
                run.finished_at = utc_now()
                run.duration_ms = int(elapsed * 1000)
                run.trace_id = trace_id_var.get() or run.trace_id
                session.commit()
        except Exception as e:
            logger.warning(f"Failed to record task run success: {e}")
            if session:
                session.rollback()
        finally:
            if session:
                session.close()

    def _record_task_run_failure(
        self,
        task_id: str,
        exc: Exception,
        einfo: Any,
        elapsed: float,
    ) -> None:
        """Update or create failed TaskRun. / 更新或创建失败 TaskRun。"""
        context = self._get_task_run_context()
        if not context:
            return

        session = None
        try:
            from app.models.system.task_run import TaskRun

            session = sync_session_factory()
            run = (
                session.query(TaskRun).filter(TaskRun.celery_task_id == task_id).first()
            )
            now = utc_now()
            if run:
                run.status = TaskStatusEnum.FAILED.value
                run.summary = str(exc)[:500]
                run.error_message_public = str(exc)[:500]
                run.error_message_internal = str(exc)[:2000]
                run.traceback_internal = str(einfo)[:5000] if einfo else None
                run.finished_at = now
                run.duration_ms = int(elapsed * 1000)
                run.trace_id = trace_id_var.get() or run.trace_id
            else:
                run = TaskRun(
                    celery_task_id=task_id,
                    run_key=self._build_context_run_key(context),
                    task_definition_id=context["task_definition_id"],
                    binding_id=context["binding_id"],
                    task_code_snapshot=context["task_code_snapshot"],
                    task_name_snapshot=context["task_name_snapshot"],
                    handler_path_snapshot=context["handler_path_snapshot"],
                    trigger_source=context["trigger_source"],
                    run_kind=context["run_kind"],
                    owner_tenant_id=context["owner_tenant_id"],
                    effective_tenant_id=context["effective_tenant_id"],
                    queue=getattr(self, "queue", "default") or "default",
                    status=TaskStatusEnum.FAILED.value,
                    summary=str(exc)[:500],
                    error_message_public=str(exc)[:500],
                    error_message_internal=str(exc)[:2000],
                    traceback_internal=str(einfo)[:5000] if einfo else None,
                    trace_id=trace_id_var.get() or None,
                    started_at=now,
                    finished_at=now,
                    duration_ms=int(elapsed * 1000),
                )
                session.add(run)
            session.commit()
        except Exception as e:
            logger.warning(f"Failed to record task run failure: {e}")
            if session:
                session.rollback()
        finally:
            if session:
                session.close()

    def _record_task_run_retry(self, task_id: str, exc: Exception) -> None:
        """Update TaskRun to RETRYING. / 更新 TaskRun 为重试状态。"""
        context = self._get_task_run_context()
        if not context:
            return

        session = None
        try:
            from app.models.system.task_run import TaskRun

            session = sync_session_factory()
            run = (
                session.query(TaskRun).filter(TaskRun.celery_task_id == task_id).first()
            )
            if run:
                run.status = TaskStatusEnum.RETRYING.value
                run.summary = str(exc)[:500]
                run.error_message_public = str(exc)[:500]
                run.error_message_internal = str(exc)[:2000]
                run.retry_count = getattr(self.request, "retries", 0)
                run.trace_id = trace_id_var.get() or run.trace_id
                session.commit()
        except Exception as e:
            logger.warning(f"Failed to record task run retry: {e}")
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
        """Update last_run_at and next_run_at in task definitions / 更新 task_definition / binding 的执行时间。"""
        session = None
        try:
            from datetime import timedelta

            from app.models.system.task_definition import TaskDefinition
            from app.models.system.tenant_task_binding import TenantTaskBinding

            session = sync_session_factory()
            now = utc_now()
            headers = getattr(self.request, "headers", None) or {}

            def _compute_next_run(
                schedule_type: str | None,
                cron_expression: str | None,
                interval_seconds: int | None,
            ):
                if schedule_type == "cron" and cron_expression:
                    try:
                        from celery.schedules import crontab

                        parts = cron_expression.strip().split()
                        if len(parts) == 5:
                            schedule = crontab(
                                minute=parts[0],
                                hour=parts[1],
                                day_of_month=parts[2],
                                month_of_year=parts[3],
                                day_of_week=parts[4],
                            )
                            remaining = schedule.remaining_estimate(now)
                            return now + remaining
                    except Exception:
                        return None
                if schedule_type == "interval" and interval_seconds:
                    return now + timedelta(seconds=interval_seconds)
                return None

            updated_new_model = False
            if isinstance(headers, dict) and headers.get("task_definition_id"):
                try:
                    task_definition_id = int(headers["task_definition_id"])
                    binding_id = (
                        int(headers["binding_id"])
                        if headers.get("binding_id") not in (None, "", "null")
                        else None
                    )
                    definition = (
                        session.query(TaskDefinition)
                        .filter(
                            TaskDefinition.id == task_definition_id,
                            TaskDefinition.is_deleted.is_(False),
                        )
                        .first()
                    )
                    binding = None
                    if binding_id is not None:
                        binding = (
                            session.query(TenantTaskBinding)
                            .filter(
                                TenantTaskBinding.id == binding_id,
                                TenantTaskBinding.is_deleted.is_(False),
                            )
                            .first()
                        )
                    if definition:
                        schedule_type = definition.default_schedule_type
                        cron_expression = definition.default_cron_expression
                        interval_seconds = definition.default_interval_seconds
                        if binding:
                            schedule_type = (
                                binding.schedule_type_override or schedule_type
                            )
                            cron_expression = (
                                binding.cron_expression_override or cron_expression
                            )
                            interval_seconds = (
                                binding.interval_seconds_override
                                if binding.interval_seconds_override is not None
                                else interval_seconds
                            )
                            binding.last_run_at = now
                            binding.next_run_at = _compute_next_run(
                                schedule_type,
                                cron_expression,
                                interval_seconds,
                            )
                        definition.last_run_at = now
                        definition.next_run_at = _compute_next_run(
                            schedule_type,
                            cron_expression,
                            interval_seconds,
                        )
                        updated_new_model = True
                except (TypeError, ValueError):
                    updated_new_model = False

            if not updated_new_model:
                return

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

    @staticmethod
    def _normalize_tenant_id(value: Any) -> int | None:
        if value in (None, "", "null"):
            return None
        try:
            tenant_id = int(value)
        except (TypeError, ValueError):
            return None
        return tenant_id if tenant_id > 0 else None

    def _before_task_run_start(
        self,
        task_id: str,
        args: tuple,
        kwargs: dict,
    ) -> None:
        _ = (task_id, args)
        tenant_id = self._normalize_tenant_id(kwargs.get("tenant_id"))
        if tenant_id is None:
            logger.warning("Rejected tenant task without tenant_id: task={}", self.name)
            raise Ignore()

        headers = getattr(self.request, "headers", None) or {}
        if isinstance(headers, dict):
            header_tenant_id = self._normalize_tenant_id(
                headers.get("effective_tenant_id")
            )
            if header_tenant_id is not None and header_tenant_id != tenant_id:
                logger.warning(
                    "Rejected tenant task with mismatched tenant context: task={} "
                    "tenant_id={} effective_tenant_id={}",
                    self.name,
                    tenant_id,
                    header_tenant_id,
                )
                raise Ignore()

        self._require_eligible_tenant(tenant_id)
        self._tenant_id = tenant_id
        logger.info("Task tenant context: tenant_id={}", self._tenant_id)

    def _require_eligible_tenant(self, tenant_id: int) -> None:
        """中文: 兜底校验企业任务资格。EN: Guard tenant task eligibility as a final runtime boundary."""
        session = None
        try:
            from app.services.system.task_tenant_eligibility_service import (
                TaskTenantEligibilityService,
            )

            session = sync_session_factory()
            result = TaskTenantEligibilityService.resolve_tenant_eligibility_sync(
                session,
                tenant_id,
            )
            if not result.is_eligible:
                logger.warning(
                    "Rejected tenant task for ineligible tenant: task={} "
                    "tenant_id={} reason={}",
                    self.name,
                    tenant_id,
                    result.reason,
                )
                raise Ignore()
        except Ignore:
            raise
        except Exception as exc:
            logger.warning(
                "Rejected tenant task because eligibility resolution failed: "
                "task={} tenant_id={} error={}",
                self.name,
                tenant_id,
                exc,
            )
            raise Ignore() from exc
        finally:
            if session:
                session.close()

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
            "base": base.__name__,
        }

        return registered_task

    return decorator
