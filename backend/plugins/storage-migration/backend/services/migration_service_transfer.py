"""Transfer-side operations for storage migration tasks."""

from __future__ import annotations

from typing import Any


async def create_task(
    service: Any,
    *,
    source_driver: str,
    target_driver: str,
    scope: str,
    concurrency: int,
    created_by: int,
    normalize_scope: Any,
    storage_manager: Any,
    storage_config_resolver_cls: Any,
    attachment_model: Any,
    select: Any,
    func: Any,
    text: Any,
    json_dumps: Any,
    utc_now: Any,
) -> dict[str, Any]:
    """Create a migration task and seed per-file logs."""
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

    conflict = await service._find_conflicting_active_task(
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

    resolver = storage_config_resolver_cls(service._db)
    try:
        source_config = await service._resolve_driver_config(
            resolver,
            source_driver,
            scope,
        )
        target_config = await service._resolve_driver_config(
            resolver,
            target_driver,
            scope,
        )
    except Exception as exc:
        return {"error": str(exc)}

    conditions = [
        attachment_model.driver == source_driver,
        attachment_model.is_deleted.is_(False),
    ]
    if scope.startswith("tenant:"):
        tenant_id = int(scope.split(":", 1)[1])
        conditions.append(attachment_model.tenant_id == tenant_id)

    count_q = select(
        func.count(attachment_model.id),
        func.coalesce(func.sum(attachment_model.size), 0),
    ).where(*conditions)
    count_result = await service._db.execute(count_q)
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
        INSERT INTO {service.TASK_TABLE}
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
    result = await service._db.execute(
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
        INSERT INTO {service.LOG_TABLE}
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
                attachment_model.id,
                attachment_model.path,
                attachment_model.size,
                attachment_model.driver,
                attachment_model.base_url,
                attachment_model.meta,
            )
            .where(*conditions)
            .order_by(attachment_model.id)
            .limit(batch_size)
            .offset(offset)
        )
        batch_result = await service._db.execute(batch_q)
        rows = batch_result.all()
        if not rows:
            break

        await service._db.execute(
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

    await service._db.commit()

    return {
        "task_id": task_id,
        "total_files": total_files,
        "total_bytes": int(total_bytes),
        "status": "pending",
    }


async def migrate_single_file(
    service: Any,
    *,
    db: Any,
    log_id: int,
    attachment_id: int,
    file_path: str,
    source_driver: object,
    target_driver: object,
    target_driver_name: str,
    target_base_url: str,
    target_storage_config: Any,
    execute_single_file_migration: Any,
    attachment_model: Any,
    utc_now: Any,
    logger: Any,
) -> bool:
    """Delegate one file transfer to the shared helper contract."""
    return await execute_single_file_migration(
        attachment_model=attachment_model,
        db=db,
        file_path=file_path,
        log_id=log_id,
        log_table=service.LOG_TABLE,
        attachment_id=attachment_id,
        source_driver=source_driver,
        target_driver=target_driver,
        target_driver_name=target_driver_name,
        target_base_url=target_base_url,
        target_storage_config=target_storage_config,
        now_factory=utc_now,
        logger=logger,
    )
