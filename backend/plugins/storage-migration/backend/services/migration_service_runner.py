"""Runtime runner operations for storage migration tasks."""

from __future__ import annotations

import asyncio
from typing import Any


def _create_background_task(asyncio_module: Any, coroutine: Any) -> Any:
    """Create a background task and close unscheduled mock coroutines in tests."""
    background_task = asyncio_module.create_task(coroutine)
    get_coro = getattr(background_task, "get_coro", None)
    scheduled_coroutine = get_coro() if callable(get_coro) else None
    if scheduled_coroutine is not coroutine and hasattr(coroutine, "close"):
        coroutine.close()
    return background_task


async def start_task(
    service: Any,
    task_id: int,
    *,
    utc_now: Any,
    asyncio_module: Any,
    activate_task: Any,
    clear_cancelled: Any,
    register_background_task: Any,
) -> dict[str, Any]:
    """Move a task into running state and boot its background worker."""
    task = await service.get_task(task_id)
    if not task:
        return {"error": "Task not found"}
    if task["status"] not in ("pending", "paused"):
        return {"error": f"Cannot start task in '{task['status']}' status"}

    await service._update_task_status(
        task_id,
        "running",
        started_at=utc_now(),
        error_message=None,
    )
    await service._db.commit()

    activate_task(task_id)
    clear_cancelled(task_id)
    background_task = _create_background_task(
        asyncio_module,
        service._run_migration(task_id),
    )
    register_background_task(task_id, background_task)
    return {"status": "running", "task_id": task_id}


async def pause_task(
    service: Any,
    task_id: int,
    *,
    pause_runtime_task: Any,
) -> dict[str, Any]:
    """Pause the runtime gate for a running migration."""
    task = await service.get_task(task_id)
    if not task:
        return {"error": "Task not found"}
    if task["status"] != "running":
        return {"error": f"Cannot pause task in '{task['status']}' status"}

    pause_runtime_task(task_id)
    await service._update_task_status(task_id, "paused")
    await service._db.commit()
    return {"status": "paused", "task_id": task_id}


async def resume_task(
    service: Any,
    task_id: int,
    *,
    asyncio_module: Any,
    activate_task: Any,
    clear_cancelled: Any,
    has_background_task: Any,
    register_background_task: Any,
) -> dict[str, Any]:
    """Resume a paused migration and recreate the worker if needed."""
    task = await service.get_task(task_id)
    if not task:
        return {"error": "Task not found"}
    if task["status"] != "paused":
        return {"error": f"Cannot resume task in '{task['status']}' status"}

    activate_task(task_id)
    await service._update_task_status(task_id, "running", error_message=None)
    await service._db.commit()

    if not has_background_task(task_id):
        clear_cancelled(task_id)
        background_task = _create_background_task(
            asyncio_module,
            service._run_migration(task_id),
        )
        register_background_task(task_id, background_task)

    return {"status": "running", "task_id": task_id}


async def cancel_task(
    service: Any,
    task_id: int,
    *,
    mark_cancelled: Any,
    pop_background_task: Any,
    clear_runtime: Any,
) -> dict[str, Any]:
    """Cancel a running or pending migration and release runtime state."""
    task = await service.get_task(task_id)
    if not task:
        return {"error": "Task not found"}
    if task["status"] not in ("running", "paused", "pending"):
        return {"error": f"Cannot cancel task in '{task['status']}' status"}

    mark_cancelled(task_id)
    await service._update_task_status(task_id, "cancelled")
    await service._db.commit()

    background_task = pop_background_task(task_id)
    if background_task and not background_task.done():
        background_task.cancel()

    clear_runtime(task_id)
    return {"status": "cancelled", "task_id": task_id}


