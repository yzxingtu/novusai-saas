"""Install/rollback helpers extracted from PluginLifecycle."""

from __future__ import annotations

import shutil
import uuid
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.base_model import utc_now
from app.core.i18n import _
from app.core.logging import get_logger
from app.core.response import build_public_error_text, resolve_public_error_message
from app.enums.plugin import (
    PluginInstallSourceEnum,
    PluginTierEnum,
    PluginVersionStatusEnum,
)
from app.plugins.exceptions import (
    PluginDependencyError,
    PluginError,
    PluginInstallError,
)
from app.plugins.lifecycle_support import _UNLOCK_IF_OWNER_LUA
from app.plugins.loader import PLUGINS_DIR
from app.plugins.preview import resolve_i18n

if TYPE_CHECKING:
    from app.models.system.plugin import Plugin


logger = get_logger(__name__)


class LifecycleInstallationMixin:
    """Install/rollback orchestration extracted from PluginLifecycle."""

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
            _install_lock_key,
            _install_owner,
            nx=True,
            ex=300,
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
            await emitter.emit_step(
                "copy", "success", f"Plugin files copied to {target_dir}"
            )
            # 2. Parse manifest (already done above) / 解析 manifest（已在上面完成）
            # 3. Validate compatibility + plugin dependency check / 校验兼容性 + 插件依赖检查
            from app.enums.plugin import PluginStatusEnum

            # 3a. Platform version compatibility check / 平台版本兼容性检查
            if (
                manifest.compatibility
                and manifest.compatibility.platform_version != "*"
            ):
                try:
                    from packaging.specifiers import SpecifierSet
                    from packaging.version import Version

                    from app.core.config import settings

                    platform_spec = SpecifierSet(
                        manifest.compatibility.platform_version
                    )
                    if Version(settings.APP_VERSION) not in platform_spec:
                        raise PluginInstallError(
                            message=f"Plugin '{plugin_name}' requires platform version "
                            f"{manifest.compatibility.platform_version}, "
                            f"but current is {settings.APP_VERSION}",
                        )
                except ImportError:
                    logger.warning(
                        "packaging library not available, skipping version check"
                    )

            # 3b. Unified plugin dependency check / 统一插件依赖检查
            await self.dependencies.assert_plugin_dependencies_ready(
                manifest,
                plugin_name=plugin_name,
                require_enabled=False,
                error_cls=PluginInstallError,
                action="install",
            )

            # 3d. Security scan (high-risk fail-close) / 安全扫描（高风险 fail-close）
            from app.plugins.security_scan import assert_plugin_security_clean

            scan_target = target_dir if target_dir.is_dir() else source_path
            assert_plugin_security_clean(
                scan_target,
                plugin_name=plugin_name,
                action="install",
            )

            # 4. Record declared deps (runtime environment changes deferred to explicit dependency handling) / 记录声明的依赖（运行时环境变更延迟到显式依赖处理）
            installed_packages = manifest.dependencies.python or []

            # 5. Run Alembic migrations / 执行 Alembic 迁移
            migrations_dir = target_dir / "backend" / "migrations" / "versions"
            if migrations_dir.is_dir():
                await emitter.emit_step(
                    "alembic", "running", "Running database migrations..."
                )
                await self.run_alembic_upgrade(plugin_name)
                await emitter.emit_step(
                    "alembic", "success", "Database migrations complete"
                )
                completed_steps.append("alembic")

            # 6. Register AI features → SystemAgentAssignment / 注册 AI features → SystemAgentAssignment
            if manifest.ai_requirements and manifest.ai_requirements.features:
                await emitter.emit_step(
                    "ai_features", "running", "Registering AI features..."
                )
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
                        self._db.add(
                            SystemAgentAssignment(
                                feature_code=feature_code,
                                feature_name=feature_name,
                                description=feature_desc,
                                agent_id=None,
                                tenant_id=None,
                                is_active=True,
                            )
                        )
                await self._db.flush()
                completed_steps.append("ai_features")
                await emitter.emit_step(
                    "ai_features",
                    "success",
                    f"Registered {len(manifest.ai_requirements.features)} AI features",
                )
                logger.info(
                    "Registered {} AI features for plugin {}",
                    len(manifest.ai_requirements.features),
                    plugin_name,
                )

            # 7. Merge i18n translations (reserved, currently only logged) / 合并 i18n 翻译（预留，当前仅记录）
            locales = self._loader.load_locales(plugin_name)
            if locales:
                logger.info(
                    "Plugin {} has {} locale(s): {}",
                    plugin_name,
                    len(locales),
                    list(locales.keys()),
                )
                completed_steps.append("i18n")

            # 8. Instantiate plugin class and call on_install / 实例化插件类并调用 on_install
            await emitter.emit_step(
                "on_install", "running", "Running plugin install hook..."
            )
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
                await emitter.emit_step(
                    "on_install", "success", "Install hook completed"
                )
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
                    plugin_name,
                    exc,
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
                description=resolve_i18n(manifest.description)
                if manifest.description
                else None,
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
                ai_requirements=manifest.ai_requirements.model_dump()
                if manifest.ai_requirements
                else None,
                pricing_type=manifest.pricing.type,
                pricing_info=manifest.pricing.model_dump()
                if manifest.pricing.type != "free"
                else None,
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
                plugin_name,
                manifest.version,
            )
            await emitter.emit_done(
                f"Plugin {plugin_name} v{manifest.version} installed successfully"
            )
            return plugin

        except Exception as exc:
            logger.error(
                "Plugin {} install failed at step {}: {}",
                plugin_name,
                completed_steps[-1] if completed_steps else "init",
                exc,
            )
            if emitter is not None:
                await emitter.emit_error(
                    build_public_error_text(
                        exc=exc,
                        message=_("plugin.error.install_failed"),
                    )
                )
            await self._rollback_install(plugin_name, completed_steps)
            if isinstance(
                exc, (PluginError, PluginInstallError, PluginDependencyError)
            ):
                raise
            raise PluginInstallError(
                message=resolve_public_error_message(
                    exc,
                    fallback_message=_("plugin.error.install_failed"),
                ),
            ) from exc
        finally:
            # Release install lock / 释放安装锁
            if _redis is not None and _install_owner is not None:
                with suppress(Exception):
                    await _redis.eval(
                        _UNLOCK_IF_OWNER_LUA, 1, _install_lock_key, _install_owner
                    )

    # ================================================================
    # enable / 启用
    # ================================================================

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
                logger.warning(
                    "Rollback: database cleanup failed for {}: {}", plugin_name, exc
                )

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
