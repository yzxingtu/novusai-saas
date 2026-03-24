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

        # Recover interrupted tasks on process restart.
        # Running migrations can be resumed safely, but interrupted rollbacks
        # require manual verification before another destructive action.
        try:
            db = ctx.get_db()
            result = await db.execute(
                text(
                    """
                    UPDATE px_storage_migration_tasks
                    SET status = CASE
                            WHEN status = 'running' THEN 'paused'
                            ELSE 'failed'
                        END,
                        updated_at = now(),
                        error_message = CASE
                            WHEN status = 'running'
                                THEN 'Interrupted by server restart; review and resume when ready'
                            ELSE 'Rollback interrupted by server restart; verify data before retrying rollback'
                        END
                    WHERE status IN ('running', 'rolling_back')
                    """
                ),
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
