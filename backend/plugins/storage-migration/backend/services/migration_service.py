"""Storage Migration Service.

Core migration contract facade for storage migration tasks.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, text, update

from app.core.base_model import utc_now
from app.core.logging import LogManager
from app.models.tenant.attachment import Attachment
from app.services.common.storage_config_resolver import StorageConfigResolver
from app.storage.base import StorageConfig
from app.storage.manager import storage_manager

from . import migration_runtime_registry as runtime_registry
from .migration_helpers import (
    deserialize_json_field,
    execute_single_file_migration,
    json_dumps,
    normalize_scope,
    scopes_overlap,
)
from .migration_impact_analyzer import MigrationImpactAnalyzer
from .migration_service_recovery import (
    cleanup_source_files as cleanup_source_files_part,
)
from .migration_service_recovery import retry_failed as retry_failed_part
from .migration_service_recovery import rollback_task as rollback_task_part
from .migration_service_runner import cancel_task as cancel_task_part
from .migration_service_runner import pause_task as pause_task_part
from .migration_service_runner import resume_task as resume_task_part
from .migration_service_runner import run_migration as run_migration_part
from .migration_service_runner import start_task as start_task_part
from .migration_service_transfer import create_task as create_task_part
from .migration_service_transfer import (
    migrate_single_file as migrate_single_file_part,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


__all__ = ["MigrationImpactAnalyzer", "StorageMigrationService"]

logger = LogManager.get_logger("storage")

ACTIVE_TASK_STATUSES = ("pending", "running", "paused", "rolling_back")
TASK_JSON_FIELDS = ("source_config_snapshot", "target_config_snapshot")
LOG_JSON_FIELDS = ("old_meta",)

_UNSET = object()


class StorageMigrationService:
    """Orchestrate file migration between storage drivers."""

    TASK_TABLE = "px_storage_migration_tasks"
    LOG_TABLE = "px_storage_migration_logs"

    def __init__(self, db: AsyncSession):
        self._db = db

    def _normalize_task_row(self, row: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(row)
        for field in TASK_JSON_FIELDS:
            normalized[field] = deserialize_json_field(normalized.get(field))
        normalized["scope"] = normalize_scope(str(normalized.get("scope") or "all"))
        normalized["source_cleanup_deleted_files"] = int(
            normalized.get("source_cleanup_deleted_files") or 0
        )
        normalized["source_cleanup_error_count"] = int(
            normalized.get("source_cleanup_error_count") or 0
        )
        return normalized

    def _normalize_log_row(self, row: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(row)
        for field in LOG_JSON_FIELDS:
            normalized[field] = deserialize_json_field(normalized.get(field))
        return normalized

    async def create_task(
        self,
        source_driver: str,
        target_driver: str,
        scope: str,
        concurrency: int,
        created_by: int,
    ) -> dict[str, Any]:
        return await create_task_part(
            self,
            source_driver=source_driver,
            target_driver=target_driver,
            scope=scope,
            concurrency=concurrency,
            created_by=created_by,
            normalize_scope=normalize_scope,
            storage_manager=storage_manager,
            storage_config_resolver_cls=StorageConfigResolver,
            attachment_model=Attachment,
            select=select,
            func=func,
            text=text,
            json_dumps=json_dumps,
            utc_now=utc_now,
        )

    async def get_task(self, task_id: int) -> dict[str, Any] | None:
        query = text(f"SELECT * FROM {self.TASK_TABLE} WHERE id = :id")
        result = await self._db.execute(query, {"id": task_id})
        row = result.mappings().one_or_none()
        if not row:
            return None
        return self._normalize_task_row(dict(row))

    async def list_tasks(
        self,
        page: int = 1,
        page_size: int = 20,
        status_filter: str | None = None,
    ) -> dict[str, Any]:
        offset = (page - 1) * page_size
        params: dict[str, Any] = {"limit": page_size, "offset": offset}
        where_clause = ""

        if status_filter:
            where_clause = "WHERE status = :status"
            params["status"] = status_filter

        count_query = text(f"SELECT count(*) FROM {self.TASK_TABLE} {where_clause}")
        count_result = await self._db.execute(count_query, params)
        total = count_result.scalar_one()

        query = text(
            f"""
            SELECT * FROM {self.TASK_TABLE}
            {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
            """
        )
        result = await self._db.execute(query, params)

        return {
            "items": [
                self._normalize_task_row(dict(row)) for row in result.mappings().all()
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_task_logs(
        self,
        task_id: int,
        status_filter: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        offset = (page - 1) * page_size
        params: dict[str, Any] = {
            "task_id": task_id,
            "limit": page_size,
            "offset": offset,
        }
        where_clause = "WHERE task_id = :task_id"

        if status_filter:
            where_clause += " AND status = :status"
            params["status"] = status_filter

        count_query = text(f"SELECT count(*) FROM {self.LOG_TABLE} {where_clause}")
        count_result = await self._db.execute(count_query, params)
        total = count_result.scalar_one()

        query = text(
            f"""
            SELECT * FROM {self.LOG_TABLE}
            {where_clause}
            ORDER BY id
            LIMIT :limit OFFSET :offset
            """
        )
        result = await self._db.execute(query, params)

        return {
            "items": [
                self._normalize_log_row(dict(row)) for row in result.mappings().all()
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def start_task(self, task_id: int) -> dict[str, Any]:
        return await start_task_part(
            self,
            task_id,
            utc_now=utc_now,
            asyncio_module=asyncio,
            activate_task=runtime_registry.activate_task,
            clear_cancelled=runtime_registry.clear_cancelled,
            register_background_task=runtime_registry.register_background_task,
        )

    async def pause_task(self, task_id: int) -> dict[str, Any]:
        return await pause_task_part(
            self,
            task_id,
            pause_runtime_task=runtime_registry.pause_task,
        )

    async def resume_task(self, task_id: int) -> dict[str, Any]:
        return await resume_task_part(
            self,
            task_id,
            asyncio_module=asyncio,
            activate_task=runtime_registry.activate_task,
            clear_cancelled=runtime_registry.clear_cancelled,
            has_background_task=runtime_registry.has_background_task,
            register_background_task=runtime_registry.register_background_task,
        )

    async def cancel_task(self, task_id: int) -> dict[str, Any]:
        return await cancel_task_part(
            self,
            task_id,
            mark_cancelled=runtime_registry.mark_cancelled,
            pop_background_task=runtime_registry.pop_background_task,
            clear_runtime=runtime_registry.clear_runtime,
        )

    async def retry_failed(self, task_id: int) -> dict[str, Any]:
        return await retry_failed_part(
            self,
            task_id,
            text=text,
        )

    async def rollback_task(self, task_id: int) -> dict[str, Any]:
        return await rollback_task_part(
            self,
            task_id,
            storage_manager=storage_manager,
            update=update,
            text=text,
            deserialize_json_field=deserialize_json_field,
            attachment_model=Attachment,
            logger=logger,
        )

    async def cleanup_source_files(self, task_id: int) -> dict[str, Any]:
        return await cleanup_source_files_part(
            self,
            task_id,
            storage_manager=storage_manager,
            text=text,
            utc_now=utc_now,
            logger=logger,
        )

    async def _run_migration(self, task_id: int) -> None:
        from app.core.database import async_session_factory

        await run_migration_part(
            self,
            task_id,
            service_factory=self.__class__,
            async_session_factory=async_session_factory,
            storage_manager=storage_manager,
            text=text,
            utc_now=utc_now,
            logger=logger,
            get_pause_event=runtime_registry.get_pause_event,
            is_cancelled=runtime_registry.is_cancelled,
            clear_runtime=runtime_registry.clear_runtime,
        )

    async def _migrate_single_file(
        self,
        db: AsyncSession,
        log_id: int,
        attachment_id: int,
        file_path: str,
        source_driver: object,
        target_driver: object,
        target_driver_name: str,
        target_base_url: str,
        target_storage_config: StorageConfig,
    ) -> bool:
        return await migrate_single_file_part(
            self,
            db=db,
            log_id=log_id,
            attachment_id=attachment_id,
            file_path=file_path,
            source_driver=source_driver,
            target_driver=target_driver,
            target_driver_name=target_driver_name,
            target_base_url=target_base_url,
            target_storage_config=target_storage_config,
            execute_single_file_migration=execute_single_file_migration,
            attachment_model=Attachment,
            utc_now=utc_now,
            logger=logger,
        )

    async def _update_task_status(
        self,
        task_id: int,
        status: str,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        error_message: object = _UNSET,
    ) -> None:
        set_parts = ["status = :status", "updated_at = now()"]
        params: dict[str, Any] = {"id": task_id, "status": status}

        if started_at is not None:
            set_parts.append("started_at = :started_at")
            params["started_at"] = started_at
        if completed_at is not None:
            set_parts.append("completed_at = :completed_at")
            params["completed_at"] = completed_at
        if error_message is not _UNSET:
            set_parts.append("error_message = :error_message")
            params["error_message"] = error_message

        query = text(
            f"UPDATE {self.TASK_TABLE} SET {', '.join(set_parts)} WHERE id = :id"
        )
        await self._db.execute(query, params)

    async def _find_conflicting_active_task(
        self,
        source_driver: str,
        target_driver: str,
        scope: str,
        exclude_task_id: int | None = None,
    ) -> dict[str, Any] | None:
        params: dict[str, Any] = {}
        query = f"""
            SELECT id, source_driver, target_driver, scope, status
            FROM {self.TASK_TABLE}
            WHERE status IN ('pending', 'running', 'paused', 'rolling_back')
        """
        if exclude_task_id is not None:
            query += " AND id != :exclude_task_id"
            params["exclude_task_id"] = exclude_task_id

        result = await self._db.execute(text(query), params)
        selected_drivers = {source_driver, target_driver}
        for row in result.mappings().all():
            current = dict(row)
            current_scope = normalize_scope(str(current.get("scope") or "all"))
            if not scopes_overlap(scope, current_scope):
                continue

            current_drivers = {
                str(current.get("source_driver") or ""),
                str(current.get("target_driver") or ""),
            }
            if selected_drivers & current_drivers:
                current["scope"] = current_scope
                return current
        return None

    @staticmethod
    async def _resolve_config_with_snapshot(
        db: AsyncSession,
        snapshot: Any,
        driver_name: str,
        scope: str,
    ) -> StorageConfig:
        resolved_snapshot = deserialize_json_field(snapshot)
        if (
            isinstance(resolved_snapshot, dict)
            and resolved_snapshot.get("driver") == driver_name
        ):
            return StorageConfig(
                driver=resolved_snapshot["driver"],
                root_path=resolved_snapshot.get("root_path", ""),
                base_url=resolved_snapshot.get("base_url"),
                options=resolved_snapshot.get("options", {}),
            )

        resolver = StorageConfigResolver(db)
        service = StorageMigrationService(db)
        return await service._resolve_driver_config(resolver, driver_name, scope)

    async def _resolve_driver_config(
        self,
        resolver: StorageConfigResolver,
        driver_name: str,
        scope: str,
    ) -> StorageConfig:
        normalized_scope = normalize_scope(scope)
        if normalized_scope.startswith("tenant:"):
            tenant_id = int(normalized_scope.split(":", 1)[1])
            config = await resolver.resolve_for_attachment(driver_name, tenant_id)
            if config.driver == driver_name:
                return config
            raise ValueError(
                f"Cannot resolve tenant config for driver '{driver_name}' "
                f"and scope '{normalized_scope}'."
            )

        config = await resolver.resolve_platform_config()
        if config.driver == driver_name:
            return config

        raise ValueError(
            f"Cannot resolve config for driver '{driver_name}'. "
            "Ensure the driver is configured in platform storage settings."
        )
