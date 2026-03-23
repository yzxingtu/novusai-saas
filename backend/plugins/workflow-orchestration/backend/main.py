from app.plugins.base import PluginBase


class WorkflowOrchestrationPlugin(PluginBase):
    async def on_install(self, ctx) -> None:
        ctx.get_logger().info("Workflow orchestration plugin installed")

    async def on_enable(self, ctx) -> None:
        ctx.get_logger().info("Workflow orchestration plugin enabled")

    async def on_disable(self, ctx) -> None:
        ctx.get_logger().info("Workflow orchestration plugin disabled")

    async def on_uninstall(self, ctx) -> None:
        ctx.get_logger().info("Workflow orchestration plugin uninstalled")

    async def on_upgrade(self, ctx, old_version: str) -> None:
        ctx.get_logger().info(
            "Workflow orchestration plugin upgraded from {}",
            old_version,
        )
