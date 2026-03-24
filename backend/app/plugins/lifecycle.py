"""
Plugin lifecycle management / 插件生命周期管理

Four core operations: install / enable / disable / uninstall.
/ install / enable / disable / uninstall 四个核心操作。
"""

from __future__ import annotations

import functools
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING

import anyio

from app.core.base_model import utc_now
from app.core.i18n import _
from app.core.logging import get_logger
from app.core.response import build_public_error_text, resolve_public_error_message
from app.enums.plugin import (
    PluginInstallSourceEnum,
    PluginStatusEnum,
    PluginTierEnum,
    PluginVersionStatusEnum,
)
from app.plugins.exceptions import (
    PluginDependencyError,
    PluginError,
    PluginInstallError,
    PluginSecurityError,
)
from app.plugins.dependencies import (
    build_plugin_dependency_states,
    detect_direct_python_dependency_conflicts,
    get_installed_distribution_version,
    iter_effective_python_requirements,
    normalize_plugin_dependencies,
    normalize_python_package_name,
)
from app.plugins.lifecycle_guards import run_plugin_lifecycle_guards
from app.plugins.loader import PLUGINS_DIR, PluginLoader
from app.plugins.migration_paths import build_migration_version_locations
from app.plugins.preview import resolve_i18n

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.system.plugin import Plugin

logger = get_logger(__name__)


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


_IS_WINDOWS = sys.platform == "win32"


async def _run_subprocess_async(
    *args: str,
    timeout: int = 120,
    cwd: str | None = None,
    text: bool = True,
    capture_output: bool = True,
    shell: bool | None = None,
    env: dict[str, str] | None = None,
):
    """
    在线程中执行 subprocess.run，避免阻塞异步事件循环 / Run subprocess.run in a thread to avoid blocking the async event loop.

    Args:
        shell: Explicit shell mode. None = auto (_IS_WINDOWS for .cmd scripts).
               Pass False for direct binaries (e.g. sys.executable -m pip)
               to avoid shell metachar issues (>=, |, & etc.).
    """
    use_shell = shell if shell is not None else _IS_WINDOWS
    return await anyio.to_thread.run_sync(
        functools.partial(
            subprocess.run,
            list(args),
            capture_output=capture_output,
            text=text,
            timeout=timeout,
            cwd=cwd,
            shell=use_shell,
            env=env,
            encoding="utf-8" if text else None,
            errors="replace" if text else None,
        )
    )


# Plugin-level distributed lock (prevent concurrent enable/disable/uninstall) / 插件级分布式锁（防止并发 enable/disable/uninstall）
_LOCK_PREFIX = "plugin:lifecycle:lock:"
_LOCK_TTL = 900  # seconds, covers long pip/migration flows to prevent premature lock expiry / 秒，覆盖 pip/迁移等长流程，避免锁提前过期导致并发操作
_UNLOCK_IF_OWNER_LUA = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""

_SAFE_PLUGIN_TABLE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _is_safe_plugin_table_name(
    table_name: str,
    expected_prefix: list[str] | str | tuple[str, ...],
):
    """
    Plugin table name safety check: only safe chars allowed and must match plugin prefix / 插件表名安全校验：只允许安全字符，且必须匹配插件前缀。
    """
    if not _SAFE_PLUGIN_TABLE_RE.match(table_name):
        return False
    if isinstance(expected_prefix, str):
        prefixes = (expected_prefix,)
    else:
        prefixes = tuple(expected_prefix)
    return any(table_name.startswith(prefix) for prefix in prefixes)


