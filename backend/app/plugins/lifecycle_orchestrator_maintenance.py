"""Maintenance/uninstall helpers extracted from LifecycleOrchestrator."""

from __future__ import annotations

import shutil
from typing import Any

from app.core.base_model import utc_now
from app.core.i18n import _
from app.core.logging import get_logger
from app.core.response import build_public_error_text
from app.enums.plugin import PluginStatusEnum
from app.plugins.exceptions import PluginDependencyError
from app.plugins.loader import PLUGINS_DIR
from app.plugins.runtime_recovery import is_schedule_refresh_error_message

logger = get_logger(__name__)


class LifecycleOrchestratorMaintenanceMixin:
    """Scheduler/dependency/uninstall helpers for LifecycleOrchestrator."""
    async def refresh_schedules_impl(self, plugin_id: int) -> dict[str, Any]:
        """Reconcile plugin task definitions with the in-process scheduler."""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel
        from app.plugins.scheduler_refresh import refresh_plugin_schedule_or_raise

        lifecycle = self._lifecycle
        result = await lifecycle._db.execute(
            select(PluginModel).where(
                PluginModel.id == plugin_id,
                PluginModel.is_deleted.is_(False),
            )
        )
        plugin = result.scalar_one_or_none()
        if not plugin:
            from app.plugins.exceptions import PluginNotFoundError

            raise PluginNotFoundError(message=f"Plugin ID {plugin_id} not found")

        manifest = lifecycle._loader.load_manifest(plugin.name)
        tasks = list(manifest.extensions.tasks or [])
        mode = "refresh_only"

        if tasks:
            if plugin.status == PluginStatusEnum.ENABLED.value:
                await lifecycle._sync_plugin_task_definitions(plugin.name, tasks)
                mode = "sync_enabled"
            elif (
                plugin.status == PluginStatusEnum.ERROR.value
                and is_schedule_refresh_error_message(plugin.error_message)
            ):
                await lifecycle._sync_plugin_task_definitions(plugin.name, tasks)
                mode = "recover_error"
            elif plugin.status == PluginStatusEnum.DISABLED.value:
                await lifecycle._deactivate_plugin_task_definitions(plugin.name)
                mode = "sync_disabled"
            elif plugin.status == PluginStatusEnum.INSTALLED.value:
                await lifecycle._delete_plugin_task_definitions(plugin.name)
                mode = "cleanup_installed"
            else:
                refresh_plugin_schedule_or_raise(
                    plugin.name,
                    action="manual_recovery",
                )
                mode = "refresh_error_state"
        else:
            refresh_plugin_schedule_or_raise(
                plugin.name,
                action="manual_recovery",
            )

        if is_schedule_refresh_error_message(plugin.error_message):
            plugin.error_message = None
            plugin.error_count = 0
            if plugin.status == PluginStatusEnum.ERROR.value and tasks:
                plugin.status = PluginStatusEnum.ENABLED.value
                plugin.enabled_at = plugin.enabled_at or utc_now()
            await lifecycle._db.flush()

        logger.info(
            "Plugin {}: scheduler reconciliation completed with mode {}",
            plugin.name,
            mode,
        )
        return {
            "mode": mode,
            "plugin_id": plugin.id,
            "plugin_name": plugin.name,
            "task_count": len(tasks),
        }

    async def install_dependencies_impl(
        self,
        plugin_id: int,
        *,
        install_python: bool = True,
    ) -> dict[str, Any]:
        """Install plugin dependencies without changing lifecycle status."""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel
        from app.plugins.exceptions import PluginNotFoundError

        lifecycle = self._lifecycle
        result = await lifecycle._db.execute(
            select(PluginModel).where(
                PluginModel.id == plugin_id,
                PluginModel.is_deleted.is_(False),
            )
        )
        plugin = result.scalar_one_or_none()
        if not plugin:
            raise PluginNotFoundError(message=f"Plugin ID {plugin_id} not found")

        manifest = lifecycle._loader.load_manifest(plugin.name)
        py_deps = list(manifest.dependencies.python or [])
        installed_python: list[str] = []
        plugin_states = await lifecycle._collect_plugin_dependency_states(
            manifest,
            require_enabled=False,
        )
        python_preflight = await lifecycle._ensure_python_dependency_preflight(
            plugin.name,
            py_deps,
        )

        if install_python and py_deps:
            installed_python = await lifecycle.dependencies.install_python_dependencies(
                plugin.name,
                py_deps,
            )

        return {
            "plugin_id": plugin.id,
            "plugin_name": plugin.name,
            "python": {
                "declared": py_deps,
                "installed": installed_python,
                "installed_count": len(installed_python),
                "preflight": python_preflight,
            },
            "plugins": plugin_states,
        }

    async def uninstall_dependencies_impl(
        self,
        plugin_id: int,
        *,
        uninstall_python: bool = True,
    ) -> dict[str, Any]:
        """Uninstall plugin dependencies without deleting plugin row/files."""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel
        from app.plugins.exceptions import PluginNotFoundError

        lifecycle = self._lifecycle
        result = await lifecycle._db.execute(
            select(PluginModel).where(
                PluginModel.id == plugin_id,
                PluginModel.is_deleted.is_(False),
            )
        )
        plugin = result.scalar_one_or_none()
        if not plugin:
            raise PluginNotFoundError(message=f"Plugin ID {plugin_id} not found")

        if plugin.status == PluginStatusEnum.ENABLED.value:
            raise PluginDependencyError(
                message=(
                    f"Cannot uninstall dependencies while plugin '{plugin.name}' is enabled. "
                    "Disable plugin first."
                ),
            )

        manifest = lifecycle._loader.load_manifest(plugin.name)
        py_deps = list(plugin.installed_packages or manifest.dependencies.python or [])
        plugin_states = await lifecycle._collect_plugin_dependency_states(
            manifest,
            require_enabled=False,
        )
        if uninstall_python and py_deps:
            await lifecycle.dependencies.uninstall_python_dependencies(
                plugin.name,
                py_deps,
            )

        return {
            "plugin_id": plugin.id,
            "plugin_name": plugin.name,
            "python": {
                "declared": py_deps,
                "attempted": uninstall_python,
            },
            "plugins": plugin_states,
        }

    async def uninstall_impl(
        self,
        plugin_id: int,
        *,
        cleanup_dependencies: bool = False,
        operator_id: int | None = None,
    ) -> None:
        """Uninstall plugin runtime, DB records, and plugin files."""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel
        from app.plugins.context_factory import create_plugin_context
        from app.plugins.registry import ExtensionRegistry

        lifecycle = self._lifecycle
        result = await lifecycle._db.execute(
            select(PluginModel).where(
                PluginModel.id == plugin_id,
                PluginModel.is_deleted.is_(False),
            )
        )
        plugin = result.scalar_one_or_none()
        if not plugin:
            from app.plugins.exceptions import PluginNotFoundError

            raise PluginNotFoundError(message=f"Plugin ID {plugin_id} not found")

        plugin_name = plugin.name

        from app.plugins.progress import PluginProgressEmitter

        emitter = PluginProgressEmitter(operator_id, plugin_name, "uninstall")

        dependents = await lifecycle._get_dependents(plugin_name)
        if dependents:
            raise PluginDependencyError(
                message=(
                    f"Cannot uninstall '{plugin_name}': plugins "
                    f"[{', '.join(dep['plugin'] for dep in dependents)}] depend on it. "
                    "Uninstall them first."
                ),
            )

        await lifecycle.guards.run(
            operation="uninstall",
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            force=False,
            manifest=plugin.manifest or {},
        )

        if plugin.status == PluginStatusEnum.ENABLED.value:
            await emitter.emit_step("disable", "running", "Disabling plugin...")
            await lifecycle._disable_impl(plugin_id, skip_lifecycle_guards=True)
            await emitter.emit_step("disable", "success", "Plugin disabled")

        manifest = lifecycle._loader.load_manifest(plugin_name)
        await emitter.emit_step("on_uninstall", "running", "Running uninstall hook...")
        try:
            plugin_cls = lifecycle._loader.load_plugin_class(plugin_name)
            ctx = create_plugin_context(
                plugin_name=plugin_name,
                manifest=manifest,
                db=lifecycle._db,
                granted_capabilities=plugin.granted_capabilities or [],
            )
            await plugin_cls().on_uninstall(ctx)
            await emitter.emit_step(
                "on_uninstall",
                "success",
                "Uninstall hook completed",
            )
        except Exception as exc:
            await emitter.emit_step(
                "on_uninstall",
                "warning",
                build_public_error_text(
                    exc=exc,
                    message=_("common.server_error"),
                ),
            )
            logger.warning("Plugin {} on_uninstall failed: {}", plugin_name, exc)

        await emitter.emit_step(
            "extensions",
            "running",
            "Cleaning plugin runtime state...",
        )
        ExtensionRegistry.get_instance().unregister_all(plugin_name)
        await emitter.emit_step(
            "extensions",
            "success",
            "Plugin runtime state cleaned",
        )

        if cleanup_dependencies:
            py_deps = list(
                plugin.installed_packages or manifest.dependencies.python or []
            )
            if py_deps:
                await emitter.emit_step(
                    "dependencies",
                    "running",
                    "Removing plugin Python dependencies...",
                )
                await lifecycle.dependencies.uninstall_python_dependencies(
                    plugin_name,
                    py_deps,
                )
                await emitter.emit_step(
                    "dependencies",
                    "success",
                    "Plugin Python dependencies removed",
                )

        await emitter.emit_step(
            "database",
            "running",
            "Cleaning plugin database resources...",
        )
        await lifecycle._cleanup_plugin_database(plugin_name)
        await emitter.emit_step(
            "database",
            "success",
            "Plugin database resources removed",
        )

        await emitter.emit_step(
            "cleanup_records",
            "running",
            "Removing plugin records...",
        )
        await lifecycle._delete_plugin_task_definitions(plugin_name)
        await lifecycle._delete_plugin_notification_templates(plugin_name)
        await lifecycle._delete_plugin_permissions_from_db(plugin_name)
        await lifecycle._delete_plugin_skill_records(plugin_name)
        await lifecycle.cleanup.remove_relational_records(plugin_id)
        await emitter.emit_step(
            "cleanup_records",
            "success",
            "Plugin records removed",
        )

        await emitter.emit_step(
            "cleanup_files",
            "running",
            "Removing plugin files...",
        )
        await lifecycle.cleanup.remove_plugin_row(plugin_id)
        await lifecycle._db.flush()

        plugin_dir = PLUGINS_DIR / plugin_name
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir, ignore_errors=True)

        from app.plugins.module_loader import unload_plugin_modules

        unload_plugin_modules(plugin_name)
        await emitter.emit_step(
            "cleanup_files",
            "success",
            "Plugin files removed",
        )

        logger.info("Plugin {} uninstalled completely", plugin_name)
        await emitter.emit_done(f"Plugin {plugin_name} uninstalled completely")
