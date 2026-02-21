"""
插件生命周期管理器（门面类）

单例模式，编排插件的安装、卸载、启用、禁用、升级和配置管理。
实际工作委托给：PluginLoader、ExtensionRegistry、PluginRouteManager、
PluginConfigManager、SkillPluginProvisioner。
"""

from __future__ import annotations

import asyncio
import functools
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI
    from app.models.system.plugin import Plugin
    from app.models.system.tenant_plugin import TenantPlugin

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.plugin import PluginStatusEnum
from app.exceptions import (
    BusinessException,
    ConflictException,
    NotFoundException,
)
from app.plugins.base import BasePlugin
from app.plugins.context import PluginContext
from app.plugins.extensions.skill_plugin import SkillPlugin
from app.plugins.config_manager import PluginConfigManager
from app.plugins.extension_registry import ExtensionRegistry
from app.plugins.loader import PluginLoader, resolve_plugin_type
from app.plugins.route_manager import PluginRouteManager
from app.plugins.skill_provisioner import SkillPluginProvisioner
from app.core.base_model import utc_now
from app.plugins.utils import (
    cleanup_plugin_directory,
    install_plugin_requirements as _install_plugin_requirements,
)

logger = LogManager.get_logger("app")


def _write_locked(func):  # type: ignore[type-arg]
    """异步写操作互斥锁装饰器

    确保 install/uninstall/enable/disable/upgrade 等写操作互斥执行，
    防止并发修改 _instances 等共享字典。
    """
    @functools.wraps(func)
    async def wrapper(self: PluginManager, *args: Any, **kwargs: Any) -> Any:
        async with self._write_lock:
            return await func(self, *args, **kwargs)
    return wrapper


