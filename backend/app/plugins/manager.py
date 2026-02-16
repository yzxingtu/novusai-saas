"""
插件生命周期管理器

单例模式，负责插件的安装、卸载、启用、禁用、升级和配置管理。
"""

from __future__ import annotations

import asyncio
import functools
import importlib
import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI
    from app.models.system.plugin import Plugin
    from app.models.system.tenant_plugin import TenantPlugin

import jsonschema
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import _
from app.core.logging import LogManager
from app.enums.plugin import PluginStatusEnum, PluginTypeEnum
from app.exceptions import (
    BusinessException,
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.plugins.base import BasePlugin
from app.plugins.context import PluginContext
from app.plugins.extensions.adapter_plugin import AdapterPlugin
from app.plugins.extensions.api_plugin import ApiPlugin
from app.plugins.extensions.hook_plugin import HookPlugin
from app.plugins.extensions.skill_plugin import SkillPlugin
from app.plugins.extensions.tool_plugin import ToolPlugin

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


def _resolve_plugin_type(plugin_instance: BasePlugin) -> str:
    """根据插件实例的类型推断 plugin_type"""
    type_map: list[tuple[type, str]] = [
        (AdapterPlugin, PluginTypeEnum.ADAPTER.value),
        (ToolPlugin, PluginTypeEnum.TOOL.value),
        (HookPlugin, PluginTypeEnum.HOOK.value),
        (ApiPlugin, PluginTypeEnum.API.value),
        (SkillPlugin, PluginTypeEnum.SKILL.value),
    ]
    types_found: list[str] = []
    for cls, type_val in type_map:
        if isinstance(plugin_instance, cls):
            types_found.append(type_val)

    if len(types_found) == 0:
        return PluginTypeEnum.COMPOSITE.value
    if len(types_found) == 1:
        return types_found[0]
    return PluginTypeEnum.COMPOSITE.value


class PluginManager:
    """
    插件生命周期管理器（单例）

    职责：
    - install: 动态导入 entry_point → 校验 manifest → 写入 DB
    - uninstall: 调用 on_uninstall → 清理 DB
    - enable / disable: 平台级 + 租户级
    - upgrade: 版本对比 → 调用 on_upgrade
    - configure: JSON Schema 校验 → 写入 config
    """

    _instance: PluginManager | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        # plugin_name -> loaded BasePlugin instance (in-memory cache)
        self._instances: dict[str, BasePlugin] = {}
        # provider_type -> plugin_name (adapter plugins registered to AdapterRegistry)
        self._plugin_adapters: dict[str, str] = {}
        # tool_name -> plugin_name (tool plugins registered to ToolRegistry)
        self._plugin_tools: dict[str, str] = {}
        # skill_type -> plugin_name (skill plugins registered)
        self._plugin_skills: dict[str, str] = {}
        # skill_type -> SkillPlugin instance (for resolve/execute delegation)
        self._skill_instances: dict[str, SkillPlugin] = {}
        # plugin_name -> route prefix (ApiPlugin routes mounted to app)
        self._plugin_routers: dict[str, str] = {}
        # FastAPI app reference for dynamic route mounting
        self._app: FastAPI | None = None
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
        self._app = app

    # ========================================
    # 动态加载
    # ========================================

    def load_plugin_class(self, entry_point: str) -> type[BasePlugin]:
        """
        从 entry_point 路径动态加载插件类

        Args:
            entry_point: 完整 Python 路径（如 app.plugins.anthropic.main.AnthropicPlugin）

        Returns:
            BasePlugin 子类

        Raises:
            BusinessException: 加载失败
        """
        try:
            module_path, class_name = entry_point.rsplit(".", 1)
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
        except (ValueError, ModuleNotFoundError, AttributeError) as exc:
            raise BusinessException(
                _("plugin.entry_point_not_found", entry_point=entry_point)
            ) from exc

        if not isinstance(cls, type) or not issubclass(cls, BasePlugin):
            raise BusinessException(
                _("plugin.entry_point_not_found", entry_point=entry_point)
            )

        return cls

    def get_or_load_instance(self, name: str, entry_point: str) -> BasePlugin:
        """
        获取已缓存的插件实例，或动态加载并缓存

        Args:
            name: 插件名称
            entry_point: 入口点路径

        Returns:
            BasePlugin 实例
        """
        if name in self._instances:
            return self._instances[name]

        plugin_cls = self.load_plugin_class(entry_point)
        instance = plugin_cls()
        self._instances[name] = instance
        return instance

    def load_and_register(
        self,
        name: str,
        entry_point: str,
        db: AsyncSession | None = None,
    ) -> BasePlugin:
        """
        加载插件实例并注册其扩展点（公共方法）

        用于启动时从 DB 恢复已启用插件的扩展点注册，
        替代直接调用 _build_context / _register_extensions。

        Args:
            name: 插件名称
            entry_point: 入口点路径
            db: 数据库会话（可选，传入后可用于 DB 操作的扩展点）

        Returns:
            已加载并注册的 BasePlugin 实例
        """
        instance = self.get_or_load_instance(name, entry_point)
        ctx = self._build_context(instance, db=db)
        self._register_extensions(instance, ctx)
        return instance

    def get_plugin_tools(self) -> dict[str, str]:
        """
        获取所有已注册的工具插件映射

        Returns:
            tool_name -> plugin_name 的映射
        """
        return dict(self._plugin_tools)

    def get_plugin_adapters(self) -> dict[str, str]:
        """
        获取所有已注册的适配器插件映射

        Returns:
            provider_type -> plugin_name 的映射
        """
        return dict(self._plugin_adapters)

    def get_adapter_plugin_info(self, provider_type: str) -> dict[str, Any] | None:
        """
        获取指定适配器插件的供应商信息

        Args:
            provider_type: 供应商类型标识

        Returns:
            供应商信息字典，或 None
        """
        plugin_name = self._plugin_adapters.get(provider_type)
        if not plugin_name:
            return None
        instance = self._instances.get(plugin_name)
        if not instance or not isinstance(instance, AdapterPlugin):
            return None
        return instance.get_provider_info()

    # ========================================
    # 安装
    # ========================================

    @_write_locked
    async def install(
        self,
        db: AsyncSession,
        entry_point: str,
        is_system: bool = False,
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
        plugin_type = _resolve_plugin_type(instance)

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
        plugin = await repo.create({
            "name": instance.name,
            "display_name": instance.display_name,
            "version": instance.version,
            "description": instance.description,
            "author": instance.author,
            "plugin_type": plugin_type,
            "status": PluginStatusEnum.INSTALLED.value,
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
        self._instances[instance.name] = instance

        # 调用生命周期钩子
        ctx = self._build_context(instance, db=db)
        try:
            await instance.on_install(ctx)
        except Exception as exc:
            logger.error(
                "Plugin on_install failed: %s — %s", instance.name, str(exc),
                exc_info=True,
            )
            # 回滚：删除刚插入的记录
            await repo.permanent_delete(plugin.id)
            self._instances.pop(instance.name, None)
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
            self._instances.pop(instance.name, None)
            raise

        from app.plugins.security import log_plugin_action
        log_plugin_action(
            action="install",
            plugin_name=instance.name,
            details={"version": instance.version, "entry_point": entry_point, "is_system": is_system},
        )

        logger.info("Plugin installed: %s v%s", instance.name, instance.version)
        return plugin

    # ========================================
    # 卸载
    # ========================================

    @_write_locked
    async def uninstall(self, db: AsyncSession, plugin_id: int) -> None:
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
            ctx = self._build_context(instance, db=db)

            # 注销扩展点（防止已启用插件直接卸载时注册泄漏）
            self._unregister_extensions(instance, ctx)

            # SkillPlugin 软删除技能包
            if isinstance(instance, SkillPlugin):
                try:
                    await self._deprovision_skill_plugin(
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
            rolled_back = await rollback_migrations(db, plugin_name)
            if rolled_back:
                logger.info(
                    "Plugin DB migrations rolled back: %s — %s",
                    plugin_name, rolled_back,
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
        self._instances.pop(plugin_name, None)

        # 清理插件文件目录（仅限 .nap 上传安装的插件）
        self._cleanup_plugin_directory(plugin_name, plugin_entry_point)

        from app.plugins.security import log_plugin_action
        log_plugin_action(
            action="uninstall",
            plugin_name=plugin_name,
            details={"version": plugin_version, "plugin_id": plugin_id},
        )

        logger.info("Plugin uninstalled: %s", plugin_name)

    # ========================================
    # 启用 / 禁用（平台级）
    # ========================================

    @_write_locked
    async def enable_platform(self, db: AsyncSession, plugin_id: int) -> Plugin:
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
        ctx = self._build_context(instance, db=db)

        try:
            await instance.on_enable(ctx)
        except Exception as exc:
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
            self._register_extensions(instance, ctx)
        except Exception as exc:
            logger.error(
                "Plugin extension registration failed: %s — %s",
                plugin.name, str(exc), exc_info=True,
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
                await self._provision_skill_plugin(db, instance)
            except Exception as exc:
                logger.error(
                    "Skill plugin provisioning failed: %s — %s",
                    plugin.name, str(exc), exc_info=True,
                )

        updated = await repo.update(
            plugin_id, {"status": PluginStatusEnum.ENABLED.value}
        )
        from app.plugins.security import log_plugin_action
        log_plugin_action(
            action="enable",
            plugin_name=plugin.name,
            details={"scope": "platform", "plugin_id": plugin_id},
        )

        logger.info("Plugin enabled (platform): %s", plugin.name)
        return updated

    @_write_locked
    async def disable_platform(self, db: AsyncSession, plugin_id: int) -> Plugin:
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

        instance = self.get_or_load_instance(plugin.name, plugin.entry_point)
        ctx = self._build_context(instance, db=db)

        try:
            await instance.on_disable(ctx)
        except Exception as exc:
            logger.error(
                "Plugin on_disable error (proceeding): %s — %s",
                plugin.name, str(exc), exc_info=True,
            )

        # 注销扩展点
        self._unregister_extensions(instance, ctx)

        # SkillPlugin 停用技能包
        if isinstance(instance, SkillPlugin):
            try:
                await self._deprovision_skill_plugin(db, instance, soft_delete=False)
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
            details={"scope": "platform", "plugin_id": plugin_id},
        )

        logger.info("Plugin disabled (platform): %s", plugin.name)
        return updated

    # ========================================
    # 启用 / 禁用（租户级）
    # ========================================

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
        merged_config = self._merge_config(plugin.default_config, config)
        if config and plugin.config_schema:
            self._validate_config(plugin.config_schema, merged_config)

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
        old_instance = self._instances.get(plugin.name)

        # 清除缓存，强制重新加载
        self._instances.pop(plugin.name, None)
        plugin_cls = self.load_plugin_class(entry_point)
        instance = plugin_cls()

        new_version = instance.version
        if new_version == old_version:
            # 版本未变，恢复旧实例
            if old_instance is not None:
                self._instances[plugin.name] = old_instance
            raise BusinessException(
                _("plugin.already_at_version", version=old_version)
            )

        # 调用升级钩子
        ctx = self._build_context(instance, db=db)
        try:
            await instance.on_upgrade(ctx, from_version=old_version)
        except Exception as exc:
            # 回滚：恢复旧实例缓存
            if old_instance is not None:
                self._instances[plugin.name] = old_instance
            logger.error(
                "Plugin on_upgrade failed (rolled back): %s %s→%s — %s",
                plugin.name, old_version, new_version, str(exc),
                exc_info=True,
            )
            raise BusinessException(
                _("plugin.upgrade_hook_failed")
            ) from exc

        # 更新 DB
        manifest = instance.get_manifest()
        version_entry = {
            "from": old_version,
            "to": new_version,
            "upgraded_at": datetime.now(timezone.utc).isoformat(),
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
                self._instances[plugin.name] = old_instance
            logger.error(
                "Plugin upgrade DB update failed (rolled back): %s — %s",
                plugin.name, str(exc), exc_info=True,
            )
            raise

        self._instances[plugin.name] = instance

        # 如果插件处于启用状态，重新注册扩展点以反映新版本
        if plugin.status == PluginStatusEnum.ENABLED.value:
            try:
                new_ctx = self._build_context(instance, db=db)
                self._unregister_extensions(old_instance or instance, new_ctx)
                self._register_extensions(instance, new_ctx)
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

        merged = self._merge_config(plugin.default_config, config)
        if plugin.config_schema:
            self._validate_config(plugin.config_schema, merged)

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

    # ========================================
    # SkillPlugin 自动装配
    # ========================================

    async def _provision_skill_plugin(
        self,
        db: AsyncSession,
        instance: SkillPlugin,
    ) -> None:
        """
        SkillPlugin 启用时自动创建 SkillPackage + Skill 记录

        幂等：若已存在同名 source_plugin 记录则恢复激活，不重复创建。
        """
        from app.repositories.ai.skill_package_repository import (
            AdminSkillPackageRepository,
        )
        from app.repositories.ai.skill_repository import AdminSkillRepository

        pkg_repo = AdminSkillPackageRepository(db)
        skill_repo = AdminSkillRepository(db)

        plugin_name = instance.name
        skill_type = instance.get_skill_type()
        display_name = instance.get_skill_display_name()

        # 幂等：检查是否已有该插件创建的技能包
        existing_pkg = await pkg_repo.get_by_source_plugin(plugin_name)
        if existing_pkg:
            # 已存在 → 恢复激活
            if existing_pkg.is_deleted or not existing_pkg.is_active:
                await pkg_repo.update(existing_pkg.id, {
                    "is_active": True,
                    "is_deleted": False,
                    "deleted_at": None,
                    "delete_level": None,
                    "name": display_name,
                    "avatar": instance.get_skill_icon(),
                })
            # 恢复技能包下的技能
            from sqlalchemy import select, and_
            from app.models.ai.skill import Skill
            stmt = select(Skill).where(
                and_(
                    Skill.package_id == existing_pkg.id,
                    Skill.type == skill_type,
                )
            )
            result = await db.execute(stmt)
            existing_skills = list(result.scalars().all())
            for s in existing_skills:
                if s.is_deleted or not s.is_active:
                    await skill_repo.update(s.id, {
                        "is_active": True,
                        "is_deleted": False,
                        "deleted_at": None,
                        "delete_level": None,
                    })
            logger.info(
                "Skill plugin re-activated: plugin=%s package_id=%d",
                plugin_name, existing_pkg.id,
            )
            return

        # 新建 SkillPackage
        config_schema = instance.get_skill_config_schema()
        default_config = self._extract_schema_defaults(config_schema)

        pkg = await pkg_repo.create({
            "name": display_name,
            "description": instance.description,
            "avatar": instance.get_skill_icon(),
            "scope": "admin",
            "source_plugin": plugin_name,
            "is_system": True,
            "is_active": True,
            "tenant_id": None,
        })
        await db.flush()

        # 新建 Skill
        await skill_repo.create({
            "package_id": pkg.id,
            "name": display_name,
            "description": instance.description,
            "avatar": instance.get_skill_icon(),
            "type": skill_type,
            "scope": "admin",
            "is_system": True,
            "is_active": True,
            "config": default_config,
            "input_schema": config_schema,
            "tenant_id": None,
        })
        await db.flush()

        logger.info(
            "Skill plugin provisioned: plugin=%s type=%s package_id=%d",
            plugin_name, skill_type, pkg.id,
        )

    async def _deprovision_skill_plugin(
        self,
        db: AsyncSession,
        instance: SkillPlugin,
        *,
        soft_delete: bool = False,
    ) -> None:
        """
        SkillPlugin 禁用/卸载时停用或软删除 SkillPackage + Skill

        Args:
            db: 数据库会话
            instance: SkillPlugin 实例
            soft_delete: True=软删除（卸载时），False=仅停用（禁用时）
        """
        from app.repositories.ai.skill_package_repository import (
            AdminSkillPackageRepository,
        )
        from app.repositories.ai.skill_repository import AdminSkillRepository

        pkg_repo = AdminSkillPackageRepository(db)
        skill_repo = AdminSkillRepository(db)
        plugin_name = instance.name

        existing_pkg = await pkg_repo.get_by_source_plugin(plugin_name)
        if not existing_pkg:
            return

        # 处理技能包下的所有技能
        from sqlalchemy import select
        from app.models.ai.skill import Skill
        stmt = select(Skill).where(Skill.package_id == existing_pkg.id)
        result = await db.execute(stmt)
        skills = list(result.scalars().all())

        if soft_delete:
            from datetime import datetime
            now = datetime.utcnow()
            for s in skills:
                await skill_repo.update(s.id, {
                    "is_active": False,
                    "is_deleted": True,
                    "deleted_at": now,
                    "delete_level": "admin",
                })
            await pkg_repo.update(existing_pkg.id, {
                "is_active": False,
                "is_deleted": True,
                "deleted_at": now,
                "delete_level": "admin",
            })
            logger.info(
                "Skill plugin soft-deleted: plugin=%s package_id=%d",
                plugin_name, existing_pkg.id,
            )
        else:
            for s in skills:
                await skill_repo.update(s.id, {"is_active": False})
            await pkg_repo.update(existing_pkg.id, {"is_active": False})
            logger.info(
                "Skill plugin deactivated: plugin=%s package_id=%d",
                plugin_name, existing_pkg.id,
            )

    @staticmethod
    def _extract_schema_defaults(schema: dict[str, Any]) -> dict[str, Any]:
        """从 JSON Schema 的 properties 中提取 default 值"""
        defaults: dict[str, Any] = {}
        if not schema:
            return defaults
        for key, prop in schema.get("properties", {}).items():
            if "default" in prop:
                defaults[key] = prop["default"]
        return defaults

    # ========================================
    # 扩展点注册 / 注销
    # ========================================

    def _register_extensions(
        self, instance: BasePlugin, ctx: PluginContext
    ) -> None:
        """启用时注册扩展点到对应的系统组件"""
        if isinstance(instance, AdapterPlugin):
            from app.ai.adapters import AdapterRegistry
            provider_info = instance.get_provider_info()
            provider_type = provider_info.get("name", instance.name)
            adapter_class = instance.get_adapter_class()
            AdapterRegistry.register(provider_type, adapter_class)
            self._plugin_adapters[provider_type] = instance.name
            logger.info(
                "Adapter plugin registered: %s -> %s",
                provider_type, adapter_class.__name__,
            )

        if isinstance(instance, HookPlugin) and ctx.event_bus:
            for event_type, handler, priority in instance.get_event_handlers():
                ctx.event_bus.subscribe(event_type, handler, priority)
                logger.debug(
                    "Hook registered: %s -> %s",
                    event_type.__name__, handler.__qualname__,
                )

        if isinstance(instance, ToolPlugin) and ctx.tool_registry:
            for tool_def in instance.get_tool_definitions():
                ctx.tool_registry.register(tool_def)
                self._plugin_tools[tool_def.name] = instance.name
                logger.debug("Tool registered: %s (plugin=%s)", tool_def.name, instance.name)

        if isinstance(instance, SkillPlugin):
            skill_type = instance.get_skill_type()
            existing_owner = self._plugin_skills.get(skill_type)
            if existing_owner and existing_owner != instance.name:
                raise ConflictException(
                    _("plugin.skill_type_conflict"),
                )
            self._plugin_skills[skill_type] = instance.name
            self._skill_instances[skill_type] = instance
            logger.info(
                "Skill plugin registered: type=%s plugin=%s",
                skill_type, instance.name,
            )

        if isinstance(instance, ApiPlugin) and self._app is not None:
            self._mount_plugin_routes(instance)

    def _unregister_extensions(
        self, instance: BasePlugin, ctx: PluginContext
    ) -> None:
        """禁用时从系统组件中注销扩展点"""
        if isinstance(instance, AdapterPlugin):
            from app.ai.adapters import AdapterRegistry
            provider_info = instance.get_provider_info()
            provider_type = provider_info.get("name", instance.name)
            AdapterRegistry.unregister(provider_type)
            self._plugin_adapters.pop(provider_type, None)
            logger.info("Adapter plugin unregistered: %s", provider_type)

        if isinstance(instance, HookPlugin) and ctx.event_bus:
            for event_type, handler, _priority in instance.get_event_handlers():
                ctx.event_bus.unsubscribe(event_type, handler)
                logger.debug(
                    "Hook unregistered: %s -> %s",
                    event_type.__name__, handler.__qualname__,
                )

        if isinstance(instance, ToolPlugin) and ctx.tool_registry:
            for tool_def in instance.get_tool_definitions():
                ctx.tool_registry.unregister(tool_def.name)
                self._plugin_tools.pop(tool_def.name, None)
                logger.debug("Tool unregistered: %s (plugin=%s)", tool_def.name, instance.name)

        if isinstance(instance, SkillPlugin):
            skill_type = instance.get_skill_type()
            self._plugin_skills.pop(skill_type, None)
            self._skill_instances.pop(skill_type, None)
            logger.info(
                "Skill plugin unregistered: type=%s plugin=%s",
                skill_type, instance.name,
            )

        if isinstance(instance, ApiPlugin) and self._app is not None:
            self._unmount_plugin_routes(instance)

    # ========================================
    # ApiPlugin 路由管理
    # ========================================

    _AUTH_LEVEL_DEPS: dict[str, list] | None = None

    @classmethod
    def _get_auth_deps(cls, auth_level: str) -> list:
        """根据认证级别返回 FastAPI 依赖列表"""
        if cls._AUTH_LEVEL_DEPS is None:
            from fastapi import Depends
            from app.core.deps import (
                get_current_active_admin,
                get_current_super_admin,
            )
            cls._AUTH_LEVEL_DEPS = {
                "public": [],
                "auth_only": [Depends(get_current_active_admin)],
                "admin_only": [Depends(get_current_super_admin)],
            }
        return cls._AUTH_LEVEL_DEPS.get(auth_level, cls._AUTH_LEVEL_DEPS["auth_only"])

    def _mount_plugin_routes(self, instance: ApiPlugin) -> None:
        """将 ApiPlugin 的路由挂载到 FastAPI 应用

        根据插件的 ``get_auth_level()`` 返回值自动注入认证依赖：
        - ``public``: 无认证
        - ``auth_only``: 需要活跃管理员（默认）
        - ``admin_only``: 需要超级管理员
        """
        plugin_name = instance.name
        if plugin_name in self._plugin_routers:
            logger.warning("Plugin routes already mounted: %s", plugin_name)
            return

        try:
            router = instance.get_router()
            route_prefix = instance.get_route_prefix()
            tags = instance.get_route_tags()
            auth_level = instance.get_auth_level()
            full_prefix = f"/plugins/{plugin_name}{route_prefix}"

            deps = self._get_auth_deps(auth_level)
            self._app.include_router(
                router, prefix=full_prefix, tags=tags, dependencies=deps,
            )
            self._plugin_routers[plugin_name] = full_prefix
            logger.info(
                "API plugin routes mounted: %s -> %s (auth=%s)",
                plugin_name, full_prefix, auth_level,
            )
        except Exception as exc:
            logger.error(
                "Failed to mount plugin routes: %s: %s",
                plugin_name, exc, exc_info=True,
            )

    def _unmount_plugin_routes(self, instance: ApiPlugin) -> None:
        """从 FastAPI 应用中移除 ApiPlugin 的路由

        同时处理 APIRoute 和 Mount 类型的路由对象，
        并清除 OpenAPI schema 缓存以确保 /docs 同步更新。
        """
        from starlette.routing import Mount

        plugin_name = instance.name
        full_prefix = self._plugin_routers.pop(plugin_name, None)
        if not full_prefix:
            return

        try:
            original_count = len(self._app.routes)

            def _is_plugin_route(route: object) -> bool:
                path = getattr(route, "path", "")
                if isinstance(path, str) and path.startswith(full_prefix):
                    return True
                if isinstance(route, Mount) and isinstance(route.path, str):
                    return route.path.startswith(full_prefix)
                return False

            self._app.routes[:] = [
                route for route in self._app.routes
                if not _is_plugin_route(route)
            ]
            removed = original_count - len(self._app.routes)

            # 清除 OpenAPI schema 缓存，确保 /docs 不再显示已卸载的路由
            self._app.openapi_schema = None

            if removed == 0:
                logger.warning(
                    "API plugin unmount: no routes matched prefix %s for %s",
                    full_prefix, plugin_name,
                )
            else:
                logger.info(
                    "API plugin routes unmounted: %s (%d routes removed, OpenAPI cache cleared)",
                    plugin_name, removed,
                )
        except Exception as exc:
            logger.error(
                "Failed to unmount plugin routes: %s: %s",
                plugin_name, exc, exc_info=True,
            )

    def get_plugin_routers(self) -> dict[str, str]:
        """
        获取所有已挂载的插件路由映射

        Returns:
            plugin_name -> route_prefix 的映射
        """
        return dict(self._plugin_routers)

    # ========================================
    # 插件文件目录清理
    # ========================================

    _PLUGINS_BASE_PREFIX = "app.plugins."

    def _cleanup_plugin_directory(
        self, plugin_name: str, entry_point: str,
    ) -> None:
        """卸载后清理插件文件目录

        仅处理通过 .nap 上传安装的插件（entry_point 以 ``app.plugins.`` 开头）。
        外部 entry_point 安装的插件不删除文件。删除失败不阻塞卸载流程。

        Args:
            plugin_name: 插件名称
            entry_point: 插件入口点路径
        """
        if not entry_point.startswith(self._PLUGINS_BASE_PREFIX):
            logger.debug(
                "Skipping directory cleanup for external plugin: %s (entry_point=%s)",
                plugin_name, entry_point,
            )
            return

        import shutil
        from pathlib import Path

        plugins_base = Path(__file__).resolve().parent.parent / "plugins"
        plugin_dir = plugins_base / plugin_name

        if not plugin_dir.exists():
            logger.debug(
                "Plugin directory does not exist, nothing to clean: %s",
                plugin_dir,
            )
            return

        try:
            shutil.rmtree(plugin_dir)
            from app.plugins.security import log_plugin_action
            log_plugin_action(
                action="cleanup_directory",
                plugin_name=plugin_name,
                details={"directory": str(plugin_dir), "status": "deleted"},
            )
            logger.info(
                "Plugin directory cleaned up: %s", plugin_dir,
            )
        except Exception as exc:
            logger.warning(
                "Failed to delete plugin directory %s: %s — "
                "manual cleanup may be required",
                plugin_dir, exc, exc_info=True,
            )

    # ========================================
    # Python 依赖安装
    # ========================================

    @staticmethod
    def install_plugin_requirements(plugin_name: str) -> list[str]:
        """安装插件 Python 依赖

        检测 ``app/plugins/{name}/requirements.txt``，若存在则执行
        ``pip install -r requirements.txt``。

        Args:
            plugin_name: 插件名称

        Returns:
            安装的依赖列表（来自 requirements.txt 的行）

        Raises:
            BusinessException: pip install 失败
        """
        import subprocess
        import sys
        from pathlib import Path

        plugins_base = Path(__file__).resolve().parent.parent / "plugins"
        req_file = plugins_base / plugin_name / "requirements.txt"

        if not req_file.exists():
            return []

        deps = [
            line.strip()
            for line in req_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if not deps:
            return []

        logger.info(
            "Installing plugin dependencies: %s (%d packages)",
            plugin_name, len(deps),
        )

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if result.returncode != 0:
                logger.error(
                    "pip install failed for plugin %s:\nstdout: %s\nstderr: %s",
                    plugin_name, result.stdout, result.stderr,
                )
                raise BusinessException(
                    _("plugin.dependency_install_failed")
                )
        except subprocess.TimeoutExpired:
            raise BusinessException(
                _("plugin.dependency_install_timeout")
            )

        from app.plugins.security import log_plugin_action
        log_plugin_action(
            action="install_dependencies",
            plugin_name=plugin_name,
            details={"dependencies": deps},
        )

        logger.info(
            "Plugin dependencies installed: %s — %s",
            plugin_name, deps,
        )
        return deps

    # ========================================
    # SkillPlugin 查询
    # ========================================

    def get_plugin_skill_types(self) -> dict[str, str]:
        """
        获取所有已注册的插件 Skill 类型

        Returns:
            skill_type -> plugin_name 的映射
        """
        return dict(self._plugin_skills)

    def get_skill_plugin(self, skill_type: str) -> SkillPlugin | None:
        """
        根据 Skill 类型获取对应的 SkillPlugin 实例

        供 SkillResolver 和 Sandbox 委托调用。

        Args:
            skill_type: Skill 类型标识

        Returns:
            SkillPlugin 实例或 None
        """
        return self._skill_instances.get(skill_type)

    def get_all_skill_metadata(self) -> list[dict[str, Any]]:
        """
        获取所有已注册的插件 Skill 元数据

        供前端 Skill 创建表单展示可选的插件 Skill 类型。

        Returns:
            元数据列表
        """
        result = []
        for skill_type, instance in self._skill_instances.items():
            result.append(instance.get_skill_metadata())
        return result

    def is_plugin_skill_type(self, skill_type: str) -> bool:
        """
        判断给定的 Skill 类型是否由插件提供

        Args:
            skill_type: Skill 类型标识

        Returns:
            是否为插件 Skill 类型
        """
        return skill_type in self._plugin_skills

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
                        config = self._merge_config(
                            instance.default_config, tp.config
                        )
            except Exception as exc:
                logger.warning(
                    "Failed to load tenant config for plugin %s tenant=%d: %s",
                    instance.name, tenant_id, str(exc),
                )

        ctx = self._build_context(instance, db=db, tenant_id=tenant_id, config=config)
        if skill_config:
            ctx.skill_config = skill_config
        return ctx

    # ========================================
    # 内部工具方法
    # ========================================

    def _build_context(
        self,
        instance: BasePlugin,
        db: AsyncSession | None = None,
        tenant_id: int | None = None,
        config: dict[str, Any] | None = None,
    ) -> PluginContext:
        """构建权限感知的插件运行时上下文"""
        from app.ai.events.bus import get_event_bus
        from app.ai.tools.registry import get_tool_registry
        from app.plugins.security import (
            build_permission_aware_context_kwargs,
            decrypt_sensitive_config,
        )

        plugin_logger = LogManager.get_logger(f"plugin.{instance.name}")

        # 根据声明的权限决定注入哪些能力
        ctx_kwargs = build_permission_aware_context_kwargs(
            declared_permissions=instance.required_permissions,
            db=db,
            event_bus=get_event_bus(),
            tool_registry=get_tool_registry(),
        )

        # 确定最终配置：优先使用传入的 config，否则用实例默认配置
        final_config = config or instance.default_config
        # 解密 DB 中存储的加密敏感字段（format:password）
        if final_config and instance.config_schema:
            final_config = decrypt_sensitive_config(
                final_config, instance.config_schema
            )

        return PluginContext(
            config=final_config,
            tenant_id=tenant_id,
            logger=plugin_logger,
            plugin_name=instance.name,
            plugin_version=instance.version,
            **ctx_kwargs,
        )

    @staticmethod
    def _merge_config(
        default: dict[str, Any] | None,
        override: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """深度合并默认配置和自定义配置（嵌套 dict 递归合并）"""
        result = dict(default or {})
        if not override:
            return result
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = PluginManager._merge_config(result[key], value)
            else:
                result[key] = value
        return result

    @staticmethod
    def _validate_config(
        schema: dict[str, Any], config: dict[str, Any]
    ) -> None:
        """使用 JSON Schema 校验配置"""
        try:
            jsonschema.validate(instance=config, schema=schema)
        except jsonschema.ValidationError as exc:
            raise ValidationException(
                _("plugin.config_validation_failed") + f": {exc.message}"
            ) from exc


# 全局便捷函数
def get_plugin_manager() -> PluginManager:
    """获取全局 PluginManager 实例"""
    return PluginManager.get_instance()


__all__ = ["PluginManager", "get_plugin_manager"]
