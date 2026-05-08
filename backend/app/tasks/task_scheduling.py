"""
Task scheduling wrapper tasks / 新任务调度包装任务

Bridges task definitions / tenant bindings to real Celery handlers while
attaching task-run metadata to the dispatched task.
将任务定义 / 企业绑定桥接到真实 Celery handler，并为真实任务附加 task_run 元数据。
"""

from __future__ import annotations

import importlib
import inspect
from typing import Any

from app.celery_app import celery_app
from app.core.base_model import utc_now
from app.core.database import sync_session_factory
from app.core.logging import LogManager
from app.enums.task import TaskRunKindEnum, TaskTriggerSourceEnum
from app.middleware.trace import trace_id_var
from app.models.system.task_definition import TaskDefinition
from app.models.system.tenant_task_binding import TenantTaskBinding
from app.services.system.task_tenant_eligibility_service import (
    TaskTenantEligibilityService,
)
from app.tasks.base import BaseTask, get_task_registry, register_task

logger = LogManager.get_logger("queue")

ALL_TENANTS_TASK_DEFINITION_WRAPPER = (
    "app.tasks.task_scheduling.run_all_tenants_task_definition"
)
TASK_DEFINITION_WRAPPER = "app.tasks.task_scheduling.run_task_definition"
TENANT_BINDING_WRAPPER = "app.tasks.task_scheduling.run_tenant_task_binding"


def _merge_kwargs(
    base_kwargs: dict[str, Any] | None,
    override_kwargs: dict[str, Any] | None,
) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    if base_kwargs:
        merged.update(base_kwargs)
    if override_kwargs:
        merged.update(override_kwargs)
    return merged