async def run_migration(
    service: Any,
    task_id: int,
    *,
    service_factory: Any,
    async_session_factory: Any,
    storage_manager: Any,
    text: Any,
    utc_now: Any,
    logger: Any,
    get_pause_event: Any,
    is_cancelled: Any,
    clear_runtime: Any,
) -> None:
    """Perform the actual file migration in a background coroutine."""

    async def mark_log_failed(log_id: int, exc: Exception) -> None:
        async with async_session_factory() as failure_db:
            await failure_db.execute(
                text(
                    f"""
                    UPDATE {service.LOG_TABLE}
                    SET status = 'failed',
                        error_message = :error
                    WHERE id = :id
                    """
                ),
                {
                    "id": log_id,
                    "error": str(exc)[:500],
                },
            )
            await failure_db.commit()

    try:
        async with async_session_factory() as setup_db:
            setup_service = service_factory(setup_db)
            task = await setup_service.get_task(task_id)
            if not task:
                return

            source_driver_name = task["source_driver"]
            target_driver_name = task["target_driver"]
            concurrency = max(1, int(task.get("concurrency") or 1))

            source_config = await setup_service._resolve_config_with_snapshot(
                setup_db,
                task.get("source_config_snapshot"),
                source_driver_name,
                task["scope"],
            )
            target_config = await setup_service._resolve_config_with_snapshot(
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
        batch_counters = {
            "migrated_files": 0,
            "failed_files": 0,
            "migrated_bytes": 0,
        }

        def reset_counters() -> None:
            batch_counters["migrated_files"] = 0
            batch_counters["failed_files"] = 0
            batch_counters["migrated_bytes"] = 0

        async def migrate_one(log_entry: dict[str, Any]) -> None:
            try:
                async with semaphore:
                    pause_event = get_pause_event(task_id)
                    if pause_event is not None:
                        await pause_event.wait()
                    if is_cancelled(task_id):
                        return

                    async with async_session_factory() as file_db:
                        file_service = service_factory(file_db)
                        ok = await file_service._migrate_single_file(
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
                            batch_counters["migrated_bytes"] += int(
                                log_entry.get("file_size") or 0
                            )
                        else:
                            batch_counters["failed_files"] += 1
            except Exception as exc:
                logger.error(
                    "Migration task {} unexpected worker failure for log {}: {}",
                    task_id,
                    log_entry.get("id"),
                    exc,
                    exc_info=True,
                )
                try:
                    await mark_log_failed(log_entry["id"], exc)
                except Exception as persist_exc:
                    logger.warning(
                        "Migration task {} failed to persist log {} failure state: {}",
                        task_id,
                        log_entry.get("id"),
                        persist_exc,
                    )
                async with counter_lock:
                    batch_counters["failed_files"] += 1

        while not is_cancelled(task_id):
            async with async_session_factory() as batch_db:
                pending_query = text(
                    f"""
                    SELECT id, attachment_id, file_path, file_size
                    FROM {service.LOG_TABLE}
                    WHERE task_id = :task_id AND status = 'pending'
                    ORDER BY id
                    LIMIT :limit
                    """
                )
                result = await batch_db.execute(
                    pending_query,
                    {"task_id": task_id, "limit": batch_size},
                )
                batch = [dict(row) for row in result.mappings().all()]

            if not batch:
                break

            reset_counters()
            await asyncio.gather(*(migrate_one(log_entry) for log_entry in batch))

            async with async_session_factory() as flush_db:
                await flush_db.execute(
                    text(
                        f"""
                        UPDATE {service.TASK_TABLE}
                        SET migrated_files = migrated_files + :migrated_files,
                            failed_files = failed_files + :failed_files,
                            migrated_bytes = migrated_bytes + :migrated_bytes,
                            updated_at = now()
                        WHERE id = :task_id
                        """
                    ),
                    {
                        "task_id": task_id,
                        "migrated_files": batch_counters["migrated_files"],
                        "failed_files": batch_counters["failed_files"],
                        "migrated_bytes": batch_counters["migrated_bytes"],
                    },
                )
                await flush_db.commit()

        if not is_cancelled(task_id):
            async with async_session_factory() as final_db:
                final_service = service_factory(final_db)
                updated_task = await final_service.get_task(task_id)
                if updated_task and updated_task["status"] == "running":
                    final_status = "completed"
                    if (
                        updated_task["failed_files"] > 0
                        and updated_task["migrated_files"] == 0
                    ):
                        final_status = "failed"

                    await final_service._update_task_status(
                        task_id,
                        final_status,
                        completed_at=utc_now(),
                    )
                    await final_db.commit()

    except asyncio.CancelledError:
        logger.info("Migration task {} cancelled", task_id)
    except Exception as exc:
        logger.error("Migration task {} failed: {}", task_id, exc, exc_info=True)
        try:
            async with async_session_factory() as error_db:
                error_service = service_factory(error_db)
                await error_service._update_task_status(
                    task_id,
                    "failed",
                    error_message=str(exc),
                )
                await error_db.commit()
        except Exception as persist_exc:
            logger.warning(
                "Migration task {} failed to persist terminal failure state: {}",
                task_id,
                persist_exc,
            )
    finally:
        clear_runtime(task_id)