def _escape_like_pattern(value: str):
    """
    Escape SQL LIKE special characters to prevent '_'/'%' from being treated as wildcards / 转义 SQL LIKE 特殊字符，防止 '_'/'%' 被当作通配符。
    """
    return (
        value
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


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


class PluginLifecycle:
    """Plugin lifecycle manager / 插件生命周期管理器"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._loader = PluginLoader()

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
        """Run lifecycle guards and raise PluginError on denial.
        / 执行生命周期阻断校验，若被拒绝则抛 PluginError。
        """
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
        """Collect normalized plugin dependency runtime states. / 收集规范化插件依赖运行时状态。"""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel

        requirements = normalize_plugin_dependencies(manifest_or_data)
        if not requirements:
            return []

        plugin_names = sorted({item.plugin for item in requirements})
        result = await self._db.execute(
            select(PluginModel.name, PluginModel.version, PluginModel.status).where(
                PluginModel.name.in_(plugin_names),
                PluginModel.is_deleted.is_(False),
            )
        )
        plugin_rows = {
            row[0]: {
                "name": row[0],
                "status": row[2],
                "version": row[1],
            }
            for row in result.all()
        }
        return [
            state.to_dict()
            for state in build_plugin_dependency_states(
                requirements,
                plugin_rows,
                require_enabled=require_enabled,
            )
        ]

    @staticmethod
    def _summarize_plugin_dependency_errors(
        states: list[dict[str, object]],
    ) -> list[str]:
        """Convert dependency states to human-readable errors. / 将依赖状态转成错误文本。"""
        errors: list[str] = []
        for state in states:
            if state.get("state") == "ready":
                continue
            message = str(state.get("message") or "").strip()
            if message:
                errors.append(message)
        return errors

    async def _assert_plugin_dependencies_ready(
        self,
        manifest_or_data: object,
        *,
        plugin_name: str,
        require_enabled: bool,
        error_cls: type[PluginError],
        action: str,
    ) -> list[dict[str, object]]:
        """Ensure plugin dependencies are satisfied. / 确保插件依赖满足要求。"""
        states = await self._collect_plugin_dependency_states(
            manifest_or_data,
            require_enabled=require_enabled,
        )
        errors = self._summarize_plugin_dependency_errors(states)
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
    def _count_declared_plugin_permissions(manifest: object) -> tuple[int, int]:
        """Count declared plugin permission targets. / 统计插件声明的权限目标数。"""
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

    async def _assert_plugin_enable_prerequisites(
        self,
        plugin: object,
        manifest: object,
        *,
        action: str,
        error_cls: type[PluginError],
    ) -> None:
        """Run enable-like runtime guards. / 运行 enable 类链路的运行前置校验。"""
        plugin_name = str(getattr(plugin, "name", "") or "").strip()
        plugin_id = int(getattr(plugin, "id"))
        pricing_type = str(getattr(plugin, "pricing_type", "") or "").strip()

        from app.plugins.license import assert_plugin_license_active

        await assert_plugin_license_active(
            plugin_id,
            pricing_type,
            self._db,
            plugin_name=plugin_name,
            operation=action,
        )

        if manifest.compatibility and manifest.compatibility.conflicts:
            from sqlalchemy import select

            from app.models.system.plugin import Plugin as PluginModel

            for conflict in manifest.compatibility.conflicts:
                dep_result = await self._db.execute(
                    select(PluginModel.status).where(
                        PluginModel.name == conflict.plugin,
                        PluginModel.is_deleted.is_(False),
                    )
                )
                dep_status = dep_result.scalar_one_or_none()
                if dep_status == PluginStatusEnum.ENABLED.value:
                    conflict_reason = (
                        conflict.reason.get("zh-CN")
                        or conflict.reason.get("en")
                        or "incompatible"
                    ) if conflict.reason else "incompatible"
                    raise error_cls(
                        message=(
                            f"Cannot {action} '{plugin_name}': conflicts with enabled plugin "
                            f"'{conflict.plugin}' ({conflict_reason}). Disable it first."
                        ),
                    )

        await self._assert_plugin_dependencies_ready(
            manifest,
            plugin_name=plugin_name,
            require_enabled=True,
            error_cls=error_cls,
            action=action,
        )

    async def _ensure_plugin_permissions_active(
        self,
        plugin_name: str,
        manifest: object,
        *,
        action: str,
    ) -> None:
        """Strictly sync + enable plugin permissions. / 严格同步并启用插件权限。"""
        declared_permissions, tenant_declared_permissions = (
            self._count_declared_plugin_permissions(manifest)
        )

        from app.rbac.sync import PermissionSyncService

        perm_sync = PermissionSyncService(self._db)
        async with self._db.begin_nested():
            synced_count = await perm_sync.sync_plugin_permissions(plugin_name)

        if declared_permissions > 0 and synced_count <= 0:
            raise PluginError(
                message=(
                    f"Cannot {action} '{plugin_name}': expected {declared_permissions} "
                    "plugin permission/menu declaration(s) to sync into DB, but none were written."
                ),
            )

        enabled_count = await self._set_plugin_permissions_enabled(plugin_name, True)
        if declared_permissions > 0 and enabled_count <= 0:
            raise PluginError(
                message=(
                    f"Cannot {action} '{plugin_name}': expected {declared_permissions} "
                    "plugin permission/menu row(s) to be enabled, but no DB rows matched."
                ),
            )

        await self._auto_grant_plugin_menus_to_plans(
            plugin_name,
            expected_tenant_permissions=tenant_declared_permissions,
            action=action,
        )

    def _load_project_pyproject_requirements(self) -> list[str]:
        """Load declared host requirements from pyproject.toml. / 从 pyproject.toml 加载宿主声明的 requirement。"""
        requirements: list[str] = []
        pyproject_path = PLUGINS_DIR.parent / "pyproject.toml"
        if not pyproject_path.is_file():
            return requirements
        try:
            raw = pyproject_path.read_bytes()
            if sys.version_info >= (3, 11):
                import tomllib

                cfg = tomllib.loads(raw.decode(encoding="utf-8"))
            else:
                import tomli

                cfg = tomli.loads(raw.decode(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to parse pyproject.toml: {}", exc)
            return requirements

        project_cfg = cfg.get("project") or {}
        for item in project_cfg.get("dependencies") or []:
            if isinstance(item, str):
                requirements.append(item)
        optional = project_cfg.get("optional-dependencies") or {}
        for deps in optional.values():
            if not isinstance(deps, list):
                continue
            for item in deps:
                if isinstance(item, str):
                    requirements.append(item)
        return list(dict.fromkeys(requirements))

    async def _load_other_plugin_python_requirements(
        self,
        *,
        exclude_plugin_name: str | None = None,
    ) -> dict[str, list[str]]:
        """Load declared Python requirements from installed plugins. / 加载已安装插件声明的 Python requirement。"""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel

        filters = [PluginModel.is_deleted.is_(False)]
        if exclude_plugin_name:
            filters.append(PluginModel.name != exclude_plugin_name)
        result = await self._db.execute(
            select(PluginModel.name, PluginModel.manifest).where(*filters)
        )

        requirements_by_owner: dict[str, list[str]] = {}
        for owner, manifest_data in result.all():
            if not manifest_data or not isinstance(manifest_data, dict):
                continue
            deps = manifest_data.get("dependencies") or {}
            raw_python = deps.get("python") if isinstance(deps, dict) else None
            if isinstance(raw_python, list) and raw_python:
                requirements_by_owner[owner] = [
                    str(item).strip()
                    for item in raw_python
                    if str(item or "").strip()
                ]
        return requirements_by_owner

    async def _ensure_python_dependency_preflight(
        self,
        plugin_name: str,
        requirements: list[str],
    ) -> dict[str, object]:
        """Preflight direct Python dependency conflicts in shared host env.
        / 对共享宿主环境做 Python 直接依赖冲突预检。
        """
        normalized_requirements = [
            str(requirement).strip()
            for requirement in requirements
            if str(requirement or "").strip()
        ]
        effective_requirements = iter_effective_python_requirements(
            normalized_requirements
        )

        requirement_groups: dict[str, list[tuple[str, str]]] = {}

        for requirement_text in self._load_project_pyproject_requirements():
            for requirement in iter_effective_python_requirements([requirement_text]):
                package = normalize_python_package_name(requirement.name)
                requirement_groups.setdefault(package, []).append(
                    ("host", str(requirement))
                )

        other_plugin_requirements = await self._load_other_plugin_python_requirements(
            exclude_plugin_name=plugin_name,
        )
        for owner, owner_requirements in other_plugin_requirements.items():
            for requirement in iter_effective_python_requirements(owner_requirements):
                package = normalize_python_package_name(requirement.name)
                requirement_groups.setdefault(package, []).append(
                    (f"plugin:{owner}", str(requirement))
                )

        for requirement in effective_requirements:
            package = normalize_python_package_name(requirement.name)
            requirement_groups.setdefault(package, []).append(
                (f"plugin:{plugin_name}", str(requirement))
            )

        installed_versions = {
            package: get_installed_distribution_version(package)
            for package in requirement_groups
        }
        conflicts = detect_direct_python_dependency_conflicts(
            requirement_groups,
            installed_versions=installed_versions,
        )
        if conflicts:
            details = "; ".join(
                f"{conflict.package}: {conflict.reason}"
                for conflict in conflicts
            )
            raise PluginDependencyError(
                message=(
                    f"Python dependency conflict for plugin '{plugin_name}': "
                    f"{details}"
                ),
            )

        return {
            "declared": [str(requirement) for requirement in effective_requirements],
            "conflicts": [],
            "installed_versions": installed_versions,
        }

    # ================================================================
    # install / 安装
    # ================================================================

    async def install(
        self,
        source_path: Path,
        config: dict | None = None,
        *,
        operator_id: int | None = None,
    ) -> Plugin:
        """
        Install plugin (10-step flow) / 安装插件（10 步流程）

        Args:
            source_path: Plugin source directory (extracted) / 插件源目录（已解压）
            config: Initial config (optional) / 初始配置（可选）
            operator_id: Operator admin ID (for WebSocket progress push) / 操作者管理员 ID（用于 WebSocket 进度推送）
        """
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel
        from app.models.system.plugin_version import PluginVersion
        from app.plugins.context_factory import create_plugin_context
        from app.plugins.crypto import encrypt_plugin_config
        from app.plugins.frontend_contract import validate_runtime_frontend_contract

        # 1. Copy to plugins dir (skip if source is already in plugins/) / 复制到 plugins 目录（如果 source 已在 plugins/ 中则跳过）
        manifest = self._loader.load_manifest_from_path(source_path)
        plugin_name = manifest.name
        target_dir = PLUGINS_DIR / plugin_name
        validate_runtime_frontend_contract(source_path, manifest)

        # Prevent concurrent installation of same-named plugin (Redis name lock) / 防止并发安装同名插件（基于 Redis 名称锁）
        from app.core.redis import get_redis_client
        _install_lock_key = f"plugin:install:lock:{plugin_name}"
        _redis = None
        _install_owner = None
        _redis = get_redis_client()
        _install_owner = str(uuid.uuid4())
        _install_locked = await _redis.set(
            _install_lock_key, _install_owner, nx=True, ex=300,
        )
        if not _install_locked:
            raise PluginInstallError(
                message=f"Plugin '{plugin_name}' is already being installed by another operation. Please retry later.",
            )

        # completed_steps / emitter initialized outside try to ensure except can always access them / completed_steps 在 try 外初始化以便 except 可访问
        # / completed_steps / emitter 在 try 外初始化，确保 except 始终能访问
        completed_steps: list[str] = []
        emitter = None

        try:
            # If source_path is already target_dir (upload endpoint already copied), skip copy / 若已就位则跳过复制
            # / 如果 source_path 就是 target_dir（上传端点已复制好），跳过复制
            source_resolved = source_path.resolve()
            target_resolved = target_dir.resolve()
            already_in_place = source_resolved == target_resolved

            if not already_in_place:
                if target_dir.exists():
                    existing = await self._db.execute(
                        select(PluginModel).where(
                            PluginModel.name == plugin_name,
                            PluginModel.is_deleted.is_(False),
                        )
                    )
                    if existing.scalar_one_or_none():
                        raise PluginInstallError(
                            message=f"Plugin '{plugin_name}' is already installed",
                        )
                    logger.warning(
                        "Stale plugin directory found for {} (no DB record), cleaning up",
                        plugin_name,
                    )
                    shutil.rmtree(target_dir, ignore_errors=True)
                shutil.copytree(source_path, target_dir)
                logger.info("Copied plugin to {}", target_dir)
                # Only mark "copy" if we actually copied — rollback deletes the dir when "copy" in completed_steps / 仅实际复制后才标记 copy，避免误删
                completed_steps.append("copy")
            else:
                # Files already in place, only check if already installed / 文件已就位，仅检查是否已安装
                existing = await self._db.execute(
                    select(PluginModel).where(
                        PluginModel.name == plugin_name,
                        PluginModel.is_deleted.is_(False),
                    )
                )
                if existing.scalar_one_or_none():
                    raise PluginInstallError(
                        message=f"Plugin '{plugin_name}' is already installed",
                    )

            from app.plugins.progress import PluginProgressEmitter
            emitter = PluginProgressEmitter(operator_id, plugin_name, "install")
            await emitter.emit_step("copy", "success", f"Plugin files copied to {target_dir}")
            # 2. Parse manifest (already done above) / 解析 manifest（已在上面完成）
            # 3. Validate compatibility + plugin dependency check / 校验兼容性 + 插件依赖检查
            from app.enums.plugin import PluginStatusEnum

            # 3a. Platform version compatibility check / 平台版本兼容性检查
            if manifest.compatibility and manifest.compatibility.platform_version != "*":
                try:
                    from packaging.specifiers import SpecifierSet
                    from packaging.version import Version

                    from app.core.config import settings

                    platform_spec = SpecifierSet(manifest.compatibility.platform_version)
                    if Version(settings.APP_VERSION) not in platform_spec:
                        raise PluginInstallError(
                            message=f"Plugin '{plugin_name}' requires platform version "
                            f"{manifest.compatibility.platform_version}, "
                            f"but current is {settings.APP_VERSION}",
                        )
                except ImportError:
                    logger.warning("packaging library not available, skipping version check")

            # 3b. Unified plugin dependency check / 统一插件依赖检查
            await self._assert_plugin_dependencies_ready(
                manifest,
                plugin_name=plugin_name,
                require_enabled=False,
                error_cls=PluginInstallError,
                action="install",
            )

            # 3d. Security scan (high-risk fail-close) / 安全扫描（高风险 fail-close）
            from app.plugins.security_scan import scan_plugin_directory

            scan_target = target_dir if target_dir.is_dir() else source_path
            scan_result = scan_plugin_directory(scan_target)
            if scan_result.has_warnings:
                top_warnings = "; ".join(scan_result.warnings[:5])
                raise PluginSecurityError(
                    message=(
                        f"Plugin '{plugin_name}' blocked by security scan: "
                        f"{top_warnings}"
                    ),
                )

            # 4. Record declared deps (runtime environment changes deferred to explicit dependency handling) / 记录声明的依赖（运行时环境变更延迟到显式依赖处理）
            installed_packages = manifest.dependencies.python or []

            # 5. Run Alembic migrations / 执行 Alembic 迁移
            migrations_dir = target_dir / "backend" / "migrations" / "versions"
            if migrations_dir.is_dir():
                await emitter.emit_step("alembic", "running", "Running database migrations...")
                await self.run_alembic_upgrade(plugin_name)
                await emitter.emit_step("alembic", "success", "Database migrations complete")
                completed_steps.append("alembic")

            # 6. Register AI features → SystemAgentAssignment / 注册 AI features → SystemAgentAssignment
            if manifest.ai_requirements and manifest.ai_requirements.features:
                await emitter.emit_step("ai_features", "running", "Registering AI features...")
                from app.models.system.agent_assignment import SystemAgentAssignment
                for feature in manifest.ai_requirements.features:
                    feature_code = f"plugin.{plugin_name}.{feature.feature_code}"
                    feature_name = feature.display_name.get(
                        "zh-CN", feature.display_name.get("en", feature.feature_code)
                    )
                    feature_desc = feature.description.get(
                        "zh-CN", feature.description.get("en", "")
                    )
                    # Check if global default already exists (only query tenant_id IS NULL) / 检查全局默认是否已存在（只查 tenant_id IS NULL）
                    existing = await self._db.execute(
                        select(SystemAgentAssignment.id).where(
                            SystemAgentAssignment.feature_code == feature_code,
                            SystemAgentAssignment.tenant_id.is_(None),
                            SystemAgentAssignment.is_deleted.is_(False),
                        )
                    )
                    if not existing.scalar_one_or_none():
                        self._db.add(SystemAgentAssignment(
                            feature_code=feature_code,
                            feature_name=feature_name,
                            description=feature_desc,
                            agent_id=None,
                            tenant_id=None,
                            is_active=True,
                        ))
                await self._db.flush()
                completed_steps.append("ai_features")
                await emitter.emit_step("ai_features", "success", f"Registered {len(manifest.ai_requirements.features)} AI features")
                logger.info(
                    "Registered {} AI features for plugin {}",
                    len(manifest.ai_requirements.features), plugin_name,
                )

            # 7. Merge i18n translations (reserved, currently only logged) / 合并 i18n 翻译（预留，当前仅记录）
            locales = self._loader.load_locales(plugin_name)
            if locales:
                logger.info(
                    "Plugin {} has {} locale(s): {}",
                    plugin_name, len(locales), list(locales.keys()),
                )
                completed_steps.append("i18n")

            # 8. Instantiate plugin class and call on_install / 实例化插件类并调用 on_install
            await emitter.emit_step("on_install", "running", "Running plugin install hook...")
            try:
                plugin_cls = self._loader.load_plugin_class(plugin_name)
                plugin_instance = plugin_cls()
                ctx = create_plugin_context(
                    plugin_name=plugin_name,
                    manifest=manifest,
                    db=self._db,
                    granted_capabilities=manifest.capabilities,
                )
                await plugin_instance.on_install(ctx)
                completed_steps.append("on_install")
                await emitter.emit_step("on_install", "success", "Install hook completed")
            except Exception as exc:
                await emitter.emit_step(
                    "on_install",
                    "warning",
                    build_public_error_text(
                        exc=exc,
                        message=_("common.server_error"),
                    ),
                )
                logger.warning(
                    "Plugin {} on_install failed (non-fatal): {}",
                    plugin_name, exc,
                )

            # 9. Write to plugins table / 写入 plugins 表
            await emitter.emit_step("db", "running", "Writing plugin record...")
            initial_config = config or {}
            config_schema = manifest.config_schema
            if config_schema and initial_config:
                initial_config = encrypt_plugin_config(initial_config, config_schema)

            plugin = PluginModel(
                name=plugin_name,
                display_name=resolve_i18n(manifest.display_name),
                version=manifest.version,
                description=resolve_i18n(manifest.description) if manifest.description else None,
                author=manifest.author or None,
                icon=manifest.icon or None,
                icon_color=manifest.icon_color or None,
                homepage=manifest.homepage or None,
                repository_url=manifest.repository_url or None,
                license_text=manifest.license or None,
                tags=manifest.tags,
                scope=manifest.scope,
                status=PluginStatusEnum.INSTALLED.value,
                tier=PluginTierEnum.COMMUNITY.value,
                install_source=PluginInstallSourceEnum.LOCAL.value,
                manifest=manifest.model_dump(),
                config=initial_config,
                ai_requirements=manifest.ai_requirements.model_dump() if manifest.ai_requirements else None,
                pricing_type=manifest.pricing.type,
                pricing_info=manifest.pricing.model_dump() if manifest.pricing.type != "free" else None,
                error_count=0,
                installed_packages=installed_packages,
                granted_capabilities=manifest.capabilities,
                installed_at=utc_now(),
            )
            self._db.add(plugin)
            await self._db.flush()
            completed_steps.append("db")

            # 10. Backup version / 备份版本
            version_record = PluginVersion(
                plugin_id=plugin.id,
                version=manifest.version,
                manifest=manifest.model_dump(),
                status=PluginVersionStatusEnum.ACTIVE.value,
                installed_at=utc_now(),
            )
            self._db.add(version_record)
            await self._db.flush()

            await emitter.emit_step("db", "success", "Plugin record saved")

            logger.info(
                "Plugin {} v{} installed successfully",
                plugin_name, manifest.version,
            )
            await emitter.emit_done(f"Plugin {plugin_name} v{manifest.version} installed successfully")
            return plugin

        except Exception as exc:
            logger.error(
                "Plugin {} install failed at step {}: {}",
                plugin_name, completed_steps[-1] if completed_steps else "init", exc,
            )
            if emitter is not None:
                await emitter.emit_error(
                    build_public_error_text(
                        exc=exc,
                        message=_("plugin.error.install_failed"),
                    )
                )
            await self._rollback_install(plugin_name, completed_steps)
            if isinstance(exc, (PluginError, PluginInstallError, PluginDependencyError)):
                raise
            raise PluginInstallError(
                message=resolve_public_error_message(
                    exc,
                    fallback_message=_("plugin.error.install_failed"),
                ),
            )
        finally:
            # Release install lock / 释放安装锁
            if _redis is not None and _install_owner is not None:
                with suppress(Exception):
                    await _redis.eval(_UNLOCK_IF_OWNER_LUA, 1, _install_lock_key, _install_owner)

    # ================================================================
    # enable / 启用
    # ================================================================

    async def enable(self, plugin_id: int, *, operator_id: int | None = None) -> None:
        """Enable plugin (with distributed lock) / 启用插件（带分布式锁）"""
        async with _plugin_lock(plugin_id):
            await self._enable_impl(plugin_id, operator_id=operator_id)

    async def _enable_impl(self, plugin_id: int, *, operator_id: int | None = None) -> None:
        """Enable plugin implementation (caller must hold lock) / 启用插件实现（调用方须持锁）"""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel
        from app.plugins.context_factory import create_plugin_context
        from app.plugins.frontend_contract import validate_runtime_frontend_contract
        from app.plugins.progress import PluginProgressEmitter
        from app.plugins.registry import ExtensionRegistry

        plugin = await self._db.execute(
            select(PluginModel).where(
                PluginModel.id == plugin_id,
                PluginModel.is_deleted.is_(False),
            )
        )
        plugin = plugin.scalar_one_or_none()
        if not plugin:
            from app.plugins.exceptions import PluginNotFoundError
            raise PluginNotFoundError(message=f"Plugin ID {plugin_id} not found")

        if plugin.status == PluginStatusEnum.ENABLED.value:
            return  # Already enabled / 已启用

        plugin_name = plugin.name
        emitter = PluginProgressEmitter(operator_id, plugin_name, "enable")
        manifest = self._loader.load_manifest(plugin_name)
        validate_runtime_frontend_contract(self._loader.plugins_dir / plugin_name, manifest)

        await self._assert_plugin_runtime_enable_guards(
            plugin,
            manifest,
            action="enable",
        )

        # Alembic migration (ensure plugin tables are created) / Alembic 迁移（确保插件表已创建）
        # fail-close: mark ERROR and abort enable on migration failure / 迁移失败时标记 ERROR 并中止启用
        # / fail-close：迁移失败则标记 ERROR 并中止 enable，防止插件在 DB 表缺失时运行。
        # Note: startup.restore_enabled_plugins also treats migration failure as fail-close per plugin.
        # / 注意：startup.restore_enabled_plugins 现也按单插件 fail-close 处理迁移失败，
        #   仅影响当前插件，不阻塞其他插件恢复。
        migrations_dir = self._loader.plugins_dir / plugin_name / "backend" / "migrations" / "versions"
        if migrations_dir.is_dir():
            await emitter.emit_step("alembic", "running", "Running database migrations...")
            try:
                await self.run_alembic_upgrade(plugin_name)
                await emitter.emit_step("alembic", "success", "Database migrations complete")
            except Exception as exc:
                err_msg = resolve_public_error_message(
                    exc,
                    fallback_message=_("common.server_error"),
                )
                plugin.status = PluginStatusEnum.ERROR.value
                plugin.error_message = err_msg
                plugin.error_count = (plugin.error_count or 0) + 1
                await self._db.flush()
                await emitter.emit_step(
                    "alembic",
                    "error",
                    build_public_error_text(
                        exc=exc,
                        message=_("common.server_error"),
                    ),
                )
                raise PluginError(
                    message=err_msg,
                )
        else:
            await emitter.emit_step("alembic", "success", "No database migrations")

        # Install Python dependencies / 安装 Python 依赖
        if manifest.dependencies.python:
            await emitter.emit_step("pip", "running", f"Checking {len(manifest.dependencies.python)} Python package(s)...")
            try:
                pip_installed = await self._install_python_deps(plugin_name, manifest.dependencies.python)
            except Exception as exc:
                await emitter.emit_error(
                    build_public_error_text(
                        exc=exc,
                        message=_("plugin.error.dependency_failed"),
                    )
                )
                raise
            if pip_installed:
                await emitter.emit_step("pip", "success", f"Installed {len(pip_installed)} package(s)")
            else:
                await emitter.emit_step("pip", "success", "Python dependencies already satisfied")
        else:
            await emitter.emit_step("pip", "success", "No Python dependencies")

        # Register extension points / 注册扩展点
        await emitter.emit_step("extensions", "running", "Registering extensions...")
        registry = ExtensionRegistry.get_instance()

        from app.plugins._extension_registrar import (
            get_failed_extensions,
            register_all_extensions,
        )

        menu_overrides = (plugin.config or {}).get("menu_overrides")
        register_all_extensions(registry, manifest, plugin_name, menu_overrides=menu_overrides)

        # fail-close: rollback registration and mark error if critical extension load failed / 关键扩展加载失败时回滚并标记错误
        # / fail-close：若有关键扩展加载失败，回滚注册并标记 error
        failed = get_failed_extensions(plugin_name)
        if failed:
            registry.unregister_all(plugin_name)
            failed_summary = "; ".join(
                f"{f['type']}:{f['entry_point']}" for f in failed[:5]
            )
            plugin.status = PluginStatusEnum.ERROR.value
            plugin.error_message = f"Extension load failed: {failed_summary}"
            plugin.error_count += 1
            await self._db.flush()
            await emitter.emit_error(f"{len(failed)} extension(s) failed to load")
            raise PluginError(
                message=f"Cannot enable '{plugin_name}': {len(failed)} extension(s) failed to load: {failed_summary}",
            )

        # Auto-create SkillPackage + Skill records (for Agent binding) / 自动创建 SkillPackage + Skill 记录（供 Agent 绑定）
        ext = manifest.extensions
        if ext.skills:
            await self._ensure_plugin_skill_records(
                plugin_name, manifest, ext.skills, active=True,
            )

        # M50-T12: Ensure SystemAgentAssignment records exist for AI features; only created once during install, restore/enable needs to rebuild after DB reset / M50-T12: 确保 AI features 对应的 SystemAgentAssignment 记录存在；install 阶段只创建一次，DB 重置后 restore/enable 需重建
        if manifest.ai_requirements and manifest.ai_requirements.features:
            await self._ensure_plugin_ai_features(plugin_name, manifest.ai_requirements.features)

        # M50-T1: Notification template DB sync — enable NotificationService.send() to find templates / 通知模板 DB 同步
        # / M50-T1: 通知模板 DB 同步 — 使 NotificationService.send() 可正常查到模板
        if ext.notifications:
            await self._sync_plugin_notification_templates(plugin_name, ext.notifications)

        # M50-T2: Task definition DB sync — enable Celery Beat to schedule plugin tasks / 任务定义 DB 同步
        # / M50-T2: 任务定义 DB 同步 — 使 Celery Beat 可正常调度插件任务
        if ext.tasks:
            await self._sync_plugin_task_definitions(plugin_name, ext.tasks)

        await emitter.emit_step("extensions", "success", f"Registered {registry.get_registered_count(plugin_name)} extension(s)")

        # Call on_enable / 调用 on_enable
        await emitter.emit_step("on_enable", "running", "Running enable hook...")
        try:
            plugin_cls = self._loader.load_plugin_class(plugin_name)
            ctx = create_plugin_context(
                plugin_name=plugin_name,
                manifest=manifest,
                db=self._db,
                granted_capabilities=plugin.granted_capabilities or [],
            )
            await plugin_cls().on_enable(ctx)
            await emitter.emit_step("on_enable", "success", "Enable hook completed")
        except Exception as exc:
            # on_enable failed: rollback registration, mark error status / on_enable 失败：回滚注册，标记 error 状态
            logger.warning("Plugin {} on_enable failed: {}", plugin_name, exc)
            registry.unregister_all(plugin_name)
            plugin.status = PluginStatusEnum.ERROR.value
            plugin.error_message = resolve_public_error_message(
                exc,
                fallback_message=_("common.server_error"),
            )
            plugin.error_count += 1
            await self._db.flush()
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
            )

        try:
            await self._restore_plugin_permissions(plugin_name)
        except Exception as exc:
            logger.warning(
                "Plugin {}: failed to restore plugin permissions during enable: {}",
                plugin_name,
                exc,
            )
            registry.unregister_all(plugin_name)
            with suppress(Exception):
                await self._set_plugin_permissions_enabled(plugin_name, False)
            plugin.status = PluginStatusEnum.ERROR.value
            plugin.error_message = resolve_public_error_message(
                exc,
                fallback_message=_("common.server_error"),
            )
            plugin.error_count = (plugin.error_count or 0) + 1
            await self._db.flush()
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

        # Update status / 更新状态
        plugin.status = PluginStatusEnum.ENABLED.value
        plugin.enabled_at = utc_now()
        plugin.error_message = None
        plugin.error_count = 0
        await self._db.flush()

        # Clear route regex cache (routes may change in DEBUG mode) / 清除路由正则缓存（DEBUG 模式下路由可能变化）
        from app.plugins.api_dispatcher import _compile_route_regex
        _compile_route_regex.cache_clear()

        await emitter.emit_done(f"Plugin {plugin_name} enabled successfully")
        logger.info("Plugin {} enabled", plugin_name)

        # T4: Trigger system hook point, other plugins can subscribe to PLUGIN_ENABLED / T4: 触发系统钩子点
        # / T4: 触发系统钩子点，其他插件可订阅 PLUGIN_ENABLED
        try:
            from app.plugins.system_hooks import SystemHookPoint, trigger_hook
            await trigger_hook(
                SystemHookPoint.PLUGIN_ENABLED,
                plugin_name=plugin_name, plugin_id=plugin_id,
            )
        except Exception as exc:
            logger.warning("system_hook PLUGIN_ENABLED failed: {}", exc)

    # ================================================================
    # disable / 禁用
    # ================================================================

    async def disable(self, plugin_id: int, *, force: bool = False, operator_id: int | None = None) -> None:
        """Disable plugin (with distributed lock) / 禁用插件（带分布式锁）"""
        async with _plugin_lock(plugin_id):
            await self._disable_impl(plugin_id, force=force, operator_id=operator_id)

    async def _disable_impl(
        self,
        plugin_id: int,
        *,
        force: bool = False,
        operator_id: int | None = None,
        skip_lifecycle_guards: bool = False,
    ) -> None:
        """Disable plugin implementation (caller must hold lock) / 禁用插件实现（调用方须持锁）"""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel
        from app.plugins.context_factory import create_plugin_context
        from app.plugins.progress import PluginProgressEmitter
        from app.plugins.registry import ExtensionRegistry

        plugin = await self._db.execute(
            select(PluginModel).where(
                PluginModel.id == plugin_id,
                PluginModel.is_deleted.is_(False),
            )
        )
        plugin = plugin.scalar_one_or_none()
        if not plugin:
            from app.plugins.exceptions import PluginNotFoundError
            raise PluginNotFoundError(message=f"Plugin ID {plugin_id} not found")

        if plugin.status == PluginStatusEnum.DISABLED.value:
            return

        plugin_name = plugin.name
        emitter = PluginProgressEmitter(operator_id, plugin_name, "disable")

        # Check if other plugins depend on this plugin / 检查是否有其他插件依赖此插件
        dependents = await self._get_dependents(
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
            await self._run_lifecycle_guards(
                operation="disable",
                plugin_id=plugin_id,
                plugin_name=plugin_name,
                force=force,
                manifest=plugin.manifest or {},
            )

        # Check if storage driver is in use (force=True auto-switches to local instead of raising) / 检查存储驱动是否正在被使用（force=True 时自动切换到 local 而非抛错）
        await self._check_storage_driver_in_use(plugin_name, plugin.manifest or {}, force=force)

        # Unregister all extension points / 反注册所有扩展点
        await emitter.emit_step("extensions", "running", "Unregistering extensions...")
        ExtensionRegistry.get_instance().unregister_all(plugin_name)
        await emitter.emit_step("extensions", "success", "Extensions unregistered")

        # Deactivate plugin skill records / 停用插件技能记录
        await emitter.emit_step("skills", "running", "Deactivating skill records...")
        await self._deactivate_plugin_skill_records(plugin_name)
        await emitter.emit_step("skills", "success", "Skill records deactivated")

        # Call on_disable / 调用 on_disable
        await emitter.emit_step("on_disable", "running", "Running disable hook...")
        try:
            manifest = self._loader.load_manifest(plugin_name)
            plugin_cls = self._loader.load_plugin_class(plugin_name)
            ctx = create_plugin_context(
                plugin_name=plugin_name,
                manifest=manifest,
                db=self._db,
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

        # Disable does not uninstall deps — deps only cleaned on uninstall / 禁用不卸载依赖，重新启用无需重装
        # / 禁用不卸载依赖 — 依赖仅在 uninstall 时清理
        # 这样用户重新启用时无需等待重新安装

        # M50-T2: Mark plugin task definitions as inactive / 标记插件任务定义为非活跃，Beat 下次刷新后停止调度
        # / M50-T2: 将插件任务定义标记为非活跃，Celery Beat 下次刷新后自动停止调度
        await emitter.emit_step("tasks", "running", "Deactivating scheduled tasks...")
        await self._deactivate_plugin_task_definitions(plugin_name)
        await emitter.emit_step("tasks", "success", "Scheduled tasks deactivated")

        # Update status / 更新状态
        plugin.status = PluginStatusEnum.DISABLED.value
        plugin.enabled_at = None
        await self._db.flush()

        # Sync-disable plugin permissions in DB so menu/API no longer authorize plugin access
        # / 同步禁用 DB 中插件权限，使菜单/API 立即失效
        await emitter.emit_step("permissions", "running", "Disabling plugin permissions...")
        await self._set_plugin_permissions_enabled(plugin_name, False)

        # Revoke tenant-scoped plugin permissions from all plans
        # / 从所有套餐中移除企业端插件权限
        try:
            await self._revoke_plugin_menus_from_plans(plugin_name)
        except Exception as exc:
            logger.warning("Plugin {}: failed to revoke permissions from plans: {}", plugin_name, exc)

        await emitter.emit_step("permissions", "success", "Plugin permissions disabled")

        await emitter.emit_done(f"Plugin {plugin_name} disabled successfully")
        logger.info("Plugin {} disabled", plugin_name)

        # T4: Trigger system hook point / T4: 触发系统钩子点
        try:
            from app.plugins.system_hooks import SystemHookPoint, trigger_hook
            await trigger_hook(
                SystemHookPoint.PLUGIN_DISABLED,
                plugin_name=plugin_name, plugin_id=plugin_id,
            )
        except Exception as exc:
            logger.warning("system_hook PLUGIN_DISABLED failed: {}", exc)

    # ================================================================
    # dependencies / 依赖
    # ================================================================

    async def install_dependencies(
        self,
        plugin_id: int,
        *,
        install_python: bool = True,
    ) -> dict:
        """
        Explicitly install plugin dependencies (without changing plugin enable status).
        / 显式安装插件依赖（不改变插件启用状态）。

        For ops scenarios: manually install deps without going through enable/repair.
        / 用于运维场景：手动补装依赖，避免只能通过 enable/repair 间接触发。
        """
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel
        from app.plugins.exceptions import PluginNotFoundError

        async with _plugin_lock(plugin_id):
            result = await self._db.execute(
                select(PluginModel).where(
                    PluginModel.id == plugin_id,
                    PluginModel.is_deleted.is_(False),
                )
            )
            plugin = result.scalar_one_or_none()
            if not plugin:
                raise PluginNotFoundError(message=f"Plugin ID {plugin_id} not found")

            manifest = self._loader.load_manifest(plugin.name)
            py_deps = list(manifest.dependencies.python or [])
            installed_python: list[str] = []
            plugin_states = await self._collect_plugin_dependency_states(
                manifest,
                require_enabled=False,
            )
            python_preflight = await self._ensure_python_dependency_preflight(
                plugin.name,
                py_deps,
            )

            if install_python and py_deps:
                installed_python = await self._install_python_deps(plugin.name, py_deps)

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

    async def uninstall_dependencies(
        self,
        plugin_id: int,
        *,
        uninstall_python: bool = True,
        force: bool = False,
    ) -> dict:
        """
        Explicitly uninstall plugin dependencies (without uninstalling the plugin itself).
        / 显式卸载插件依赖（不卸载插件本体）。

        Safety: deps cannot be uninstalled while plugin is enabled.
        force param kept for backward compat only, no longer allows bypass.
        / 安全策略：插件处于 enabled 状态时，禁止卸载依赖。
        force 参数保留仅为兼容旧调用，实际不再允许绕过。
        """
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel
        from app.plugins.exceptions import PluginNotFoundError

        async with _plugin_lock(plugin_id):
            result = await self._db.execute(
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

            if force:
                logger.warning(
                    "Ignoring deprecated force=true in dependency uninstall for plugin {}",
                    plugin.name,
                )

            manifest = self._loader.load_manifest(plugin.name)
            py_deps = list(plugin.installed_packages or manifest.dependencies.python or [])
            plugin_states = await self._collect_plugin_dependency_states(
                manifest,
                require_enabled=False,
            )
            if uninstall_python and py_deps:
                await self._uninstall_python_deps(plugin.name, py_deps)

            return {
                "plugin_id": plugin.id,
                "plugin_name": plugin.name,
                "python": {
                    "declared": py_deps,
                    "attempted": uninstall_python,
                },
                "plugins": plugin_states,
                "forced": False,
            }

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
        _confirm_data_delete = confirm_data_delete
        from sqlalchemy import delete, select

        from app.models.system.plugin import Plugin as PluginModel
        from app.models.system.plugin_license import PluginLicense
        from app.models.system.plugin_version import PluginVersion
        from app.models.system.resource_tenant_assignment import (
            ResourceTenantAssignment,
        )
        from app.plugins.context_factory import create_plugin_context
        from app.plugins.registry import ExtensionRegistry

        plugin = await self._db.execute(
            select(PluginModel).where(
                PluginModel.id == plugin_id,
                PluginModel.is_deleted.is_(False),
            )
        )
        plugin = plugin.scalar_one_or_none()
        if not plugin:
            from app.plugins.exceptions import PluginNotFoundError
            raise PluginNotFoundError(message=f"Plugin ID {plugin_id} not found")

        plugin_name = plugin.name

        from app.plugins.progress import PluginProgressEmitter
        emitter = PluginProgressEmitter(operator_id, plugin_name, "uninstall")

        # 1. Check dependents (other plugins depend on this plugin) / 检查依赖（其他插件依赖此插件）
        dependents = await self._get_dependents(plugin_name)
        if dependents:
            raise PluginDependencyError(
                message=(
                    f"Cannot uninstall '{plugin_name}': plugins "
                    f"[{', '.join(dep['plugin'] for dep in dependents)}] depend on it. "
                    "Uninstall them first."
                ),
            )

        await self._run_lifecycle_guards(
            operation="uninstall",
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            force=False,
            manifest=plugin.manifest or {},
        )

        # 2. Disable (if enabled) / 禁用（如果启用中）
        if plugin.status == PluginStatusEnum.ENABLED.value:
            await emitter.emit_step("disable", "running", "Disabling plugin...")
            await self._disable_impl(plugin_id, skip_lifecycle_guards=True)
            await emitter.emit_step("disable", "success", "Plugin disabled")

        # 3. Call on_uninstall / 调用 on_uninstall
        await emitter.emit_step("on_uninstall", "running", "Running uninstall hook...")
        try:
            manifest = self._loader.load_manifest(plugin_name)
            plugin_cls = self._loader.load_plugin_class(plugin_name)
            ctx = create_plugin_context(
                plugin_name=plugin_name,
                manifest=manifest,
                db=self._db,
                granted_capabilities=plugin.granted_capabilities or [],
            )
            await plugin_cls().on_uninstall(ctx)
            await emitter.emit_step("on_uninstall", "success", "Uninstall hook completed")
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

        # 4. Unregister all extension points / 反注册所有扩展点
        await emitter.emit_step("cleanup_extensions", "running", "Unregistering extensions...")
        ExtensionRegistry.get_instance().unregister_all(plugin_name)
        await emitter.emit_step("cleanup_extensions", "success", "Extensions unregistered")

        # 4.1 Hard-delete plugin menu permission DB records (M50-T14)
        # _set_plugin_permissions_enabled only sets is_enabled=False; after uninstall should hard-delete
        # / 4.1 删除插件菜单权限 DB 记录（M50-T14）
        # _set_plugin_permissions_enabled 只设 is_enabled=False，uninstall 后应硬删除
        await self._delete_plugin_permissions_from_db(plugin_name)

        # 5. Delete plugin-created SkillPackage + Skill records / 删除插件创建的 SkillPackage + Skill 记录
        await emitter.emit_step("cleanup_skills", "running", "Removing skill records...")
        await self._delete_plugin_skill_records(plugin_name)
        await emitter.emit_step("cleanup_skills", "success", "Skill records removed")

        # 5.1 Delete plugin notification template records (M50-T1) / 删除插件通知模板记录（M50-T1）
        await emitter.emit_step("cleanup_notifications", "running", "Removing notification templates...")
        await self._delete_plugin_notification_templates(plugin_name)
        await emitter.emit_step("cleanup_notifications", "success", "Notification templates removed")

        # 5.2 Delete plugin task definition records (M50-T2) / 删除插件任务定义记录（M50-T2）
        await emitter.emit_step("cleanup_tasks", "running", "Removing task definitions...")
        await self._delete_plugin_task_definitions(plugin_name)
        await emitter.emit_step("cleanup_tasks", "success", "Task definitions removed")

        # 6-8. Remove AI features / 移除 AI features
        await emitter.emit_step("cleanup_ai_features", "running", "Removing AI features...")
        try:
            from app.models.system.agent_assignment import SystemAgentAssignment
            _escaped_pname = plugin_name.replace("_", "\\_").replace("%", "\\%")
            await self._db.execute(
                delete(SystemAgentAssignment).where(
                    SystemAgentAssignment.feature_code.like(f"plugin.{_escaped_pname}.%", escape="\\")
                )
            )
            await emitter.emit_step("cleanup_ai_features", "success", "AI features removed")
        except Exception as exc:
            await emitter.emit_step(
                "cleanup_ai_features",
                "success",
                build_public_error_text(
                    exc=exc,
                    message=_("common.server_error"),
                ),
            )
            logger.warning("Failed to cleanup AI features for {}: {}", plugin_name, exc)

        # 8.5 Pre-uninstall data backup (non-fatal, failure doesn't block uninstall) / 卸载前数据备份（non-fatal，失败不阻止卸载）
        try:
            from app.plugins.backup import backup_plugin_data
            await emitter.emit_step("cleanup_db", "running", "Backing up plugin data before deletion...")
            backup_path = await backup_plugin_data(plugin_name, plugin.version or "unknown", self._db)
            logger.info("Plugin {}: pre-uninstall backup saved to {}", plugin_name, backup_path)
        except Exception as exc:
            logger.warning("Plugin {}: pre-uninstall backup failed (continuing): {}", plugin_name, exc)

        # 9. Database cleanup / 数据库清理
        await emitter.emit_step("cleanup_db", "running", "Cleaning up database tables...")
        await self._cleanup_plugin_database(plugin_name)
        await emitter.emit_step("cleanup_db", "success", "Database tables cleaned")

        if cleanup_dependencies:
            # 10. Uninstall Python deps (shared check: other plugins/project/reverse deps) / 卸载 Python 依赖（共享检查：其他插件/项目/反向依赖）
            if plugin.installed_packages:
                await emitter.emit_step("cleanup_pip", "running", "Uninstalling Python dependencies...")
                await self._uninstall_python_deps(plugin_name, plugin.installed_packages)
                await emitter.emit_step("cleanup_pip", "success", "Python dependencies cleaned")
            else:
                await emitter.emit_step("cleanup_pip", "success", "No Python dependencies to clean")
        else:
            await emitter.emit_step(
                "cleanup_pip",
                "success",
                "Skipped dependency cleanup (use dependency management API for explicit cleanup)",
            )

        # 11-13. Delete related records / 删除关联记录
        await emitter.emit_step("cleanup_records", "running", "Removing plugin records...")
        await self._db.execute(
            delete(PluginVersion).where(PluginVersion.plugin_id == plugin_id)
        )
        await self._db.execute(
            delete(ResourceTenantAssignment).where(
                ResourceTenantAssignment.resource_type == "plugin",
                ResourceTenantAssignment.resource_id == plugin_id,
            )
        )
        await self._db.execute(
            delete(PluginLicense).where(PluginLicense.plugin_id == plugin_id)
        )
        await emitter.emit_step("cleanup_records", "success", "Plugin records removed")

        # 14. Delete plugin record + physical files / 删除 plugins 记录 + 物理文件
        await emitter.emit_step("cleanup_files", "running", "Removing plugin files...")
        await self._db.execute(
            delete(PluginModel).where(PluginModel.id == plugin_id)
        )
        await self._db.flush()

        plugin_dir = PLUGINS_DIR / plugin_name
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir, ignore_errors=True)

        from app.plugins.module_loader import unload_plugin_modules
        unload_plugin_modules(plugin_name)
        await emitter.emit_step("cleanup_files", "success", "Plugin files removed")

        logger.info("Plugin {} uninstalled completely", plugin_name)
        await emitter.emit_done(f"Plugin {plugin_name} uninstalled completely")

    # ================================================================
    # Dependency checks / 依赖检查
    # ================================================================

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
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel

        filters = [
            PluginModel.name != plugin_name,
            PluginModel.is_deleted.is_(False),
        ]
        if statuses:
            filters.append(PluginModel.status.in_(sorted(statuses)))

        result = await self._db.execute(
            select(
                PluginModel.id,
                PluginModel.name,
                PluginModel.version,
                PluginModel.status,
                PluginModel.manifest,
            ).where(*filters)
        )
        dependents: list[dict[str, object]] = []
        for plugin_id, name, version, status, manifest_data in result.all():
            try:
                requirements = normalize_plugin_dependencies(manifest_data)
            except Exception as exc:
                logger.warning(
                    "Failed to normalize dependent plugin manifest {}: {}",
                    name,
                    exc,
                )
                continue

            for requirement in requirements:
                if requirement.plugin != plugin_name:
                    continue
                dependents.append(
                    {
                        "plugin_id": plugin_id,
                        "plugin": name,
                        "version": version,
                        "status": status,
                        "required_version": requirement.version,
                        "source": requirement.source,
                    }
                )
        return dependents

    async def get_dependents(self, plugin_id: int) -> list[dict[str, object]]:
        """Get list of plugins that depend on the specified plugin (for API use) / 获取依赖指定插件的插件列表（API 用）"""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel

        result = await self._db.execute(
            select(PluginModel.name).where(
                PluginModel.id == plugin_id,
                PluginModel.is_deleted.is_(False),
            )
        )
        name = result.scalar_one_or_none()
        if not name:
            return []
        return await self._get_dependents(name)

    async def get_dependencies(self, plugin_id: int) -> list[dict[str, object]]:
        """Get list of dependency plugins for the specified plugin (for API use) / 获取指定插件的依赖插件列表（API 用）"""
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel

        result = await self._db.execute(
            select(PluginModel.name, PluginModel.manifest).where(
                PluginModel.id == plugin_id,
                PluginModel.is_deleted.is_(False),
            )
        )
        row = result.one_or_none()
        if not row:
            return []
        plugin_name, manifest_data = row
        if not manifest_data or not isinstance(manifest_data, dict):
            return []
        return await self._collect_plugin_dependency_states(
            manifest_data,
            require_enabled=False,
        )

    # ================================================================
    # Internal methods / 内部方法
    # ================================================================

    async def _set_plugin_permissions_enabled(self, plugin_name: str, is_enabled: bool) -> None:
        """
        Batch enable or disable plugin permission records in DB.
        / 批量启用或禁用插件在 DB 中的权限记录。

        Covers:
        - menu:admin.plugin_{safe_name}_*
        - menu:tenant.plugin_{safe_name}_*
        - plugin.{plugin_name}.*
        / 覆盖菜单权限与插件动作权限。
        """
        from sqlalchemy import or_, update

        from app.models.auth.permission import Permission

        safe_name = plugin_name.replace("-", "_")
        admin_prefix = f"menu:admin.plugin_{safe_name}_"
        tenant_prefix = f"menu:tenant.plugin_{safe_name}_"
        plugin_prefix = f"plugin.{plugin_name}."

        await self._db.execute(
            update(Permission)
            .where(
                or_(
                    Permission.code.startswith(admin_prefix, autoescape=True),
                    Permission.code.startswith(tenant_prefix, autoescape=True),
                    Permission.code.startswith(plugin_prefix, autoescape=True),
                ),
                Permission.is_deleted.is_(False),
            )
            .values(is_enabled=is_enabled)
        )
        action = "enabled" if is_enabled else "disabled"
        logger.info("Plugin {}: {} plugin permissions in DB", plugin_name, action)

    async def _restore_plugin_permissions(
        self,
        plugin_name: str,
        *,
        auto_grant_plans: bool = True,
    ) -> None:
        """
        Strictly rebuild and enable plugin permission rows.
        / 严格重建并启用插件权限记录。

        This is shared by enable / repair / startup restore so those flows
        fail-close consistently when menu/action permissions cannot be restored.
        / enable / repair / startup restore 共享此逻辑，确保菜单/动作权限恢复失败时统一 fail-close。
        """
        from app.rbac.sync import PermissionSyncService

        perm_sync = PermissionSyncService(self._db)
        await perm_sync.sync_plugin_permissions(plugin_name)
        await self._set_plugin_permissions_enabled(plugin_name, True)
        if auto_grant_plans:
            await self._auto_grant_plugin_menus_to_plans(plugin_name)

    async def _assert_plugin_runtime_enable_guards(
        self,
        plugin: Plugin,
        manifest,
        *,
        action: str,
        error_cls: type[Exception] = PluginDependencyError,
    ) -> None:
        """
        Shared runtime guards for enable-like flows.
        / enable 类链路共享的运行前置校验。
        """
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel
        from app.plugins.license import assert_plugin_license_active

        plugin_name = plugin.name

        await assert_plugin_license_active(
            plugin.id,
            plugin.pricing_type,
            self._db,
            plugin_name=plugin_name,
            operation=action,
        )

        # DEBUG mode: sync key fields from disk plugin.yaml to DB (scope/manifest etc.) / DEBUG 模式：从磁盘 plugin.yaml 同步到 DB
        # / DEBUG 模式：同步磁盘 plugin.yaml 的关键字段到 DB（scope/manifest 等）
        from app.core.config import settings

        if settings.DEBUG:
            plugin.scope = manifest.scope
            plugin.manifest = manifest.model_dump()
            plugin.display_name = resolve_i18n(manifest.display_name)
            plugin.description = resolve_i18n(manifest.description) if manifest.description else plugin.description
            plugin.icon = manifest.icon or plugin.icon
            plugin.icon_color = manifest.icon_color or plugin.icon_color
            plugin.tags = manifest.tags
            plugin.installed_packages = manifest.dependencies.python or []
            plugin.ai_requirements = manifest.ai_requirements.model_dump() if manifest.ai_requirements else plugin.ai_requirements
            await self._db.flush()

        # Check compatibility.conflicts (enabled conflicting plugins) / 检查 compatibility.conflicts（已启用的冲突插件）
        if manifest.compatibility and manifest.compatibility.conflicts:
            for conflict in manifest.compatibility.conflicts:
                dep_result = await self._db.execute(
                    select(PluginModel.status).where(
                        PluginModel.name == conflict.plugin,
                        PluginModel.is_deleted.is_(False),
                    )
                )
                dep_status = dep_result.scalar_one_or_none()
                if dep_status == PluginStatusEnum.ENABLED.value:
                    conflict_reason = (
                        conflict.reason.get("zh-CN")
                        or conflict.reason.get("en")
                        or "incompatible"
                    ) if conflict.reason else "incompatible"
                    raise error_cls(
                        message=(
                            f"Cannot {action} '{plugin_name}': conflicts with enabled plugin "
                            f"'{conflict.plugin}' ({conflict_reason}). Disable it first."
                        ),
                    )

        await self._assert_plugin_dependencies_ready(
            manifest,
            plugin_name=plugin_name,
            require_enabled=True,
            error_cls=error_cls,
            action=action,
        )

    async def _auto_grant_plugin_menus_to_plans(self, plugin_name: str) -> None:
        """
        Auto-grant tenant-scoped plugin permissions to all active plans.
        Uses INSERT ... ON CONFLICT DO NOTHING (idempotent).
        If plugin declares tenant menu policy as `manual_entitlement`, skip auto-grant.
        / 将企业端插件权限自动关联到所有活跃套餐（幂等）。
        若插件声明 `manual_entitlement`，跳过自动授权。
        """
        from sqlalchemy import select, text

        from app.models.auth.permission import Permission
        from app.models.tenant.tenant_plan import TenantPlan
        from app.plugins.registry import ExtensionRegistry

        safe_name = plugin_name.replace("-", "_")
        tenant_prefix = f"menu:tenant.plugin_{safe_name}_%"
        plugin_prefix = f"plugin.{plugin_name}.%"

        policy = ExtensionRegistry.get_instance().get_plugin_tenant_menu_policy(plugin_name)
        if policy.get("grant_mode") == "manual_entitlement":
            logger.info(
                "Plugin {}: skip auto-grant due to tenant menu policy manual_entitlement",
                plugin_name,
            )
            return

        perm_ids = (await self._db.execute(
            select(Permission.id).where(
                (
                    Permission.code.like(tenant_prefix)
                    | Permission.code.like(plugin_prefix)
                ),
                Permission.scope.in_(["tenant", "both"]),
                Permission.is_enabled.is_(True),
                Permission.is_deleted.is_(False),
            )
        )).scalars().all()
        if not perm_ids:
            return

        plan_ids = (await self._db.execute(
            select(TenantPlan.id).where(TenantPlan.is_active.is_(True))
        )).scalars().all()
        if not plan_ids:
            return

        pairs = [(pid, perm_id) for pid in plan_ids for perm_id in perm_ids]
        await self._db.execute(
            text(
                "INSERT INTO tenant_plan_permissions (plan_id, permission_id) "
                "VALUES (:plan_id, :permission_id) "
                "ON CONFLICT DO NOTHING"
            ),
            [{"plan_id": p, "permission_id": perm} for p, perm in pairs],
        )
        await self._db.flush()
        logger.info(
            "Plugin {}: auto-granted {} permission(s) to {} plan(s)",
            plugin_name, len(perm_ids), len(plan_ids),
        )

    async def _revoke_plugin_menus_from_plans(self, plugin_name: str) -> None:
        """
        Revoke tenant-scoped plugin permissions from all plans on disable.
        / 插件禁用时，从所有套餐中移除企业端插件权限。
        """
        from sqlalchemy import select

        from app.models.auth.permission import Permission
        from app.models.tenant.tenant_plan import tenant_plan_permissions

        safe_name = plugin_name.replace("-", "_")
        tenant_prefix = f"menu:tenant.plugin_{safe_name}_%"
        plugin_prefix = f"plugin.{plugin_name}.%"

        perm_ids = (await self._db.execute(
            select(Permission.id).where(
                (
                    Permission.code.like(tenant_prefix)
                    | Permission.code.like(plugin_prefix)
                ),
                Permission.scope.in_(["tenant", "both"]),
                Permission.is_deleted.is_(False),
            )
        )).scalars().all()
        if not perm_ids:
            return

        await self._db.execute(
            tenant_plan_permissions.delete().where(
                tenant_plan_permissions.c.permission_id.in_(perm_ids)
            )
        )
        await self._db.flush()
        logger.info(
            "Plugin {}: revoked {} permission(s) from all plans",
            plugin_name, len(perm_ids),
        )

    async def _check_storage_driver_in_use(
        self, plugin_name: str, manifest_data: dict, *, force: bool = False
    ) -> None:
        """
        检查该插件提供的存储驱动是否正在被使用 / Check if this plugin provides storage drivers that are currently in use.

        Queries platform_storage_driver and all tenant tenant_storage_driver configs.
        If any reference a driver code from this plugin, block the disable.
        """
        extensions = manifest_data.get("extensions", {})
        storage_drivers = extensions.get("storage_drivers", [])
        if not storage_drivers:
            return

        driver_codes = {
            sd.get("code") for sd in storage_drivers if sd.get("code")
        }
        if not driver_codes:
            return

        from app.configs.service import ConfigService

        config_service = ConfigService(self._db)

        # Check platform storage driver / 检查平台存储驱动
        platform_driver = await config_service.get_platform_config(
            "platform_storage_driver", default="local"
        )
        if str(platform_driver) in driver_codes:
            if not force:
                raise PluginError(
                    message=(
                        f"Cannot disable '{plugin_name}': storage driver "
                        f"'{platform_driver}' is used as platform storage driver. "
                        f"Switch to another driver first."
                    ),
                )
            logger.warning(
                "Force-disabling '{}': switching platform storage driver from '{}' to 'local'",
                plugin_name, platform_driver,
            )
            await config_service.set_platform_config("platform_storage_driver", "local")

        # Check tenant storage drivers — batch query to avoid N+1 / 检查企业存储驱动（批量查询避免 N+1）
        from sqlalchemy import and_, select

        from app.models.system.config import SystemConfig, SystemConfigValue

        # Batch fetch: query tenant_storage_driver and tenant_storage_mode configs in one go
        # Use IN (subquery) on config_id to avoid N+1 per-tenant queries
        # / 批量获取：一次查出 tenant_storage_driver 和 tenant_storage_mode 两张配置表
        # 用 IN (subquery) 关联 config_id，避免 N+1 per-tenant 查询
        config_ids_result = await self._db.execute(
            select(SystemConfig.id, SystemConfig.key).where(
                SystemConfig.key.in_(["tenant_storage_driver", "tenant_storage_mode"]),
                SystemConfig.is_deleted.is_(False),
            )
        )
        config_id_map: dict[str, int] = {row[1]: row[0] for row in config_ids_result.all()}

        driver_config_id = config_id_map.get("tenant_storage_driver")
        mode_config_id = config_id_map.get("tenant_storage_mode")

        if driver_config_id:
            # Get all tenants' driver configs / 获取所有企业的驱动配置
            driver_values_result = await self._db.execute(
                select(SystemConfigValue.tenant_id, SystemConfigValue.value).where(
                    and_(
                        SystemConfigValue.config_id == driver_config_id,
                        SystemConfigValue.is_deleted.is_(False),
                    )
                )
            )
            # Get all tenants' storage mode configs (one-shot batch) / 获取所有企业的存储模式配置（一次性批量）
            mode_by_tenant: dict[int, str] = {}
            if mode_config_id:
                mode_values_result = await self._db.execute(
                    select(SystemConfigValue.tenant_id, SystemConfigValue.value).where(
                        and_(
                            SystemConfigValue.config_id == mode_config_id,
                            SystemConfigValue.is_deleted.is_(False),
                        )
                    )
                )
                for t_id, mode_raw in mode_values_result.all():
                    try:
                        mode_by_tenant[t_id] = str(json.loads(mode_raw) if mode_raw else "platform")
                    except (json.JSONDecodeError, TypeError):
                        mode_by_tenant[t_id] = str(mode_raw) if mode_raw else "platform"

            for row in driver_values_result.all():
                tenant_id, raw_value = row
                if raw_value:
                    try:
                        val = json.loads(raw_value)
                    except (json.JSONDecodeError, TypeError):
                        val = raw_value
                    if str(val) in driver_codes:
                        mode = mode_by_tenant.get(tenant_id, "platform")
                        if mode in ("custom", "admin_override"):
                            if not force:
                                raise PluginError(
                                    message=(
                                        f"Cannot disable '{plugin_name}': storage driver "
                                        f"'{val}' is used by tenant {tenant_id}. "
                                        f"Switch the tenant to another driver first."
                                    ),
                                )
                            logger.warning(
                                "Force-disabling '{}': resetting tenant {} storage mode to 'platform'",
                                plugin_name, tenant_id,
                            )
                            await config_service.set_tenant_config(tenant_id, "tenant_storage_mode", "platform")

    async def _install_python_deps(
        self, plugin_name: str, requirements: list[str]
    ) -> list[str]:
        """Install Python dependencies into the current venv.
        / 安装 Python 依赖到当前 venv。

        First checks via importlib.metadata whether packages already satisfy version constraints;
        skips pip if satisfied to avoid network requests on every startup causing false errors on flaky networks.
        Only calls pip install when package is missing or version doesn't match.
        / 先用 importlib.metadata 检查包是否已满足版本约束；
        已满足则跳过 pip，避免每次启动都触发网络请求导致网络抖动时误报异常。
        只有在包缺失或版本不满足时才调用 pip install。

        Calls importlib.invalidate_caches() after pip install to refresh import path cache,
        ensuring newly installed packages can be imported without server restart.
        / pip 安装成功后调用 importlib.invalidate_caches() 刷新导入路径缓存，
        确保新安装的包无需重启服务器即可 import。
        """
        import importlib
        import importlib.metadata as _imeta
        import importlib.util as _iutil
        import site

        from packaging.requirements import Requirement
        from packaging.version import Version

        def _module_candidates(req_name: str, dist=None) -> list[str]:
            """根据 requirement 名构建可能的 import 模块名 / Build likely import module names for a requirement."""
            names: list[str] = []

            # Heuristic fallback: `foo-bar` -> `foo_bar` / 启发式回退：包名转模块名
            fallback = req_name.replace("-", "_").replace(".", "_").strip()
            if fallback and fallback.isidentifier():
                names.append(fallback)

            # Preferred source: top_level.txt from wheel metadata / 优先来源：wheel 元数据中的 top_level.txt
            if dist is not None:
                with suppress(Exception):
                    top_level = dist.read_text("top_level.txt")
                    if top_level:
                        for raw in top_level.splitlines():
                            mod = raw.strip()
                            if mod and mod.isidentifier() and mod not in names:
                                names.append(mod)

            return names

        def _has_importable_module(candidates: list[str]) -> bool | None:
            """有候选时返回 True/False，无候选时返回 None / Return True/False when candidates exist; None when no candidates."""
            if not candidates:
                return None
            for mod in candidates:
                with suppress(Exception):
                    if _iutil.find_spec(mod) is not None:
                        return True
            return False

        installed: list[str] = []
        needs_cache_refresh = False
        pip_python = self._resolve_pip_python_executable()
        pip_env = self._build_python_install_env(plugin_name)
        await self._ensure_python_dependency_preflight(plugin_name, requirements)

        for req in requirements:
            normalized_req = req.strip()
            try:
                req_obj = Requirement(normalized_req)
            except Exception as exc:
                raise PluginDependencyError(
                    message=resolve_public_error_message(
                        exc,
                        fallback_message=_("plugin.error.dependency_failed"),
                    ),
                ) from exc

            if req_obj.url:
                raise PluginDependencyError(
                    message=(
                        f"Direct URL requirement is not allowed for plugin '{plugin_name}': "
                        f"{normalized_req}"
                    ),
                )
            marker_text = str(req_obj.marker) if req_obj.marker else ""
            if marker_text and any(ch in marker_text for ch in [";", "&", "|", "`", "$", "\n", "\r"]):
                # Reject markers containing shell metacharacters to prevent log/command parameter pollution
                # / 拒绝包含 shell 元字符的 marker，防止极端情况下拼接污染日志/命令参数
                raise PluginDependencyError(
                    message=(
                        f"Invalid environment marker in requirement '{normalized_req}'"
                    ),
                )
            if req_obj.marker and not req_obj.marker.evaluate():
                logger.debug(
                    "Skipping requirement for {} due environment marker mismatch: {}",
                    plugin_name,
                    normalized_req,
                )
                continue

            # ── Check if version constraint is already satisfied, skip pip if so ──
            # / ── 检查是否已满足版本约束，满足则跳过 pip ──
            force_reinstall = False
            import_candidates = _module_candidates(req_obj.name)
            try:
                dist = _imeta.distribution(req_obj.name)
                import_candidates = _module_candidates(req_obj.name, dist)
                metadata_text = None
                with suppress(Exception):
                    metadata_text = dist.read_text("METADATA")
                if not metadata_text:
                    # Defense: cancelled/interrupted install may leave corrupted dist-info with only INSTALLER/REQUESTED
                    # / 防御：取消/中断安装可能留下仅含 INSTALLER/REQUESTED 的残缺 dist-info
                    force_reinstall = True
                    logger.warning(
                        "Plugin {}: package {} metadata is corrupted, forcing reinstall",
                        plugin_name,
                        req_obj.name,
                    )

                installed_version = getattr(dist, "version", None)
                if installed_version:
                    try:
                        if (
                            not req_obj.specifier
                            or Version(installed_version) in req_obj.specifier
                        ):
                            importable = _has_importable_module(import_candidates)
                            if importable is False:
                                force_reinstall = True
                                logger.warning(
                                    "Plugin {}: package {} is installed ({}) but import path is missing, forcing reinstall",
                                    plugin_name,
                                    req_obj.name,
                                    installed_version,
                                )
                            elif not force_reinstall:
                                logger.debug(
                                    "Skipping pip install for {}: already satisfied ({}=={})",
                                    plugin_name,
                                    req_obj.name,
                                    installed_version,
                                )
                                continue
                    except Exception as exc:
                        # Some abnormal dist metadata may return invalid version; fallback to reinstall to avoid 500
                        # / 某些异常分发元数据可能返回非法 version；回退到重装，避免 500
                        force_reinstall = True
                        logger.warning(
                            "Plugin {}: invalid installed version for {} ({!r}), reinstalling: {}",
                            plugin_name,
                            req_obj.name,
                            installed_version,
                            exc,
                        )
                else:
                    force_reinstall = True
                    logger.debug(
                        "Plugin {}: installed package {} has no version metadata, reinstalling",
                        plugin_name,
                        req_obj.name,
                    )
            except _imeta.PackageNotFoundError:
                pass  # 包不存在，继续走 pip install

            install_args = [pip_python, "-m", "pip", "install", normalized_req, "--quiet"]
            if force_reinstall:
                install_args.extend(["--upgrade", "--force-reinstall"])

            result = await _run_subprocess_async(
                *install_args,
                timeout=180,
                shell=False,
                env=pip_env,
            )
            if result.returncode != 0:
                raise PluginDependencyError(
                    message=f"Failed to install {normalized_req}: {result.stderr.strip()}",
                )

            # Post-install conservative verification: only strongly verify importability when metadata provides top_level, to avoid false positives from distribution/import name mismatch (e.g. Pillow -> PIL) / 安装后保守校验：仅当元数据提供 top_level 时强校验可导入性，避免分发名与导入名不一致的误报
            # / 安装后做一次保守校验：仅当 metadata 能提供 top_level 时才强校验 importability，
            # 避免因发行名/导入名不一致导致误报（如 Pillow -> PIL）。
            post_top_level = ""
            try:
                post_dist = _imeta.distribution(req_obj.name)
                post_top_level = post_dist.read_text("top_level.txt") or ""
            except Exception:
                post_dist = None
            if post_dist is not None and post_top_level.strip():
                post_candidates = _module_candidates(req_obj.name, post_dist)
                post_importable = _has_importable_module(post_candidates)
                if post_importable is False:
                    raise PluginDependencyError(
                        message=(
                            f"Installed {normalized_req}, but runtime import check failed "
                            f"(candidates: {', '.join(post_candidates)})"
                        ),
                    )

            installed.append(normalized_req)
            needs_cache_refresh = True
            logger.info("Installed {} for plugin {}", normalized_req, plugin_name)

        if needs_cache_refresh:
            # Ensure newly installed packages are immediately importable (no restart needed), refresh sys.path and importlib cache / 确保新安装的包立即可导入（无需重启），刷新 sys.path 与 importlib 缓存
            for sp in site.getsitepackages():
                if sp not in sys.path:
                    sys.path.insert(0, sp)
            importlib.invalidate_caches()
            logger.debug("Import caches refreshed after pip install for plugin {}", plugin_name)

        return installed

    def _resolve_pip_python_executable(self) -> str:
        """
        解析用于 pip 操作的 Python 解释器 / Resolve the Python executable used for pip operations.

        Why:
        - In some Windows starts, uvicorn may run as:
          `python.exe <project>/.venv/Scripts/uvicorn.exe ...`
          where `sys.executable` points to global Python, but runtime packages are
          imported from project `.venv/Lib/site-packages`.
        - If pip uses the wrong interpreter, dependencies appear "installed"
          while runtime `import` still fails.
        """
        import site

        py_rel = Path("Scripts/python.exe" if _IS_WINDOWS else "bin/python")
        candidates: list[Path] = []

        # 1) Active virtual env declared by environment. / 环境变量声明的活动虚拟环境
        venv = os.environ.get("VIRTUAL_ENV")
        if venv:
            candidates.append(Path(venv) / py_rel)

        # 2) Project-local .venv (backend/.venv). / 项目内 .venv
        candidates.append((PLUGINS_DIR.parent / ".venv") / py_rel)

        # 3) Derive venv root from runtime site-packages paths. / 由 site-packages 反推 venv 根
        path_sources: list[str] = []
        with suppress(Exception):
            path_sources.extend(site.getsitepackages())
        path_sources.extend(str(p) for p in sys.path if "site-packages" in str(p).lower())

        for raw in path_sources:
            try:
                sp = Path(raw)
                if sp.name.lower() == "site-packages" and sp.parent.name.lower() == "lib":
                    candidates.append(sp.parent.parent / py_rel)
            except Exception:
                continue

        # Keep order, drop duplicates/non-existing. / 保序去重并跳过不存在路径
        seen: set[str] = set()
        existing: list[Path] = []
        for cand in candidates:
            key = os.path.normcase(str(cand))
            if key in seen:
                continue
            seen.add(key)
            if cand.is_file():
                existing.append(cand)

        if existing:
            chosen = str(existing[0])
            if os.path.normcase(chosen) != os.path.normcase(sys.executable):
                logger.info(
                    "Plugin lifecycle pip interpreter switched: runtime={} pip={}",
                    sys.executable,
                    chosen,
                )
            return chosen

        return sys.executable

    def _build_python_install_env(self, plugin_name: str) -> dict[str, str]:
        """
        构建 pip 子进程环境（Windows 下补全 Cargo PATH）/ Build pip subprocess env with a resilient Cargo PATH on Windows.

        Some Rust-backed packages (e.g. y-py) run build backends that require `cargo`
        to be resolvable in the current process PATH. Rust may be installed, but PATH
        not refreshed in this uvicorn process. We prepend discovered cargo dirs.
        """
        env = os.environ.copy()
        current_path = env.get("PATH", "")

        # Fast path: already available. / 快速路径：已可用则直接返回
        if shutil.which("cargo", path=current_path):
            return env

        cargo_bin_name = "cargo.exe" if _IS_WINDOWS else "cargo"
        candidate_dirs: list[Path] = []

        # 1) Standard rustup/cargo home / 标准 rustup 安装目录
        home_cargo_bin = Path.home() / ".cargo" / "bin"
        candidate_dirs.append(home_cargo_bin)

        cargo_home = env.get("CARGO_HOME")
        if cargo_home:
            candidate_dirs.append(Path(cargo_home) / "bin")

        # 2) Some build tools (maturin/puccinialin) bootstrap rustup into cache dirs. / 部分构建工具把 rustup 装到缓存目录
        local_app_data = env.get("LOCALAPPDATA")
        if local_app_data:
            cache_root = Path(local_app_data) / "puccinialin" / "puccinialin" / "Cache"
            if cache_root.is_dir():
                with suppress(Exception):
                    for cargo_path in cache_root.rglob(cargo_bin_name):
                        candidate_dirs.append(cargo_path.parent)

        # Keep only existing dirs containing cargo binary, and de-duplicate / 仅保留含 cargo 二进制且存在的目录，并去重
        resolved_dirs: list[str] = []
        seen: set[str] = set()
        for p in candidate_dirs:
            cargo_path = p / cargo_bin_name
            if not cargo_path.exists():
                continue
            p_str = str(p)
            if p_str in seen:
                continue
            seen.add(p_str)
            resolved_dirs.append(p_str)

        if not resolved_dirs:
            logger.warning(
                "Plugin {}: cargo not found on PATH and no fallback cargo dir discovered",
                plugin_name,
            )
            return env

        env["PATH"] = os.pathsep.join(
            [*resolved_dirs, current_path] if current_path else resolved_dirs
        )
        logger.info(
            "Plugin {}: prepended {} Cargo PATH candidate(s) for pip install",
            plugin_name,
            len(resolved_dirs),
        )
        return env

    @staticmethod
    def _normalize_pkg_name(raw: str) -> str:
        """将 pip requirement 字符串规范化为小写包名 / Normalize a pip requirement string to a lowercase package name.

        Handles version specifiers (>=, ==, <, >, !=, ~=) and PEP 503 name normalization
        (hyphens, underscores, dots → unified lowercase).
        """
        import re
        pkg = re.split(r"[><=!~;@\[]", raw, maxsplit=1)[0].strip()
        return re.sub(r"[-_.]+", "-", pkg).lower()

    def _load_project_pyproject_dependencies(self) -> set[str]:
        """从主项目 pyproject.toml 加载包名（dependencies + optional-dependencies 各组）。"""
        protected: set[str] = set()
        pyproject_path = PLUGINS_DIR.parent / "pyproject.toml"
        if not pyproject_path.is_file():
            return protected
        try:
            raw = pyproject_path.read_bytes()
            if sys.version_info >= (3, 11):
                import tomllib

                cfg = tomllib.loads(raw.decode(encoding="utf-8"))
            else:
                import tomli

                cfg = tomli.loads(raw.decode(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to parse pyproject.toml: {}", exc)
            return protected

        project_cfg = cfg.get("project") or {}
        for item in project_cfg.get("dependencies") or []:
            if isinstance(item, str):
                protected.add(self._normalize_pkg_name(item))
        optional = project_cfg.get("optional-dependencies") or {}
        for deps in optional.values():
            if not isinstance(deps, list):
                continue
            for item in deps:
                if isinstance(item, str):
                    protected.add(self._normalize_pkg_name(item))
        return protected

    async def _uninstall_python_deps(
        self, plugin_name: str, packages: list[str]
    ) -> None:
        """Uninstall plugin-exclusive Python dependencies (3-layer safety check).
        / 卸载插件独占的 Python 依赖（三层安全检查）

        Safety policy (keep if any check hits):
        1. Other installed plugins' installed_packages declare the same package
        2. Main project pyproject.toml declares the same package
        3. pip show Required-by is non-empty (other packages reverse-depend on it)
        / 安全策略（任一命中则保留不删）：
        1. 其他已安装插件的 installed_packages 中声明了同名包
        2. 主项目 pyproject.toml（dependencies 与 optional-dependencies）中声明了同名包
        3. pip show 的 Required-by 非空（有其他包反向依赖它）
        """
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel

        # Layer 1: Collect other plugins' dependencies / 收集其他插件的依赖
        result = await self._db.execute(
            select(PluginModel.installed_packages).where(
                PluginModel.name != plugin_name,
                PluginModel.is_deleted.is_(False),
            )
        )
        other_plugin_deps: set[str] = set()
        for row in result.scalars():
            if row:
                for req in row:
                    other_plugin_deps.add(self._normalize_pkg_name(req))

        # Layer 2: Main project pyproject.toml protection list / 主项目 pyproject.toml 保护名单
        project_deps = self._load_project_pyproject_dependencies()
        pip_python = self._resolve_pip_python_executable()

        for req in packages:
            pkg = self._normalize_pkg_name(req)
            if not pkg:
                continue

            # Check 1: other plugin needs it / 检查 1：其他插件需要
            if pkg in other_plugin_deps:
                logger.info("Kept {} (still needed by other plugins)", pkg)
                continue

            # Check 2: main project needs it / 检查 2：主项目需要
            if pkg in project_deps:
                logger.info("Kept {} (declared in project pyproject.toml)", pkg)
                continue

            # Check 3: pip reverse dependency check / 检查 3：pip 反向依赖检查
            try:
                pip_result = await _run_subprocess_async(
                    pip_python, "-m", "pip", "show", pkg,
                    timeout=30,
                    shell=False,
                )
                if pip_result.returncode == 0:
                    for line in pip_result.stdout.splitlines():
                        if line.startswith("Required-by:"):
                            required_by = line.split(":", 1)[1].strip()
                            if required_by:
                                logger.info(
                                    "Kept {} (Required-by: {})", pkg, required_by,
                                )
                                break
                    else:
                        # No Required-by found or empty → safe to remove / 无 Required-by 或为空 → 可安全移除
                        await _run_subprocess_async(
                            pip_python, "-m", "pip", "uninstall", pkg, "-y", "--quiet",
                            timeout=60,
                            shell=False,
                        )
                        logger.info("Uninstalled {} (no longer needed)", pkg)
                else:
                    logger.info("Package {} not installed, skipping", pkg)
            except Exception as exc:
                logger.warning("Failed to check/uninstall {}: {}", pkg, exc)

    async def _purge_orphaned_alembic_stamps(self) -> None:
        """Purge orphaned version stamps in alembic_version that no longer have corresponding migration files.
        / 升级前清除 alembic_version 中已无对应迁移文件的孤立版本戳。

        Background: if downgrade fails during plugin uninstall, or revision ID prefix doesn't
        match plugin name (e.g. some plugins use custom prefix like ncc_001),
        the version stamp remains in alembic_version, causing subsequent upgrades to fail:
          "Can't locate revision identified by 'xxx'"
        This method scans all currently installed migration files to get valid revision IDs,
        then deletes stamps that don't belong to any known migration.
        / 背景：插件卸载时若 downgrade 失败或 revision ID 前缀与插件名不一致，
        其版本戳会残留在 alembic_version，导致后续任何 upgrade 均报错。
        此方法通过扫描所有当前安装的迁移文件获取合法 revision ID，
        然后删除不属于任何已知迁移的孤立戳。
        """
        import re as _re

        from sqlalchemy import text

        # 1. Collect valid revision IDs from main project + DB-registered plugins
        # / 1. 收集主项目 + 数据库已注册插件的合法 revision ID
        known_revisions: set[str] = set()
        dirs_to_scan = [
            Path(path)
            for path in build_migration_version_locations(
                backend_dir=PLUGINS_DIR.parent,
            )
        ]

        for vdir in dirs_to_scan:
            if not vdir.is_dir():
                continue
            for f in vdir.iterdir():
                if f.suffix == ".py" and f.name != "__init__.py":
                    try:
                        source = f.read_text(encoding="utf-8")
                        m = _re.search(
                            r'^revision\s*(?::[^=]*)?=\s*["\']([^"\']+)["\']',
                            source,
                            _re.MULTILINE,
                        )
                        if m:
                            known_revisions.add(m.group(1))
                    except Exception:
                        pass

        # 2. Query all version stamps in alembic_version / 查询 alembic_version 中的全部版本戳
        try:
            result = await self._db.execute(text("SELECT version_num FROM alembic_version"))
            all_stamps = [row[0] for row in result.fetchall()]
        except Exception:
            return

        # 3. Delete orphaned stamps (not in any known migration file)
        # / 3. 删除孤立戳（不在任何已知迁移文件中）
        orphaned = [s for s in all_stamps if s not in known_revisions]
        for stamp in orphaned:
            logger.warning(
                "Purging orphaned alembic stamp '{}' (no migration file found for it)", stamp
            )
            await self._db.execute(
                text("DELETE FROM alembic_version WHERE version_num = :vid"),
                {"vid": stamp},
            )
        if orphaned:
            await self._db.flush()
            logger.info("Purged {} orphaned alembic stamp(s): {}", len(orphaned), orphaned)

    async def run_alembic_upgrade(self, plugin_name: str) -> None:
        """Run plugin Alembic migration (public interface, called by version_manager etc.).
        / 执行插件 Alembic 迁移（公共接口，供 version_manager 等调用）

        Uses Alembic Python API (not CLI) to dynamically inject version_locations.
        Alembic CLI reads version_locations from alembic.ini at ScriptDirectory.from_config(),
        before env.py runs, so dynamic paths won't take effect.
        Using Python API to set Config then call command.upgrade() solves this.
        / 使用 Alembic Python API（而非 CLI）来动态注入 version_locations。

        Important: must add ALL installed plugins' migration paths to version_locations,
        otherwise other plugins' revision stamps in alembic_version can't be resolved,
        causing "Can't locate revision identified by 'xxx'" errors.
        / 重要：必须把所有已安装插件的迁移路径都加入 version_locations。
        """
        import os

        # Purge orphaned version stamps before upgrade (prevent uninstalled plugins' stamps from blocking upgrade)
        # / 升级前清除孤立版本戳（防止已卸载插件的 stamp 阻断升级）
        await self._purge_orphaned_alembic_stamps()

        branch_label = f"plugin_{plugin_name.replace('-', '_')}"

        version_locations = build_migration_version_locations(
            backend_dir=PLUGINS_DIR.parent,
            include_plugin_names=[plugin_name],
        )

        # Run via sys.executable -c to use Alembic Python API in a subprocess,
        # keeping sync Alembic isolated from the async event loop.
        # alembic.ini only has 'migrations/versions' (main app); plugin paths are injected here.
        #
        # Compat scenario: plugin tables exist but version stamp is missing (common in historical data/manual fixes);
        # upgrade may fail with DuplicateTable. In that case stamp the plugin branch to head
        # to clear duplicate warnings and restore migration state consistency.
        # / 兼容场景：插件表已存在但版本戳缺失时，
        # upgrade 可能因 DuplicateTable 失败。此时对插件分支执行 stamp 到 head。
        script = f"""
from alembic.config import Config
from alembic import command
import os

cfg = Config('alembic.ini')
version_locations = {version_locations!r}
target = {f"{branch_label}@head"!r}

cfg.set_main_option('version_locations', '\\n'.join(version_locations))

try:
    command.upgrade(cfg, target)
except Exception as exc:
    err = str(exc)
    if 'already exists' in err or 'DuplicateTable' in type(exc).__name__:
        command.stamp(cfg, target)
    else:
        raise
"""
        result = await _run_subprocess_async(
            sys.executable, "-c", script,
            timeout=120,
            cwd=str(PLUGINS_DIR.parent),
            shell=False,
        )
        if result.returncode != 0:
            err_output = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise PluginInstallError(
                message=resolve_public_error_message(
                    err_output,
                    fallback_message=f"Alembic upgrade failed for '{plugin_name}'",
                ),
            )

    def _plugin_has_migrations(self, plugin_name: str) -> bool:
        """Check if plugin has Alembic migration files / 检查插件是否有 Alembic 迁移文件"""
        migrations_dir = PLUGINS_DIR / plugin_name / "backend" / "migrations" / "versions"
        if not migrations_dir.is_dir():
            return False
        return any(f.suffix == ".py" and f.name != "__init__.py" for f in migrations_dir.iterdir())

    async def run_alembic_downgrade(self, plugin_name: str) -> None:
        """Downgrade plugin Alembic migration (public interface, called by version_manager etc.).
        / 回退插件 Alembic 迁移（公共接口，供 version_manager 等调用）

        Safety checks:
        - Plugin must have migration files, otherwise skip (prevent accidentally downgrading main project migrations)
        - Uses plugin's revision ID prefix matching, not branch_label (plugin migrations may not declare branch_labels)
        / 安全检查：
        - 插件必须有迁移文件，否则跳过（防止误回退主项目迁移）
        - 使用插件的 revision ID 前缀匹配，而非 branch_label
        """
        if not self._plugin_has_migrations(plugin_name):
            logger.info("Plugin {} has no migration files, skipping alembic downgrade", plugin_name)
            return

        import re as _re

        from sqlalchemy import text as _text

        branch_label = f"plugin_{plugin_name.replace('-', '_')}"
        version_locations = build_migration_version_locations(
            backend_dir=PLUGINS_DIR.parent,
            include_plugin_names=[plugin_name],
        )

        # Scan migration files to get actual revision IDs, then query DB directly.
        # More reliable than alembic command.current(): the latter depends on version_locations containing plugin paths,
        # and assumes revision ID contains plugin name prefix (e.g. ncc_001 doesn't contain novus_crud_code prefix).
        # / 扫描迁移文件获取实际 revision ID，然后直接查询 DB。
        migrations_dir = PLUGINS_DIR / plugin_name / "backend" / "migrations" / "versions"
        plugin_revision_ids: list[str] = []
        for _f in migrations_dir.iterdir():
            if _f.suffix == ".py" and _f.name != "__init__.py":
                try:
                    _src = _f.read_text(encoding="utf-8")
                    _m = _re.search(
                        r'^revision\s*(?::[^=]*)?=\s*["\']([^"\']+)["\']',
                        _src,
                        _re.MULTILINE,
                    )
                    if _m:
                        plugin_revision_ids.append(_m.group(1))
                except Exception:
                    pass

        if not plugin_revision_ids:
            logger.info("Plugin {}: no revision IDs found in migration files, skipping downgrade", plugin_name)
            return

        # Directly query alembic_version table, no alembic subprocess needed
        # / 直接查询 alembic_version 表，无需 alembic subprocess
        has_stamp = False
        for _rev_id in plugin_revision_ids:
            _row = await self._db.execute(
                _text("SELECT 1 FROM alembic_version WHERE version_num = :vid"),
                {"vid": _rev_id},
            )
            if _row.scalar():
                has_stamp = True
                break

        if not has_stamp:
            logger.info("Plugin {} has no alembic version stamp, skipping downgrade", plugin_name)
            return

        downgrade_script = f"""
from alembic.config import Config
from alembic import command
import os

cfg = Config('alembic.ini')
version_locations = {version_locations!r}
cfg.set_main_option('version_locations', '\\n'.join(version_locations))
command.downgrade(cfg, {f"{branch_label}@base"!r})
"""
        result = await _run_subprocess_async(
            sys.executable, "-c", downgrade_script,
            timeout=120,
            cwd=str(PLUGINS_DIR.parent),
            shell=False,
        )
        if result.returncode != 0:
            logger.warning(
                "Alembic downgrade for {}: {}", plugin_name, result.stderr.strip()
            )

    async def _cleanup_plugin_database(self, plugin_name: str) -> None:
        """Clean up plugin database resources: DROP plugin tables + clean alembic version stamps.
        / 清理插件数据库资源：DROP 插件表 + 清理 alembic 版本戳

        Strategy:
        1. Try alembic downgrade (graceful rollback, preserves data integrity)
        2. If alembic fails, directly DROP all plugin-prefixed tables (fallback)
        3. Always clean alembic_version plugin version stamps
        / 策略：
        1. 尝试 alembic downgrade（优雅回退）
        2. 若 alembic 失败，直接 DROP 所有插件前缀表（兜底）
        3. 无论如何，清理 alembic_version 中的插件版本戳
        """
        from sqlalchemy import text

        table_prefixes = self._resolve_plugin_table_prefixes(plugin_name)
        escaped_table_prefixes = [_escape_like_pattern(prefix) for prefix in table_prefixes]

        # Step 1: Try alembic downgrade (only when plugin has migration files)
        # / Step 1: 尝试 alembic downgrade（仅当插件有迁移文件时）
        alembic_ok = False
        if self._plugin_has_migrations(plugin_name):
            try:
                await self.run_alembic_downgrade(plugin_name)
                alembic_ok = True
            except Exception as exc:
                logger.warning("Plugin {} alembic downgrade failed: {}", plugin_name, exc)
        else:
            logger.info("Plugin {} has no migrations, skipping alembic downgrade", plugin_name)

        # Step 2: Check for remaining tables, DROP directly if found
        # / Step 2: 检查是否还有残留表，若有则直接 DROP
        try:
            # Critical cleanup SQL uses savepoint to prevent local exceptions from polluting outer transaction
            # / 关键清理 SQL 使用 savepoint，避免局部异常污染外层事务
            async with self._db.begin_nested():
                remaining_tables: set[str] = set()
                for escaped_prefix in escaped_table_prefixes:
                    result = await self._db.execute(
                        text(
                            "SELECT tablename FROM pg_tables "
                            "WHERE schemaname = 'public' AND tablename LIKE :prefix ESCAPE '\\'"
                        ),
                        {"prefix": f"{escaped_prefix}%"},
                    )
                    remaining_tables.update(row[0] for row in result.fetchall())

                if remaining_tables:
                    if alembic_ok:
                        logger.warning(
                            "Plugin {}: alembic downgrade succeeded but {} tables remain, dropping directly",
                            plugin_name, len(remaining_tables),
                        )
                    for tbl in sorted(remaining_tables):
                        if not _is_safe_plugin_table_name(tbl, table_prefixes):
                            logger.warning(
                                "Plugin {}: skip dropping unsafe table name '{}'",
                                plugin_name, tbl,
                            )
                            continue
                        try:
                            await self._db.execute(text(f'DROP TABLE IF EXISTS "{tbl}" CASCADE'))
                            logger.info("Plugin {}: dropped table {}", plugin_name, tbl)
                        except Exception as exc:
                            logger.error("Plugin {}: failed to drop table {}: {}", plugin_name, tbl, exc)
                    await self._db.flush()
        except Exception as exc:
            logger.error("Plugin {}: failed to query/drop residual tables: {}", plugin_name, exc)

        # Step 3: Clean alembic_version plugin version stamps
        # Prefer scanning migration files for actual revision IDs (avoid short prefix like ncc_ not matching plugin name)
        # / Step 3: 清理 alembic_version 中的插件版本戳
        # 优先通过扫描迁移文件获取实际 revision ID
        import re as _re

        revision_ids_from_files: list[str] = []
        migrations_dir = PLUGINS_DIR / plugin_name / "backend" / "migrations" / "versions"
        if migrations_dir.is_dir():
            for f in migrations_dir.iterdir():
                if f.suffix == ".py" and f.name != "__init__.py":
                    try:
                        source = f.read_text(encoding="utf-8")
                        m = _re.search(
                            r'^revision\s*(?::[^=]*)?=\s*["\']([^"\']+)["\']',
                            source,
                            _re.MULTILINE,
                        )
                        if m:
                            revision_ids_from_files.append(m.group(1))
                    except Exception:
                        pass

        try:
            # Critical cleanup SQL uses savepoint to prevent local exceptions from polluting outer transaction
            # / 关键清理 SQL 使用 savepoint，避免局部异常污染外层事务
            async with self._db.begin_nested():
                if revision_ids_from_files:
                    # Exact match: delete by revision IDs read from files
                    # / 精确匹配：用文件中读到的 revision ID 删除
                    deleted_count = 0
                    for vid in revision_ids_from_files:
                        result = await self._db.execute(
                            text("DELETE FROM alembic_version WHERE version_num = :vid"),
                            {"vid": vid},
                        )
                        deleted_count += result.rowcount
                    if deleted_count:
                        logger.info(
                            "Plugin {}: cleaned {} alembic_version stamp(s) by revision ID",
                            plugin_name, deleted_count,
                        )
                else:
                    # Fallback: match by plugin name prefix, escaping LIKE wildcards
                    # / 兜底：按插件名前缀匹配，并转义 LIKE 通配符
                    version_prefix = plugin_name.replace("-", "_") + "_"
                    escaped_version_prefix = _escape_like_pattern(version_prefix)
                    result = await self._db.execute(
                        text("DELETE FROM alembic_version WHERE version_num LIKE :prefix ESCAPE '\\'"),
                        {"prefix": f"{escaped_version_prefix}%"},
                    )
                    if result.rowcount:
                        logger.info(
                            "Plugin {}: cleaned {} alembic_version stamp(s) by prefix fallback",
                            plugin_name, result.rowcount,
                        )
                await self._db.flush()
        except Exception as exc:
            logger.warning("Plugin {}: failed to clean alembic_version: {}", plugin_name, exc)

    async def _rollback_install(
        self, plugin_name: str, completed_steps: list[str]
    ) -> None:
        """Full rollback on install failure (zero residue).
        / 安装失败时的完整回滚（零残留）

        Rollback strategy:
        1. DB transaction rollback — undo all ORM writes (plugins/versions/agent_assignments etc.)
        2. Alembic + plugin tables — reuse _cleanup_plugin_database (downgrade → DROP → clean stamps)
        3. File cleanup — delete directory copied to plugins/
        (runtime dependencies are not installed during install phase, no rollback needed)
        / 回滚策略：
        1. DB 事务回滚
        2. Alembic + 插件表 — 复用 _cleanup_plugin_database
        3. 文件清理 — 删除复制到 plugins/ 的目录
        """
        logger.info(
            "Rolling back install for {} (steps: {})", plugin_name, completed_steps
        )

        # Step 1: Rollback DB transaction / 回滚 DB 事务
        try:
            await self._db.rollback()
            logger.info("Rollback: DB transaction rolled back for {}", plugin_name)
        except Exception as exc:
            logger.warning("Rollback: DB rollback failed for {}: {}", plugin_name, exc)

        # Step 2: Clean alembic migrations + plugin tables + version stamps
        # / Step 2: 清理 alembic 迁移 + 插件表 + 版本戳
        if "alembic" in completed_steps:
            try:
                await self._cleanup_plugin_database(plugin_name)
                logger.info("Rollback: cleaned plugin database for {}", plugin_name)
            except Exception as exc:
                logger.warning("Rollback: database cleanup failed for {}: {}", plugin_name, exc)

        # Step 3: Delete copied plugin directory / 删除复制的插件目录
        if "copy" in completed_steps:
            target_dir = PLUGINS_DIR / plugin_name
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
                logger.info("Rollback: removed plugin directory {}", target_dir)

    # ================================================================
    # Plugin skill record management (SkillPackage + Skill) / 插件技能记录管理（SkillPackage + Skill）
    # / 插件技能记录管理（SkillPackage + Skill）
    # ================================================================

    async def _ensure_plugin_skill_records(
        self,
        plugin_name: str,
        manifest,
        skill_extensions: list,
        active: bool = True,
    ) -> None:
        """
        确保插件的 SkillPackage 和 Skill 记录存在于 DB 中 / Ensure plugin's SkillPackage and Skill records exist in DB.

        - If SkillPackage with source_plugin=plugin_name already exists, reuse and update status
        - Otherwise create new platform-level SkillPackage (tenant_id=NULL, is_system=True)
        - Package visibility is determined by platform ownership + agent binding, not package audience
        - Create or update Skill records for each skill extension

        如果已有 source_plugin=plugin_name 的 SkillPackage，则复用并更新状态；
        否则创建新的平台级 SkillPackage（tenant_id=NULL, is_system=True）。
        技能包可见性由平台归属 + 智能体绑定决定，不再依赖包级受众字段。
        对每个 skill extension 创建或更新 Skill 记录。
        """
        from sqlalchemy import select

        from app.models.ai.skill import Skill
        from app.models.ai.skill_package import SkillPackage
        from app.plugins.preview import resolve_i18n

        # Find or create SkillPackage / 查找或创建 SkillPackage
        result = await self._db.execute(
            select(SkillPackage).where(
                SkillPackage.source_plugin == plugin_name,
                SkillPackage.is_deleted.is_(False),
            )
        )
        package = result.scalar_one_or_none()

        display_name = resolve_i18n(manifest.display_name)

        if not package:
            # 创建平台级技能包：tenant_id=NULL，实际使用范围由 Agent 绑定决定
            # Create platform-level package: tenant_id=NULL; effective usage is determined by agent binding
            package = SkillPackage(
                name=display_name,
                description=resolve_i18n(manifest.description) if manifest.description else None,
                source_plugin=plugin_name,
                is_system=True,
                is_active=active,
                tenant_id=None,
            )
            self._db.add(package)
            await self._db.flush()
            logger.info(
                "Created SkillPackage '{}' (id={}) for plugin {}",
                package.name, package.id, plugin_name,
            )
        else:
            # Update existing package status / 更新已有包的状态
            package.is_active = active
            package.name = display_name
            await self._db.flush()

        # Preload all existing system skills in the package (for match-update)
        # / 预加载包内所有已有的系统技能（用于匹配更新）
        existing_skills_result = await self._db.execute(
            select(Skill).where(
                Skill.package_id == package.id,
                Skill.is_system.is_(True),
                Skill.is_deleted.is_(False),
            )
        )
        existing_skills = list(existing_skills_result.scalars().all())

        # Create or update Skill record for each skill extension
        # / 对每个 skill extension 创建或更新 Skill 记录
        for skill_ext in skill_extensions:
            # Match by name first, then by type, then take the first one
            # / 先按 name 匹配，再按 type 匹配，最后取第一个
            existing_skill = next(
                (s for s in existing_skills if s.name == (resolve_i18n(skill_ext.display_name) if skill_ext.display_name else skill_ext.name)),
                next((s for s in existing_skills if s.type == skill_ext.type), None),
            )
            if existing_skill is None and len(existing_skills) == 1 and len(skill_extensions) == 1:
                existing_skill = existing_skills[0]

            skill_display = resolve_i18n(skill_ext.display_name) if skill_ext.display_name else skill_ext.name
            skill_desc = resolve_i18n(skill_ext.description) if skill_ext.description else None

            if not existing_skill:
                skill = Skill(
                    package_id=package.id,
                    name=skill_display,
                    description=skill_desc,
                    type=skill_ext.type,
                    config=skill_ext.config_schema or {},
                    is_system=True,
                    is_active=active,
                    tenant_id=None,
                )
                self._db.add(skill)
                logger.info(
                    "Created Skill '{}' (type={}) for plugin {}",
                    skill_display, skill_ext.type, plugin_name,
                )
            else:
                existing_skill.is_active = active
                existing_skill.name = skill_display
                existing_skill.description = skill_desc
                existing_skill.type = skill_ext.type

        await self._db.flush()

    async def _deactivate_plugin_skill_records(self, plugin_name: str) -> None:
        """On disable: mark plugin's SkillPackage and Skill records as inactive / 禁用时：将插件的 SkillPackage 和 Skill 标记为不活跃"""
        from sqlalchemy import select, update

        from app.models.ai.skill import Skill
        from app.models.ai.skill_package import SkillPackage

        result = await self._db.execute(
            select(SkillPackage.id).where(
                SkillPackage.source_plugin == plugin_name,
                SkillPackage.is_deleted.is_(False),
            )
        )
        package_id = result.scalar_one_or_none()
        if not package_id:
            return

        # Deactivate SkillPackage / 停用 SkillPackage
        await self._db.execute(
            update(SkillPackage).where(
                SkillPackage.id == package_id,
            ).values(is_active=False)
        )

        # Deactivate all Skills under the package / 停用包下所有 Skill
        await self._db.execute(
            update(Skill).where(
                Skill.package_id == package_id,
                Skill.is_deleted.is_(False),
            ).values(is_active=False)
        )

        await self._db.flush()
        logger.info("Deactivated skill records for plugin {}", plugin_name)

    async def _delete_plugin_skill_records(self, plugin_name: str) -> None:
        """On uninstall: delete plugin-created SkillPackage (cascade delete Skill) / 卸载时：删除插件创建的 SkillPackage（级联删除 Skill）"""
        from sqlalchemy import delete, select

        from app.models.ai.skill import Skill
        from app.models.ai.skill_package import SkillPackage

        result = await self._db.execute(
            select(SkillPackage.id).where(
                SkillPackage.source_plugin == plugin_name,
                SkillPackage.is_deleted.is_(False),
            )
        )
        package_id = result.scalar_one_or_none()
        if not package_id:
            return

        # Delete child Skill table first, then SkillPackage / 先删子表 Skill，再删 SkillPackage
        await self._db.execute(
            delete(Skill).where(Skill.package_id == package_id)
        )
        await self._db.execute(
            delete(SkillPackage).where(SkillPackage.id == package_id)
        )
        await self._db.flush()
        logger.info("Deleted skill records for plugin {}", plugin_name)

    # ================================================================
    # Module loading / 模块加载
    # ================================================================

    # ================================================================
    # Permission DB record cleanup (M50-T14) / 权限 DB 记录清理
    # ================================================================

    async def _delete_plugin_permissions_from_db(self, plugin_name: str) -> None:
        """
        Hard-delete plugin permission records from permissions table on uninstall.
        / 卸载时从 permissions 表硬删除插件权限记录。

        _set_plugin_permissions_enabled only sets is_enabled=False;
        after uninstall, residual records show as ghost menus in admin pages, need full deletion.
        / _set_plugin_permissions_enabled 只做 is_enabled=False，
        uninstall 后残留记录需彻底删除。

        Covered code prefixes:
          menu:admin.plugin_{safe_name}_{menu_name}
          menu:tenant.plugin_{safe_name}_{menu_name}
          plugin.{plugin_name}.*
        """
        from sqlalchemy import delete, or_

        from app.models.auth.permission import Permission

        safe_name = plugin_name.replace("-", "_")
        admin_prefix = f"menu:admin.plugin_{safe_name}_"
        tenant_prefix = f"menu:tenant.plugin_{safe_name}_"
        plugin_prefix = f"plugin.{plugin_name}."

        result = await self._db.execute(
            delete(Permission).where(
                or_(
                    Permission.code.startswith(admin_prefix, autoescape=True),
                    Permission.code.startswith(tenant_prefix, autoescape=True),
                    Permission.code.startswith(plugin_prefix, autoescape=True),
                )
            )
        )
        if result.rowcount:
            await self._db.flush()
            logger.info(
                "Plugin {}: deleted {} permission record(s) from DB",
                plugin_name, result.rowcount,
            )

    # ================================================================
    # AI Features ensure (M50-T12) / AI 功能确保
    # ================================================================

    async def _ensure_plugin_ai_features(
        self,
        plugin_name: str,
        features: list,
    ) -> None:
        """
        Ensure plugin AI feature's SystemAgentAssignment global default records exist.
        / 确保插件 AI 功能对应的 SystemAgentAssignment 全局默认记录存在。

        Only created once during install phase; after DB reset, restore_enabled_plugins / enable
        won't recreate this record, causing ctx.call_ai_feature() to throw "not bound" error.
        Uses the same upsert logic as install.
        / install 阶段只创建一次，DB 重置后调用 restore_enabled_plugins / enable
        不会重建该记录。使用与 install 完全相同的 upsert 逻辑。
        """
        from sqlalchemy import select

        from app.models.system.agent_assignment import SystemAgentAssignment

        created = 0
        for feature in features:
            feature_code = f"plugin.{plugin_name}.{feature.feature_code}"
            feature_name = feature.display_name.get(
                "zh-CN", feature.display_name.get("en", feature.feature_code)
            )
            feature_desc = feature.description.get(
                "zh-CN", feature.description.get("en", "")
            )
            existing = await self._db.execute(
                select(SystemAgentAssignment.id).where(
                    SystemAgentAssignment.feature_code == feature_code,
                    SystemAgentAssignment.tenant_id.is_(None),
                    SystemAgentAssignment.is_deleted.is_(False),
                )
            )
            if not existing.scalar_one_or_none():
                self._db.add(SystemAgentAssignment(
                    feature_code=feature_code,
                    feature_name=feature_name,
                    description=feature_desc,
                    agent_id=None,
                    tenant_id=None,
                    is_active=True,
                ))
                created += 1

        if created:
            await self._db.flush()
            logger.info(
                "Plugin {}: ensured {} AI feature assignment(s) in DB",
                plugin_name, created,
            )

    # ================================================================
    # Notification template DB sync (M50-T1) / 通知模板 DB 同步
    # ================================================================

    async def _sync_plugin_notification_templates(
        self,
        plugin_name: str,
        notifications: list,
    ) -> None:
        """
        Upsert notification templates to notification_templates table on plugin enable.
        / 插件启用时将通知模板 upsert 到 notification_templates 表。

        NotificationService.send() queries DB for templates; if no record exists, degrades to
        no notification (silent failure). Idempotent: update if exists, create if not.
        / NotificationService.send() 查询 DB 获取模板，若无记录则静默失败。
        幂等：已存在则更新，不存在则创建。
        """
        from sqlalchemy import select

        from app.core.base_model import utc_now
        from app.models.common.notification_template import NotificationTemplate
        from app.plugins.preview import resolve_i18n

        synced = 0
        for notif in notifications:
            full_code = (
                f"plugin.{plugin_name}.{notif.code}"
                if not notif.code.startswith("plugin.")
                else notif.code
            )
            title = resolve_i18n(notif.title) if notif.title else full_code
            channels = notif.channels or ["ws", "inbox"]
            category = notif.category or "biz"

            # Include soft-deleted records too, to avoid UNIQUE conflict when inserting new records
            # / 包含软删除的记录也查出，避免加入新记录时触发 UNIQUE 冲突
            result = await self._db.execute(
                select(NotificationTemplate).where(
                    NotificationTemplate.code == full_code,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Already exists (including soft-deleted) → restore + update
                # / 已存在（含软删除）→ 恢复 + 更新
                existing.is_deleted = False
                existing.deleted_at = None
                existing.channels = channels
                existing.category = category
                existing.title_template = title
                existing.updated_at = utc_now()
            else:
                self._db.add(NotificationTemplate(
                    code=full_code,
                    category=category,
                    title_template=title,
                    channels=channels,
                    priority="normal",
                    is_system=True,
                ))
            synced += 1

        if synced:
            await self._db.flush()
            logger.info(
                "Plugin {}: synced {} notification template(s) to DB",
                plugin_name, synced,
            )

    async def _delete_plugin_notification_templates(self, plugin_name: str) -> None:
        """Delete plugin notification templates on uninstall (hard delete) / 卸载时删除插件通知模板（硬删除）"""
        from sqlalchemy import delete

        from app.models.common.notification_template import NotificationTemplate

        _escaped_name = plugin_name.replace("_", "\\_").replace("%", "\\%")
        result = await self._db.execute(
            delete(NotificationTemplate).where(
                NotificationTemplate.code.like(f"plugin.{_escaped_name}.%", escape="\\"),
            )
        )
        if result.rowcount:
            await self._db.flush()
            logger.info(
                "Plugin {}: deleted {} notification template(s) from DB",
                plugin_name, result.rowcount,
            )

    # ================================================================
    # Task definition DB sync (M50-T2) / 任务定义 DB 同步
    # ================================================================

    async def _sync_plugin_task_definitions(
        self,
        plugin_name: str,
        tasks: list,
    ) -> None:
        """
        Upsert plugin schedules to task_definitions on plugin enable.
        / 插件启用时将插件定时任务 upsert 到 task_definitions 表。

        Celery Beat reads schedules from task_definitions;
        plugin-managed tasks are represented as non-editable plugin definitions.
        / Celery Beat 通过 task_definitions 读取调度；
        插件管理任务以不可编辑的插件任务定义方式表达。
        """
        from sqlalchemy import select

        from app.enums.common import ResourceScopeEnum
        from app.enums.task import ScheduleTypeEnum
        from app.models.system.task_definition import TaskDefinition

        synced = 0
        for task_ext in tasks:
            task_code = f"plugin.{plugin_name}.{task_ext.name}"
            handler_path = task_code
            result = await self._db.execute(
                select(TaskDefinition).where(
                    TaskDefinition.code == task_code,
                )
            )
            existing = result.scalar_one_or_none()

            schedule_type = task_ext.schedule_type or ScheduleTypeEnum.INTERVAL.value

            if existing:
                existing.is_deleted = False
                existing.deleted_at = None
                existing.is_enabled = True
                existing.name = task_code
                existing.handler_path = handler_path
                existing.definition_type = "plugin"
                existing.category = "plugin"
                existing.scope = ResourceScopeEnum.ADMIN_ONLY.value
                existing.default_schedule_type = schedule_type
                existing.default_cron_expression = task_ext.cron_expression
                existing.default_interval_seconds = task_ext.interval_seconds
                existing.default_queue = "scheduled"
                existing.is_system_builtin = True
                existing.is_editable = False
                existing.is_deletable = False
                if task_ext.description:
                    existing.description = task_ext.description
            else:
                self._db.add(TaskDefinition(
                    code=task_code,
                    name=task_code,
                    definition_type="plugin",
                    handler_path=handler_path,
                    category="plugin",
                    default_schedule_type=schedule_type,
                    default_cron_expression=task_ext.cron_expression,
                    default_interval_seconds=task_ext.interval_seconds,
                    default_queue="scheduled",
                    is_enabled=True,
                    scope=ResourceScopeEnum.ADMIN_ONLY.value,
                    is_system_builtin=True,
                    is_editable=False,
                    is_deletable=False,
                    description=task_ext.description or "",
                ))
            synced += 1

        if synced:
            await self._db.flush()
            # Refresh Celery Beat schedule (take effect immediately in current process's Beat)
            # / 刷新 Celery Beat 调度（让当前进程的 Beat 立即生效）
            try:
                from app.tasks.scheduler import refresh_schedule
                refresh_schedule()
            except Exception as exc:
                logger.warning(
                    "Plugin {}: failed to refresh Celery schedule after enable: {}",
                    plugin_name, exc,
                )
            logger.info(
                "Plugin {}: synced {} task definition(s) to DB",
                plugin_name, synced,
            )

    async def _deactivate_plugin_task_definitions(self, plugin_name: str) -> None:
        """On disable: mark plugin task definitions inactive. / 禁用时将插件任务定义标记为非活跃。"""
        from sqlalchemy import update

        from app.models.system.task_definition import TaskDefinition

        _escaped_name = plugin_name.replace("_", "\\_").replace("%", "\\%")
        result = await self._db.execute(
            update(TaskDefinition).where(
                TaskDefinition.code.like(f"plugin.{_escaped_name}.%", escape="\\"),
                TaskDefinition.is_deleted.is_(False),
            ).values(is_enabled=False)
        )
        if result.rowcount:
            await self._db.flush()
            try:
                from app.tasks.scheduler import refresh_schedule
                refresh_schedule()
            except Exception as exc:
                logger.warning(
                    "Plugin {}: failed to refresh Celery schedule after disable: {}",
                    plugin_name, exc,
                )
            logger.info(
                "Plugin {}: deactivated {} task definition(s)",
                plugin_name, result.rowcount,
            )

    async def _delete_plugin_task_definitions(self, plugin_name: str) -> None:
        """Hard-delete plugin task definitions on uninstall / 卸载时硬删除插件任务定义 DB 记录"""
        from sqlalchemy import delete

        from app.models.system.task_definition import TaskDefinition

        _escaped_name = plugin_name.replace("_", "\\_").replace("%", "\\%")
        result = await self._db.execute(
            delete(TaskDefinition).where(
                TaskDefinition.code.like(f"plugin.{_escaped_name}.%", escape="\\"),
            )
        )
        if result.rowcount:
            await self._db.flush()
            try:
                from app.tasks.scheduler import refresh_schedule
                refresh_schedule()
            except Exception as exc:
                logger.warning(
                    "Plugin {}: failed to refresh Celery schedule after uninstall: {}",
                    plugin_name, exc,
                )
            logger.info(
                "Plugin {}: deleted {} task definition(s) from DB",
                plugin_name, result.rowcount,
            )

    def _load_handler(self, plugin_name: str, handler_path: str):
        """Load plugin handler function — delegate to unified loader / 加载插件处理函数 — 委托给统一加载器"""
        from app.plugins.module_loader import load_plugin_handler
        return load_plugin_handler(plugin_name, handler_path)

    def _load_plugin_executor(self, plugin_name: str, skill_type: str):
        """Load plugin executor class — delegate to unified loader / 加载插件 executor 类 — 委托给统一加载器"""
        from app.plugins.module_loader import load_plugin_executor
        return load_plugin_executor(plugin_name, skill_type)
