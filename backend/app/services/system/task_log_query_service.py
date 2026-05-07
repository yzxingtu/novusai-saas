"""Task-log read models used by admin controllers."""

from __future__ import annotations

from sqlalchemy import select

from app.models.system.task_definition import TaskDefinition
from app.models.tenant.tenant import Tenant
from app.schemas.system import TaskLogDetailResponse, TaskLogResponse


class TaskLogRelationService:
    """Resolve task definition and tenant display metadata for task logs."""

    def __init__(self, db):
        self._db = db

    async def build_maps(
        self,
        task_runs: list,
    ) -> tuple[dict[int, dict[str, str]], dict[int, str]]:
        definition_ids = sorted(
            {
                task_run.task_definition_id
                for task_run in task_runs
                if task_run.task_definition_id is not None
            }
        )
        tenant_ids = sorted(
            {
                tenant_id
                for task_run in task_runs
                for tenant_id in (
                    task_run.owner_tenant_id,
                    task_run.effective_tenant_id,
                )
                if tenant_id is not None
            }
        )

        definition_map: dict[int, dict[str, str]] = {}
        tenant_map: dict[int, str] = {}

        if definition_ids:
            result = await self._db.execute(
                select(
                    TaskDefinition.id, TaskDefinition.name, TaskDefinition.scope
                ).where(TaskDefinition.id.in_(definition_ids))
            )
            definition_map = {
                row.id: {"name": row.name, "scope": row.scope} for row in result.all()
            }

        if tenant_ids:
            result = await self._db.execute(
                select(Tenant.id, Tenant.name).where(Tenant.id.in_(tenant_ids))
            )
            tenant_map = {row.id: row.name for row in result.all()}

        return definition_map, tenant_map

    @staticmethod
    def unpack_args_kwargs(
        args_summary: object | None,
    ) -> tuple[list | None, dict | None]:
        args = None
        kwargs = None
        if isinstance(args_summary, dict):
            raw_args = args_summary.get("args")
            raw_kwargs = args_summary.get("kwargs")
            args = raw_args if isinstance(raw_args, list) else None
            kwargs = raw_kwargs if isinstance(raw_kwargs, dict) else None
        return args, kwargs

    def serialize_task_run(
        self,
        task_run,
        *,
        definition_map: dict[int, dict[str, str]] | None = None,
        tenant_map: dict[int, str] | None = None,
    ) -> dict:
        args, kwargs = self.unpack_args_kwargs(task_run.args_summary)
        definition_info = (
            definition_map.get(task_run.task_definition_id, {})
            if definition_map and task_run.task_definition_id is not None
            else {}
        )
        owner_tenant_name = (
            tenant_map.get(task_run.owner_tenant_id)
            if tenant_map and task_run.owner_tenant_id is not None
            else None
        )
        effective_tenant_name = (
            tenant_map.get(task_run.effective_tenant_id)
            if tenant_map and task_run.effective_tenant_id is not None
            else None
        )
        return TaskLogResponse(
            id=task_run.id,
            task_id=task_run.celery_task_id,
            run_key=task_run.run_key,
            task_name=task_run.task_name_snapshot,
            handler_path=task_run.handler_path_snapshot,
            task_definition_id=task_run.task_definition_id,
            binding_id=task_run.binding_id,
            task_definition_name=definition_info.get("name"),
            task_scope=definition_info.get("scope"),
            owner_tenant_id=task_run.owner_tenant_id,
            owner_tenant_name=owner_tenant_name,
            effective_tenant_id=task_run.effective_tenant_id,
            effective_tenant_name=effective_tenant_name,
            queue=task_run.queue,
            status=task_run.status,
            args=args,
            kwargs=kwargs,
            result=task_run.result_summary,
            error_message=task_run.error_message_public
            or task_run.error_message_internal,
            trigger_source=task_run.trigger_source,
            run_kind=task_run.run_kind,
            trace_id=task_run.trace_id,
            started_at=task_run.started_at,
            finished_at=task_run.finished_at,
            duration_ms=task_run.duration_ms,
            retry_count=task_run.retry_count,
            tenant_id=task_run.effective_tenant_id,
            created_at=task_run.created_at,
        ).model_dump()

    def serialize_task_run_detail(
        self,
        task_run,
        *,
        definition_map: dict[int, dict[str, str]] | None = None,
        tenant_map: dict[int, str] | None = None,
    ) -> dict:
        args, kwargs = self.unpack_args_kwargs(task_run.args_summary)
        definition_info = (
            definition_map.get(task_run.task_definition_id, {})
            if definition_map and task_run.task_definition_id is not None
            else {}
        )
        owner_tenant_name = (
            tenant_map.get(task_run.owner_tenant_id)
            if tenant_map and task_run.owner_tenant_id is not None
            else None
        )
        effective_tenant_name = (
            tenant_map.get(task_run.effective_tenant_id)
            if tenant_map and task_run.effective_tenant_id is not None
            else None
        )
        return TaskLogDetailResponse(
            id=task_run.id,
            task_id=task_run.celery_task_id,
            run_key=task_run.run_key,
            task_name=task_run.task_name_snapshot,
            handler_path=task_run.handler_path_snapshot,
            task_definition_id=task_run.task_definition_id,
            binding_id=task_run.binding_id,
            task_definition_name=definition_info.get("name"),
            task_scope=definition_info.get("scope"),
            owner_tenant_id=task_run.owner_tenant_id,
            owner_tenant_name=owner_tenant_name,
            effective_tenant_id=task_run.effective_tenant_id,
            effective_tenant_name=effective_tenant_name,
            queue=task_run.queue,
            status=task_run.status,
            args=args,
            kwargs=kwargs,
            result=task_run.result_summary,
            error_message=task_run.error_message_public
            or task_run.error_message_internal,
            trigger_source=task_run.trigger_source,
            run_kind=task_run.run_kind,
            trace_id=task_run.trace_id,
            started_at=task_run.started_at,
            finished_at=task_run.finished_at,
            duration_ms=task_run.duration_ms,
            retry_count=task_run.retry_count,
            tenant_id=task_run.effective_tenant_id,
            created_at=task_run.created_at,
            traceback=task_run.traceback_internal,
        ).model_dump()


__all__ = ["TaskLogRelationService"]
