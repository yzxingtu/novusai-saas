"""Recovery and cleanup operations for storage migration tasks."""

from __future__ import annotations

from typing import Any


async def retry_failed(
    service: Any,
    task_id: int,
    *,
    text: Any,
) -> dict[str, Any]:
    """Reset failed file logs and restart the task."""
    task = await service.get_task(task_id)
    if not task:
        return {"error": "Task not found"}
    if task["status"] not in ("completed", "failed"):
        return {"error": f"Cannot retry task in '{task['status']}' status"}

    reset_q = text(
        f"""
        UPDATE {service.LOG_TABLE}
        SET status = 'pending',
            error_message = NULL,
            migrated_at = NULL
        WHERE task_id = :task_id AND status = 'failed'
        """
    )
    result = await service._db.execute(reset_q, {"task_id": task_id})
    reset_count = result.rowcount
    if reset_count == 0:
        return {"error": "No failed files to retry"}

    await service._db.execute(
        text(
            f"""
            UPDATE {service.TASK_TABLE}
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
    await service._db.commit()

    return await service.start_task(task_id)


async def rollback_task(
    service: Any,
    task_id: int,
    *,
    storage_manager: Any,
    update: Any,
    text: Any,
    deserialize_json_field: Any,
    attachment_model: Any,
    logger: Any,
) -> dict[str, Any]:
    """Rollback migrated attachment records and target files."""
    task = await service.get_task(task_id)
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

    conflict = await service._find_conflicting_active_task(
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

    await service._update_task_status(
        task_id,
        "rolling_back",
        error_message=None,
    )
    await service._db.commit()

    target_delete_errors = 0
    try:
        target_config = await service._resolve_config_with_snapshot(
            service._db,
            task.get("target_config_snapshot"),
            task["target_driver"],
            task["scope"],
        )
        target_storage = storage_manager.get_driver(target_config)

        paths_q = text(
            f"""
            SELECT file_path
            FROM {service.LOG_TABLE}
            WHERE task_id = :task_id AND status = 'success'
            """
        )
        paths_result = await service._db.execute(paths_q, {"task_id": task_id})
        for row in paths_result.mappings().all():
            try:
                await target_storage.delete(row["file_path"])
            except Exception as exc:
                logger.warning(
                    "Rollback: failed to delete target file {}: {}",
                    row["file_path"],
                    exc,
                )
                target_delete_errors += 1
    except Exception as exc:
        logger.warning(
            "Rollback: cannot resolve target driver for cleanup: {}",
            exc,
        )

    logs_q = text(
        f"""
        SELECT attachment_id, old_driver, old_base_url, old_meta
        FROM {service.LOG_TABLE}
        WHERE task_id = :task_id AND status = 'success'
        """
    )
    logs_result = await service._db.execute(logs_q, {"task_id": task_id})

    reverted = 0
    for log_row in logs_result.mappings().all():
        await service._db.execute(
            update(attachment_model)
            .where(attachment_model.id == log_row["attachment_id"])
            .values(
                driver=log_row["old_driver"],
                base_url=log_row["old_base_url"],
                meta=deserialize_json_field(log_row["old_meta"]),
            )
        )
        reverted += 1

    await service._db.execute(
        text(
            f"""
            UPDATE {service.LOG_TABLE}
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

    await service._db.execute(
        text(
            f"""
            UPDATE {service.TASK_TABLE}
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
    await service._db.commit()

    return {
        "status": "pending",
        "task_id": task_id,
        "reverted_files": reverted,
        "target_delete_errors": target_delete_errors,
    }


async def cleanup_source_files(
    service: Any,
    task_id: int,
    *,
    storage_manager: Any,
    text: Any,
    utc_now: Any,
    logger: Any,
) -> dict[str, Any]:
    """Delete source-side files after a completed migration."""
    task = await service.get_task(task_id)
    if not task:
        return {"error": "Task not found"}
    if task["status"] != "completed":
        return {"error": "Can only cleanup source files for completed tasks"}
    if task.get("source_cleanup_completed_at"):
        return {"error": "Source files were already cleaned up for this task"}

    try:
        source_config = await service._resolve_config_with_snapshot(
            service._db,
            task.get("source_config_snapshot"),
            task["source_driver"],
            task["scope"],
        )
    except Exception as exc:
        return {"error": f"Cannot resolve source config: {exc}"}

    source_driver = storage_manager.get_driver(source_config)
    started_at = utc_now()
    await service._db.execute(
        text(
            f"""
            UPDATE {service.TASK_TABLE}
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
        FROM {service.LOG_TABLE}
        WHERE task_id = :task_id AND status = 'success'
        """
    )
    logs_result = await service._db.execute(logs_q, {"task_id": task_id})

    deleted = 0
    errors = 0
    for row in logs_result.mappings().all():
        try:
            await source_driver.delete(row["file_path"])
            deleted += 1
        except Exception as exc:
            logger.warning(
                "Failed to delete source file {}: {}",
                row["file_path"],
                exc,
            )
            errors += 1

    completed_at = utc_now()
    await service._db.execute(
        text(
            f"""
            UPDATE {service.TASK_TABLE}
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
    await service._db.commit()

    return {
        "task_id": task_id,
        "deleted_files": deleted,
        "errors": errors,
        "cleanup_completed_at": completed_at,
    }
