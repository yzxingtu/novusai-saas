"""
Task scheduling wrapper tasks / 新任务调度包装任务

Bridges task definitions / tenant bindings to real Celery handlers while
attaching task-run metadata to the dispatched task.
将任务定义 / 企业绑定桥接到真实 Celery handler，并为真实任务附加 task_run 元数据。
"""

from __future__ import annotations

from typing import Any

from app.celery_app import celery_app
from app.core.database import sync_session_factory
from app.core.logging import LogManager
from app.enums.task import TaskRunKindEnum, TaskTriggerSourceEnum
from app.models.system.task_definition import TaskDefinition
from app.models.system.tenant_task_binding import TenantTaskBinding
from app.models.tenant.tenant import Tenant
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
) -> dict[str, Any]:
    return {
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


def _resolve_queue(definition: TaskDefinition) -> str:
    registry_info = get_task_registry().get(definition.handler_path, {})
    return str(definition.default_queue or registry_info.get("queue") or "scheduled")


def handler_supports_tenant_dispatch(handler_path: str) -> bool:
    registry_info = get_task_registry().get(handler_path, {})
    return registry_info.get("base") == "TenantTask"


def _handler_requires_tenant(definition: TaskDefinition) -> bool:
    return handler_supports_tenant_dispatch(definition.handler_path)


def _resolve_all_tenant_ids(session) -> list[int]:
    rows = (
        session.query(Tenant.id)
        .filter(Tenant.is_deleted.is_(False))
        .order_by(Tenant.id.asc())
        .all()
    )
    return [tenant_id for (tenant_id,) in rows]


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

        args = _resolve_args(definition.default_args, None)
        kwargs = _merge_kwargs(definition.default_kwargs, None)
        headers = _build_task_run_headers(
            definition=definition,
            binding=None,
            trigger_source=trigger_source,
            run_kind=TaskRunKindEnum.PLATFORM.value,
            effective_tenant_id=None,
        )

        result = celery_app.send_task(
            definition.handler_path,
            args=args,
            kwargs=kwargs,
            queue=_resolve_queue(definition),
            headers=headers,
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
        if not handler_supports_tenant_dispatch(definition.handler_path):
            return {
                "dispatched": False,
                "reason": "tenant_dispatch_unsupported",
                "task_definition_id": task_definition_id,
                "handler_path": definition.handler_path,
            }

        tenant_ids = _resolve_all_tenant_ids(session)
        dispatched_task_ids: list[str] = []

        for tenant_id in tenant_ids:
            args = _resolve_args(definition.default_args, None)
            kwargs = _merge_kwargs(definition.default_kwargs, None)
            if _handler_requires_tenant(definition):
                kwargs.setdefault("tenant_id", tenant_id)

            headers = _build_task_run_headers(
                definition=definition,
                binding=None,
                trigger_source=trigger_source,
                run_kind=TaskRunKindEnum.TENANT_BINDING.value,
                effective_tenant_id=tenant_id,
            )

            result = celery_app.send_task(
                definition.handler_path,
                args=args,
                kwargs=kwargs,
                queue=_resolve_queue(definition),
                headers=headers,
            )
            dispatched_task_ids.append(str(result.id))

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
            "dispatched_task_ids": dispatched_task_ids,
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
        tenant = (
            session.query(Tenant)
            .filter(
                Tenant.id == binding.tenant_id,
                Tenant.is_deleted.is_(False),
            )
            .first()
        )
        if tenant is None:
            return {
                "dispatched": False,
                "reason": "tenant_not_available",
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
        if not handler_supports_tenant_dispatch(definition.handler_path):
            return {
                "dispatched": False,
                "reason": "tenant_dispatch_unsupported",
                "binding_id": binding_id,
                "task_definition_id": binding.task_definition_id,
                "handler_path": definition.handler_path,
            }

        args = _resolve_args(definition.default_args, binding.args_override)
        kwargs = _merge_kwargs(definition.default_kwargs, binding.kwargs_override)
        if _handler_requires_tenant(definition):
            kwargs.setdefault("tenant_id", binding.tenant_id)

        headers = _build_task_run_headers(
            definition=definition,
            binding=binding,
            trigger_source=trigger_source,
            run_kind=TaskRunKindEnum.TENANT_BINDING.value,
            effective_tenant_id=binding.tenant_id,
        )

        result = celery_app.send_task(
            definition.handler_path,
            args=args,
            kwargs=kwargs,
            queue=_resolve_queue(definition),
            headers=headers,
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
    "handler_supports_tenant_dispatch",
    "run_all_tenants_task_definition",
    "run_task_definition",
    "run_tenant_task_binding",
]
