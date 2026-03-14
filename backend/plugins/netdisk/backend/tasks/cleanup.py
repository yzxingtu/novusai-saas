"""
网盘回收站清理 + 配额重算定时任务
每天 02:00 运行，避开平台 cleanup_recycle_bin 的 03:00
"""

from __future__ import annotations

import time
from datetime import timedelta

from app.core.base_model import utc_now
from app.core.logging import LogManager
from app.tasks.base import BaseTask, register_task

logger = LogManager.get_logger("task")


@register_task(
    queue="scheduled",
    description="网盘回收站清理（物理删除 + 回收 Storage + 重算配额）",
    max_retries=1,
)
def netdisk_cleanup(self: BaseTask, retention_days: int = 0) -> dict:
    """
    合并任务（原 clean_trash + sync_quota）：
    1. 物理删除超时回收站节点（px_netdisk_nodes）
    2. 调用 StorageManager 删除真实文件
    3. 重算各受影响企业的 used_bytes

    Args:
        retention_days: 回收站保留天数，默认从插件 config 读取，此处为 fallback
    """
    from sqlalchemy import delete as sa_delete
    from sqlalchemy import func, select, update

    from app.core.database import sync_session_factory

    # 从插件配置读取 recycle_bin_days，fallback 到0时尝试读配置，再尝试默认30
    if retention_days <= 0:
        try:
            cfg = self.plugin_config or {}
            retention_days = int(cfg.get("recycle_bin_days", 30))
        except Exception:
            retention_days = 30

    start = time.monotonic()
    cleaned_count = 0
    freed_bytes   = 0
    tenants_updated = 0

    cutoff = utc_now() - timedelta(days=retention_days)

    session = None
    try:
        session = sync_session_factory()

        # ── 步骤 1：查找超时回收站节点（仅 file 类型需要删 storage）
        from ..models.node import FileNode, NodeTypeEnum
        from ..models.quota import Quota

        file_nodes = session.execute(
            select(FileNode).where(
                FileNode.is_deleted.is_(True),
                FileNode.deleted_at.is_not(None),
                FileNode.deleted_at < cutoff,
                FileNode.node_type == NodeTypeEnum.FILE.value,
            )
        ).scalars().all()

        # ── 步骤 2：删除 Storage 文件
        import asyncio

        from app.storage.manager import StorageManager

        storage = StorageManager.get_driver()
        affected_tenants: set[int] = set()

        for node in file_nodes:
            if node.storage_key:
                try:
                    asyncio.run(storage.delete(node.storage_key))
                    freed_bytes += node.size_bytes
                except Exception as e:
                    logger.warning(
                        "netdisk cleanup: storage delete failed key=%s: %s",
                        node.storage_key, e,
                    )
            affected_tenants.add(node.tenant_id)

        # ── 步骤 3：物理删除 DB 节点（CASCADE 自动删 shares）
        # 注意：删除后 offset 必须为 0，否则每批删完记录就会跟踊并跳过后续记录
        batch_size = 100
        while True:
            sub = (
                select(FileNode.id)
                .where(
                    FileNode.is_deleted.is_(True),
                    FileNode.deleted_at.is_not(None),
                    FileNode.deleted_at < cutoff,
                )
                .limit(batch_size)
                .subquery()
            )
            result = session.execute(
                sa_delete(FileNode)
                .where(FileNode.id.in_(select(sub.c.id)))
                .execution_options(synchronize_session=False)
            )
            batch_count = result.rowcount
            session.commit()
            if batch_count == 0:
                break
            cleaned_count += batch_count

        # ── 步骤 4：重算受影响企业的 used_bytes
        for tenant_id in affected_tenants:
            actual = session.execute(
                select(func.coalesce(func.sum(FileNode.size_bytes), 0)).where(
                    FileNode.tenant_id == tenant_id,
                    FileNode.is_deleted.is_(False),
                    FileNode.node_type == NodeTypeEnum.FILE.value,
                )
            ).scalar_one() or 0

            session.execute(
                update(Quota)
                .where(Quota.tenant_id == tenant_id)
                .values(used_bytes=actual, updated_at=utc_now())
            )
            tenants_updated += 1

        session.commit()

    except Exception as e:
        logger.error("netdisk cleanup failed: %s", e)
        if session:
            session.rollback()
    finally:
        if session:
            session.close()

    elapsed = time.monotonic() - start
    result = {
        "cleaned_count":  cleaned_count,
        "freed_bytes":    freed_bytes,
        "tenants_updated": tenants_updated,
        "elapsed_seconds": round(elapsed, 2),
    }
    logger.info("netdisk cleanup done: %s", result)
    return result
