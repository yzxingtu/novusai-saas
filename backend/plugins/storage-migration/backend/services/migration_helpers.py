"""Shared helpers for storage migration services."""

from __future__ import annotations

import json
from contextlib import suppress
from io import BytesIO
from typing import Any

from sqlalchemy import select, text, update

from app.services.common.storage_config_resolver import (
    infer_attachment_storage_scope,
    merge_attachment_storage_snapshot,
    strip_internal_attachment_meta,
)
from app.storage.base import StorageConfig, StorageVisibility


def normalize_scope(scope: str) -> str:
    normalized = str(scope or "all").strip()
    if not normalized or normalized == "all":
        return "all"
    if not normalized.startswith("tenant:"):
        raise ValueError("scope must be 'all' or 'tenant:{id}'")

    tenant_part = normalized.split(":", 1)[1].strip()
    tenant_id = int(tenant_part)
    if tenant_id <= 0:
        raise ValueError("tenant scope id must be a positive integer")
    return f"tenant:{tenant_id}"


def scopes_overlap(left: str, right: str) -> bool:
    if left == "all" or right == "all":
        return True
    return left == right


def deserialize_json_field(value: Any) -> Any:
    if value is None or isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return value
    return value


def json_dumps(obj: Any) -> str | None:
    if obj is None:
        return None
    return json.dumps(obj, ensure_ascii=False, default=str)


async def execute_single_file_migration(
    *,
    attachment_model: Any,
    db: Any,
    file_path: str,
    log_id: int,
    log_table: str,
    attachment_id: int,
    source_driver: Any,
    target_driver: Any,
    target_driver_name: str,
    target_base_url: str,
    target_storage_config: StorageConfig,
    now_factory: Any,
    logger: Any,
) -> bool:
    """Migrate one attachment and persist migration log updates."""
    target_written = False

    try:
        attachment_meta_q = select(
            attachment_model.visibility,
            attachment_model.mime_type,
            attachment_model.meta,
            attachment_model.tenant_id,
        ).where(attachment_model.id == attachment_id)
        attachment_meta_result = await db.execute(attachment_meta_q)
        attachment_meta = attachment_meta_result.one_or_none()
        if attachment_meta is None:
            raise RuntimeError(
                f"Attachment {attachment_id} not found during storage migration"
            )

        visibility = StorageVisibility(
            attachment_meta.visibility or StorageVisibility.PRIVATE.value
        )
        metadata = attachment_meta.meta if isinstance(attachment_meta.meta, dict) else None
        object_metadata = strip_internal_attachment_meta(metadata)
        storage_scope = (
            infer_attachment_storage_scope(
                metadata,
                file_path,
                attachment_meta.tenant_id,
            )
            or "platform"
        )
        updated_meta = merge_attachment_storage_snapshot(
            metadata,
            target_storage_config,
            storage_scope,
        )

        content = await source_driver.get(file_path)  # type: ignore[union-attr]
        file_data = BytesIO(content) if isinstance(content, (bytes, bytearray)) else content

        await target_driver.put(  # type: ignore[union-attr]
            path=file_path,
            content=file_data,
            mime_type=attachment_meta.mime_type,
            visibility=visibility,
            metadata=object_metadata,
        )
        target_written = True

        await db.execute(
            update(attachment_model)
            .where(attachment_model.id == attachment_id)
            .values(
                driver=target_driver_name,
                base_url=target_base_url,
                meta=updated_meta,
            )
        )

        await db.execute(
            text(
                f"""
                UPDATE {log_table}
                SET status = 'success',
                    new_driver = :driver,
                    new_base_url = :base_url,
                    migrated_at = :now,
                    error_message = NULL
                WHERE id = :id
                """
            ),
            {
                "id": log_id,
                "driver": target_driver_name,
                "base_url": target_base_url,
                "now": now_factory(),
            },
        )
        await db.commit()
        return True
    except Exception as exc:
        logger.warning("Failed to migrate file %s (log=%d): %s", file_path, log_id, exc)

        with suppress(Exception):
            await db.rollback()

        if target_written:
            try:
                await target_driver.delete(file_path)  # type: ignore[union-attr]
            except Exception as cleanup_exc:
                logger.warning(
                    "Failed to cleanup partially written target file %s: %s",
                    file_path,
                    cleanup_exc,
                )

        try:
            await db.execute(
                text(
                    f"""
                    UPDATE {log_table}
                    SET status = 'failed',
                        error_message = :error
                    WHERE id = :id
                    """
                ),
                {"id": log_id, "error": str(exc)[:500]},
            )
            await db.commit()
        except Exception:
            pass
        return False
