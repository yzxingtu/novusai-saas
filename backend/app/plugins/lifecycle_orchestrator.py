"""Lifecycle orchestrator helpers extracted from PluginLifecycle."""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any

from app.core.base_model import utc_now
from app.core.i18n import _
from app.core.logging import get_logger
from app.core.response import build_public_error_text, resolve_public_error_message
from app.enums.plugin import PluginStatusEnum
from app.plugins.exceptions import PluginDependencyError, PluginError
from app.plugins.lifecycle_guards import run_plugin_lifecycle_guards

if TYPE_CHECKING:
    from app.plugins.lifecycle import PluginLifecycle

logger = get_logger(__name__)
from app.plugins.lifecycle_orchestrator_maintenance import (  # noqa: E402
    LifecycleOrchestratorMaintenanceMixin,
)


class LifecycleOrchestrator(LifecycleOrchestratorMaintenanceMixin):
    """Guard/dependency/permission orchestration for lifecycle enable-like flows."""

    def __init__(self, lifecycle: PluginLifecycle) -> None:
        self._lifecycle = lifecycle

    async def run_lifecycle_guards(
        self,
        *,
        operation: str,
        plugin_id: int,
        plugin_name: str,
        force: bool,
        manifest: dict[str, Any] | None,
    ) -> None:
        result = await run_plugin_lifecycle_guards(
            {
                "operation": operation,
                "plugin_id": plugin_id,
                "plugin_name": plugin_name,
                "force": force,
                "manifest": dict(manifest or {}),
            }
        )
        if result.get("allowed", True):
            return

        raise PluginError(
            message=result.get("message") or f"Plugin {operation} blocked",
            data={
                "reason_code": result.get("reason_code") or "lifecycle_blocked",
                "details": result.get("details") or {},
                "operation": operation,
                "plugin_id": plugin_id,
                "plugin_name": plugin_name,
            },
        )

    async def collect_plugin_dependency_states(
        self,
        manifest_or_data: object,
        *,
        require_enabled: bool,
    ) -> list[dict[str, object]]:
        return await self._lifecycle.read_models.collect_dependency_states(
            manifest_or_data,
            require_enabled=require_enabled,
        )

    @staticmethod
    def summarize_plugin_dependency_errors(
        states: list[dict[str, object]],
    ) -> list[str]:
        errors: list[str] = []
        for state in states:
            if state.get("state") == "ready":
                continue
            message = str(state.get("message") or "").strip()
            if message:
                errors.append(message)
        return errors

    async def assert_plugin_dependencies_ready(
        self,
        manifest_or_data: object,
        *,
        plugin_name: str,
        require_enabled: bool,
        error_cls: type[PluginError],
        action: str,
    ) -> list[dict[str, object]]:
        states = await self.collect_plugin_dependency_states(
            manifest_or_data,
            require_enabled=require_enabled,
        )
        errors = self.summarize_plugin_dependency_errors(states)
        if errors:
            verb = "enabled" if require_enabled else "installed"
            raise error_cls(
                message=(
                    f"Cannot {action} '{plugin_name}': plugin dependencies are not "
                    f"{verb}: {'; '.join(errors)}"
                ),
            )
        return states

    @staticmethod
    def count_declared_plugin_permissions(manifest: object) -> tuple[int, int]:
        extensions = getattr(manifest, "extensions", None)
        frontend = getattr(extensions, "frontend", None)
        pages = getattr(frontend, "pages", None) or []
        permission_exts = getattr(extensions, "permissions", None) or []

        total_declared = 0
        tenant_declared = 0

        for page in pages:
            if getattr(page, "menu", None) is None:
                continue
            total_declared += 1
            if str(getattr(page, "scope", "") or "").strip().lower() == "tenant":
                tenant_declared += 1

        for perm_ext in permission_exts:
            actions = [
                str(action).strip()
                for action in (getattr(perm_ext, "actions", None) or [])
                if str(action or "").strip()
            ]
            if not actions:
                continue

            action_count = len(actions)
            total_declared += action_count

            scope = str(getattr(perm_ext, "scope", "") or "").strip().lower()
            if scope in {"both", "tenant"}:
                tenant_declared += action_count

        return total_declared, tenant_declared

    async def assert_plugin_enable_prerequisites(
        self,
        plugin: object,
        manifest: object,
        *,
        action: str,
        error_cls: type[PluginError],
    ) -> None:
        plugin_name = str(getattr(plugin, "name", "") or "").strip()
        plugin_id = int(plugin.id)
        pricing_type = str(getattr(plugin, "pricing_type", "") or "").strip()

        from app.plugins.license import assert_plugin_license_active

        await assert_plugin_license_active(
            plugin_id,
            pricing_type,
            self._lifecycle._db,
            plugin_name=plugin_name,
            operation=action,
        )

        if manifest.compatibility and manifest.compatibility.conflicts:
            from sqlalchemy import select

            from app.models.system.plugin import Plugin as PluginModel

            for conflict in manifest.compatibility.conflicts:
                dep_result = await self._lifecycle._db.execute(
                    select(PluginModel.status).where(
                        PluginModel.name == conflict.plugin,
                        PluginModel.is_deleted.is_(False),
                    )
                )
                dep_status = dep_result.scalar_one_or_none()
                if dep_status == PluginStatusEnum.ENABLED.value:
                    conflict_reason = (
                        (
                            conflict.reason.get("zh-CN")
                            or conflict.reason.get("en")
                            or "incompatible"
                        )
                        if conflict.reason
                        else "incompatible"
                    )
                    raise error_cls(
                        message=(
                            f"Cannot {action} '{plugin_name}': conflicts with enabled plugin "
                            f"'{conflict.plugin}' ({conflict_reason}). Disable it first."
                        ),
                    )

        await self._lifecycle.dependencies.assert_plugin_dependencies_ready(
            manifest,
            plugin_name=plugin_name,
            require_enabled=True,
            error_cls=error_cls,
            action=action,
        )

    async def ensure_plugin_permissions_active(
        self,
        plugin_name: str,
        manifest: object,
        *,
        action: str,
    ) -> None:
        declared_permissions, tenant_declared_permissions = (
            self.count_declared_plugin_permissions(manifest)
        )

        from app.rbac.sync import PermissionSyncService

        perm_sync = PermissionSyncService(self._lifecycle._db)
        async with self._lifecycle._db.begin_nested():
            synced_count = await perm_sync.sync_plugin_permissions(plugin_name)

        if declared_permissions > 0 and synced_count <= 0:
            raise PluginError(
                message=(
                    f"Cannot {action} '{plugin_name}': expected {declared_permissions} "
                    "plugin permission/menu declaration(s) to sync into DB, but none were written."
                ),
            )

        enabled_count = await self._lifecycle.permissions.set_enabled(plugin_name, True)
        if declared_permissions > 0 and enabled_count <= 0:
            raise PluginError(
                message=(
                    f"Cannot {action} '{plugin_name}': expected {declared_permissions} "
                    "plugin permission/menu row(s) to be enabled, but no DB rows matched."
                ),
            )

        await self._lifecycle.permissions.auto_grant_plan_menus(
            plugin_name,
            expected_tenant_permissions=tenant_declared_permissions,
            action=action,
        )

    async def enable_impl(
        self,
        plugin_id: int,
        *,
        operator_id: int | None = None,
    ) -> None:
        """Enable plugin runtime after lock acquisition."""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel
        from app.plugins.context_factory import create_plugin_context
        from app.plugins.frontend_contract import validate_runtime_frontend_contract
        from app.plugins.progress import PluginProgressEmitter
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

        if plugin.status == PluginStatusEnum.ENABLED.value:
            return

        plugin_name = plugin.name
        emitter = PluginProgressEmitter(operator_id, plugin_name, "enable")
        plugin_dir = lifecycle._loader.plugins_dir / plugin_name
        await emitter.emit_step(
            "security_scan",
            "running",
            "Running plugin security scan...",
        )
        try:
            from app.plugins.security_scan import assert_plugin_security_clean

            assert_plugin_security_clean(
                plugin_dir,
                plugin_name=plugin_name,
                action="enable",
            )
            await emitter.emit_step(
                "security_scan",
                "success",
                "Security scan passed",
            )
        except Exception as exc:
            err_msg = resolve_public_error_message(
                exc,
                fallback_message=_("plugin.error.security_violation"),
            )
            plugin.status = PluginStatusEnum.ERROR.value
            plugin.error_message = err_msg
            plugin.error_count = (plugin.error_count or 0) + 1
            await lifecycle._db.flush()
            await emitter.emit_error(
                build_public_error_text(
                    exc=exc,
                    message=_("plugin.error.security_violation"),
                )
            )
            raise

        manifest = lifecycle._loader.load_manifest(plugin_name)
        validate_runtime_frontend_contract(
            lifecycle._loader.plugins_dir / plugin_name,
            manifest,
        )

        await lifecycle._assert_plugin_runtime_enable_guards(
            plugin,
            manifest,
            action="enable",
        )

        migrations_dir = (
            lifecycle._loader.plugins_dir
            / plugin_name
            / "backend"
            / "migrations"
            / "versions"
        )
        if migrations_dir.is_dir():
            await emitter.emit_step(
                "alembic",
                "running",
                "Running database migrations...",
            )
            try:
                await lifecycle.run_alembic_upgrade(plugin_name)
                await emitter.emit_step(
                    "alembic",
                    "success",
                    "Database migrations complete",
                )
            except Exception as exc:
                err_msg = resolve_public_error_message(
                    exc,
                    fallback_message=_("common.server_error"),
                )
                plugin.status = PluginStatusEnum.ERROR.value
                plugin.error_message = err_msg
                plugin.error_count = (plugin.error_count or 0) + 1
                await lifecycle._db.flush()
                await emitter.emit_step(
                    "alembic",
                    "error",
                    build_public_error_text(
                        exc=exc,
                        message=_("common.server_error"),
                    ),
                )
                raise PluginError(message=err_msg) from exc
        else:
            await emitter.emit_step("alembic", "success", "No database migrations")

        if manifest.dependencies.python:
            await emitter.emit_step(
                "pip",
                "running",
                f"Checking {len(manifest.dependencies.python)} Python package(s)...",
            )
            try:
                pip_installed = await lifecycle.dependencies.install_python_dependencies(
                    plugin_name,
                    manifest.dependencies.python,
                )
            except Exception as exc:
                await emitter.emit_error(
                    build_public_error_text(
                        exc=exc,
                        message=_("plugin.error.dependency_failed"),
                    )
                )
                raise
            if pip_installed:
                await emitter.emit_step(
                    "pip",
                    "success",
                    f"Installed {len(pip_installed)} package(s)",
                )
            else:
                await emitter.emit_step(
                    "pip",
                    "success",
                    "Python dependencies already satisfied",
                )
        else:
            await emitter.emit_step("pip", "success", "No Python dependencies")

        await emitter.emit_step("extensions", "running", "Registering extensions...")
        registry = ExtensionRegistry.get_instance()

        from app.plugins._extension_registrar import (
            get_failed_extensions,
            register_all_extensions,
        )

        menu_overrides = (plugin.config or {}).get("menu_overrides")
        register_all_extensions(
            registry,
            manifest,
            plugin_name,
            menu_overrides=menu_overrides,
        )

        failed = get_failed_extensions(plugin_name)
        if failed:
            registry.unregister_all(plugin_name)
            failed_summary = "; ".join(
                f"{item['type']}:{item['entry_point']}" for item in failed[:5]
            )
            plugin.status = PluginStatusEnum.ERROR.value
            plugin.error_message = f"Extension load failed: {failed_summary}"
            plugin.error_count = (plugin.error_count or 0) + 1
            await lifecycle._db.flush()
            await emitter.emit_error(f"{len(failed)} extension(s) failed to load")
            raise PluginError(
                message=(
                    f"Cannot enable '{plugin_name}': {len(failed)} extension(s) "
                    f"failed to load: {failed_summary}"
                ),
            )

        ext = manifest.extensions
        if ext.skills:
            await lifecycle._ensure_plugin_skill_records(
                plugin_name,
                manifest,
                ext.skills,
                active=True,
            )

        if manifest.ai_requirements and manifest.ai_requirements.features:
            await lifecycle._ensure_plugin_ai_features(
                plugin_name,
                manifest.ai_requirements.features,
            )

        if ext.notifications:
            await lifecycle._sync_plugin_notification_templates(
                plugin_name,
                ext.notifications,
            )

        if ext.tasks:
            try:
                await lifecycle._sync_plugin_task_definitions(
                    plugin_name,
                    ext.tasks,
                )
            except Exception as exc:
                registry.unregister_all(plugin_name)
                plugin.status = PluginStatusEnum.ERROR.value
                plugin.enabled_at = None
                plugin.error_message = resolve_public_error_message(
                    exc,
                    fallback_message=_("plugin.error.schedule_refresh_failed").format(
                        plugin_name=plugin_name,
                        action="enable",
                    ),
                )
                plugin.error_count = (plugin.error_count or 0) + 1
                await lifecycle._db.flush()
                await emitter.emit_error(
                    build_public_error_text(
                        exc=exc,
                        message=_("plugin.error.schedule_refresh_failed").format(
                            plugin_name=plugin_name,
                            action="enable",
                        ),
                    )
                )
                raise PluginError(message=plugin.error_message) from exc

        await emitter.emit_step(
            "extensions",
            "success",
            f"Registered {registry.get_registered_count(plugin_name)} extension(s)",
        )

        await emitter.emit_step("on_enable", "running", "Running enable hook...")
        try:
            plugin_cls = lifecycle._loader.load_plugin_class(plugin_name)
            ctx = create_plugin_context(
                plugin_name=plugin_name,
                manifest=manifest,
                db=lifecycle._db,
                granted_capabilities=plugin.granted_capabilities or [],
            )
            await plugin_cls().on_enable(ctx)
            await emitter.emit_step("on_enable", "success", "Enable hook completed")
        except Exception as exc:
            logger.warning("Plugin {} on_enable failed: {}", plugin_name, exc)
            registry.unregister_all(plugin_name)
            plugin.status = PluginStatusEnum.ERROR.value
            plugin.error_message = resolve_public_error_message(
                exc,
                fallback_message=_("common.server_error"),
            )
            plugin.error_count = (plugin.error_count or 0) + 1
            await lifecycle._db.flush()
            await emitter.emit_error(
                build_public_error_text(
                    exc=exc,
                    message=_("common.server_error"),
                )
            )
            raise PluginError(
                message=resolve_public_error_message(
                    exc,
                    fallback_message=_("common.server_error"),
                ),
            ) from exc

        try:
            await lifecycle.permissions.restore(plugin_name)
        except Exception as exc:
            logger.warning(
                "Plugin {}: failed to restore plugin permissions during enable: {}",
                plugin_name,
                exc,
            )
            registry.unregister_all(plugin_name)
            with suppress(Exception):
                await lifecycle.permissions.set_enabled(plugin_name, False)
            plugin.status = PluginStatusEnum.ERROR.value
            plugin.error_message = resolve_public_error_message(
                exc,
                fallback_message=_("common.server_error"),
            )
            plugin.error_count = (plugin.error_count or 0) + 1
            await lifecycle._db.flush()
            await emitter.emit_error(
                build_public_error_text(
                    exc=exc,
                    message=_("common.server_error"),
                )
            )
            raise PluginError(
                message=resolve_public_error_message(
                    exc,
                    fallback_message=_("common.server_error"),
                ),
            ) from exc

        plugin.status = PluginStatusEnum.ENABLED.value
        plugin.enabled_at = utc_now()
        plugin.error_message = None
        plugin.error_count = 0
        await lifecycle._db.flush()

        from app.plugins.api_dispatcher import _compile_route_regex

        _compile_route_regex.cache_clear()

        await emitter.emit_done(f"Plugin {plugin_name} enabled successfully")
        logger.info("Plugin {} enabled", plugin_name)

        try:
            from app.plugins.system_hooks import SystemHookPoint, trigger_hook

            await trigger_hook(
                SystemHookPoint.PLUGIN_ENABLED,
                plugin_name=plugin_name,
                plugin_id=plugin_id,
            )
        except Exception as exc:
            logger.warning("system_hook PLUGIN_ENABLED failed: {}", exc)

    async def repair_impl(
        self,
        plugin_id: int,
        *,
        operator_id: int | None = None,
    ) -> None:
        """Repair plugin runtime by replaying enable-side orchestration."""
        from sqlalchemy import select

        from app.exceptions.base import BusinessException
        from app.models.system.plugin import Plugin as PluginModel
        from app.plugins._extension_registrar import (
            get_failed_extensions,
            register_all_extensions,
        )
        from app.plugins.exceptions import PluginNotFoundError
        from app.plugins.frontend_contract import validate_runtime_frontend_contract
        from app.plugins.progress import PluginProgressEmitter
        from app.plugins.registry import ExtensionRegistry

        lifecycle = self._lifecycle
        result = await lifecycle._db.execute(
            select(PluginModel).where(
                PluginModel.id == plugin_id,
                PluginModel.is_deleted.is_(False),
            )
        )
        plugin = result.scalar_one_or_none()
        if plugin is None:
            raise PluginNotFoundError(message=f"Plugin ID {plugin_id} not found")

        if plugin.status not in (
            PluginStatusEnum.ERROR.value,
            PluginStatusEnum.ENABLED.value,
        ):
            raise BusinessException(message=_("plugin.error.repair_not_needed"))

        plugin_name = plugin.name
        emitter = PluginProgressEmitter(operator_id, plugin_name, "enable")
        registry = ExtensionRegistry.get_instance()
        try:
            manifest = lifecycle._loader.load_manifest(plugin_name)
            validate_runtime_frontend_contract(
                lifecycle._loader.plugins_dir / plugin_name,
                manifest,
            )
            await lifecycle._assert_plugin_runtime_enable_guards(
                plugin,
                manifest,
                action="repair",
            )

            if manifest.dependencies.python:
                await emitter.emit_step(
                    "pip",
                    "running",
                    f"Checking {len(manifest.dependencies.python)} Python package(s)...",
                )
                pip_installed = await lifecycle.dependencies.install_python_dependencies(
                    plugin_name,
                    manifest.dependencies.python,
                )
                if pip_installed:
                    await emitter.emit_step(
                        "pip",
                        "success",
                        f"Installed {len(pip_installed)} package(s)",
                    )
                else:
                    await emitter.emit_step(
                        "pip",
                        "success",
                        "Python dependencies already satisfied",
                    )
            else:
                await emitter.emit_step("pip", "success", "No Python dependencies")

            migrations_dir = (
                lifecycle._loader.plugins_dir
                / plugin_name
                / "backend"
                / "migrations"
                / "versions"
            )
            if migrations_dir.is_dir():
                await emitter.emit_step(
                    "alembic",
                    "running",
                    "Ensuring database tables...",
                )
                try:
                    await lifecycle.run_alembic_upgrade(plugin_name)
                    await emitter.emit_step(
                        "alembic",
                        "success",
                        "Database tables verified",
                    )
                except Exception as alembic_exc:
                    await emitter.emit_step(
                        "alembic",
                        "error",
                        build_public_error_text(
                            message=_("plugin.error.db_migration_failed"),
                            exc=alembic_exc,
                        ),
                    )
                    raise

            await emitter.emit_step(
                "extensions",
                "running",
                "Registering extensions...",
            )
            menu_overrides = (plugin.config or {}).get("menu_overrides")
            register_all_extensions(
                registry,
                manifest,
                plugin_name,
                menu_overrides=menu_overrides,
            )

            failed = get_failed_extensions(plugin_name)
            if failed:
                failed_summary = "; ".join(
                    f"{item['type']}:{item['entry_point']}" for item in failed[:5]
                )
                plugin.status = PluginStatusEnum.ERROR.value
                plugin.error_message = (
                    f"Repair failed: extension load failed: {failed_summary}"
                )
                plugin.error_count = (plugin.error_count or 0) + 1
                await lifecycle._fail_close_plugin_runtime(
                    plugin_name,
                    registry=registry,
                )
                await lifecycle._db.flush()
                await emitter.emit_error(f"{len(failed)} extension(s) failed to load")
                raise BusinessException(
                    message=_("plugin.error.repair_extensions_failed").format(
                        count=len(failed),
                    )
                )

            await emitter.emit_step(
                "extensions",
                "success",
                f"Registered {registry.get_registered_count(plugin_name)} extension(s)",
            )

            ext = manifest.extensions
            if ext.skills:
                await lifecycle._ensure_plugin_skill_records(
                    plugin_name,
                    manifest,
                    ext.skills,
                    active=True,
                )
            if manifest.ai_requirements and manifest.ai_requirements.features:
                await lifecycle._ensure_plugin_ai_features(
                    plugin_name,
                    manifest.ai_requirements.features,
                )
            if ext.notifications:
                await lifecycle._sync_plugin_notification_templates(
                    plugin_name,
                    ext.notifications,
                )
            if ext.tasks:
                await lifecycle._sync_plugin_task_definitions(
                    plugin_name,
                    ext.tasks,
                )

            await lifecycle._restore_plugin_permissions(
                plugin_name,
                auto_grant_plans=True,
            )

            plugin.status = PluginStatusEnum.ENABLED.value
            plugin.error_count = 0
            plugin.error_message = None
            await lifecycle._db.flush()

            await emitter.emit_done(
                _("plugin.repaired_successfully").format(
                    plugin_name=plugin_name,
                )
            )
            logger.info("Plugin {} repaired and restored", plugin_name)
        except BusinessException:
            raise
        except Exception as exc:
            plugin.status = PluginStatusEnum.ERROR.value
            plugin.error_count = (plugin.error_count or 0) + 1
            plugin.error_message = resolve_public_error_message(
                exc,
                fallback_message=_("plugin.error.repair_failed"),
            )
            await lifecycle._fail_close_plugin_runtime(plugin_name, registry=registry)
            await lifecycle._db.flush()
            await emitter.emit_error(
                build_public_error_text(
                    message=_("plugin.error.repair_failed"),
                    exc=exc,
                )
            )
            raise BusinessException(
                message=resolve_public_error_message(
                    exc,
                    fallback_message=_("plugin.error.repair_failed"),
                )
            ) from exc

    async def disable_impl(
        self,
        plugin_id: int,
        *,
        force: bool = False,
        operator_id: int | None = None,
        skip_lifecycle_guards: bool = False,
    ) -> None:
        """Disable plugin runtime after lock acquisition."""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel
        from app.plugins.context_factory import create_plugin_context
        from app.plugins.progress import PluginProgressEmitter
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

        if plugin.status == PluginStatusEnum.DISABLED.value:
            return

        plugin_name = plugin.name
        emitter = PluginProgressEmitter(operator_id, plugin_name, "disable")

        dependents = await lifecycle._get_dependents(
            plugin_name,
            statuses={PluginStatusEnum.ENABLED.value},
        )
        if dependents:
            raise PluginDependencyError(
                message=(
                    f"Cannot disable '{plugin_name}': plugins "
                    f"[{', '.join(dep['plugin'] for dep in dependents)}] depend on it. "
                    "Disable them first."
                ),
            )

        if not skip_lifecycle_guards:
            await lifecycle.guards.run(
                operation="disable",
                plugin_id=plugin_id,
                plugin_name=plugin_name,
                force=force,
                manifest=plugin.manifest or {},
            )

        await lifecycle._check_storage_driver_in_use(
            plugin_name,
            plugin.manifest or {},
            force=force,
        )

        await emitter.emit_step("extensions", "running", "Unregistering extensions...")
        ExtensionRegistry.get_instance().unregister_all(plugin_name)
        await emitter.emit_step("extensions", "success", "Extensions unregistered")

        await emitter.emit_step("skills", "running", "Deactivating skill records...")
        await lifecycle._deactivate_plugin_skill_records(plugin_name)
        await emitter.emit_step("skills", "success", "Skill records deactivated")

        await emitter.emit_step("on_disable", "running", "Running disable hook...")
        try:
            manifest = lifecycle._loader.load_manifest(plugin_name)
            plugin_cls = lifecycle._loader.load_plugin_class(plugin_name)
            ctx = create_plugin_context(
                plugin_name=plugin_name,
                manifest=manifest,
                db=lifecycle._db,
                granted_capabilities=plugin.granted_capabilities or [],
            )
            await plugin_cls().on_disable(ctx)
            await emitter.emit_step("on_disable", "success", "Disable hook completed")
        except Exception as exc:
            logger.warning("Plugin {} on_disable failed: {}", plugin_name, exc)
            await emitter.emit_step(
                "on_disable",
                "success",
                build_public_error_text(
                    exc=exc,
                    message=_("common.server_error"),
                ),
            )

        await emitter.emit_step("tasks", "running", "Deactivating scheduled tasks...")
        await lifecycle._deactivate_plugin_task_definitions(plugin_name)
        await emitter.emit_step("tasks", "success", "Scheduled tasks deactivated")

        plugin.status = PluginStatusEnum.DISABLED.value
        plugin.enabled_at = None
        await lifecycle._db.flush()

        await emitter.emit_step(
            "permissions",
            "running",
            "Disabling plugin permissions...",
        )
        await lifecycle.permissions.set_enabled(plugin_name, False)

        try:
            await lifecycle.permissions.revoke_plan_menus(plugin_name)
        except Exception as exc:
            logger.warning(
                "Plugin {}: failed to revoke permissions from plans: {}",
                plugin_name,
                exc,
            )

        await emitter.emit_step("permissions", "success", "Plugin permissions disabled")

        await emitter.emit_done(f"Plugin {plugin_name} disabled successfully")
        logger.info("Plugin {} disabled", plugin_name)

        try:
            from app.plugins.system_hooks import SystemHookPoint, trigger_hook

            await trigger_hook(
                SystemHookPoint.PLUGIN_DISABLED,
                plugin_name=plugin_name,
                plugin_id=plugin_id,
            )
        except Exception as exc:
            logger.warning("system_hook PLUGIN_DISABLED failed: {}", exc)
