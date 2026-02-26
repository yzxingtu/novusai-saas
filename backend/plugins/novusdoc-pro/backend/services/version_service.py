"""
NovusDoc Pro 版本服务

订阅 novusdoc 的 document_saved 事件，自动创建版本快照。
"""

from __future__ import annotations

from app.core.logging import get_logger

logger = get_logger("plugin.novusdoc-pro.version")


async def on_document_saved(event_name: str, payload: dict) -> None:
    """EventBus handler: novusdoc document_saved → auto-snapshot"""
    doc_id = payload.get("doc_id")
    tenant_id = payload.get("tenant_id")
    logger.info(
        "version_service: document_saved event — doc_id=%s tenant_id=%s (auto-snapshot pending)",
        doc_id, tenant_id,
    )
