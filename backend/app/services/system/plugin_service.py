"""
插件 Service / Plugin Service

封装插件安装/启停/卸载/配置/企业分配等业务逻辑。
Encapsulates plugin install/enable/disable/uninstall/config/tenant assignment business logic.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.base_service import BaseService
from app.core.logging import get_logger
from app.exceptions.base import BusinessException, NotFoundException, ValidationException
from app.models.system.plugin import Plugin
from app.plugins.dependencies import (
    build_plugin_dependency_states,
    build_python_dependency_states,
    normalize_plugin_dependencies,
)
from app.repositories.system.plugin_repository import PluginRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class PluginService(BaseService[Plugin, PluginRepository]):
    """插件业务服务 / Plugin business service."""

    model = Plugin
    repository_class = PluginRepository

    def __init__(self, db: AsyncSession) -> None:
        super().__init__(db)
        from app.plugins.lifecycle import PluginLifecycle
        from app.plugins.loader import PluginLoader

        self._lifecycle = PluginLifecycle(db)
        self._loader = PluginLoader()

    @staticmethod
    def _validate_config_against_schema(config: dict, schema: dict) -> None:
        """
        对插件配置执行轻量级 JSON-Schema 校验。 / Lightweight JSON-Schema validation for plugin config.
        说明：当前只覆盖 required/type/enum/min-max/pattern；required 拦截空字符串。
        Note: Covers required/type/enum/min-max/pattern; required rejects empty string.
        """
        if not isinstance(config, dict):
            raise ValidationException(message="Plugin config must be an object")
        if not isinstance(schema, dict):
            return

        properties = schema.get("properties") or {}
        required_fields = schema.get("required") or []

        # required: 同时拦截 key 缺失与空字符串
        missing_required: list[str] = []
        for field in required_fields:
            if field not in config:
                missing_required.append(field)
                continue
            value = config.get(field)
            if value is None:
                missing_required.append(field)
                continue
            if isinstance(value, str) and value.strip() == "":
                missing_required.append(field)
        if missing_required:
            raise ValidationException(
                message=f"Missing required plugin config fields: {', '.join(missing_required)}",
            )

        def _type_ok(value: object, expected_type: str) -> bool:
            if expected_type == "string":
                return isinstance(value, str)
            if expected_type == "integer":
                return isinstance(value, int) and not isinstance(value, bool)
            if expected_type == "number":
                return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
            if expected_type == "boolean":
                return isinstance(value, bool)
            if expected_type == "object":
                return isinstance(value, dict)
            if expected_type == "array":
                return isinstance(value, list)
            return True

        for key, value in config.items():
            if key not in properties:
                # 允许额外字段，保持向后兼容 / Allow extra fields for backward compatibility
                continue
            spec = properties.get(key) or {}
            expected_type = spec.get("type")
            if isinstance(expected_type, str) and not _type_ok(value, expected_type):
                raise ValidationException(
                    message=f"Invalid type for config '{key}', expected {expected_type}",
                )

            if "enum" in spec and value not in (spec.get("enum") or []):
                raise ValidationException(
                    message=f"Invalid value for config '{key}', allowed: {spec.get('enum')}",
                )

            if isinstance(value, str):
                min_len = spec.get("minLength")
                if isinstance(min_len, int) and len(value) < min_len:
                    raise ValidationException(
                        message=f"Config '{key}' must have at least {min_len} characters",
                    )
                max_len = spec.get("maxLength")
                if isinstance(max_len, int) and len(value) > max_len:
                    raise ValidationException(
                        message=f"Config '{key}' must have at most {max_len} characters",
                    )
                pattern = spec.get("pattern")
                if isinstance(pattern, str) and not re.search(pattern, value):
                    raise ValidationException(
                        message=f"Config '{key}' format is invalid",
                    )

            if isinstance(value, int) or isinstance(value, float):
                minimum = spec.get("minimum")
                if isinstance(minimum, int) or isinstance(minimum, float):
                    if value < minimum:
                        raise ValidationException(
                            message=f"Config '{key}' must be >= {minimum}",
                        )
                maximum = spec.get("maximum")
                if isinstance(maximum, int) or isinstance(maximum, float):
                    if value > maximum:
                        raise ValidationException(
                            message=f"Config '{key}' must be <= {maximum}",
                        )

    # ── 安装/启停/卸载 ── / ── Install / enable-disable / uninstall ──

    async def install_from_path(
        self,
        source_path: Path,
        config: dict | None = None,
        capabilities: list[str] | None = None,
        operator_id: int | None = None,
    ) -> Plugin:
        """
        安装插件 / Install plugin.

        Args:
            source_path: 插件源目录
            config: 初始配置
            capabilities: 授权能力列表
            operator_id: 操作者管理员 ID（用于进度推送）
        """
        plugin = await self._lifecycle.install(source_path, config, operator_id=operator_id)
        if capabilities:
            plugin.granted_capabilities = capabilities
            await self.db.flush()
        return plugin

    async def enable_plugin(self, plugin_id: int, operator_id: int | None = None) -> None:
        """启用插件 / Enable plugin."""
        await self._lifecycle.enable(plugin_id, operator_id=operator_id)

    async def disable_plugin(self, plugin_id: int, force: bool = False, operator_id: int | None = None) -> None:
        """禁用插件 / Disable plugin."""
        await self._lifecycle.disable(plugin_id, force=force, operator_id=operator_id)

    async def install_plugin_dependencies(
        self,
        plugin_id: int,
        *,
        install_python: bool = True,
    ) -> dict:
        """显式安装插件依赖（不改变插件状态） / Install plugin deps (does not change plugin state)."""
        return await self._lifecycle.install_dependencies(
            plugin_id,
            install_python=install_python,
        )

    async def uninstall_plugin_dependencies(
        self,
        plugin_id: int,
        *,
        uninstall_python: bool = True,
        force: bool = False,
    ) -> dict:
        """显式卸载插件依赖（不卸载插件本体） / Uninstall plugin deps (plugin itself remains)."""
        return await self._lifecycle.uninstall_dependencies(
            plugin_id,
            uninstall_python=uninstall_python,
            force=force,
        )

    async def uninstall_plugin(
        self,
        plugin_id: int,
        confirm_data_delete: bool = False,
        *,
        cleanup_dependencies: bool = False,
        operator_id: int | None = None,
    ) -> None:
        """卸载插件 / Uninstall plugin."""
        await self._lifecycle.uninstall(
            plugin_id,
            confirm_data_delete,
            cleanup_dependencies=cleanup_dependencies,
            operator_id=operator_id,
        )

    async def sync_manifest(
        self,
        plugin_id: int,
    ) -> Plugin:
        """显式同步磁盘 manifest 到 DB；版本变化必须走正式 upgrade。 / Explicitly sync disk manifest to DB; version drift must use formal upgrade."""
        from app.enums.plugin import PluginStatusEnum
        from app.plugins._extension_registrar import (
            get_failed_extensions,
            register_all_extensions,
        )
        from app.plugins.frontend_contract import validate_runtime_frontend_contract
        from app.plugins.manifest import PluginManifest
        from app.plugins.preview import resolve_i18n
        from app.plugins.registry import ExtensionRegistry
        from app.rbac.sync import PermissionSyncService

        plugin = await self.repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(message="plugin.error.not_found")

        manifest = self._loader.load_manifest(plugin.name)
        if manifest.version != plugin.version:
            raise ValidationException(
                message=(
                    f"Plugin '{plugin.name}' disk version is {manifest.version}, "
                    f"but DB version is {plugin.version}. Use formal upgrade instead of sync-manifest."
                ),
            )

        validate_runtime_frontend_contract(self._loader.plugins_dir / plugin.name, manifest)

        previous_manifest = None
        if plugin.manifest:
            try:
                previous_manifest = PluginManifest.model_validate(plugin.manifest)
            except Exception:
                previous_manifest = None

        stale_manifest_error = (
            plugin.status == PluginStatusEnum.ERROR.value
            and "Manifest drift detected on disk." in str(plugin.error_message or "")
        )
        should_restore_runtime = (
            plugin.status == PluginStatusEnum.ENABLED.value
            or (
                stale_manifest_error
                and plugin.enabled_at is not None
            )
        )

        manifest_dump = manifest.model_dump()
        plugin.display_name = resolve_i18n(manifest.display_name)
        plugin.description = (
            resolve_i18n(manifest.description)
            if manifest.description
            else plugin.description
        )
        plugin.author = manifest.author or None
        plugin.icon = manifest.icon or None
        plugin.icon_color = manifest.icon_color or None
        plugin.homepage = manifest.homepage or None
        plugin.repository_url = manifest.repository_url or None
        plugin.license_text = manifest.license or None
        plugin.tags = manifest.tags
        plugin.scope = manifest.scope
        plugin.manifest = manifest_dump
        plugin.ai_requirements = (
            manifest.ai_requirements.model_dump()
            if manifest.ai_requirements
            else None
        )
        plugin.pricing_type = manifest.pricing.type
        plugin.pricing_info = (
            manifest.pricing.model_dump()
            if manifest.pricing.type != "free"
            else None
        )
        plugin.installed_packages = manifest.dependencies.python or []
        await self.db.flush()

        if should_restore_runtime:
            registry = ExtensionRegistry.get_instance()
            menu_overrides = (plugin.config or {}).get("menu_overrides")
            registry.unregister_all(plugin.name)
            register_all_extensions(
                registry,
                manifest,
                plugin.name,
                menu_overrides=menu_overrides,
            )
            failed = get_failed_extensions(plugin.name)
            if failed:
                registry.unregister_all(plugin.name)
                if previous_manifest is not None:
                    register_all_extensions(
                        registry,
                        previous_manifest,
                        plugin.name,
                        menu_overrides=menu_overrides,
                    )
                failed_summary = "; ".join(
                    f"{item['type']}:{item['entry_point']}"
                    for item in failed[:5]
                )
                raise BusinessException(
                    message=(
                        "Sync manifest failed: "
                        f"{len(failed)} extension(s) failed to load. {failed_summary}"
                    ),
                )

            sync_service = PermissionSyncService(self.db)
            await self._lifecycle._delete_plugin_permissions_from_db(plugin.name)
            await sync_service.sync_plugin_permissions(plugin.name)
            await self._lifecycle._set_plugin_permissions_enabled(plugin.name, True)
            if manifest.extensions.tasks:
                await self._lifecycle._sync_plugin_task_definitions(
                    plugin.name,
                    manifest.extensions.tasks,
                )
            plugin.status = PluginStatusEnum.ENABLED.value
            plugin.error_message = None
            plugin.error_count = 0
            await self.db.flush()
        elif stale_manifest_error:
            plugin.status = (
                PluginStatusEnum.DISABLED.value
                if plugin.enabled_at is not None
                else PluginStatusEnum.INSTALLED.value
            )
            plugin.error_message = None
            plugin.error_count = 0
            await self.db.flush()

        return plugin

    # ── 配置 ── / ── Configuration ──

    async def update_plugin_config(
        self, plugin_id: int, config: dict
    ) -> Plugin:
        """更新插件全局配置（自动加密敏感字段） / Update plugin global config (auto-encrypt sensitive)."""
        from app.plugins.crypto import encrypt_plugin_config

        plugin = await self.repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(message="plugin.error.not_found")

        # 优先读取磁盘最新 manifest 做 schema 校验，但不在配置保存路径上隐式同步
        # manifest snapshot；same-version drift 仍必须显式走 sync-manifest。
        # / Prefer the latest disk manifest for schema validation, but do not
        # implicitly sync the DB manifest snapshot during config updates.
        manifest_data = plugin.manifest or {}
        try:
            latest_manifest = self._loader.load_manifest(plugin.name)
            manifest_data = latest_manifest.model_dump(exclude_none=True)
        except Exception as exc:
            logger.warning(
                "Failed to load latest manifest for plugin {}, fallback to DB manifest: {}",
                plugin.name,
                exc,
            )

        config_schema = manifest_data.get("config_schema")
        if config_schema:
            self._validate_config_against_schema(config, config_schema)
            config = encrypt_plugin_config(config, config_schema)

        plugin.config = config
        await self.db.flush()
        return plugin

    async def update_capabilities(
        self, plugin_id: int, capabilities: list[str]
    ) -> Plugin:
        """更新插件授权能力列表 / Update plugin granted capabilities."""
        plugin = await self.repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(message="plugin.error.not_found")

        plugin.granted_capabilities = capabilities
        await self.db.flush()
        return plugin

    # ── 企业分配 ── / ── Tenant assignment ──

    async def assign_tenants(
        self, plugin_id: int, tenant_ids: list[int]
    ) -> int:
        """
        批量分配企业 / Assign tenants to plugin in batch.

        Returns:
            实际新增的分配数量 / Number of newly created assignments.
        """
        from sqlalchemy import select

        from app.models.system.resource_tenant_assignment import (
            ResourceTenantAssignment,
        )

        plugin = await self.repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(message="plugin.error.not_found")

        # 查询已有分配（仅非软删除记录；已删除的分配不阻止重新分配） / Query existing assignments (non-deleted only; deleted rows do not block re-assign)
        result = await self.db.execute(
            select(ResourceTenantAssignment.tenant_id).where(
                ResourceTenantAssignment.resource_type == "plugin",
                ResourceTenantAssignment.resource_id == plugin_id,
                ResourceTenantAssignment.is_deleted.is_(False),
            )
        )
        existing = set(result.scalars())

        count = 0
        for tid in tenant_ids:
            if tid not in existing:
                self.db.add(ResourceTenantAssignment(
                    resource_type="plugin",
                    resource_id=plugin_id,
                    tenant_id=tid,
                    is_active=True,
                    config={},
                ))
                count += 1

        if count:
            await self.db.flush()
        return count

    async def unassign_tenant(self, plugin_id: int, tenant_id: int) -> None:
        """取消企业分配 / Unassign tenant from plugin."""
        from sqlalchemy import delete

        from app.models.system.resource_tenant_assignment import (
            ResourceTenantAssignment,
        )

        await self.db.execute(
            delete(ResourceTenantAssignment).where(
                ResourceTenantAssignment.resource_type == "plugin",
                ResourceTenantAssignment.resource_id == plugin_id,
                ResourceTenantAssignment.tenant_id == tenant_id,
            )
        )
        await self.db.flush()

    async def toggle_tenant_assignment(
        self, plugin_id: int, tenant_id: int, is_active: bool
    ) -> None:
        """切换企业分配启用状态 / Toggle tenant assignment active state."""
        from sqlalchemy import update

        from app.models.system.resource_tenant_assignment import (
            ResourceTenantAssignment,
        )

        await self.db.execute(
            update(ResourceTenantAssignment).where(
                ResourceTenantAssignment.resource_type == "plugin",
                ResourceTenantAssignment.resource_id == plugin_id,
                ResourceTenantAssignment.tenant_id == tenant_id,
            ).values(is_active=is_active)
        )
        await self.db.flush()

    # ── License ──

    async def activate_license(
        self, plugin_id: int, license_key: str
    ) -> None:
        """激活插件 License / Activate plugin license."""
        from app.plugins.license import activate_license as activate_plugin_license

        result = await activate_plugin_license(plugin_id, license_key, self.db)
        if not result.get("success"):
            raise BusinessException(
                message=result.get("message") or "plugin.error.license_invalid",
            )

    # ── 查询辅助 ── / ── Query helpers ──

    async def get_readme(
        self, plugin_id: int, locale: str = "zh-CN"
    ) -> str | None:
        """获取插件 README / Get plugin README content."""
        plugin = await self.repo.get_by_id(plugin_id)
        if not plugin:
            raise NotFoundException(message="plugin.error.not_found")
        return self._loader.load_readme(plugin.name, locale)

    async def get_by_name(self, name: str) -> Plugin | None:
        """根据名称查询插件 / Get plugin by name."""
        return await self.repo.get_by_name(name)

    async def list_enabled(self) -> list[Plugin]:
        """查询所有已启用的插件 / List all enabled plugins."""
        return await self.repo.list_enabled()

    async def get_tenant_visible_plugin_names(self, tenant_id: int) -> set[str]:
        """
        获取当前企业可见的已启用插件名称集合。 / Get set of enabled plugin names visible to tenant.
        过滤规则（ResourceScopeEnum）：all_tenants/global_shared 全可见；selected_tenants/admin_and_selected_tenants 仅已分配。
        Filter: all_tenants/global_shared for all tenants; selected_* only if assigned in RTA.
        """
        from sqlalchemy import select

        from app.enums.plugin import PluginStatusEnum
        from app.plugins.runtime_gate import evaluate_plugin_runtime_gate

        # 仅先取已启用插件，再逐个走统一 runtime gate（scope + tenant assignment + license）
        # / First fetch enabled plugins, then apply the unified runtime gate per plugin.
        plugin_result = await self.db.execute(
            select(Plugin.name).where(
                Plugin.status == PluginStatusEnum.ENABLED.value,
                Plugin.is_deleted.is_(False),
            )
        )
        plugin_names = [row[0] for row in plugin_result.all()]

        visible: set[str] = set()
        for plugin_name in plugin_names:
            gate = await evaluate_plugin_runtime_gate(
                self.db,
                plugin_name,
                tenant_id=tenant_id,
                require_enabled=True,
                enforce_scope=True,
            )
            if gate.allowed:
                visible.add(plugin_name)
        return visible

    # ── 依赖状态（用于前端卡片展示） ── / ── Dependency status (for frontend cards) ──

    async def get_dependency_status(self, plugin: Plugin) -> dict:
        """
        计算插件依赖状态 / Compute plugin dependency status.

        Returns the real runtime dependency model:
        - python: shared host environment requirements
        - plugins: normalized plugin-to-plugin dependencies
        / 返回真实运行时依赖模型：
        - python：共享宿主环境 requirement
        - plugins：规范化后的插件间依赖
        """
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel
        manifest = plugin.manifest or {}
        dependencies = manifest.get("dependencies", {}) if isinstance(manifest, dict) else {}
        raw_python_deps = dependencies.get("python", []) if isinstance(dependencies, dict) else []
        python_states = build_python_dependency_states(
            raw_python_deps if isinstance(raw_python_deps, list) else []
        )
        missing_python = [
            str(item["requirement"])
            for item in python_states
            if not item["satisfied"]
        ]

        plugin_requirements = normalize_plugin_dependencies(manifest)
        plugin_rows: dict[str, dict[str, str]] = {}
        if plugin_requirements:
            dependency_names = sorted({item.plugin for item in plugin_requirements})
            result = await self.db.execute(
                select(PluginModel.name, PluginModel.version, PluginModel.status).where(
                    PluginModel.name.in_(dependency_names),
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

        plugin_states = [
            state.to_dict()
            for state in build_plugin_dependency_states(
                plugin_requirements,
                plugin_rows,
                require_enabled=True,
            )
        ]
        missing_plugins = [
            str(item["message"])
            for item in plugin_states
            if item["state"] != "ready"
        ]

        overall_ready = len(missing_python) == 0 and len(missing_plugins) == 0

        return {
            "overall": "installed" if overall_ready else "missing",
            "python": {
                "declared": len(python_states),
                "installed": len(python_states) - len(missing_python),
                "missing": missing_python,
                "details": python_states,
                "state": "installed" if len(missing_python) == 0 else "missing",
            },
            "plugins": {
                "declared": len(plugin_states),
                "installed": len(plugin_states) - len(missing_plugins),
                "missing": missing_plugins,
                "details": plugin_states,
                "state": "installed" if len(missing_plugins) == 0 else "missing",
            },
        }
