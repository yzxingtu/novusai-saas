"""
Celery 任务基类与装饰器

提供 BaseTask、TenantTask 基类和 @register_task 装饰器
"""

from __future__ import annotations

import time
from typing import Any, Callable

from celery import Task
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.core.config import settings
from app.core.database import sync_session_factory
from app.core.logging import LogManager

logger = LogManager.get_logger("queue")

_task_registry: dict[str, dict[str, Any]] = {}


def get_task_registry() -> dict[str, dict[str, Any]]:
    return _task_registry


class BaseTask(Task):
    """
    Celery 任务基类

    自动记录日志、处理重试和错误回调
    """

    abstract = True
    max_retries = 3
    default_retry_delay = 60
    _start_time: float | None = None

    def before_start(self, task_id: str, args: tuple, kwargs: dict) -> None:
        self._start_time = time.monotonic()
        logger.info(f"Task started: {self.name} [{task_id}]")

    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        elapsed = self._get_elapsed()
        logger.info(
            f"Task succeeded: {self.name} [{task_id}] "
            f"elapsed={elapsed:.2f}s"
        )

    def on_failure(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        elapsed = self._get_elapsed()
        logger.error(
            f"Task failed: {self.name} [{task_id}] "
            f"elapsed={elapsed:.2f}s error={exc!r}"
        )

    def on_retry(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        logger.warning(
            f"Task retrying: {self.name} [{task_id}] "
            f"retry={self.request.retries}/{self.max_retries} error={exc!r}"
        )

    def _get_elapsed(self) -> float:
        if self._start_time is not None:
            return time.monotonic() - self._start_time
        return 0.0

    def get_db_session(self) -> Session:
        return sync_session_factory()


class TenantTask(BaseTask):
    """
    租户隔离任务基类

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
    任务注册装饰器

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
