"""
NovusDoc Pro 文档归属校验服务

提供跨插件文档存在性与归属校验，供 Pro API handler 在写入操作前调用。
避免写入孤儿数据（引用不存在的 document_id）。

由于 novusdoc 和 novusdoc-pro 是独立插件（各自 Alembic 分支），
不使用数据库 FK 约束，改为应用层一致性防护。
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger("plugin.novusdoc-pro.validator")


async def verify_document_exists(
    db: Any,
    tenant_id: int,
    doc_id: int,
) -> bool:
    """
    校验 novusdoc 文档是否存在且属于指定租户。

    通过插件模块加载器跨插件调用 novusdoc 的 get_document。
    若 novusdoc 插件不可用，降级为直接查询文档表。

    Returns:
        True = 文档存在且属于该租户, False = 不存在/不属于
    """
    # 方式 1：通过插件模块加载器调用 novusdoc service
    try:
        from app.plugins.module_loader import load_plugin_handler
        get_document = load_plugin_handler(
            "novusdoc", "services.document_service.get_document",
        )
        if get_document:
            doc = await get_document(db, tenant_id, doc_id)
            return doc is not None
    except Exception as exc:
        logger.warning(
            "doc_validator: failed to call novusdoc service: %s", exc,
        )

    # 方式 2：降级直接查询文档表（novusdoc 插件加载失败时）
    try:
        from sqlalchemy import text
        result = await db.execute(
            text(
                "SELECT 1 FROM px_novusdoc_documents "
                "WHERE id = :doc_id AND tenant_id = :tenant_id "
                "AND is_deleted = false LIMIT 1"
            ),
            {"doc_id": doc_id, "tenant_id": tenant_id},
        )
        return result.scalar_one_or_none() is not None
    except Exception as exc:
        logger.error("doc_validator: fallback query failed: %s", exc)
        return False