def find_invalid_handler_kwargs(
    handler_path: str,
    kwargs: dict[str, Any] | None,
) -> list[str]:
    if not kwargs:
        return []
    task = get_registered_handler_task(handler_path)
    if task is None:
        return []
    try:
        signature = inspect.signature(task.run)
    except (TypeError, ValueError):
        return []
    parameters = signature.parameters
    if any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    ):
        return []
    accepted = {
        name
        for name, parameter in parameters.items()
        if name != "self"
        and parameter.kind
        in (
            inspect.Parameter.KEYWORD_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    }
    return sorted(str(key) for key in kwargs if str(key) not in accepted)


def get_registered_handler_task(handler_path: str):
    task = celery_app.tasks.get(handler_path)
    if task is None and "." in handler_path:
        module_path = handler_path.rsplit(".", 1)[0]
        try:
            importlib.import_module(module_path)
        except Exception:
            return None
        task = celery_app.tasks.get(handler_path)
    return task


def is_handler_registered(handler_path: str | None) -> bool:
    if not handler_path:
        return False
    return get_registered_handler_task(handler_path) is not None


def _resolve_args(
    base_args: dict[str, Any] | list[Any] | None,
    override_args: dict[str, Any] | list[Any] | None,
) -> list[Any]:
    raw_args = override_args if override_args is not None else base_args
    if raw_args is None:
        return []
    if isinstance(raw_args, list):
        return list(raw_args)
    if isinstance(raw_args, tuple):
        return list(raw_args)
    if isinstance(raw_args, dict):
        return list(raw_args.values())
    return [raw_args]


def _build_task_run_headers(
    *,
    definition: TaskDefinition,
    binding: TenantTaskBinding | None,
    trigger_source: str,
    run_kind: str,
    effective_tenant_id: int | None,
    trigger_id: str | None = None,
    trigger_slot: str | None = None,
) -> dict[str, Any]:
    headers = {
        "task_definition_id": definition.id,
        "binding_id": binding.id if binding else None,
        "task_code_snapshot": definition.code,
        "task_name_snapshot": definition.name,
        "handler_path_snapshot": definition.handler_path,
        "trigger_source": trigger_source,
        "run_kind": run_kind,
        "owner_tenant_id": definition.owner_tenant_id,
        "effective_tenant_id": effective_tenant_id,
    }
    trace_id = trace_id_var.get()
    if trace_id:
        headers["trace_id"] = trace_id
    if trigger_id:
        headers["trigger_id"] = trigger_id
    if trigger_slot:
        headers["trigger_slot"] = trigger_slot
    return headers


def _resolve_trigger_slot(
    *,
    definition: TaskDefinition,
    binding: TenantTaskBinding | None,
    trigger_source: str,
) -> str | None:
    if trigger_source != TaskTriggerSourceEnum.SCHEDULER.value:
        return None
    schedule_type = getattr(definition, "default_schedule_type", None)
    interval_seconds = getattr(definition, "default_interval_seconds", None)
    cron_expression = getattr(definition, "default_cron_expression", None)
    if binding:
        schedule_type = (
            getattr(binding, "schedule_type_override", None) or schedule_type
        )
        interval_seconds = (
            getattr(binding, "interval_seconds_override", None)
            if getattr(binding, "interval_seconds_override", None) is not None
            else interval_seconds
        )
        cron_expression = (
            getattr(binding, "cron_expression_override", None) or cron_expression
        )
    now = utc_now()
    if schedule_type == "interval" and interval_seconds:
        slot = int(now.timestamp()) // int(interval_seconds)
        return f"interval:{interval_seconds}:{slot}"
    if schedule_type == "cron" and cron_expression:
        return f"cron:{cron_expression}:{now.strftime('%Y%m%dT%H%M')}"
    return f"scheduler:{now.strftime('%Y%m%dT%H%M')}"


def _get_current_request_id(task: BaseTask) -> str | None:
    request_id = getattr(getattr(task, "request", None), "id", None)
    return str(request_id) if request_id else None


def _resolve_queue(definition: TaskDefinition) -> str:
    registry_info = get_task_registry().get(definition.handler_path, {})
    return str(definition.default_queue or registry_info.get("queue") or "scheduled")


def _resolve_priority(definition: TaskDefinition) -> int | None:
    priority = getattr(definition, "default_priority", None)
    if priority is None:
        return None
    return int(priority)


def _build_handler_options(
    definition: TaskDefinition,
    *,
    headers: dict[str, Any],
) -> dict[str, Any]:
    options: dict[str, Any] = {
        "queue": _resolve_queue(definition),
        "headers": headers,
    }
    priority = _resolve_priority(definition)
    if priority is not None:
        options["priority"] = priority
    return options


def handler_supports_tenant_dispatch(handler_path: str) -> bool:
    get_registered_handler_task(handler_path)
    registry_info = get_task_registry().get(handler_path, {})
    return registry_info.get("base") == "TenantTask"


def _handler_requires_tenant(definition: TaskDefinition) -> bool:
    return handler_supports_tenant_dispatch(definition.handler_path)


def resolve_handler_kwargs(
    handler_path: str,
    base_kwargs: dict[str, Any] | None,
    override_kwargs: dict[str, Any] | None = None,
    *,
    tenant_id: int | None = None,
) -> dict[str, Any]:
    kwargs = _merge_kwargs(base_kwargs, override_kwargs)
    if tenant_id is not None and handler_supports_tenant_dispatch(handler_path):
        kwargs["tenant_id"] = tenant_id
    return kwargs


def _resolve_all_tenant_ids(session, task_definition_id: int) -> list[int]:
    return TaskTenantEligibilityService.resolve_all_tenant_ids_sync(
        session,
        task_definition_id=task_definition_id,
    )


@register_task(
    queue="scheduled",
    description="Dispatch platform task definition / 分发平台任务定义",
    max_retries=1,
)
def run_task_definition(
    self: BaseTask,
    task_definition_id: int,
    trigger_source: str = TaskTriggerSourceEnum.SCHEDULER.value,
) -> dict:
    session = None
    try:
        session = sync_session_factory()
        definition = (
            session.query(TaskDefinition)
            .filter(
                TaskDefinition.id == task_definition_id,
                TaskDefinition.is_deleted.is_(False),
            )
            .first()
        )
        if not definition or not definition.is_enabled:
            return {
                "dispatched": False,
                "reason": "definition_not_available",
                "task_definition_id": task_definition_id,
            }
        if not is_handler_registered(definition.handler_path):
            return {
                "dispatched": False,
                "reason": "handler_not_registered",
                "task_definition_id": task_definition_id,
                "handler_path": definition.handler_path,
            }

        args = _resolve_args(definition.default_args, None)
        kwargs = resolve_handler_kwargs(
            definition.handler_path,
            definition.default_kwargs,
        )
        invalid_kwargs = find_invalid_handler_kwargs(definition.handler_path, kwargs)
        if invalid_kwargs:
            return {
                "dispatched": False,
                "reason": "handler_kwargs_invalid",
                "task_definition_id": task_definition_id,
                "handler_path": definition.handler_path,
                "invalid_kwargs": invalid_kwargs,
            }
        headers = _build_task_run_headers(
            definition=definition,
            binding=None,
            trigger_source=trigger_source,
            run_kind=TaskRunKindEnum.PLATFORM.value,
            effective_tenant_id=None,
            trigger_id=_get_current_request_id(self),
            trigger_slot=_resolve_trigger_slot(
                definition=definition,
                binding=None,
                trigger_source=trigger_source,
            ),
        )

        result = celery_app.send_task(
            definition.handler_path,
            args=args,
            kwargs=kwargs,
            **_build_handler_options(definition, headers=headers),
        )
        logger.info(
            "Dispatched task definition {} -> {}",
            definition.code,
            result.id,
        )
        return {
            "dispatched": True,
            "task_definition_id": definition.id,
            "handler_path": definition.handler_path,
            "dispatched_task_id": result.id,
        }
    finally:
        if session:
            session.close()


@register_task(
    queue="scheduled",
    description="Dispatch all-tenant task definition / 分发全企业任务定义",
    max_retries=1,
)
def run_all_tenants_task_definition(
    self: BaseTask,
    task_definition_id: int,
    trigger_source: str = TaskTriggerSourceEnum.SCHEDULER.value,
) -> dict:
    session = None
    try:
        session = sync_session_factory()
        definition = (
            session.query(TaskDefinition)
            .filter(
                TaskDefinition.id == task_definition_id,
                TaskDefinition.is_deleted.is_(False),
            )
            .first()
        )
        if not definition or not definition.is_enabled:
            return {
                "dispatched": False,
                "reason": "definition_not_available",
                "task_definition_id": task_definition_id,
            }
        if not is_handler_registered(definition.handler_path):
            return {
                "dispatched": False,
                "reason": "handler_not_registered",
                "task_definition_id": task_definition_id,
                "handler_path": definition.handler_path,
            }
        if not handler_supports_tenant_dispatch(definition.handler_path):
            return {
                "dispatched": False,
                "reason": "tenant_dispatch_unsupported",
                "task_definition_id": task_definition_id,
                "handler_path": definition.handler_path,
            }

        tenant_ids = _resolve_all_tenant_ids(session, definition.id)
        dispatched_task_ids: list[str] = []
        dispatch_results: list[dict[str, Any]] = []

        for tenant_id in tenant_ids:
            args = _resolve_args(definition.default_args, None)
            kwargs = resolve_handler_kwargs(
                definition.handler_path,
                definition.default_kwargs,
                tenant_id=tenant_id,
            )
            invalid_kwargs = find_invalid_handler_kwargs(
                definition.handler_path, kwargs
            )
            if invalid_kwargs:
                dispatch_results.append(
                    {
                        "tenant_id": tenant_id,
                        "dispatched": False,
                        "reason": "handler_kwargs_invalid",
                        "invalid_kwargs": invalid_kwargs,
                    }
                )
                continue

            headers = _build_task_run_headers(
                definition=definition,
                binding=None,
                trigger_source=trigger_source,
                run_kind=TaskRunKindEnum.TENANT_BINDING.value,
                effective_tenant_id=tenant_id,
                trigger_id=_get_current_request_id(self),
                trigger_slot=_resolve_trigger_slot(
                    definition=definition,
                    binding=None,
                    trigger_source=trigger_source,
                ),
            )

            try:
                result = celery_app.send_task(
                    definition.handler_path,
                    args=args,
                    kwargs=kwargs,
                    **_build_handler_options(definition, headers=headers),
                )
                dispatched_task_id = str(result.id)
                dispatched_task_ids.append(dispatched_task_id)
                dispatch_results.append(
                    {
                        "tenant_id": tenant_id,
                        "dispatched": True,
                        "task_id": dispatched_task_id,
                    }
                )
            except Exception as exc:
                logger.error(
                    "Failed to dispatch all-tenant task definition {} tenant={} error={}",
                    definition.code,
                    tenant_id,
                    str(exc),
                )
                dispatch_results.append(
                    {
                        "tenant_id": tenant_id,
                        "dispatched": False,
                        "error": str(exc)[:500],
                    }
                )
                continue

        logger.info(
            "Dispatched all-tenant task definition {} -> {} tenant task(s)",
            definition.code,
            len(dispatched_task_ids),
        )
        return {
            "dispatched": True,
            "task_definition_id": definition.id,
            "handler_path": definition.handler_path,
            "tenant_count": len(tenant_ids),
            "dispatched_count": len(dispatched_task_ids),
            "failed_count": len(tenant_ids) - len(dispatched_task_ids),
            "dispatched_task_ids": dispatched_task_ids,
            "dispatch_results": dispatch_results,
        }
    finally:
        if session:
            session.close()


@register_task(
    queue="scheduled",
    description="Dispatch tenant task binding / 分发企业任务绑定",
    max_retries=1,
)
def run_tenant_task_binding(
    self: BaseTask,
    binding_id: int,
    trigger_source: str = TaskTriggerSourceEnum.SCHEDULER.value,
) -> dict:
    session = None
    try:
        session = sync_session_factory()
        binding = (
            session.query(TenantTaskBinding)
            .filter(
                TenantTaskBinding.id == binding_id,
                TenantTaskBinding.is_deleted.is_(False),
            )
            .first()
        )
        if not binding or not binding.is_enabled:
            return {
                "dispatched": False,
                "reason": "binding_not_available",
                "binding_id": binding_id,
            }
        eligibility = TaskTenantEligibilityService.resolve_tenant_eligibility_sync(
            session,
            binding.tenant_id,
        )
        if not eligibility.is_eligible:
            return {
                "dispatched": False,
                "reason": eligibility.reason,
                "binding_id": binding_id,
                "tenant_id": binding.tenant_id,
            }

        definition = (
            session.query(TaskDefinition)
            .filter(
                TaskDefinition.id == binding.task_definition_id,
                TaskDefinition.is_deleted.is_(False),
            )
            .first()
        )
        if not definition or not definition.is_enabled:
            return {
                "dispatched": False,
                "reason": "definition_not_available",
                "binding_id": binding_id,
                "task_definition_id": binding.task_definition_id,
            }
        if not is_handler_registered(definition.handler_path):
            return {
                "dispatched": False,
                "reason": "handler_not_registered",
                "binding_id": binding_id,
                "task_definition_id": binding.task_definition_id,
                "handler_path": definition.handler_path,
            }
        if not handler_supports_tenant_dispatch(definition.handler_path):
            return {
                "dispatched": False,
                "reason": "tenant_dispatch_unsupported",
                "binding_id": binding_id,
                "task_definition_id": binding.task_definition_id,
                "handler_path": definition.handler_path,
            }

        args = _resolve_args(definition.default_args, binding.args_override)
        kwargs = resolve_handler_kwargs(
            definition.handler_path,
            definition.default_kwargs,
            binding.kwargs_override,
            tenant_id=binding.tenant_id,
        )
        invalid_kwargs = find_invalid_handler_kwargs(definition.handler_path, kwargs)
        if invalid_kwargs:
            return {
                "dispatched": False,
                "reason": "handler_kwargs_invalid",
                "binding_id": binding_id,
                "task_definition_id": definition.id,
                "handler_path": definition.handler_path,
                "invalid_kwargs": invalid_kwargs,
            }

        headers = _build_task_run_headers(
            definition=definition,
            binding=binding,
            trigger_source=trigger_source,
            run_kind=TaskRunKindEnum.TENANT_BINDING.value,
            effective_tenant_id=binding.tenant_id,
            trigger_id=_get_current_request_id(self),
            trigger_slot=_resolve_trigger_slot(
                definition=definition,
                binding=binding,
                trigger_source=trigger_source,
            ),
        )

        result = celery_app.send_task(
            definition.handler_path,
            args=args,
            kwargs=kwargs,
            **_build_handler_options(definition, headers=headers),
        )
        logger.info(
            "Dispatched tenant task binding {} (tenant={}) -> {}",
            binding.id,
            binding.tenant_id,
            result.id,
        )
        return {
            "dispatched": True,
            "binding_id": binding.id,
            "task_definition_id": definition.id,
            "tenant_id": binding.tenant_id,
            "handler_path": definition.handler_path,
            "dispatched_task_id": result.id,
        }
    finally:
        if session:
            session.close()


__all__ = [
    "ALL_TENANTS_TASK_DEFINITION_WRAPPER",
    "TASK_DEFINITION_WRAPPER",
    "TENANT_BINDING_WRAPPER",
    "find_invalid_handler_kwargs",
    "handler_supports_tenant_dispatch",
    "is_handler_registered",
    "resolve_handler_kwargs",
    "run_all_tenants_task_definition",
    "run_task_definition",
    "run_tenant_task_binding",
]
