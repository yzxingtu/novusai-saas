"""
Storage Migration Service

Core migration logic: impact analysis, batch file transfer,
DB record updates, pause/resume, retry, rollback.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING

from sqlalchemy import func, select, text, update

from app.core.base_model import utc_now
from app.core.logging import LogManager
from app.models.tenant.attachment import Attachment
from app.services.common.storage_config_resolver import StorageConfigResolver
from app.storage.base import StorageConfig, StorageVisibility
from app.storage.manager import storage_manager

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = LogManager.get_logger("storage")

# In-memory registry of running migration coroutines
_running_migrations: dict[int, asyncio.Task[None]] = {}
# Pause flags: task_id -> Event (cleared = paused, set = running)
_pause_events: dict[int, asyncio.Event] = {}
# Cancel flags
_cancel_flags: set[int] = set()


class MigrationImpactAnalyzer:
    """Analyze impact before switching storage driver"""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def analyze(
        self,
        source_driver: str,
        target_driver: str,
        scope: str = "all",
    ) -> dict:
        """
        Analyze impact of switching from source_driver to target_driver.

        Returns file counts, sizes, and visibility breakdown.
        """
        conditions = [Attachment.driver == source_driver, Attachment.is_deleted.is_(False)]

        if scope.startswith("tenant:"):
            tenant_id = int(scope.split(":")[1])
            conditions.append(Attachment.tenant_id == tenant_id)

        # Total stats
        total_q = select(
            func.count(Attachment.id).label("total_files"),
            func.coalesce(func.sum(Attachment.size), 0).label("total_size_bytes"),
        ).where(*conditions)
        total_result = await self._db.execute(total_q)
        total_row = total_result.one()

        # Visibility breakdown
        visibility_q = (
            select(
                Attachment.visibility,
                func.count(Attachment.id).label("count"),
                func.coalesce(func.sum(Attachment.size), 0).label("size_bytes"),
            )
            .where(*conditions)
            .group_by(Attachment.visibility)
        )
        visibility_result = await self._db.execute(visibility_q)
        visibility_rows = visibility_result.all()

        private_files = 0
        private_size = 0
        public_files = 0
        public_size = 0
        for row in visibility_rows:
            if row.visibility == StorageVisibility.PRIVATE:
                private_files = row.count
                private_size = row.size_bytes
            elif row.visibility == StorageVisibility.PUBLIC:
                public_files = row.count
                public_size = row.size_bytes

        # Tenant breakdown (for scope=all)
        tenant_breakdown = []
        if scope == "all":
            tenant_q = (
                select(
                    Attachment.tenant_id,
                    func.count(Attachment.id).label("count"),
                    func.coalesce(func.sum(Attachment.size), 0).label("size_bytes"),
                )
                .where(*conditions)
                .group_by(Attachment.tenant_id)
                .order_by(func.count(Attachment.id).desc())
                .limit(20)
            )
            tenant_result = await self._db.execute(tenant_q)
            for row in tenant_result.all():
                tenant_breakdown.append({
                    "tenant_id": row.tenant_id,
                    "file_count": row.count,
                    "size_bytes": int(row.size_bytes),
                })

        # Check if target driver is available
        target_available = storage_manager.has_driver(target_driver)
        source_available = storage_manager.has_driver(source_driver)

        return {
            "source_driver": source_driver,
            "target_driver": target_driver,
            "source_available": source_available,
            "target_available": target_available,
            "total_files": total_row.total_files,
            "total_size_bytes": int(total_row.total_size_bytes),
            "private_files": private_files,
            "private_size_bytes": int(private_size),
            "public_files": public_files,
            "public_size_bytes": int(public_size),
            "tenant_breakdown": tenant_breakdown,
            "scope": scope,
        }


class StorageMigrationService:
    """
    Orchestrates file migration between storage drivers.

    Uses raw AsyncSession to access both plugin tables (px_storage_migration_*)
    and main tables (attachments). This is acceptable because:
    - Plugin is admin_only scope
    - Migration requires cross-table access by design
    """

    TASK_TABLE = "px_storage_migration_tasks"
    LOG_TABLE = "px_storage_migration_logs"

    def __init__(self, db: AsyncSession):
        self._db = db

    # ── Task CRUD ──────────────────────────────────────────────

    async def create_task(
        self,
        source_driver: str,
        target_driver: str,
        scope: str,
        concurrency: int,
        created_by: int,
    ) -> dict:
        """Create a migration task and populate log entries for each file."""
        # Validate drivers
        if not storage_manager.has_driver(source_driver):
            return {"error": f"Source driver '{source_driver}' is not available"}
        if not storage_manager.has_driver(target_driver):
            return {"error": f"Target driver '{target_driver}' is not available"}
        if source_driver == target_driver:
            return {"error": "Source and target drivers must be different"}

        # Resolve storage configs
        resolver = StorageConfigResolver(self._db)
        try:
            source_config = await self._resolve_driver_config(resolver, source_driver, scope)
            target_config = await self._resolve_driver_config(resolver, target_driver, scope)
        except Exception as exc:
            return {"error": str(exc)}

        # Count files to migrate
        conditions = [Attachment.driver == source_driver, Attachment.is_deleted.is_(False)]
        if scope.startswith("tenant:"):
            tenant_id = int(scope.split(":")[1])
            conditions.append(Attachment.tenant_id == tenant_id)

        count_q = select(
            func.count(Attachment.id),
            func.coalesce(func.sum(Attachment.size), 0),
        ).where(*conditions)
        count_result = await self._db.execute(count_q)
        total_files, total_bytes = count_result.one()

        if total_files == 0:
            return {"error": "No files found for the specified source driver and scope"}

        # Save full config snapshots including options (credentials).
        # These are stored in the DB (admin-only access) and needed for
        # _resolve_config_with_snapshot to reconstruct working drivers
        # even if the live config changes mid-migration.
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

        # Insert task record
        now = utc_now()
        insert_task = text(f"""
            INSERT INTO {self.TASK_TABLE}
            (source_driver, target_driver, status, scope, total_files,
             migrated_files, failed_files, skipped_files, total_bytes,
             migrated_bytes, concurrency, source_config_snapshot,
             target_config_snapshot, created_by, created_at, updated_at)
            VALUES
            (:source_driver, :target_driver, 'pending', :scope, :total_files,
             0, 0, 0, :total_bytes, 0, :concurrency,
             :source_snapshot, :target_snapshot, :created_by, :now, :now)
            RETURNING id
        """)
        result = await self._db.execute(
            insert_task,
            {
                "source_driver": source_driver,
                "target_driver": target_driver,
                "scope": scope,
                "total_files": total_files,
                "total_bytes": int(total_bytes),
                "concurrency": concurrency,
                "source_snapshot": _json_dumps(source_snapshot),
                "target_snapshot": _json_dumps(target_snapshot),
                "created_by": created_by,
                "now": now,
            },
        )
        # asyncpg needs JSON as string; text() doesn't auto-serialize
        task_id = result.scalar_one()

        # Populate log entries in batches to avoid OOM on large file sets
        BATCH_SIZE = 1000
        insert_log = text(f"""
            INSERT INTO {self.LOG_TABLE}
            (task_id, attachment_id, file_path, file_size, status,
             old_driver, old_base_url, created_at)
            VALUES
            (:task_id, :attachment_id, :file_path, :file_size, :status,
             :old_driver, :old_base_url, now())
        """)
        offset = 0
        while True:
            batch_q = (
                select(Attachment.id, Attachment.path, Attachment.size,
                       Attachment.driver, Attachment.base_url)
                .where(*conditions)
                .order_by(Attachment.id)
                .limit(BATCH_SIZE)
                .offset(offset)
            )
            batch_result = await self._db.execute(batch_q)
            rows = batch_result.all()
            if not rows:
                break

            log_values = [
                {
                    "task_id": task_id,
                    "attachment_id": row.id,
                    "file_path": row.path,
                    "file_size": row.size,
                    "status": "pending",
                    "old_driver": row.driver,
                    "old_base_url": row.base_url or "",
                }
                for row in rows
            ]
            await self._db.execute(insert_log, log_values)
            offset += BATCH_SIZE
            if len(rows) < BATCH_SIZE:
                break

        await self._db.commit()

        return {
            "task_id": task_id,
            "total_files": total_files,
            "total_bytes": int(total_bytes),
            "status": "pending",
        }

    async def get_task(self, task_id: int) -> dict | None:
        """Get migration task detail."""
        q = text(f"SELECT * FROM {self.TASK_TABLE} WHERE id = :id")
        result = await self._db.execute(q, {"id": task_id})
        row = result.mappings().one_or_none()
        if not row:
            return None
        return dict(row)

    async def list_tasks(self, page: int = 1, page_size: int = 20) -> dict:
        """List migration tasks with pagination."""
        offset = (page - 1) * page_size

        count_q = text(f"SELECT count(*) FROM {self.TASK_TABLE}")
        count_result = await self._db.execute(count_q)
        total = count_result.scalar_one()

        q = text(f"""
            SELECT * FROM {self.TASK_TABLE}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """)
        result = await self._db.execute(q, {"limit": page_size, "offset": offset})
        rows = [dict(r) for r in result.mappings().all()]

        return {
            "items": rows,
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
    ) -> dict:
        """Get migration logs for a task."""
        offset = (page - 1) * page_size
        params: dict = {"task_id": task_id, "limit": page_size, "offset": offset}

        where_clause = "WHERE task_id = :task_id"
        if status_filter:
            where_clause += " AND status = :status"
            params["status"] = status_filter

        count_q = text(f"SELECT count(*) FROM {self.LOG_TABLE} {where_clause}")
        count_result = await self._db.execute(count_q, params)
        total = count_result.scalar_one()

        q = text(f"""
            SELECT * FROM {self.LOG_TABLE}
            {where_clause}
            ORDER BY id
            LIMIT :limit OFFSET :offset
        """)
        result = await self._db.execute(q, params)
        rows = [dict(r) for r in result.mappings().all()]

        return {
            "items": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ── Task Control ───────────────────────────────────────────

    async def start_task(self, task_id: int) -> dict:
        """Start executing a migration task in the background."""
        task = await self.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        if task["status"] not in ("pending", "paused"):
            return {"error": f"Cannot start task in '{task['status']}' status"}

        # Set running status
        await self._update_task_status(task_id, "running", started_at=utc_now())
        await self._db.commit()

        # Create pause event (set = running, clear = paused)
        event = asyncio.Event()
        event.set()
        _pause_events[task_id] = event
        _cancel_flags.discard(task_id)

        # Start background coroutine
        bg_task = asyncio.create_task(self._run_migration(task_id))
        _running_migrations[task_id] = bg_task

        return {"status": "running", "task_id": task_id}

    async def pause_task(self, task_id: int) -> dict:
        """Pause a running migration task."""
        task = await self.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        if task["status"] != "running":
            return {"error": f"Cannot pause task in '{task['status']}' status"}

        event = _pause_events.get(task_id)
        if event:
            event.clear()  # Signal the migration loop to pause
        await self._update_task_status(task_id, "paused")
        await self._db.commit()
        return {"status": "paused", "task_id": task_id}

    async def resume_task(self, task_id: int) -> dict:
        """Resume a paused migration task."""
        task = await self.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        if task["status"] != "paused":
            return {"error": f"Cannot resume task in '{task['status']}' status"}

        event = _pause_events.get(task_id)
        if event:
            event.set()  # Signal the migration loop to resume
        await self._update_task_status(task_id, "running")
        await self._db.commit()

        # If server restarted, there is no in-memory coroutine running.
        # In that case, we must re-create the pause event and start the
        # background migration coroutine, otherwise task will be stuck.
        if task_id not in _running_migrations:
            event = asyncio.Event()
            event.set()
            _pause_events[task_id] = event
            _cancel_flags.discard(task_id)

            bg_task = asyncio.create_task(self._run_migration(task_id))
            _running_migrations[task_id] = bg_task

        return {"status": "running", "task_id": task_id}

    async def cancel_task(self, task_id: int) -> dict:
        """Cancel a running or paused migration task."""
        task = await self.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        if task["status"] not in ("running", "paused", "pending"):
            return {"error": f"Cannot cancel task in '{task['status']}' status"}

        _cancel_flags.add(task_id)
        event = _pause_events.get(task_id)
        if event:
            event.set()  # Unblock if paused so it can check cancel flag
        await self._update_task_status(task_id, "cancelled")
        await self._db.commit()

        # Clean up background task
        bg = _running_migrations.pop(task_id, None)
        if bg and not bg.done():
            bg.cancel()
        _pause_events.pop(task_id, None)
        _cancel_flags.discard(task_id)

        return {"status": "cancelled", "task_id": task_id}

    # ── Retry & Rollback ───────────────────────────────────────

    async def retry_failed(self, task_id: int) -> dict:
        """Reset failed log entries to pending and restart migration."""
        task = await self.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        if task["status"] not in ("completed", "failed"):
            return {"error": f"Cannot retry task in '{task['status']}' status"}

        # Reset failed logs to pending
        reset_q = text(f"""
            UPDATE {self.LOG_TABLE}
            SET status = 'pending', error_message = NULL, migrated_at = NULL
            WHERE task_id = :task_id AND status = 'failed'
        """)
        result = await self._db.execute(reset_q, {"task_id": task_id})
        reset_count = result.rowcount

        if reset_count == 0:
            return {"error": "No failed files to retry"}

        # Update task counters
        await self._db.execute(
            text(f"""
                UPDATE {self.TASK_TABLE}
                SET failed_files = failed_files - :count,
                    status = 'pending',
                    error_message = NULL,
                    completed_at = NULL,
                    updated_at = now()
                WHERE id = :id
            """),
            {"id": task_id, "count": reset_count},
        )
        await self._db.commit()

        # Start the migration again
        return await self.start_task(task_id)

    async def rollback_task(self, task_id: int) -> dict:
        """Rollback a completed migration by reverting DB records and deleting target files."""
        task = await self.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        if task["status"] not in ("completed", "failed"):
            return {"error": f"Cannot rollback task in '{task['status']}' status"}

        await self._update_task_status(task_id, "rolling_back")
        await self._db.commit()

        # Best-effort: delete files from target storage
        target_delete_errors = 0
        try:
            target_config = await self._resolve_config_with_snapshot(
                self._db, task.get("target_config_snapshot"),
                task["target_driver"], task["scope"],
            )
            target_storage = storage_manager.get_driver(target_config)

            paths_q = text(f"""
                SELECT file_path FROM {self.LOG_TABLE}
                WHERE task_id = :task_id AND status = 'success'
            """)
            paths_result = await self._db.execute(paths_q, {"task_id": task_id})
            for row in paths_result.mappings().all():
                try:
                    await target_storage.delete(row["file_path"])
                except Exception as exc:
                    logger.warning(
                        "Rollback: failed to delete target file %s: %s",
                        row["file_path"], exc,
                    )
                    target_delete_errors += 1
        except Exception as exc:
            logger.warning("Rollback: cannot resolve target driver for cleanup: %s", exc)

        # Revert attachment records using migration logs
        logs_q = text(f"""
            SELECT attachment_id, old_driver, old_base_url
            FROM {self.LOG_TABLE}
            WHERE task_id = :task_id AND status = 'success'
        """)
        logs_result = await self._db.execute(logs_q, {"task_id": task_id})
        reverted = 0

        for log_row in logs_result.mappings().all():
            await self._db.execute(
                update(Attachment)
                .where(Attachment.id == log_row["attachment_id"])
                .values(
                    driver=log_row["old_driver"],
                    base_url=log_row["old_base_url"],
                )
            )
            reverted += 1

        # Mark logs as rolled back
        await self._db.execute(
            text(f"""
                UPDATE {self.LOG_TABLE}
                SET status = 'pending', new_driver = NULL, new_base_url = NULL,
                    migrated_at = NULL
                WHERE task_id = :task_id AND status = 'success'
            """),
            {"task_id": task_id},
        )

        # Reset task counters
        await self._db.execute(
            text(f"""
                UPDATE {self.TASK_TABLE}
                SET status = 'pending', migrated_files = 0, migrated_bytes = 0,
                    failed_files = 0, skipped_files = 0,
                    started_at = NULL, completed_at = NULL,
                    error_message = NULL, updated_at = now()
                WHERE id = :id
            """),
            {"id": task_id},
        )
        await self._db.commit()

        return {
            "status": "pending",
            "task_id": task_id,
            "reverted_files": reverted,
            "target_delete_errors": target_delete_errors,
        }

    async def cleanup_source_files(self, task_id: int) -> dict:
        """Delete source files after successful migration."""
        task = await self.get_task(task_id)
        if not task:
            return {"error": "Task not found"}
        if task["status"] != "completed":
            return {"error": "Can only cleanup source files for completed tasks"}

        try:
            source_config = await self._resolve_config_with_snapshot(
                self._db, task.get("source_config_snapshot"),
                task["source_driver"], task["scope"],
            )
        except Exception as exc:
            return {"error": f"Cannot resolve source config: {exc}"}

        source_driver = storage_manager.get_driver(source_config)

        logs_q = text(f"""
            SELECT file_path FROM {self.LOG_TABLE}
            WHERE task_id = :task_id AND status = 'success'
        """)
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

        return {
            "task_id": task_id,
            "deleted_files": deleted,
            "errors": errors,
        }

    # ── Migration Execution ────────────────────────────────────

    async def _run_migration(self, task_id: int) -> None:
        """
        Background coroutine that performs the actual file migration.

        IMPORTANT: This runs as an asyncio.Task that outlives the HTTP request.
        It must NOT use self._db (request-scoped session). Instead, it creates
        independent sessions from async_session_factory for all DB operations.
        """
        from app.core.database import async_session_factory

        try:
            # Use a dedicated session for setup queries
            async with async_session_factory() as setup_db:
                svc = StorageMigrationService(setup_db)
                task = await svc.get_task(task_id)
                if not task:
                    return

                source_driver_name = task["source_driver"]
                target_driver_name = task["target_driver"]
                concurrency = task.get("concurrency", 5)

                # Use config snapshot if available, fallback to live resolution
                source_config = await self._resolve_config_with_snapshot(
                    setup_db, task.get("source_config_snapshot"),
                    source_driver_name, task["scope"],
                )
                target_config = await self._resolve_config_with_snapshot(
                    setup_db, task.get("target_config_snapshot"),
                    target_driver_name, task["scope"],
                )

                source_storage = storage_manager.get_driver(source_config)
                target_storage = storage_manager.get_driver(target_config)
                target_base_url = target_storage.get_base_url()

            # Process pending files in batches to avoid OOM on large file sets.
            # Each file gets its own DB session for concurrency safety.
            # Counters are accumulated in memory per batch, then flushed once.
            BATCH_SIZE = 1000
            semaphore = asyncio.Semaphore(concurrency)
            counter_lock = asyncio.Lock()
            batch_counters: dict[str, int] = {}

            def _reset_counters() -> None:
                batch_counters.clear()
                batch_counters.update(
                    migrated_files=0, failed_files=0, migrated_bytes=0,
                )

            async def migrate_one(log_entry: dict) -> None:
                async with semaphore:
                    # Check pause/cancel
                    event = _pause_events.get(task_id)
                    if event:
                        await event.wait()
                    if task_id in _cancel_flags:
                        return

                    # Each file gets its own session
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
                        )

                    # Accumulate counters (lock-protected for safety)
                    async with counter_lock:
                        if ok:
                            batch_counters["migrated_files"] += 1
                            batch_counters["migrated_bytes"] += log_entry["file_size"]
                        else:
                            batch_counters["failed_files"] += 1

            while task_id not in _cancel_flags:
                async with async_session_factory() as batch_db:
                    pending_q = text(f"""
                        SELECT id, attachment_id, file_path, file_size
                        FROM {self.LOG_TABLE}
                        WHERE task_id = :task_id AND status = 'pending'
                        ORDER BY id
                        LIMIT :limit
                    """)
                    result = await batch_db.execute(
                        pending_q, {"task_id": task_id, "limit": BATCH_SIZE}
                    )
                    batch = [dict(r) for r in result.mappings().all()]

                if not batch:
                    break

                _reset_counters()
                batch_tasks = [migrate_one(log) for log in batch]
                await asyncio.gather(*batch_tasks, return_exceptions=True)

                # Flush accumulated counters in a single UPDATE
                async with async_session_factory() as flush_db:
                    await flush_db.execute(
                        text(f"""
                            UPDATE {self.TASK_TABLE}
                            SET migrated_files = migrated_files + :mf,
                                failed_files = failed_files + :ff,
                                migrated_bytes = migrated_bytes + :mb,
                                updated_at = now()
                            WHERE id = :task_id
                        """),
                        {
                            "task_id": task_id,
                            "mf": batch_counters["migrated_files"],
                            "ff": batch_counters["failed_files"],
                            "mb": batch_counters["migrated_bytes"],
                        },
                    )
                    await flush_db.commit()

            # Check final status with a fresh session
            if task_id not in _cancel_flags:
                async with async_session_factory() as final_db:
                    final_svc = StorageMigrationService(final_db)
                    updated_task = await final_svc.get_task(task_id)
                    if updated_task and updated_task["status"] == "running":
                        final_status = "completed"
                        if updated_task["failed_files"] > 0:
                            final_status = (
                                "failed" if updated_task["migrated_files"] == 0
                                else "completed"
                            )
                        await final_svc._update_task_status(
                            task_id, final_status, completed_at=utc_now()
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
                        task_id, "failed", error_message=str(exc)
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
    ) -> bool:
        """Migrate a single file from source to target driver.

        Uses the provided `db` session (NOT self._db) to ensure each
        concurrent file migration has its own session.

        Returns True on success, False on failure.
        Task-level counters are NOT updated here; callers accumulate
        them in memory and flush per batch.
        """
        try:
            # Get file info for visibility (metadata only, no file content)
            file_info = await source_driver.get_info(file_path)  # type: ignore[union-attr]
            visibility = (
                file_info.visibility if file_info
                else StorageVisibility.PRIVATE
            )

            # Read from source — returns BinaryIO stream.
            # Pass directly to put() to avoid loading entire file into memory.
            content = await source_driver.get(file_path)  # type: ignore[union-attr]
            file_data = BytesIO(content) if isinstance(content, bytes) else content

            # Write to target (streaming)
            await target_driver.put(  # type: ignore[union-attr]
                path=file_path,
                content=file_data,
                visibility=visibility,
            )

            # Update attachment record
            await db.execute(
                update(Attachment)
                .where(Attachment.id == attachment_id)
                .values(driver=target_driver_name, base_url=target_base_url)
            )

            # Update log entry
            now = utc_now()
            await db.execute(
                text(f"""
                    UPDATE {self.LOG_TABLE}
                    SET status = 'success', new_driver = :driver,
                        new_base_url = :base_url, migrated_at = :now
                    WHERE id = :id
                """),
                {
                    "id": log_id,
                    "driver": target_driver_name,
                    "base_url": target_base_url,
                    "now": now,
                },
            )
            await db.commit()
            return True

        except Exception as exc:
            logger.warning(
                "Failed to migrate file %s (log=%d): %s",
                file_path, log_id, exc,
            )
            try:
                await db.rollback()
                await db.execute(
                    text(f"""
                        UPDATE {self.LOG_TABLE}
                        SET status = 'failed', error_message = :error
                        WHERE id = :id
                    """),
                    {"id": log_id, "error": str(exc)[:500]},
                )
                await db.commit()
            except Exception:
                pass
            return False

    # ── Helpers ─────────────────────────────────────────────────

    async def _update_task_status(
        self,
        task_id: int,
        status: str,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update task status and optional timestamps."""
        set_parts = ["status = :status", "updated_at = now()"]
        params: dict = {"id": task_id, "status": status}

        if started_at is not None:
            set_parts.append("started_at = :started_at")
            params["started_at"] = started_at
        if completed_at is not None:
            set_parts.append("completed_at = :completed_at")
            params["completed_at"] = completed_at
        if error_message is not None:
            set_parts.append("error_message = :error_message")
            params["error_message"] = error_message

        q = text(f"UPDATE {self.TASK_TABLE} SET {', '.join(set_parts)} WHERE id = :id")
        await self._db.execute(q, params)

    @staticmethod
    async def _resolve_config_with_snapshot(
        db: AsyncSession,
        snapshot: dict | None,
        driver_name: str,
        scope: str,
    ) -> StorageConfig:
        """Resolve config preferring saved snapshot over live resolution.

        During migration execution, the config may have changed since the task
        was created. Using the snapshot ensures consistency.
        """
        if snapshot and snapshot.get("driver") == driver_name:
            return StorageConfig(
                driver=snapshot["driver"],
                root_path=snapshot.get("root_path", ""),
                base_url=snapshot.get("base_url"),
                options=snapshot.get("options", {}),
            )
        # Fallback: live resolution (snapshot may lack options/credentials)
        resolver = StorageConfigResolver(db)
        svc = StorageMigrationService(db)
        return await svc._resolve_driver_config(resolver, driver_name, scope)

    async def _resolve_driver_config(
        self,
        resolver: StorageConfigResolver,
        driver_name: str,
        scope: str,
    ) -> StorageConfig:
        """Resolve storage config for a driver, considering scope."""
        tenant_id = 0
        if scope.startswith("tenant:"):
            tenant_id = int(scope.split(":")[1])

        # Use resolve_for_attachment which handles driver → config mapping
        # including local fallback, tenant/platform config matching, etc.
        try:
            return await resolver.resolve_for_attachment(driver_name, tenant_id)
        except Exception:
            pass

        # Last resort: if driver doesn't match any config, try platform config
        config = await resolver.resolve_platform_config()
        if config.driver == driver_name:
            return config

        raise ValueError(
            f"Cannot resolve config for driver '{driver_name}'. "
            f"Ensure the driver is configured in platform or tenant storage settings."
        )


def _json_dumps(obj: dict) -> str:
    """Serialize dict to JSON string for SQL insertion."""
    return json.dumps(obj, ensure_ascii=False, default=str)