class PluginManager:
    """
    插件生命周期管理器 — 门面类（单例）

    编排插件生命周期操作，委托子组件执行具体工作：
    - loader: 动态导入 + 实例缓存
    - extension_registry: 扩展点注册/注销
    - route_manager: ApiPlugin 路由挂载/卸载
    - config_manager: 配置合并/校验/上下文构建
    - SkillPluginProvisioner: Skill 自动装配/停用
    """

    _instance: PluginManager | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        # 插件加载器（动态导入 + 实例缓存）
        self.loader: PluginLoader = PluginLoader()
        # 路由管理器（ApiPlugin 路由挂载/卸载）
        self.route_manager: PluginRouteManager = PluginRouteManager()
        # 配置管理器（合并/校验/上下文构建）
        self.config_manager: PluginConfigManager = PluginConfigManager()
        # 扩展点注册表（Adapter/Hook/Tool/Skill/Api/Storage）
        self.extension_registry: ExtensionRegistry = ExtensionRegistry(self.route_manager)
        # 异步写操作互斥锁（install/uninstall/enable/disable/upgrade）
        self._write_lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> PluginManager:
        """获取单例实例（线程安全）"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """重置单例（仅用于测试）"""
        cls._instance = None

    def set_app(self, app: FastAPI) -> None:
        """
        设置 FastAPI 应用引用（用于 ApiPlugin 动态路由挂载）

        Args:
            app: FastAPI 应用实例
        """
        self.route_manager.set_app(app)

    # ========================================
    # 动态加载
    # ========================================

    def load_plugin_class(self, entry_point: str) -> type[BasePlugin]:
        """从 entry_point 路径动态加载插件类（委托 PluginLoader）"""
        return self.loader.load_plugin_class(entry_point)

    def get_or_load_instance(self, name: str, entry_point: str) -> BasePlugin:
        """获取已缓存的插件实例，或动态加载并缓存（委托 PluginLoader）"""
        return self.loader.get_or_load_instance(name, entry_point)

    def load_and_register(
        self,
        name: str,
        entry_point: str,
        db: AsyncSession | None = None,
    ) -> BasePlugin:
        """
        加载插件实例并注册其扩展点（公共方法）

        用于启动时从 DB 恢复已启用插件的扩展点注册，
        替代直接调用 config_manager.build_context / extension_registry.register。

        Args:
            name: 插件名称
            entry_point: 入口点路径
            db: 数据库会话（可选，传入后可用于 DB 操作的扩展点）

        Returns:
            已加载并注册的 BasePlugin 实例
        """
        instance = self.get_or_load_instance(name, entry_point)
        ctx = self.config_manager.build_context(instance, db=db)
        self.extension_registry.register(instance, ctx)
        return instance

    def get_plugin_tools(self) -> dict[str, str]:
        """获取所有已注册的工具插件映射（委托 ExtensionRegistry）"""
        return self.extension_registry.get_plugin_tools()

    def get_plugin_adapters(self) -> dict[str, str]:
        """获取所有已注册的适配器插件映射（委托 ExtensionRegistry）"""
        return self.extension_registry.get_plugin_adapters()

    def get_adapter_plugin_info(self, provider_type: str) -> dict[str, Any] | None:
        """获取适配器插件的 provider_info（委托 ExtensionRegistry）"""
        return self.extension_registry.get_adapter_plugin_info(provider_type)

    # ========================================
    # 安装
    # ========================================

    @_write_locked
    async def install(
        self,
        db: AsyncSession,
        entry_point: str,
        is_system: bool = False,
        admin_id: int | None = None,
    ) -> Plugin:
        """
        安装插件

        流程：动态导入 → 实例化 → 校验 → 写入 DB → 调用 on_install

        Args:
            db: 数据库会话
            entry_point: 插件入口点
            is_system: 是否标记为系统内置

        Returns:
            Plugin 模型实例
        """
        from app.repositories.system.plugin_repository import PluginRepository

        from app.plugins.security import validate_manifest_or_raise, encrypt_sensitive_config
        from app.plugins.dependencies import (
            check_dependencies_or_raise,
            check_conflicts_or_raise,
            check_platform_version_or_raise,
        )

        plugin_cls = self.load_plugin_class(entry_point)
        instance = plugin_cls()

        # 校验唯一性
        repo = PluginRepository(db)
        existing = await repo.get_by_name(instance.name)
        if existing:
            raise ConflictException(_("plugin.already_exists"))

        # 推断类型
        plugin_type = resolve_plugin_type(instance)

        # 校验 manifest 完整性
        manifest = instance.get_manifest()
        manifest["entry_point"] = entry_point
        validate_manifest_or_raise(manifest)

        # 校验平台版本要求
        check_platform_version_or_raise(instance.platform_version)

        # 校验依赖插件
        await check_dependencies_or_raise(db, instance.dependencies)

        # 校验冲突插件
        await check_conflicts_or_raise(db, instance.conflicts, instance.name)

        # 加密默认配置中的敏感字段
        default_config = instance.default_config
        if default_config and instance.config_schema:
            default_config = encrypt_sensitive_config(default_config, instance.config_schema)
        # scope 优先从 manifest 读取，其次从实例 property 读取
        plugin_scope = manifest.get("scope") or instance.scope
        from app.enums.plugin import PluginScopeEnum
        valid_scopes = {s.value for s in PluginScopeEnum}
        if plugin_scope not in valid_scopes:
            plugin_scope = PluginScopeEnum.ALL_TENANTS.value

        plugin = await repo.create({
            "name": instance.name,
            "display_name": instance.display_name,
            "version": instance.version,
            "description": instance.description,
            "author": instance.author,
            "plugin_type": plugin_type,
            "status": PluginStatusEnum.INSTALLED.value,
            "scope": plugin_scope,
            "entry_point": entry_point,
            "manifest": manifest,
            "is_system": is_system,
            "required_permissions": instance.required_permissions or None,
            "dependencies": instance.dependencies or None,
            "conflicts": instance.conflicts or None,
            "platform_version": instance.platform_version,
            "config_schema": instance.config_schema,
            "default_config": default_config or None,
            "icon": instance.icon or None,
            "homepage": instance.homepage or None,
        })
        await db.flush()

        # 缓存实例
        self.loader.set_instance(instance.name, instance)

        # 调用生命周期钩子
        ctx = self.config_manager.build_context(instance, db=db)
        try:
            await instance.on_install(ctx)
        except Exception as exc:
            logger.error(
                "Plugin on_install failed: %s — %s", instance.name, str(exc),
                exc_info=True,
            )
            # 回滚：删除刚插入的记录
            await repo.permanent_delete(plugin.id)
            self.loader.pop_instance(instance.name)
            raise BusinessException(
                _("plugin.install_hook_failed")
            ) from exc

        # 执行插件数据库迁移
        try:
            from app.plugins.migration_runner import run_migrations
            applied = await run_migrations(db, instance.name)
            if applied:
                logger.info(
                    "Plugin DB migrations applied during install: %s — %s",
                    instance.name, applied,
                )
        except Exception as exc:
            logger.error(
                "Plugin migration failed during install: %s — %s",
                instance.name, str(exc), exc_info=True,
            )
            await repo.permanent_delete(plugin.id)
            self.loader.pop_instance(instance.name)
            raise

        from app.plugins.security import log_plugin_action
        log_plugin_action(
            action="install",
            plugin_name=instance.name,
            admin_id=admin_id,
            details={"version": instance.version, "entry_point": entry_point, "is_system": is_system},
        )

        logger.info("Plugin installed: %s v%s", instance.name, instance.version)
        return plugin

    # ========================================
    # 卸载
    # ========================================

    @_write_locked
    async def uninstall(self, db: AsyncSession, plugin_id: int, admin_id: int | None = None) -> None:
        """
        卸载插件

        流程：校验 → 调用 on_uninstall → 清理 tenant_plugins → 删除 plugin

        Args:
            db: 数据库会话
            plugin_id: 插件 ID
        """
        from app.repositories.system.plugin_repository import PluginRepository
        from app.repositories.system.tenant_plugin_repository import (
            TenantPluginRepository,
        )

        repo = PluginRepository(db)
        plugin = await repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(_("plugin.not_found"))
        if plugin.is_system:
            raise BusinessException(_("plugin.cannot_uninstall_system"))

        # 检查反向依赖：是否有其他插件依赖当前插件
        from app.plugins.dependencies import check_reverse_dependencies_or_raise
        await check_reverse_dependencies_or_raise(db, plugin.name, action="uninstall")

        # 保存插件信息（后续 rollback 可能导致 plugin 对象失效）
        plugin_name = plugin.name
        plugin_version = plugin.version
        plugin_entry_point = plugin.entry_point

        # 加载实例并调用 on_uninstall
        try:
            instance = self.get_or_load_instance(plugin_name, plugin_entry_point)
            ctx = self.config_manager.build_context(instance, db=db)

            # 注销扩展点（防止已启用插件直接卸载时注册泄漏）
            self.extension_registry.unregister(instance, ctx)

            # SkillPlugin：检查技能是否被 Agent 引用，然后软删除技能包
            if isinstance(instance, SkillPlugin):
                affected_agents = await self._check_skill_references(db, instance)
                if affected_agents:
                    logger.warning(
                        "Uninstalling skill plugin %s: %d agents reference its skills: %s",
                        plugin_name, len(affected_agents), affected_agents,
                    )
                try:
                    await SkillPluginProvisioner.deprovision(
                        db, instance, soft_delete=True,
                    )
                except Exception as deprov_exc:
                    await db.rollback()
                    logger.error(
                        "Skill plugin soft-delete failed: %s — %s",
                        plugin_name, str(deprov_exc), exc_info=True,
                    )

            try:
                await instance.on_uninstall(ctx)
            except Exception as hook_exc:
                await db.rollback()
                logger.error(
                    "Plugin on_uninstall hook error (proceeding): %s — %s",
                    plugin_name, str(hook_exc), exc_info=True,
                )
        except Exception as exc:
            await db.rollback()
            logger.error(
                "Plugin uninstall prep error (proceeding): %s — %s",
                plugin_name, str(exc), exc_info=True,
            )

        # 回滚插件数据库迁移（失败不阻塞卸载）
        try:
            from app.plugins.migration_runner import rollback_migrations
            rollback_result = await rollback_migrations(db, plugin_name)
            if rollback_result.get("rolled_back") or rollback_result.get("skipped"):
                logger.info(
                    "Plugin DB migrations rolled back: %s — %s",
                    plugin_name, rollback_result,
                )
        except Exception as mig_exc:
            await db.rollback()
            logger.warning(
                "Plugin migration rollback error (proceeding): %s — %s",
                plugin_name, str(mig_exc), exc_info=True,
            )

        # 清理租户关联
        tp_repo = TenantPluginRepository(db)
        tenant_records = await tp_repo.get_list(limit=10000, plugin_id=plugin_id)
        for tp in tenant_records:
            await tp_repo.permanent_delete(tp.id)

        # 删除插件记录
        await repo.permanent_delete(plugin_id)
        self.loader.pop_instance(plugin_name)

        # 卸载前自动备份插件为 .nap（失败不阻塞）
        from app.plugins.utils import backup_plugin_directory
        backup_path = backup_plugin_directory(plugin_name, plugin_version, plugin_entry_point)

        # 清理插件文件目录（仅限 .nap 上传安装的插件）
        cleanup_plugin_directory(plugin_name, plugin_entry_point)

        from app.plugins.security import log_plugin_action
        log_plugin_action(
            action="uninstall",
            plugin_name=plugin_name,
            admin_id=admin_id,
            details={
                "version": plugin_version,
                "plugin_id": plugin_id,
                "backup_path": backup_path,
            },
        )

        logger.info("Plugin uninstalled: %s", plugin_name)

    # ========================================
    # 启用 / 禁用（平台级）
    # ========================================

    @_write_locked
    async def enable_platform(self, db: AsyncSession, plugin_id: int, admin_id: int | None = None) -> Plugin:
        """
        平台级启用插件

        Args:
            db: 数据库会话
            plugin_id: 插件 ID

        Returns:
            更新后的 Plugin 模型
        """
        from app.repositories.system.plugin_repository import PluginRepository

        repo = PluginRepository(db)
        plugin = await repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(_("plugin.not_found"))

        instance = self.get_or_load_instance(plugin.name, plugin.entry_point)
        ctx = self.config_manager.build_context(instance, db=db)

        # 创建 savepoint 以便在后续步骤失败时回滚 on_enable 的 DB 副作用
        savepoint = await db.begin_nested()

        try:
            await instance.on_enable(ctx)
        except Exception as exc:
            await savepoint.rollback()
            logger.error(
                "Plugin on_enable failed: %s — %s", plugin.name, str(exc),
                exc_info=True,
            )
            await repo.update(
                plugin_id, {"status": PluginStatusEnum.ERROR.value}
            )
            raise BusinessException(
                _("plugin.enable_hook_failed")
            ) from exc

        # 注册扩展点
        try:
            self.extension_registry.register(instance, ctx)
        except Exception as exc:
            await savepoint.rollback()
            logger.error(
                "Plugin extension registration failed: %s — %s",
                plugin.name, str(exc), exc_info=True,
            )
            try:
                await instance.on_disable(ctx)
            except Exception as rollback_exc:
                logger.warning(
                    "Failed to rollback on_enable for %s: %s",
                    plugin.name, str(rollback_exc),
                )
            await repo.update(
                plugin_id, {"status": PluginStatusEnum.ERROR.value}
            )
            raise BusinessException(
                _("plugin.enable_hook_failed")
            ) from exc

        # SkillPlugin 自动装配
        if isinstance(instance, SkillPlugin):
            try:
                await SkillPluginProvisioner.provision(db, instance)
            except Exception as exc:
                await savepoint.rollback()
                logger.error(
                    "Skill plugin provisioning failed: %s — %s",
                    plugin.name, str(exc), exc_info=True,
                )
                self.extension_registry.unregister(instance, ctx)
                try:
                    await instance.on_disable(ctx)
                except Exception:
                    pass
                await repo.update(
                    plugin_id, {"status": PluginStatusEnum.ERROR.value}
                )
                raise BusinessException(
                    _("plugin.enable_hook_failed")
                ) from exc

        # savepoint 成功，提交
        await savepoint.commit()

        updated = await repo.update(
            plugin_id, {"status": PluginStatusEnum.ENABLED.value}
        )

        # Eager Provisioning: scope=global/all_tenants 时自动为所有现存租户创建 tenant_plugins 记录
        from app.enums.plugin import PluginScopeEnum
        if plugin.scope in (PluginScopeEnum.GLOBAL.value, PluginScopeEnum.ALL_TENANTS.value):
            try:
                await self._provision_all_tenants(db, plugin)
            except Exception as prov_exc:
                logger.error(
                    "Tenant provisioning failed for plugin %s (scope=%s): %s",
                    plugin.name, plugin.scope, str(prov_exc), exc_info=True,
                )

        from app.plugins.security import log_plugin_action
        log_plugin_action(
            action="enable",
            plugin_name=plugin.name,
            admin_id=admin_id,
            details={"scope": "platform", "plugin_id": plugin_id, "plugin_scope": plugin.scope},
        )

        logger.info("Plugin enabled (platform): %s (scope=%s)", plugin.name, plugin.scope)
        return updated

    @_write_locked
    async def disable_platform(self, db: AsyncSession, plugin_id: int, admin_id: int | None = None) -> Plugin:
        """
        平台级禁用插件

        Args:
            db: 数据库会话
            plugin_id: 插件 ID

        Returns:
            更新后的 Plugin 模型
        """
        from app.repositories.system.plugin_repository import PluginRepository

        repo = PluginRepository(db)
        plugin = await repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(_("plugin.not_found"))
        if plugin.is_system:
            raise BusinessException(_("plugin.cannot_disable_system"))

        # 检查反向依赖：是否有其他已启用插件依赖当前插件
        from app.plugins.dependencies import check_reverse_dependencies_or_raise
        await check_reverse_dependencies_or_raise(db, plugin.name, action="disable")

        # 联动禁用所有租户的 tenant_plugins 记录
        from app.repositories.system.tenant_plugin_repository import (
            TenantPluginRepository as _TpRepo,
        )
        _tp_repo = _TpRepo(db)
        active_tenants = await _tp_repo.get_list(
            limit=10000, plugin_id=plugin_id, is_active=True
        )
        if active_tenants:
            disabled_count = 0
            for tp in active_tenants:
                await _tp_repo.update(tp.id, {"is_active": False})
                disabled_count += 1
            logger.info(
                "Cascade disabled %d tenant plugin records for plugin %s",
                disabled_count, plugin.name,
            )

        instance = self.get_or_load_instance(plugin.name, plugin.entry_point)
        ctx = self.config_manager.build_context(instance, db=db)

        try:
            await instance.on_disable(ctx)
        except Exception as exc:
            logger.error(
                "Plugin on_disable error (proceeding): %s — %s",
                plugin.name, str(exc), exc_info=True,
            )

        # 注销扩展点
        self.extension_registry.unregister(instance, ctx)

        # SkillPlugin 停用技能包
        if isinstance(instance, SkillPlugin):
            try:
                await SkillPluginProvisioner.deprovision(db, instance, soft_delete=False)
            except Exception as exc:
                logger.error(
                    "Skill plugin deprovisioning failed: %s — %s",
                    plugin.name, str(exc), exc_info=True,
                )

        updated = await repo.update(
            plugin_id, {"status": PluginStatusEnum.DISABLED.value}
        )
        from app.plugins.security import log_plugin_action
        log_plugin_action(
            action="disable",
            plugin_name=plugin.name,
            admin_id=admin_id,
            details={"scope": "platform", "plugin_id": plugin_id},
        )

        logger.info("Plugin disabled (platform): %s", plugin.name)
        return updated

    # ========================================
    # 内部辅助方法
    # ========================================

    @staticmethod
    async def _check_skill_references(
        db: AsyncSession, instance: SkillPlugin,
    ) -> list[str]:
        """
        检查是否有 Agent 引用了该 SkillPlugin 提供的技能

        Args:
            db: 数据库会话
            instance: SkillPlugin 实例

        Returns:
            引用该技能的 Agent 名称列表（空列表表示无引用）
        """
        try:
            from sqlalchemy import select
            from app.models.ai.skill import Skill
            from app.models.ai.agent_skill_binding import AgentSkillBinding
            from app.models.ai.agent import Agent

            skill_type = instance.get_skill_type()

            # 查找该插件创建的技能 ID
            stmt = select(Skill.id).where(
                Skill.type == skill_type,
                Skill.is_deleted.is_(False),
            )
            result = await db.execute(stmt)
            skill_ids = [row[0] for row in result.all()]

            if not skill_ids:
                return []

            # 查找绑定了这些技能的 Agent
            stmt = (
                select(Agent.name)
                .join(AgentSkillBinding, AgentSkillBinding.agent_id == Agent.id)
                .where(
                    AgentSkillBinding.skill_id.in_(skill_ids),
                    Agent.is_deleted.is_(False),
                )
                .distinct()
            )
            result = await db.execute(stmt)
            return [row[0] for row in result.all()]
        except Exception as exc:
            logger.warning(
                "Failed to check skill references for plugin %s: %s",
                instance.name, str(exc),
            )
            return []

    @staticmethod
    async def _check_config_schema_compat(
        db: AsyncSession,
        plugin_id: int,
        plugin_name: str,
        old_schema: dict[str, Any],
        new_schema: dict[str, Any],
    ) -> None:
        """
        检查新旧 config_schema 兼容性，记录破坏性变更

        检测项：
        - 新增了 required 字段（旧配置可能缺少）
        - 删除了字段（旧配置中的值会被忽略）
        - 字段类型变更
        """
        old_props = old_schema.get("properties", {})
        new_props = new_schema.get("properties", {})
        old_required = set(old_schema.get("required", []))
        new_required = set(new_schema.get("required", []))

        warnings: list[str] = []

        # 新增的 required 字段
        new_required_fields = new_required - old_required
        for field in new_required_fields:
            if field not in old_props:
                warnings.append(f"New required field: {field}")

        # 删除的字段
        removed_fields = set(old_props.keys()) - set(new_props.keys())
        for field in removed_fields:
            warnings.append(f"Removed field: {field}")

        # 类型变更
        for field in set(old_props.keys()) & set(new_props.keys()):
            old_type = old_props[field].get("type")
            new_type = new_props[field].get("type")
            if old_type and new_type and old_type != new_type:
                warnings.append(f"Type changed: {field} ({old_type} → {new_type})")

        if not warnings:
            return

        # 统计受影响的租户数量
        from app.repositories.system.tenant_plugin_repository import TenantPluginRepository
        tp_repo = TenantPluginRepository(db)
        active_tenants = await tp_repo.get_list(
            limit=10000, plugin_id=plugin_id, is_active=True,
        )
        tenant_with_config = [
            tp for tp in active_tenants if tp.config
        ]

        from app.plugins.security import log_plugin_action
        log_plugin_action(
            action="config_schema_compat_warning",
            plugin_name=plugin_name,
            details={
                "warnings": warnings,
                "affected_tenants": len(tenant_with_config),
                "total_active_tenants": len(active_tenants),
            },
        )
        logger.warning(
            "Plugin %s config_schema breaking changes detected: %s "
            "(affected tenants with custom config: %d/%d)",
            plugin_name, warnings, len(tenant_with_config), len(active_tenants),
        )

    # ========================================
    # 租户批量分配（内部方法）
    # ========================================

    async def _provision_all_tenants(
        self,
        db: AsyncSession,
        plugin: Plugin,
    ) -> int:
        """
        为所有现存租户创建 tenant_plugins 记录（Eager Provisioning）

        仅在 scope=global 或 scope=all_tenants 时调用。
        跳过已有记录的租户，不阻塞主流程（失败记录日志）。

        Args:
            db: 数据库会话
            plugin: 已启用的插件模型

        Returns:
            新创建的 tenant_plugins 记录数
        """
        from sqlalchemy import select
        from app.models.tenant.tenant import Tenant
        from app.repositories.system.tenant_plugin_repository import TenantPluginRepository

        # 获取所有活跃租户 ID
        stmt = select(Tenant.id).where(Tenant.is_deleted.is_(False))
        result = await db.execute(stmt)
        tenant_ids = [row[0] for row in result.all()]

        if not tenant_ids:
            return 0

        tp_repo = TenantPluginRepository(db)
        created_count = 0

        for tid in tenant_ids:
            existing = await tp_repo.get_by_tenant_and_plugin(tid, plugin.id)
            if existing:
                # 已有记录：如果是禁用状态则重新激活
                if not existing.is_active:
                    await tp_repo.update(existing.id, {"is_active": True})
                    created_count += 1
                continue
            await tp_repo.create({
                "tenant_id": tid,
                "plugin_id": plugin.id,
                "is_active": True,
                "config": None,
            })
            created_count += 1

        if created_count > 0:
            await db.flush()
            logger.info(
                "Provisioned plugin %s to %d tenants (scope=%s)",
                plugin.name, created_count, plugin.scope,
            )

        return created_count

    # ========================================
    # 启用 / 禁用（租户级）
    # ========================================

    @_write_locked
    async def enable_tenant(
        self,
        db: AsyncSession,
        tenant_id: int,
        plugin_id: int,
        config: dict[str, Any] | None = None,
    ) -> TenantPlugin:
        """
        租户级启用插件

        前提：平台已启用该插件。

        Args:
            db: 数据库会话
            tenant_id: 租户 ID
            plugin_id: 插件 ID
            config: 租户自定义配置

        Returns:
            TenantPlugin 模型实例
        """
        from app.repositories.system.plugin_repository import PluginRepository
        from app.repositories.system.tenant_plugin_repository import (
            TenantPluginRepository,
        )

        # 校验平台状态
        plugin_repo = PluginRepository(db)
        plugin = await plugin_repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(_("plugin.not_found"))
        if plugin.status != PluginStatusEnum.ENABLED.value:
            raise BusinessException(_("tenant_plugin.plugin_not_enabled"))

        # 校验并合并配置
        merged_config = self.config_manager.merge_config(plugin.default_config, config)
        if config and plugin.config_schema:
            self.config_manager.validate_config(plugin.config_schema, merged_config)

        # 加密敏感配置字段
        if plugin.config_schema:
            from app.plugins.security import encrypt_sensitive_config
            merged_config = encrypt_sensitive_config(merged_config, plugin.config_schema)

        tp_repo = TenantPluginRepository(db)
        existing = await tp_repo.get_by_tenant_and_plugin(tenant_id, plugin_id)

        if existing:
            result = await tp_repo.update(
                existing.id, {"is_active": True, "config": merged_config}
            )
        else:
            result = await tp_repo.create({
                "tenant_id": tenant_id,
                "plugin_id": plugin_id,
                "is_active": True,
                "config": merged_config,
            })
            await db.flush()

        from app.plugins.security import log_plugin_action
        log_plugin_action(
            action="enable",
            plugin_name=plugin.name,
            tenant_id=tenant_id,
            details={"scope": "tenant", "plugin_id": plugin_id},
        )

        logger.info(
            "Plugin enabled for tenant: plugin=%s tenant=%d", plugin.name, tenant_id
        )
        return result

    @_write_locked
    async def disable_tenant(
        self, db: AsyncSession, tenant_id: int, plugin_id: int
    ) -> TenantPlugin:
        """
        租户级禁用插件

        Args:
            db: 数据库会话
            tenant_id: 租户 ID
            plugin_id: 插件 ID

        Returns:
            更新后的 TenantPlugin 模型
        """
        from app.repositories.system.plugin_repository import PluginRepository
        from app.repositories.system.tenant_plugin_repository import (
            TenantPluginRepository,
        )

        tp_repo = TenantPluginRepository(db)
        existing = await tp_repo.get_by_tenant_and_plugin(tenant_id, plugin_id)
        if not existing:
            raise NotFoundException(_("tenant_plugin.not_found"))

        # 获取插件名称用于审计日志
        plugin_repo = PluginRepository(db)
        plugin = await plugin_repo.get_by_id(plugin_id)
        plugin_name = plugin.name if plugin else f"plugin_id:{plugin_id}"

        result = await tp_repo.update(existing.id, {"is_active": False})
        from app.plugins.security import log_plugin_action
        log_plugin_action(
            action="disable",
            plugin_name=plugin_name,
            tenant_id=tenant_id,
            details={"scope": "tenant", "plugin_id": plugin_id},
        )

        logger.info(
            "Plugin disabled for tenant: plugin=%s tenant=%d", plugin_name, tenant_id
        )
        return result

    # ========================================
    # 升级
    # ========================================

    @_write_locked
    async def upgrade(
        self,
        db: AsyncSession,
        plugin_id: int,
        new_entry_point: str | None = None,
    ) -> Plugin:
        """
        升级插件到新版本

        流程：加载新版本 → 版本对比 → 调用 on_upgrade → 更新 DB

        Args:
            db: 数据库会话
            plugin_id: 插件 ID
            new_entry_point: 新入口点（可选，默认使用原入口点重新加载）

        Returns:
            更新后的 Plugin 模型
        """
        from app.repositories.system.plugin_repository import PluginRepository

        repo = PluginRepository(db)
        plugin = await repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(_("plugin.not_found"))

        entry_point = new_entry_point or plugin.entry_point
        old_version = plugin.version

        # 保留旧实例以便回滚（必须在 pop 之前保存）
        old_instance = self.loader.get_instance(plugin.name)

        # 清除实例缓存 + Python 模块缓存，确保加载新版本代码
        self.loader.pop_instance(plugin.name)
        self.loader.clear_module_cache(plugin.name)
        plugin_cls = self.load_plugin_class(entry_point)
        instance = plugin_cls()

        new_version = instance.version
        if new_version == old_version:
            # 版本未变，恢复旧实例
            if old_instance is not None:
                self.loader.set_instance(plugin.name, old_instance)
            raise BusinessException(
                _("plugin.already_at_version", version=old_version)
            )

        # 版本降级保护：比较 semver 主版本号
        try:
            old_parts = [int(x) for x in old_version.split("-")[0].split("+")[0].split(".")]
            new_parts = [int(x) for x in new_version.split("-")[0].split("+")[0].split(".")]
            if new_parts < old_parts:
                if old_instance is not None:
                    self.loader.set_instance(plugin.name, old_instance)
                raise BusinessException(
                    _("plugin.downgrade_not_allowed")
                )
        except (ValueError, IndexError):
            pass  # 非标准版本号，跳过比较

        # 校验新版本的平台兼容性、依赖和冲突
        from app.plugins.dependencies import (
            check_platform_version_or_raise,
            check_dependencies_or_raise,
            check_conflicts_or_raise,
        )
        try:
            check_platform_version_or_raise(instance.platform_version)
            await check_dependencies_or_raise(db, instance.dependencies)
            await check_conflicts_or_raise(db, instance.conflicts, instance.name)
        except Exception:
            if old_instance is not None:
                self.loader.set_instance(plugin.name, old_instance)
            raise

        # 调用升级钩子
        ctx = self.config_manager.build_context(instance, db=db)
        try:
            await instance.on_upgrade(ctx, from_version=old_version)
        except Exception as exc:
            # 回滚：恢复旧实例缓存
            if old_instance is not None:
                self.loader.set_instance(plugin.name, old_instance)
            logger.error(
                "Plugin on_upgrade failed (rolled back): %s %s→%s — %s",
                plugin.name, old_version, new_version, str(exc),
                exc_info=True,
            )
            raise BusinessException(
                _("plugin.upgrade_hook_failed")
            ) from exc

        # 执行新版本的数据库迁移
        try:
            from app.plugins.migration_runner import run_migrations
            applied = await run_migrations(db, instance.name)
            if applied:
                logger.info(
                    "Plugin DB migrations applied during upgrade: %s %s→%s — %s",
                    plugin.name, old_version, new_version, applied,
                )
        except Exception as mig_exc:
            # 迁移失败：回滚实例缓存
            if old_instance is not None:
                self.loader.set_instance(plugin.name, old_instance)
            logger.error(
                "Plugin migration failed during upgrade: %s — %s",
                plugin.name, str(mig_exc), exc_info=True,
            )
            raise BusinessException(
                _("plugin.upgrade_hook_failed")
            ) from mig_exc

        # 更新 DB
        manifest = instance.get_manifest()
        version_entry = {
            "from": old_version,
            "to": new_version,
            "upgraded_at": utc_now().isoformat(),
        }
        version_history = list(plugin.version_history or [])
        version_history.append(version_entry)

        # 加密新版本 default_config 中的敏感字段
        new_default_config = instance.default_config or None
        if new_default_config and instance.config_schema:
            from app.plugins.security import encrypt_sensitive_config
            new_default_config = encrypt_sensitive_config(
                new_default_config, instance.config_schema
            )

        try:
            updated = await repo.update(plugin_id, {
                "version": new_version,
                "display_name": instance.display_name,
                "description": instance.description,
                "author": instance.author,
                "entry_point": entry_point,
                "manifest": manifest,
                "config_schema": instance.config_schema,
                "default_config": new_default_config,
                "icon": instance.icon or None,
                "homepage": instance.homepage or None,
                "version_history": version_history,
            })
        except Exception as exc:
            # DB 更新失败：回滚实例缓存
            if old_instance is not None:
                self.loader.set_instance(plugin.name, old_instance)
            logger.error(
                "Plugin upgrade DB update failed (rolled back): %s — %s",
                plugin.name, str(exc), exc_info=True,
            )
            raise

        self.loader.set_instance(plugin.name, instance)

        # 检查 config_schema 兼容性：新版本是否与现有租户配置兼容
        old_schema = plugin.config_schema
        new_schema = instance.config_schema
        if old_schema and new_schema:
            try:
                await self._check_config_schema_compat(
                    db, plugin_id, plugin.name, old_schema, new_schema,
                )
            except Exception as compat_exc:
                logger.warning(
                    "Config schema compat check failed for %s: %s",
                    plugin.name, str(compat_exc),
                )

        # 如果插件处于启用状态，重新注册扩展点以反映新版本
        if plugin.status == PluginStatusEnum.ENABLED.value:
            try:
                new_ctx = self.config_manager.build_context(instance, db=db)
                self.extension_registry.unregister(old_instance or instance, new_ctx)
                self.extension_registry.register(instance, new_ctx)
                logger.info(
                    "Plugin extensions re-registered after upgrade: %s",
                    plugin.name,
                )
            except Exception as ext_exc:
                logger.error(
                    "Failed to re-register extensions after upgrade: %s — %s",
                    plugin.name, str(ext_exc), exc_info=True,
                )

        from app.plugins.security import log_plugin_action
        log_plugin_action(
            action="upgrade",
            plugin_name=plugin.name,
            details={
                "from_version": old_version,
                "to_version": new_version,
                "plugin_id": plugin_id,
            },
        )

        logger.info(
            "Plugin upgraded: %s %s → %s", plugin.name, old_version, new_version
        )
        return updated

    # ========================================
    # 配置
    # ========================================

    @_write_locked
    async def configure_tenant(
        self,
        db: AsyncSession,
        tenant_id: int,
        plugin_id: int,
        config: dict[str, Any],
    ) -> TenantPlugin:
        """
        更新租户插件配置（带 JSON Schema 校验）

        Args:
            db: 数据库会话
            tenant_id: 租户 ID
            plugin_id: 插件 ID
            config: 新的配置

        Returns:
            更新后的 TenantPlugin 模型
        """
        from app.repositories.system.plugin_repository import PluginRepository
        from app.repositories.system.tenant_plugin_repository import (
            TenantPluginRepository,
        )

        # 获取插件的 config_schema
        plugin_repo = PluginRepository(db)
        plugin = await plugin_repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(_("plugin.not_found"))

        tp_repo = TenantPluginRepository(db)
        existing = await tp_repo.get_by_tenant_and_plugin(tenant_id, plugin_id)
        if not existing:
            raise NotFoundException(_("tenant_plugin.not_found"))

        merged = self.config_manager.merge_config(plugin.default_config, config)
        if plugin.config_schema:
            self.config_manager.validate_config(plugin.config_schema, merged)

        # 保留未修改的密码字段（前端回传 ****** 表示未更改）
        if plugin.config_schema:
            props = plugin.config_schema.get("properties", {})
            old_config = existing.config or {}
            for field_name, field_schema in props.items():
                if field_schema.get("format") == "password":
                    if merged.get(field_name) == "******":
                        merged[field_name] = old_config.get(field_name, "")

        # 加密敏感配置字段
        if plugin.config_schema:
            from app.plugins.security import encrypt_sensitive_config
            merged = encrypt_sensitive_config(merged, plugin.config_schema)

        result = await tp_repo.update(existing.id, {"config": merged})
        from app.plugins.security import log_plugin_action
        log_plugin_action(
            action="configure",
            plugin_name=plugin.name,
            tenant_id=tenant_id,
            details={"plugin_id": plugin_id},
        )

        logger.info(
            "Plugin config updated: plugin_id=%d tenant=%d", plugin_id, tenant_id
        )
        return result

    def get_plugin_routers(self) -> dict[str, str]:
        """获取所有已挂载的插件路由映射（委托 PluginRouteManager）"""
        return self.route_manager.get_plugin_routers()

    @staticmethod
    def install_plugin_requirements(plugin_name: str) -> list[str]:
        """安装插件 Python 依赖（委托 utils）"""
        return _install_plugin_requirements(plugin_name)

    def get_plugin_skill_types(self) -> dict[str, str]:
        """获取所有已注册的插件 Skill 类型（委托 ExtensionRegistry）"""
        return self.extension_registry.get_plugin_skill_types()

    def get_skill_plugin(self, skill_type: str) -> SkillPlugin | None:
        """根据 Skill 类型获取 SkillPlugin 实例（委托 ExtensionRegistry）"""
        return self.extension_registry.get_skill_plugin(skill_type)

    def get_all_skill_metadata(self) -> list[dict[str, Any]]:
        """获取所有已注册的插件 Skill 元数据（委托 ExtensionRegistry）"""
        return self.extension_registry.get_all_skill_metadata()

    def is_plugin_skill_type(self, skill_type: str) -> bool:
        """判断 Skill 类型是否由插件提供（委托 ExtensionRegistry）"""
        return self.extension_registry.is_plugin_skill_type(skill_type)

    # ========================================
    # 公共上下文构建
    # ========================================

    async def build_execution_context(
        self,
        instance: BasePlugin,
        db: AsyncSession | None = None,
        tenant_id: int | None = None,
        config: dict[str, Any] | None = None,
        skill_config: dict[str, Any] | None = None,
    ) -> PluginContext:
        """
        构建插件执行上下文（公共 API）

        供 PluginSkillExecutor 等外部组件调用，替代直接访问 _build_context。
        当 tenant_id 和 db 均提供且未显式传入 config 时，
        自动从 DB 加载租户自定义配置并合并 default_config。

        Args:
            instance: 插件实例
            db: 数据库会话
            tenant_id: 租户 ID
            config: 插件级配置覆盖
            skill_config: Skill 级配置（从 ToolDefinition.config 提取）

        Returns:
            PluginContext 实例
        """
        # 自动加载租户自定义配置（当未显式传入 config 时）
        if config is None and tenant_id is not None and db is not None:
            try:
                from app.repositories.system.plugin_repository import PluginRepository
                from app.repositories.system.tenant_plugin_repository import (
                    TenantPluginRepository,
                )

                plugin_repo = PluginRepository(db)
                plugin = await plugin_repo.get_by_name(instance.name)
                if plugin:
                    tp_repo = TenantPluginRepository(db)
                    tp = await tp_repo.get_by_tenant_and_plugin(
                        tenant_id, plugin.id
                    )
                    if tp and tp.config:
                        config = self.config_manager.merge_config(
                            instance.default_config, tp.config
                        )
            except Exception as exc:
                logger.warning(
                    "Failed to load tenant config for plugin %s tenant=%d: %s",
                    instance.name, tenant_id, str(exc),
                )

        ctx = self.config_manager.build_context(instance, db=db, tenant_id=tenant_id, config=config)
        if skill_config:
            ctx.skill_config = skill_config
        return ctx



# 全局便捷函数
def get_plugin_manager() -> PluginManager:
    """获取全局 PluginManager 实例"""
    return PluginManager.get_instance()


__all__ = ["PluginManager", "get_plugin_manager"]
