"""
Storage Migration Tool Plugin
"""

from sqlalchemy import text

from app.plugins.base import PluginBase


class StorageMigrationPlugin(PluginBase):
    """Cross-driver storage migration tool"""

    async def on_install(self, ctx) -> None:
        ctx.get_logger().info("Storage migration plugin installed")

    async def on_enable(self, ctx) -> None:
        logger = ctx.get_logger()
        logger.info("Storage migration plugin enabled")

        # Recover interrupted tasks: after server restart no background
        # coroutine is running, so mark 'running' tasks as 'paused'.
        try:
            db = ctx.get_db()
            result = await db.execute(
                text("""
                    UPDATE px_storage_migration_tasks
                    SET status = 'paused', updated_at = now(),
                        error_message = 'Interrupted by server restart'
                    WHERE status = 'running'
                """),
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
