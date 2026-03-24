"""存储迁移工具插件 / Storage Migration Tool Plugin"""

from sqlalchemy import text

from app.plugins.base import PluginBase


class StorageMigrationPlugin(PluginBase):
    """跨驱动存储迁移工具 / Cross-driver storage migration tool"""

    async def on_install(self, ctx) -> None:
        ctx.get_logger().info("Storage migration plugin installed")

    async def on_enable(self, ctx) -> None:
        logger = ctx.get_logger()
        logger.info("Storage migration plugin enabled")

        # Recover interrupted tasks: after server restart no background / 恢复中断任务：重启后内存无后台
        # coroutine is running, so mark 'running' tasks as 'paused'. / 协程，将 running 任务标为 paused
        try:
            db = ctx.get_db()
            result = await db.execute(
                text("""UPDATE px_storage_migration_tasks / 迁移
                    SET status = 'paused', updated_at = now(),
                        error_message = 'Interrupted by server restart'
                    WHERE status = 'running'"""),
            )
            if result.rowcount > 0:
                await db.commit()
                logger.info(
                    "Recovered %d interrupted migration task(s)",
                    result.rowcount,
                )
        except Exception as exc:
            logger.warning("Failed to recover migration tasks: %s", exc)

    async def on_disable(self, ctx) -> None:
        ctx.get_logger().info("Storage migration plugin disabled")

    async def on_uninstall(self, ctx) -> None:
        ctx.get_logger().info("Storage migration plugin uninstalled")
