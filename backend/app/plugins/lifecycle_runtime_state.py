"""Permission/runtime-state helpers extracted from PluginLifecycle."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.ai.skills.plugin_identity import make_plugin_skill_identity
from app.core.logging import get_logger
from app.enums.plugin import PluginStatusEnum
from app.enums.skill import SkillSourceTypeEnum
from app.plugins.exceptions import PluginDependencyError
from app.plugins.preview import resolve_i18n

if TYPE_CHECKING:
    from app.models.system.plugin import Plugin


logger = get_logger(__name__)


class LifecycleRuntimeStateMixin:
    """Permission/runtime-state helpers extracted from PluginLifecycle."""

    async def _set_plugin_permissions_enabled(
        self, plugin_name: str, is_enabled: bool
    ) -> None:
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

    async def _fail_close_plugin_runtime(
        self,
        plugin_name: str,
        *,
        registry=None,
    ) -> None:
        """Fail-close runtime by unregistering extensions and disabling plugin-facing surfaces."""
        if registry is None:
            from app.plugins.registry import ExtensionRegistry

            registry = ExtensionRegistry.get_instance()

        try:
            registry.unregister_all(plugin_name)
        except Exception as cleanup_exc:
            logger.warning(
                "Repair: failed to unregister runtime extensions for {}: {}",
                plugin_name,
                cleanup_exc,
            )

        try:
            await self._deactivate_plugin_skill_records(plugin_name)
        except Exception as skill_exc:
            logger.warning(
                "Repair: failed to deactivate skill records for {}: {}",
                plugin_name,
                skill_exc,
            )

        try:
            await self._set_plugin_permissions_enabled(plugin_name, False)
        except Exception as perm_exc:
            logger.warning(
                "Repair: failed to disable permissions for {}: {}",
                plugin_name,
                perm_exc,
            )

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
        await self.permissions.set_enabled(plugin_name, True)
        if auto_grant_plans:
            await self.permissions.auto_grant_plan_menus(plugin_name)

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
            plugin.description = (
                resolve_i18n(manifest.description)
                if manifest.description
                else plugin.description
            )
            plugin.icon = manifest.icon or plugin.icon
            plugin.icon_color = manifest.icon_color or plugin.icon_color
            plugin.tags = manifest.tags
            plugin.installed_packages = manifest.dependencies.python or []
            plugin.ai_requirements = (
                manifest.ai_requirements.model_dump()
                if manifest.ai_requirements
                else plugin.ai_requirements
            )
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

        await self.dependencies.assert_plugin_dependencies_ready(
            manifest,
            plugin_name=plugin_name,
            require_enabled=True,
            error_cls=error_cls,
            action=action,
        )

    async def _auto_grant_plugin_menus_to_plans(
        self,
        plugin_name: str,
        **_: Any,
    ) -> None:
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

        policy = ExtensionRegistry.get_instance().get_plugin_tenant_menu_policy(
            plugin_name
        )
        if policy.get("grant_mode") == "manual_entitlement":
            logger.info(
                "Plugin {}: skip auto-grant due to tenant menu policy manual_entitlement",
                plugin_name,
            )
            return

        perm_ids = (
            (
                await self._db.execute(
                    select(Permission.id).where(
                        (
                            Permission.code.like(tenant_prefix)
                            | Permission.code.like(plugin_prefix)
                        ),
                        Permission.scope.in_(["tenant", "both"]),
                        Permission.is_enabled.is_(True),
                        Permission.is_deleted.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
        if not perm_ids:
            return

        plan_ids = (
            (
                await self._db.execute(
                    select(TenantPlan.id).where(TenantPlan.is_active.is_(True))
                )
            )
            .scalars()
            .all()
        )
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
            plugin_name,
            len(perm_ids),
            len(plan_ids),
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

        perm_ids = (
            (
                await self._db.execute(
                    select(Permission.id).where(
                        (
                            Permission.code.like(tenant_prefix)
                            | Permission.code.like(plugin_prefix)
                        ),
                        Permission.scope.in_(["tenant", "both"]),
                        Permission.is_deleted.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
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
            plugin_name,
            len(perm_ids),
        )

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
                description=resolve_i18n(manifest.description)
                if manifest.description
                else None,
                source_plugin=plugin_name,
                is_system=True,
                is_active=active,
                tenant_id=None,
            )
            self._db.add(package)
            await self._db.flush()
            logger.info(
                "Created SkillPackage '{}' (id={}) for plugin {}",
                package.name,
                package.id,
                plugin_name,
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

        desired_source_refs: set[str] = set()
        touched_skill_ids: set[int] = set()

        # Create or update Skill record for each skill extension
        # / 对每个 skill extension 创建或更新 Skill 记录
        for skill_ext in skill_extensions:
            skill_key, source_ref = make_plugin_skill_identity(
                plugin_name,
                skill_ext.name,
            )
            desired_source_refs.add(source_ref)
            existing_skill = next(
                (
                    s
                    for s in existing_skills
                    if str(getattr(s, "source_ref", "") or "").strip() == source_ref
                    or str(getattr(s, "key", "") or "").strip() == skill_key
                ),
                None,
            )

            skill_display = (
                resolve_i18n(skill_ext.display_name)
                if skill_ext.display_name
                else skill_ext.name
            )
            skill_desc = (
                resolve_i18n(skill_ext.description) if skill_ext.description else None
            )

            if not existing_skill:
                skill = Skill(
                    package_id=package.id,
                    name=skill_display,
                    key=skill_key,
                    description=skill_desc,
                    type=skill_ext.type,
                    source_type=SkillSourceTypeEnum.PLUGIN.value,
                    source_ref=source_ref,
                    version=str(getattr(manifest, "version", "") or "1.0.0"),
                    config=skill_ext.config_schema or {},
                    is_system=True,
                    is_active=active,
                    tenant_id=None,
                )
                self._db.add(skill)
                logger.info(
                    "Created Skill '{}' (type={}) for plugin {}",
                    skill_display,
                    skill_ext.type,
                    plugin_name,
                )
            else:
                existing_skill.is_active = active
                existing_skill.name = skill_display
                existing_skill.description = skill_desc
                existing_skill.type = skill_ext.type
                existing_skill.key = skill_key
                existing_skill.source_type = SkillSourceTypeEnum.PLUGIN.value
                existing_skill.source_ref = source_ref
                existing_skill.version = str(
                    getattr(manifest, "version", "")
                    or getattr(existing_skill, "version", "")
                    or "1.0.0"
                )
                existing_skill.config = skill_ext.config_schema or {}
                touched_skill_ids.add(existing_skill.id)

        for existing_skill in existing_skills:
            if getattr(existing_skill, "id", None) in touched_skill_ids:
                continue
            existing_source_ref = str(
                getattr(existing_skill, "source_ref", "") or ""
            ).strip()
            if existing_source_ref not in desired_source_refs:
                existing_skill.is_active = False
                logger.info(
                    "Deactivated stale Skill '{}' for plugin {}",
                    existing_skill.name,
                    plugin_name,
                )

        await self._db.flush()

    async def _deactivate_plugin_skill_records(self, plugin_name: str) -> None:
        """On disable, mark plugin skill package + skills inactive."""
        await self.cleanup.deactivate_plugin_skill_records(plugin_name)

    async def _delete_plugin_skill_records(self, plugin_name: str) -> None:
        """On uninstall, hard-delete plugin skill package + skills."""
        await self.cleanup.delete_plugin_skill_records(plugin_name)

    # ================================================================
    # Module loading / 模块加载
    # ================================================================

    # ================================================================
    # Permission DB record cleanup (M50-T14) / 权限 DB 记录清理
    # ================================================================

    async def _delete_plugin_permissions_from_db(self, plugin_name: str) -> None:
        """Hard-delete plugin permissions after uninstall."""
        await self.cleanup.delete_plugin_permissions_from_db(plugin_name)

    # ================================================================
    # AI Features ensure (M50-T12) / AI 功能确保
    # ================================================================

    async def _ensure_plugin_ai_features(
        self,
        plugin_name: str,
        features: list,
    ) -> None:
        """Ensure plugin AI feature assignment records exist."""
        await self.cleanup.ensure_plugin_ai_features(plugin_name, features)

    # ================================================================
    # Notification template DB sync (M50-T1) / 通知模板 DB 同步
    # ================================================================

    async def _sync_plugin_notification_templates(
        self,
        plugin_name: str,
        notifications: list,
    ) -> None:
        """Upsert plugin notification templates."""
        await self.cleanup.sync_plugin_notification_templates(
            plugin_name,
            notifications,
        )

    async def _delete_plugin_notification_templates(self, plugin_name: str) -> None:
        """Delete plugin notification templates on uninstall."""
        await self.cleanup.delete_plugin_notification_templates(plugin_name)

    # ================================================================
    # Task definition DB sync (M50-T2) / 任务定义 DB 同步
    # ================================================================

    async def _sync_plugin_task_definitions(
        self,
        plugin_name: str,
        tasks: list,
    ) -> None:
        """Upsert plugin task definitions and refresh scheduler."""
        await self.cleanup.sync_plugin_task_definitions(plugin_name, tasks)

    async def _deactivate_plugin_task_definitions(self, plugin_name: str) -> None:
        """Deactivate plugin task definitions."""
        await self.cleanup.deactivate_plugin_task_definitions(plugin_name)

    async def _delete_plugin_task_definitions(self, plugin_name: str) -> None:
        """Delete plugin task definitions."""
        await self.cleanup.delete_plugin_task_definitions(plugin_name)

    def _load_handler(self, plugin_name: str, handler_path: str):
        """Load plugin handler function — delegate to unified loader / 加载插件处理函数 — 委托给统一加载器"""
        from app.plugins.module_loader import load_plugin_handler

        return load_plugin_handler(plugin_name, handler_path)

    def _load_plugin_executor(self, plugin_name: str, skill_type: str):
        """Load plugin executor class — delegate to unified loader / 加载插件 executor 类 — 委托给统一加载器"""
        from app.plugins.module_loader import load_plugin_executor

        return load_plugin_executor(plugin_name, skill_type)
