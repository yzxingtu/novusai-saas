"""
任务管理服务 / Task Manager Service

提供任务重试、取消、活跃任务查询等管理功能
Provides task retry, cancel, active task query and other management features.
"""

from typing import Any
from uuid import uuid4

from app.celery_app import celery_app
from app.core.logging import LogManager
from app.tasks.base import build_task_run_key

logger = LogManager.get_logger("queue")


class TaskManagerService:
    """
    任务管理服务 / Task manager service.

    封装 Celery 控制操作，提供任务重试、取消和监控功能
    """

    @staticmethod
    def _build_retry_headers(original_run: Any | None) -> dict[str, Any]:
        if original_run is None:
            return {}

        trigger_id = (
            f"manual_retry:{getattr(original_run, 'id', 'unknown')}:{uuid4().hex}"
        )
        run_key = build_task_run_key(
            task_definition_id=getattr(original_run, "task_definition_id", None),
            binding_id=getattr(original_run, "binding_id", None),
            owner_tenant_id=getattr(original_run, "owner_tenant_id", None),
            effective_tenant_id=getattr(original_run, "effective_tenant_id", None),
            trigger_source=getattr(original_run, "trigger_source", None),
            trigger_id=trigger_id,
        )
        headers = {
            "task_definition_id": getattr(original_run, "task_definition_id", None),
            "binding_id": getattr(original_run, "binding_id", None),
            "task_code_snapshot": getattr(original_run, "task_code_snapshot", None),
            "task_name_snapshot": getattr(original_run, "task_name_snapshot", None),
            "handler_path_snapshot": getattr(
                original_run,
                "handler_path_snapshot",
                None,
            ),
            "trigger_source": getattr(original_run, "trigger_source", None),
            "run_kind": getattr(original_run, "run_kind", None),
            "owner_tenant_id": getattr(original_run, "owner_tenant_id", None),
            "effective_tenant_id": getattr(original_run, "effective_tenant_id", None),
            "trace_id": getattr(original_run, "trace_id", None),
            "trigger_id": trigger_id,
            "retry_of_run_id": getattr(original_run, "id", None),
            "retry_of_task_id": getattr(original_run, "celery_task_id", None),
            "run_key": run_key,
        }
        return {key: value for key, value in headers.items() if value is not None}

    @staticmethod
    def retry_task(
        task_name: str,
        args: list | None = None,
        kwargs: dict | None = None,
        queue: str | None = None,
        original_run: Any | None = None,
    ) -> dict[str, Any]:
        headers = TaskManagerService._build_retry_headers(original_run)
        send_options: dict[str, Any] = {
            "args": args or [],
            "kwargs": kwargs or {},
            "queue": queue or "default",
        }
        if headers:
            send_options["headers"] = headers
        result = celery_app.send_task(task_name, **send_options)
        logger.info(f"Task retried: {task_name} -> new task_id={result.id}")
        response: dict[str, Any] = {
            "new_task_id": result.id,
        }
        if original_run is not None:
            response.update(
                {
                    "retry_of_run_id": getattr(original_run, "id", None),
                    "retry_of_task_id": getattr(original_run, "celery_task_id", None),
                    "task_definition_id": getattr(
                        original_run,
                        "task_definition_id",
                        None,
                    ),
                    "binding_id": getattr(original_run, "binding_id", None),
                    "owner_tenant_id": getattr(original_run, "owner_tenant_id", None),
                    "effective_tenant_id": getattr(
                        original_run,
                        "effective_tenant_id",
                        None,
                    ),
                    "trace_id": getattr(original_run, "trace_id", None),
                    "run_key": headers.get("run_key"),
                }
            )
        return response

    @staticmethod
    def cancel_task(task_id: str, terminate: bool = False) -> None:
        celery_app.control.revoke(task_id, terminate=terminate)
        logger.info(f"Task cancelled: {task_id} terminate={terminate}")

    @staticmethod
    def get_active_tasks() -> list[dict]:
        inspect = celery_app.control.inspect()
        active = inspect.active()
        if not active:
            return []

        tasks = []
        for worker_name, worker_tasks in active.items():
            for task in worker_tasks:
                tasks.append(
                    {
                        "task_id": task.get("id", ""),
                        "task_name": task.get("name", ""),
                        "worker": worker_name,
                        "started_at": task.get("time_start"),
                    }
                )
        return tasks

    @staticmethod
    def get_scheduled_tasks() -> list[dict]:
        inspect = celery_app.control.inspect()
        scheduled = inspect.scheduled()
        if not scheduled:
            return []

        tasks = []
        for worker_name, worker_tasks in scheduled.items():
            for task in worker_tasks:
                req = task.get("request", {})
                tasks.append(
                    {
                        "task_id": req.get("id", ""),
                        "task_name": req.get("name", ""),
                        "worker": worker_name,
                        "eta": task.get("eta"),
                    }
                )
        return tasks
