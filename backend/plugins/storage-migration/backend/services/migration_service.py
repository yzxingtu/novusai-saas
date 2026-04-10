"""Storage Migration Service.

Core migration logic: impact analysis, batch file transfer,
DB record updates, pause/resume, retry, rollback, and source cleanup safety.
"""

from __future__ import annotations

import asyncio
import importlib.util
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, text, update

from app.core.base_model import utc_now
from app.core.logging import LogManager
from app.models.tenant.attachment import Attachment
from app.services.common.storage_config_resolver import StorageConfigResolver
from app.storage.base import StorageConfig
from app.storage.manager import storage_manager

try:
    from .migration_helpers import (
        deserialize_json_field,
        execute_single_file_migration,
        json_dumps,
        normalize_scope,
        scopes_overlap,
    )
    from .migration_impact_analyzer import MigrationImpactAnalyzer
except ImportError:
    _services_dir = Path(__file__).resolve().parent

    def _load_local_service_module(module_name: str, file_name: str) -> Any:
        spec = importlib.util.spec_from_file_location(
            module_name,
            _services_dir / file_name,
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load {file_name}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    _helpers = _load_local_service_module(
        "storage_migration_runtime_helpers",
        "migration_helpers.py",
    )
    deserialize_json_field = _helpers.deserialize_json_field
    execute_single_file_migration = _helpers.execute_single_file_migration
    json_dumps = _helpers.json_dumps
    normalize_scope = _helpers.normalize_scope
    scopes_overlap = _helpers.scopes_overlap

    _impact_module = _load_local_service_module(
        "storage_migration_runtime_impact_analyzer",
        "migration_impact_analyzer.py",
    )
    MigrationImpactAnalyzer = _impact_module.MigrationImpactAnalyzer

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ["MigrationImpactAnalyzer", "StorageMigrationService"]

logger = LogManager.get_logger("storage")

ACTIVE_TASK_STATUSES = ("pending", "running", "paused", "rolling_back")
TASK_JSON_FIELDS = ("source_config_snapshot", "target_config_snapshot")
LOG_JSON_FIELDS = ("old_meta",)

_running_migrations: dict[int, asyncio.Task[None]] = {}
_pause_events: dict[int, asyncio.Event] = {}
_cancel_flags: set[int] = set()
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
        try:
            scope = normalize_scope(scope)
        except ValueError as exc:
            return {"error": str(exc)}

        if source_driver == target_driver:
            return {"error": "Source and target drivers must be different"}
        if not storage_manager.has_driver(source_driver):
            return {"error": f"Source driver '{source_driver}' is not available"}
        if not storage_manager.has_driver(target_driver):
            return {"error": f"Target driver '{target_driver}' is not available"}

        conflict = await self._find_conflicting_active_task(
            source_driver=source_driver,
            target_driver=target_driver,
            scope=scope,
        )
        if conflict:
            return {
                "error": (
                    "Another active migration task already touches the same driver scope: "
                    f"task #{conflict['id']} ({conflict['status']})"
                )
            }

        resolver = StorageConfigResolver(self._db)
        try:
            source_config = await self._resolve_driver_config(
                resolver,
                source_driver,
                scope,
            )
            target_config = await self._resolve_driver_config(
                resolver,
                target_driver,
                scope,
            )
        except Exception as exc:
            return {"error": str(exc)}

        conditions = [
            Attachment.driver == source_driver,
            Attachment.is_deleted.is_(False),
        ]
        if scope.startswith("tenant:"):
            tenant_id = int(scope.split(":", 1)[1])
            conditions.append(Attachment.tenant_id == tenant_id)

        count_q = select(
            func.count(Attachment.id),
            func.coalesce(func.sum(Attachment.size), 0),
        ).where(*conditions)
        count_result = await self._db.execute(count_q)
        total_files, total_bytes = count_result.one()

        if total_files == 0:
            return {"error": "No files found for the specified source driver and scope"}

        source_snapshot = {
            "driver": source_config.driver,
            "root_path": source_config.root_path,
            "base_url": source_config.base_url,
            "options": source_config.options,
        }
        target_snapshot = {
            "driver": target_config.driver,
            "root_path": target_config.root_path,
            "base_url": target_config.base_url,
            "options": target_config.options,
        }

        now = utc_now()
        insert_task = text(
            f"""
            INSERT INTO {self.TASK_TABLE}
            (
                source_driver,
                target_driver,
                status,
                scope,
                total_files,
                migrated_files,
                failed_files,
                skipped_files,
                total_bytes,
                migrated_bytes,
                concurrency,
                source_config_snapshot,
                target_config_snapshot,
                source_cleanup_deleted_files,
                source_cleanup_error_count,
                created_by,
                created_at,
                updated_at
            )
            VALUES
            (
                :source_driver,
                :target_driver,
                'pending',
                :scope,
                :total_files,
                0,
                0,
                0,
                :total_bytes,
                0,
                :concurrency,
                :source_snapshot,
                :target_snapshot,
                0,
                0,
                :created_by,
                :now,
                :now
            )
            RETURNING id
            """
        )
        result = await self._db.execute(
            insert_task,
            {
                "source_driver": source_driver,
                "target_driver": target_driver,
                "scope": scope,
                "total_files": total_files,
                "total_bytes": int(total_bytes),
                "concurrency": concurrency,
                "source_snapshot": json_dumps(source_snapshot),
                "target_snapshot": json_dumps(target_snapshot),
                "created_by": created_by,
                "now": now,
            },
        )
        task_id = result.scalar_one()

        batch_size = 1000
        insert_log = text(
            f"""
            INSERT INTO {self.LOG_TABLE}
            (
                task_id,
                attachment_id,
                file_path,
                file_size,
                status,
                old_driver,
                old_base_url,
                old_meta,
                created_at
            )
            VALUES
            (
                :task_id,
                :attachment_id,
                :file_path,
                :file_size,
                :status,
                :old_driver,
                :old_base_url,
                :old_meta,
                now()
            )
            """
        )

        offset = 0
        while True:
            batch_q = (
                select(
                    Attachment.id,
                    Attachment.path,
                    Attachment.size,
                    Attachment.driver,
                    Attachment.base_url,
                    Attachment.meta,
                )
                .where(*conditions)
                .order_by(Attachment.id)
                .limit(batch_size)
                .offset(offset)
            )
            batch_result = await self._db.execute(batch_q)
            rows = batch_result.all()
            if not rows:
                break

            await self._db.execute(
                insert_log,
                [
                    {
                        "task_id": task_id,
                        "attachment_id": row.id,
                        "file_path": row.path,
                        "file_size": row.size,
                        "status": "pending",
                        "old_driver": row.driver,
                        "old_base_url": row.base_url or "",
                        "old_meta": json_dumps(row.meta),
                    }
                    for row in rows
                ],
            )

            offset += batch_size
            if len(rows) < batch_size:
                break

        await self._db.commit()

        return {
            "task_id": task_id,
            "total_files": total_files,
            "total_bytes": int(total_bytes),
            "status": "pending",
        }

    async def get_task(self, task_id: int) -> dict[str, Any] | None:
        q = text(f"SELECT * FROM {self.TASK_TABLE} WHERE id = :id")
        result = await self._db.execute(q, {"id": task_id})
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

        count_q = text(f"SELECT count(*) FROM {self.TASK_TABLE} {where_clause}")
        count_result = await self._db.execute(count_q, params)
        total = count_result.scalar_one()

        q = text(
            f"""
            SELECT * FROM {self.TASK_TABLE}
            {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
            """
        )
        result = await self._db.execute(q, params)

        return {
            "items": [self._normalize_task_row(dict(row)) for row in result.mappings().all()],
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
        params: dict[str, Any] = {"task_id": task_id, "limit": page_size, "offset": offset}
        where_clause = "WHERE task_id = :task_id"

        if status_filter:
            where_clause += " AND status = :status"
            params["status"] = status_filter

        count_q = text(f"SELECT count(*) FROM {self.LOG_TABLE} {where_clause}")
        count_result = await self._db.execute(count_q, params)
        total = count_result.scalar_one()

        q = text(
            f"""
            SELECT * FROM {self.LOG_TABLE}
            {where_clause}
            ORDER BY id
            LIMIT :limit OFFSET :offset
            """
        )
        result = await self._db.execute(q, params)

        return {
            "items": [self._normalize_log_row(dict(row)) for row in result.mappings().all()],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def start_task(self, task_id: int) -> dict[str, Any]:
        task = await self.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        if task["status"] not in ("pending", "paused"):
            return {"error": f"Cannot start task in '{task['status']}' status"}

        await self._update_task_status(
            task_id,
            "running",
            started_at=utc_now(),
            error_message=None,
        )
        await self._db.commit()

        event = asyncio.Event()
        event.set()
        _pause_events[task_id] = event
        _cancel_flags.discard(task_id)

        bg_task = asyncio.create_task(self._run_migration(task_id))
        _running_migrations[task_id] = bg_task
        return {"status": "running", "task_id": task_id}

    async def pause_task(self, task_id: int) -> dict[str, Any]:
        task = await self.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        if task["status"] != "running":
            return {"error": f"Cannot pause task in '{task['status']}' status"}

        event = _pause_events.get(task_id)
        if event:
            event.clear()

        await self._update_task_status(task_id, "paused")
        await self._db.commit()
        return {"status": "paused", "task_id": task_id}

    async def resume_task(self, task_id: int) -> dict[str, Any]:
        task = await self.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        if task["status"] != "paused":
            return {"error": f"Cannot resume task in '{task['status']}' status"}

        event = _pause_events.get(task_id)
        if event:
            event.set()

        await self._update_task_status(task_id, "running", error_message=None)
        await self._db.commit()

        if task_id not in _running_migrations:
            event = asyncio.Event()
            event.set()
            _pause_events[task_id] = event
            _cancel_flags.discard(task_id)

            bg_task = asyncio.create_task(self._run_migration(task_id))
            _running_migrations[task_id] = bg_task

        return {"status": "running", "task_id": task_id}

    async def cancel_task(self, task_id: int) -> dict[str, Any]:
        task = await self.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        if task["status"] not in ("running", "paused", "pending"):
            return {"error": f"Cannot cancel task in '{task['status']}' status"}

        _cancel_flags.add(task_id)
        event = _pause_events.get(task_id)
        if event:
            event.set()

        await self._update_task_status(task_id, "cancelled")
        await self._db.commit()

        bg = _running_migrations.pop(task_id, None)
        if bg and not bg.done():
            bg.cancel()

        _pause_events.pop(task_id, None)
        _cancel_flags.discard(task_id)
        return {"status": "cancelled", "task_id": task_id}

    async def retry_failed(self, task_id: int) -> dict[str, Any]:
        task = await self.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        if task["status"] not in ("completed", "failed"):
            return {"error": f"Cannot retry task in '{task['status']}' status"}

        reset_q = text(
            f"""
            UPDATE {self.LOG_TABLE}
            SET status = 'pending',
                error_message = NULL,
                migrated_at = NULL
            WHERE task_id = :task_id AND status = 'failed'
            """
        )
        result = await self._db.execute(reset_q, {"task_id": task_id})
        reset_count = result.rowcount
        if reset_count == 0:
            return {"error": "No failed files to retry"}

        await self._db.execute(
            text(
                f"""
                UPDATE {self.TASK_TABLE}
                SET failed_files = failed_files - :count,
                    status = 'pending',
                    error_message = NULL,
                    completed_at = NULL,
                    updated_at = now()
                WHERE id = :id
                """
            ),
            {"id": task_id, "count": reset_count},
        )
        await self._db.commit()

        return await self.start_task(task_id)

    async def rollback_task(self, task_id: int) -> dict[str, Any]:
        task = await self.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        if task["status"] not in ("completed", "failed"):
            return {"error": f"Cannot rollback task in '{task['status']}' status"}
        if (
            task.get("source_cleanup_started_at")
            or task.get("source_cleanup_completed_at")
            or task.get("source_cleanup_deleted_files", 0)
        ):
            return {
                "error": "Cannot rollback after source cleanup has started or completed"
            }

        conflict = await self._find_conflicting_active_task(
            source_driver=task["source_driver"],
            target_driver=task["target_driver"],
            scope=task["scope"],
            exclude_task_id=task_id,
        )
        if conflict:
            return {
                "error": (
                    "Cannot rollback while another active migration touches the same driver scope: "
                    f"task #{conflict['id']} ({conflict['status']})"
                )
            }

        await self._update_task_status(
            task_id,
            "rolling_back",
            error_message=None,
        )
        await self._db.commit()

        target_delete_errors = 0
        try:
            target_config = await self._resolve_config_with_snapshot(
                self._db,
                task.get("target_config_snapshot"),
                task["target_driver"],
                task["scope"],
            )
            target_storage = storage_manager.get_driver(target_config)

            paths_q = text(
                f"""
                SELECT file_path
                FROM {self.LOG_TABLE}
                WHERE task_id = :task_id AND status = 'success'
                """
            )
            paths_result = await self._db.execute(paths_q, {"task_id": task_id})
            for row in paths_result.mappings().all():
                try:
                    await target_storage.delete(row["file_path"])
                except Exception as exc:
                    logger.warning(
                        "Rollback: failed to delete target file %s: %s",
                        row["file_path"],
                        exc,
                    )
                    target_delete_errors += 1
        except Exception as exc:
            logger.warning("Rollback: cannot resolve target driver for cleanup: %s", exc)

        logs_q = text(
            f"""
            SELECT attachment_id, old_driver, old_base_url, old_meta
            FROM {self.LOG_TABLE}
            WHERE task_id = :task_id AND status = 'success'
            """
        )
        logs_result = await self._db.execute(logs_q, {"task_id": task_id})

        reverted = 0
        for log_row in logs_result.mappings().all():
            await self._db.execute(
                update(Attachment)
                .where(Attachment.id == log_row["attachment_id"])
                .values(
                    driver=log_row["old_driver"],
                    base_url=log_row["old_base_url"],
                    meta=deserialize_json_field(log_row["old_meta"]),
                )
            )
            reverted += 1

        await self._db.execute(
            text(
                f"""
                UPDATE {self.LOG_TABLE}
                SET status = 'pending',
                    new_driver = NULL,
                    new_base_url = NULL,
                    migrated_at = NULL,
                    error_message = NULL
                WHERE task_id = :task_id AND status = 'success'
                """
            ),
            {"task_id": task_id},
        )

        await self._db.execute(
            text(
                f"""
                UPDATE {self.TASK_TABLE}
                SET status = 'pending',
                    migrated_files = 0,
                    migrated_bytes = 0,
                    failed_files = 0,
                    skipped_files = 0,
                    started_at = NULL,
                    completed_at = NULL,
                    error_message = NULL,
                    updated_at = now()
                WHERE id = :id
                """
            ),
            {"id": task_id},
        )
        await self._db.commit()

        return {
            "status": "pending",
            "task_id": task_id,
            "reverted_files": reverted,
            "target_delete_errors": target_delete_errors,
        }

    async def cleanup_source_files(self, task_id: int) -> dict[str, Any]:
        task = await self.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        if task["status"] != "completed":
            return {"error": "Can only cleanup source files for completed tasks"}
        if task.get("source_cleanup_completed_at"):
            return {"error": "Source files were already cleaned up for this task"}

        try:
            source_config = await self._resolve_config_with_snapshot(
                self._db,
                task.get("source_config_snapshot"),
                task["source_driver"],
                task["scope"],
            )
        except Exception as exc:
            return {"error": f"Cannot resolve source config: {exc}"}

        source_driver = storage_manager.get_driver(source_config)
        started_at = utc_now()
        await self._db.execute(
            text(
                f"""
                UPDATE {self.TASK_TABLE}
                SET source_cleanup_started_at = :started_at,
                    updated_at = now()
                WHERE id = :id
                """
            ),
            {"id": task_id, "started_at": started_at},
        )

        logs_q = text(
            f"""
            SELECT file_path
            FROM {self.LOG_TABLE}
            WHERE task_id = :task_id AND status = 'success'
            """
        )
        logs_result = await self._db.execute(logs_q, {"task_id": task_id})

        deleted = 0
        errors = 0
        for row in logs_result.mappings().all():
            try:
                await source_driver.delete(row["file_path"])
                deleted += 1
            except Exception as exc:
                logger.warning("Failed to delete source file %s: %s", row["file_path"], exc)
                errors += 1

        completed_at = utc_now()
        await self._db.execute(
            text(
                f"""
                UPDATE {self.TASK_TABLE}
                SET source_cleanup_completed_at = :completed_at,
                    source_cleanup_deleted_files = :deleted_files,
                    source_cleanup_error_count = :error_count,
                    updated_at = now()
                WHERE id = :id
                """
            ),
            {
                "id": task_id,
                "completed_at": completed_at,
                "deleted_files": deleted,
                "error_count": errors,
            },
        )
        await self._db.commit()

        return {
            "task_id": task_id,
            "deleted_files": deleted,
            "errors": errors,
            "cleanup_completed_at": completed_at,
        }

    async def _run_migration(self, task_id: int) -> None:
        """Perform the actual file migration in a background coroutine."""
        from app.core.database import async_session_factory

        try:
            async with async_session_factory() as setup_db:
                svc = StorageMigrationService(setup_db)
                task = await svc.get_task(task_id)
                if not task:
                    return

                source_driver_name = task["source_driver"]
                target_driver_name = task["target_driver"]
                concurrency = task.get("concurrency", 5)

                source_config = await self._resolve_config_with_snapshot(
                    setup_db,
                    task.get("source_config_snapshot"),
                    source_driver_name,
                    task["scope"],
                )
                target_config = await self._resolve_config_with_snapshot(
                    setup_db,
                    task.get("target_config_snapshot"),
                    target_driver_name,
                    task["scope"],
                )

                source_storage = storage_manager.get_driver(source_config)
                target_storage = storage_manager.get_driver(target_config)
                target_base_url = target_storage.get_base_url()

            batch_size = 1000
            semaphore = asyncio.Semaphore(concurrency)
            counter_lock = asyncio.Lock()
            batch_counters: dict[str, int] = {}

            def reset_counters() -> None:
                batch_counters.clear()
                batch_counters.update(
                    migrated_files=0,
                    failed_files=0,
                    migrated_bytes=0,
                )

            async def migrate_one(log_entry: dict[str, Any]) -> None:
                async with semaphore:
                    event = _pause_events.get(task_id)
                    if event:
                        await event.wait()
                    if task_id in _cancel_flags:
                        return

                    async with async_session_factory() as file_db:
                        ok = await self._migrate_single_file(
                            db=file_db,
                            log_id=log_entry["id"],
                            attachment_id=log_entry["attachment_id"],
                            file_path=log_entry["file_path"],
                            source_driver=source_storage,
                            target_driver=target_storage,
                            target_driver_name=target_driver_name,
                            target_base_url=target_base_url,
                            target_storage_config=target_config,
                        )

                    async with counter_lock:
                        if ok:
                            batch_counters["migrated_files"] += 1
                            batch_counters["migrated_bytes"] += int(log_entry["file_size"] or 0)
                        else:
                            batch_counters["failed_files"] += 1

            while task_id not in _cancel_flags:
                async with async_session_factory() as batch_db:
                    pending_q = text(
                        f"""
                        SELECT id, attachment_id, file_path, file_size
                        FROM {self.LOG_TABLE}
                        WHERE task_id = :task_id AND status = 'pending'
                        ORDER BY id
                        LIMIT :limit
                        """
                    )
                    result = await batch_db.execute(
                        pending_q,
                        {"task_id": task_id, "limit": batch_size},
                    )
                    batch = [dict(row) for row in result.mappings().all()]

                if not batch:
                    break

                reset_counters()
                await asyncio.gather(*(migrate_one(log) for log in batch), return_exceptions=True)

                async with async_session_factory() as flush_db:
                    await flush_db.execute(
                        text(
                            f"""
                            UPDATE {self.TASK_TABLE}
                            SET migrated_files = migrated_files + :mf,
                                failed_files = failed_files + :ff,
                                migrated_bytes = migrated_bytes + :mb,
                                updated_at = now()
                            WHERE id = :task_id
                            """
                        ),
                        {
                            "task_id": task_id,
                            "mf": batch_counters["migrated_files"],
                            "ff": batch_counters["failed_files"],
                            "mb": batch_counters["migrated_bytes"],
                        },
                    )
                    await flush_db.commit()

            if task_id not in _cancel_flags:
                async with async_session_factory() as final_db:
                    final_svc = StorageMigrationService(final_db)
                    updated_task = await final_svc.get_task(task_id)
                    if updated_task and updated_task["status"] == "running":
                        final_status = "completed"
                        if updated_task["failed_files"] > 0 and updated_task["migrated_files"] == 0:
                            final_status = "failed"
                        await final_svc._update_task_status(
                            task_id,
                            final_status,
                            completed_at=utc_now(),
                        )
                        await final_db.commit()

        except asyncio.CancelledError:
            logger.info("Migration task %d cancelled", task_id)
        except Exception as exc:
            logger.error("Migration task %d failed: %s", task_id, exc, exc_info=True)
            try:
                async with async_session_factory() as err_db:
                    err_svc = StorageMigrationService(err_db)
                    await err_svc._update_task_status(
                        task_id,
                        "failed",
                        error_message=str(exc),
                    )
                    await err_db.commit()
            except Exception:
                pass
        finally:
            _running_migrations.pop(task_id, None)
            _pause_events.pop(task_id, None)
            _cancel_flags.discard(task_id)

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
        return await execute_single_file_migration(
            attachment_model=Attachment,
            db=db,
            file_path=file_path,
            log_id=log_id,
            log_table=self.LOG_TABLE,
            attachment_id=attachment_id,
            source_driver=source_driver,
            target_driver=target_driver,
            target_driver_name=target_driver_name,
            target_base_url=target_base_url,
            target_storage_config=target_storage_config,
            now_factory=utc_now,
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

        q = text(f"UPDATE {self.TASK_TABLE} SET {', '.join(set_parts)} WHERE id = :id")
        await self._db.execute(q, params)

    async def _find_conflicting_active_task(
        self,
        source_driver: str,
        target_driver: str,
        scope: str,
        exclude_task_id: int | None = None,
    ) -> dict[str, Any] | None:
        params: dict[str, Any] = {}
        q = (
            f"""
            SELECT id, source_driver, target_driver, scope, status
            FROM {self.TASK_TABLE}
            WHERE status IN ('pending', 'running', 'paused', 'rolling_back')
            """
        )
        if exclude_task_id is not None:
            q += " AND id != :exclude_task_id"
            params["exclude_task_id"] = exclude_task_id

        result = await self._db.execute(text(q), params)
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
        if isinstance(resolved_snapshot, dict) and resolved_snapshot.get("driver") == driver_name:
            return StorageConfig(
                driver=resolved_snapshot["driver"],
                root_path=resolved_snapshot.get("root_path", ""),
                base_url=resolved_snapshot.get("base_url"),
                options=resolved_snapshot.get("options", {}),
            )

        resolver = StorageConfigResolver(db)
        svc = StorageMigrationService(db)
        return await svc._resolve_driver_config(resolver, driver_name, scope)

    async def _resolve_driver_config(
        self,
        resolver: StorageConfigResolver,
        driver_name: str,
        scope: str,
    ) -> StorageConfig:
        scope = normalize_scope(scope)
        tenant_id = 0
        if scope.startswith("tenant:"):
            tenant_id = int(scope.split(":", 1)[1])

        try:
            return await resolver.resolve_for_attachment(driver_name, tenant_id)
        except Exception:
            pass

        config = await resolver.resolve_platform_config()
        if config.driver == driver_name:
            return config

        raise ValueError(
            f"Cannot resolve config for driver '{driver_name}'. "
            "Ensure the driver is configured in platform or tenant storage settings."
        )
