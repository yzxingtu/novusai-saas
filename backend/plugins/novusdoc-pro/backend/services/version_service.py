"""
NovusDoc Pro 版本服务

订阅 novusdoc 的 document_saved 事件，自动创建版本快照。
去重策略：同一文档 10 分钟内不重复创建快照。
"""

from __future__ import annotations

import time
from typing import Any

from app.core.logging import get_logger

logger = get_logger("plugin.novusdoc-pro.version")

# 去重缓存：{(tenant_id, doc_id): last_snapshot_time}
_snapshot_cooldown: dict[tuple[int, int], float] = {}
_COOLDOWN_SECONDS = 600  # 10 minutes


async def on_document_saved(event_name: str, payload: dict) -> None:
    """EventBus handler: novusdoc document_saved → auto-snapshot"""
    doc_id = payload.get("doc_id")
    tenant_id = payload.get("tenant_id")

    if doc_id is None or tenant_id is None:
        logger.warning("version_service: missing doc_id or tenant_id in payload")
        return

    doc_id = int(doc_id)
    tenant_id = int(tenant_id)

    # Cooldown check: skip if snapshot created recently
    key = (tenant_id, doc_id)
    now = time.time()

    # Periodic cleanup: remove stale entries to prevent unbounded dict growth
    if len(_snapshot_cooldown) > 500:
        stale_threshold = now - _COOLDOWN_SECONDS * 2
        stale_keys = [k for k, v in _snapshot_cooldown.items() if v < stale_threshold]
        for k in stale_keys:
            del _snapshot_cooldown[k]

    last_time = _snapshot_cooldown.get(key, 0)
    if now - last_time < _COOLDOWN_SECONDS:
        return

    try:
        await _create_auto_snapshot(tenant_id, doc_id, payload)
        _snapshot_cooldown[key] = now
        logger.info(
            "version_service: auto-snapshot created for doc_id=%d tenant_id=%d",
            doc_id, tenant_id,
        )
    except Exception as exc:
        logger.error(
            "version_service: failed to create auto-snapshot for doc_id=%d: %s",
            doc_id, exc,
        )


async def _create_auto_snapshot(tenant_id: int, doc_id: int, payload: dict) -> None:
    """Create a version snapshot for the document."""
    from app.core.database import async_session_factory
    from ..models.version import NovusdocProVersion

    # Fetch current document content via novusdoc service
    async with async_session_factory() as db:
        try:
            from app.plugins.module_loader import load_plugin_handler
            get_document = load_plugin_handler(
                "novusdoc", "services.document_service.get_document",
            )
            if not get_document:
                logger.warning("version_service: novusdoc service not available")
                return

            doc = await get_document(db, tenant_id, doc_id)
            if not doc:
                return

            version = NovusdocProVersion(
                tenant_id=tenant_id,
                document_id=doc_id,
                title=doc.get("title", ""),
                content=doc.get("content"),
                content_text=doc.get("content_text", ""),
                word_count=doc.get("word_count", 0),
                creator_id=doc.get("last_edited_by"),
                creator_name="System",
                version_note="auto-save",
            )
            db.add(version)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
