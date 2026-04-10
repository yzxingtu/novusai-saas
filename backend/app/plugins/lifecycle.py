"""
Plugin lifecycle management / 插件生命周期管理

Four core operations: install / enable / disable / uninstall.
/ install / enable / disable / uninstall 四个核心操作。
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from app.core.logging import get_logger
from app.plugins import dependencies as _plugin_dependencies
from app.plugins import lifecycle_support as _lifecycle_support
from app.plugins.exceptions import (
    PluginError,
)
from app.plugins.lifecycle_guards import run_plugin_lifecycle_guards
from app.plugins.lifecycle_orchestrator import LifecycleOrchestrator
from app.plugins.loader import PluginLoader
from app.services.system.plugin_cleanup_service import PluginCleanupService
from app.services.system.plugin_read_model_service import PluginReadModelService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


logger = get_logger(__name__)
_UNLOCK_IF_OWNER_LUA = _lifecycle_support._UNLOCK_IF_OWNER_LUA
# Compatibility re-exports for tests and maintenance code that still patch/import these names.
_escape_like_pattern = _lifecycle_support.escape_like_pattern
_is_safe_plugin_table_name = _lifecycle_support.is_safe_plugin_table_name
detect_direct_python_dependency_conflicts = (
    _plugin_dependencies.detect_direct_python_dependency_conflicts
)
get_installed_distribution_version = (
    _plugin_dependencies.get_installed_distribution_version
)
iter_effective_python_requirements = (
    _plugin_dependencies.iter_effective_python_requirements
)
normalize_python_package_name = _plugin_dependencies.normalize_python_package_name


def _log_lifecycle_action(
    action: str,
    plugin_name: str,
    duration_ms: int,
    success: bool = True,
    detail: str = "",
):
    """
    Unified plugin lifecycle action log (structured fields for log search and monitoring) / 统一的插件生命周期操作日志（结构化字段，便于日志检索和监控）
    """
    status = "ok" if success else "fail"
    msg = (
        f"plugin_lifecycle: action={action} plugin={plugin_name} "
        f"status={status} duration_ms={duration_ms}"
    )
    if detail:
        msg += f" detail={detail}"
    if success:
        logger.info(msg)
    else:
        logger.error(msg)

# Plugin-level distributed lock (prevent concurrent enable/disable/uninstall) / 插件级分布式锁（防止并发 enable/disable/uninstall）
_LOCK_PREFIX = "plugin:lifecycle:lock:"
_LOCK_TTL = 900  # seconds, covers long pip/migration flows to prevent premature lock expiry / 秒，覆盖 pip/迁移等长流程，避免锁提前过期导致并发操作


@asynccontextmanager
async def _plugin_lock(plugin_id: int):
    """
    Redis distributed lock, scoped to a single plugin.
    / Redis 分布式锁，粒度为单个插件。

    Raises PluginError(409) on acquisition failure; caller need not release manually.
    TTL auto-expires to prevent deadlocks (default 900s, covers long lifecycle flows).
    / 获取失败时抛出 PluginError(409)，调用方无需手动释放。
    TTL 自动过期防死锁（默认 900s，覆盖长耗时生命周期流程）。
    """
    from app.core.redis import get_redis_client
    from app.plugins.exceptions import PluginError

    key = f"{_LOCK_PREFIX}{plugin_id}"
    client = get_redis_client()
    owner_token = str(uuid.uuid4())
    acquired = await client.set(key, owner_token, nx=True, ex=_LOCK_TTL)
    if not acquired:
        raise PluginError(
            message=f"Plugin {plugin_id} is being modified by another operation. Please retry later.",
            status_code=409,
        )
    try:
        yield
    finally:
        try:
            await client.eval(_UNLOCK_IF_OWNER_LUA, 1, key, owner_token)
        except Exception as exc:
            logger.warning("Failed to release plugin lock {} safely: {}", key, exc)



# Late imports keep lifecycle helper symbols initialized before mixin modules
# import from this module for compatibility-preserving composition.
from app.plugins.lifecycle_dependency_runtime import (  # noqa: E402
    LifecycleDependencyRuntimeMixin,
)
from app.plugins.lifecycle_installation import LifecycleInstallationMixin  # noqa: E402
from app.plugins.lifecycle_migrations import LifecycleMigrationMixin  # noqa: E402
from app.plugins.lifecycle_parts.facade_modules import (  # noqa: E402
    LifecycleDependencyModule,
    LifecycleGuardModule,
    LifecyclePermissionModule,
)
from app.plugins.lifecycle_runtime_state import LifecycleRuntimeStateMixin  # noqa: E402


class PluginLifecycle(
    LifecycleInstallationMixin,
    LifecycleDependencyRuntimeMixin,
    LifecycleMigrationMixin,
    LifecycleRuntimeStateMixin,
):
    """Plugin lifecycle manager / 插件生命周期管理器"""

    """Plugin lifecycle manager / 插件生命周期管理器"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._loader = PluginLoader()
        self.read_models = PluginReadModelService(db)
        self.cleanup = PluginCleanupService(db)
        # Keep public lifecycle facade stable while splitting responsibilities internally.
        # / 对外保持 PluginLifecycle facade 不变，内部职责按模块拆分。
        self.guards = LifecycleGuardModule(self)
        self.dependencies = LifecycleDependencyModule(self)
        self.permissions = LifecyclePermissionModule(self)
        self.orchestrator = LifecycleOrchestrator(self)

    def _resolve_plugin_table_prefixes(self, plugin_name: str) -> list[str]:
        """Resolve plugin-operable DB table prefixes (default px_{plugin}_* + manifest-declared extra prefixes) / 解析插件可操作的 DB 表前缀（默认 px_{plugin}_* + manifest 声明扩展前缀）。"""
        own_prefix = f"px_{plugin_name.replace('-', '_')}_"
        prefixes: list[str] = [own_prefix]
        try:
            manifest = self._loader.load_manifest(plugin_name)
            extra_prefixes = getattr(manifest, "db_table_prefixes", None) or []
            for prefix in extra_prefixes:
                normalized = (prefix or "").strip()
                if normalized:
                    prefixes.append(normalized)
        except Exception as exc:
            logger.warning(
                "Plugin {}: failed to resolve custom DB table prefixes, fallback to default: {}",
                plugin_name,
                exc,
            )
        return list(dict.fromkeys(prefixes))

    async def _run_lifecycle_guards(
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

    async def _collect_plugin_dependency_states(
        self,
        manifest_or_data: object,
        *,
        require_enabled: bool,
    ) -> list[dict[str, object]]:
        return await self.orchestrator.collect_plugin_dependency_states(
            manifest_or_data,
            require_enabled=require_enabled,
        )

    @staticmethod
    def _summarize_plugin_dependency_errors(
        states: list[dict[str, object]],
    ) -> list[str]:
        return LifecycleOrchestrator.summarize_plugin_dependency_errors(states)

    async def _assert_plugin_dependencies_ready(
        self,
        manifest_or_data: object,
        *,
        plugin_name: str,
        require_enabled: bool,
        error_cls: type[PluginError],
        action: str,
    ) -> list[dict[str, object]]:
        return await self.orchestrator.assert_plugin_dependencies_ready(
            manifest_or_data,
            plugin_name=plugin_name,
            require_enabled=require_enabled,
            error_cls=error_cls,
            action=action,
        )

    @staticmethod
    def _count_declared_plugin_permissions(manifest: object) -> tuple[int, int]:
        return LifecycleOrchestrator.count_declared_plugin_permissions(manifest)

    async def _assert_plugin_enable_prerequisites(
        self,
        plugin: object,
        manifest: object,
        *,
        action: str,
        error_cls: type[PluginError],
    ) -> None:
        await self.orchestrator.assert_plugin_enable_prerequisites(
            plugin,
            manifest,
            action=action,
            error_cls=error_cls,
        )

    async def _ensure_plugin_permissions_active(
        self,
        plugin_name: str,
        manifest: object,
        *,
        action: str,
    ) -> None:
        await self.orchestrator.ensure_plugin_permissions_active(
            plugin_name,
            manifest,
            action=action,
        )

    async def enable(self, plugin_id: int, *, operator_id: int | None = None) -> None:
        """Enable plugin (with distributed lock) / 启用插件（带分布式锁）"""
        async with _plugin_lock(plugin_id):
            await self._enable_impl(plugin_id, operator_id=operator_id)

    async def _enable_impl(
        self, plugin_id: int, *, operator_id: int | None = None
    ) -> None:
        """Enable plugin implementation (caller must hold lock) / 启用插件实现（调用方须持锁）"""
        await self.orchestrator.enable_impl(plugin_id, operator_id=operator_id)

    # ================================================================
    # disable / 禁用
    # ================================================================

    async def disable(
        self, plugin_id: int, *, force: bool = False, operator_id: int | None = None
    ) -> None:
        """Disable plugin (with distributed lock) / 禁用插件（带分布式锁）"""
        async with _plugin_lock(plugin_id):
            await self._disable_impl(plugin_id, force=force, operator_id=operator_id)

    async def refresh_schedules(
        self,
        plugin_id: int,
        *,
        operator_id: int | None = None,
    ) -> dict[str, Any]:
        """Retry scheduler refresh/reconciliation for a plugin's task definitions."""
        _ = operator_id
        async with _plugin_lock(plugin_id):
            return await self._refresh_schedules_impl(plugin_id)

    async def repair(
        self,
        plugin_id: int,
        *,
        operator_id: int | None = None,
    ) -> None:
        """Repair plugin runtime and restore enabled state (with distributed lock)."""
        async with _plugin_lock(plugin_id):
            await self._repair_impl(plugin_id, operator_id=operator_id)

    async def _repair_impl(
        self,
        plugin_id: int,
        *,
        operator_id: int | None = None,
    ) -> None:
        """Repair plugin runtime by re-running enable-side checks and registration."""
        await self.orchestrator.repair_impl(plugin_id, operator_id=operator_id)

    async def _disable_impl(
        self,
        plugin_id: int,
        *,
        force: bool = False,
        operator_id: int | None = None,
        skip_lifecycle_guards: bool = False,
    ) -> None:
        """Disable plugin implementation (caller must hold lock) / 禁用插件实现（调用方须持锁）"""
        await self.orchestrator.disable_impl(
            plugin_id,
            force=force,
            operator_id=operator_id,
            skip_lifecycle_guards=skip_lifecycle_guards,
        )

    async def _refresh_schedules_impl(self, plugin_id: int) -> dict[str, Any]:
        """Reconcile plugin task definitions with the in-process scheduler."""
        return await self.orchestrator.refresh_schedules_impl(plugin_id)

    # ================================================================
    # dependencies / 依赖
    # ================================================================

    async def install_dependencies(
        self,
        plugin_id: int,
        *,
        install_python: bool = True,
    ) -> dict[str, Any]:
        """Explicitly install plugin dependencies (without changing plugin enable status)."""
        async with _plugin_lock(plugin_id):
            return await self.orchestrator.install_dependencies_impl(
                plugin_id,
                install_python=install_python,
            )

    async def uninstall_dependencies(
        self,
        plugin_id: int,
        *,
        uninstall_python: bool = True,
    ) -> dict[str, Any]:
        """Explicitly uninstall plugin dependencies (without uninstalling the plugin itself)."""
        async with _plugin_lock(plugin_id):
            return await self.orchestrator.uninstall_dependencies_impl(
                plugin_id,
                uninstall_python=uninstall_python,
            )

    # ================================================================
    # uninstall / 卸载
    # ================================================================

    async def uninstall(
        self,
        plugin_id: int,
        confirm_data_delete: bool = False,
        *,
        cleanup_dependencies: bool = False,
        operator_id: int | None = None,
    ) -> None:
        """Uninstall plugin (with distributed lock) / 卸载插件（带分布式锁）"""
        async with _plugin_lock(plugin_id):
            await self._uninstall_impl(
                plugin_id,
                confirm_data_delete,
                cleanup_dependencies=cleanup_dependencies,
                operator_id=operator_id,
            )

    async def _uninstall_impl(
        self,
        plugin_id: int,
        confirm_data_delete: bool = False,
        *,
        cleanup_dependencies: bool = False,
        operator_id: int | None = None,
    ) -> None:
        """Uninstall plugin implementation (14-step cleanup) / 卸载插件实现（14 步清理）"""
        _ = confirm_data_delete
        await self.orchestrator.uninstall_impl(
            plugin_id,
            cleanup_dependencies=cleanup_dependencies,
            operator_id=operator_id,
        )

    async def _get_dependents(
        self,
        plugin_name: str,
        *,
        statuses: set[str] | None = None,
    ) -> list[dict[str, object]]:
        """
        Find plugins that depend on the specified plugin.
        / 查找依赖指定插件的插件列表。
        """
        return await self.read_models.list_dependents(
            plugin_name,
            statuses=statuses,
        )

    async def get_dependents(self, plugin_id: int) -> list[dict[str, object]]:
        """Get list of plugins that depend on the specified plugin (for API use) / 获取依赖指定插件的插件列表（API 用）"""
        return await self.read_models.list_dependents_by_plugin_id(plugin_id)

    async def get_dependencies(self, plugin_id: int) -> list[dict[str, object]]:
        """Get list of dependency plugins for the specified plugin (for API use) / 获取指定插件的依赖插件列表（API 用）"""
        return await self.read_models.list_dependencies_by_plugin_id(
            plugin_id,
            require_enabled=False,
        )

    # ================================================================
    # Internal methods / 内部方法
    # ================================================================
