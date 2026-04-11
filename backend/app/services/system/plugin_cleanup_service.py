"""Plugin cleanup helpers used by admin controllers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import delete, or_, select, text, update

from app.core.base_model import utc_now
from app.core.i18n import _
from app.core.logging import get_logger
from app.exceptions import BusinessException, NotFoundException
from app.models.auth.permission import Permission
from app.models.common.notification_template import NotificationTemplate
from app.models.system.agent_assignment import SystemAgentAssignment
from app.models.system.plugin import Plugin as PluginModel
from app.models.system.plugin_license import PluginLicense
from app.models.system.plugin_version import PluginVersion
from app.models.system.resource_tenant_assignment import ResourceTenantAssignment
from app.plugins.loader import PLUGINS_DIR
from app.plugins.preview import resolve_i18n

if TYPE_CHECKING:
    from typing import Any

    from app.services.system.plugin_service import PluginService

logger = get_logger(__name__)


def _escape_like_pattern(value: str) -> str:
    """Escape SQL LIKE wildcards for plugin-owned prefix deletes."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class PluginCleanupService:
    """Perform targeted cleanup and maintenance helpers for admin plugin flows."""

    def __init__(self, db):
        self._db = db
        self._plugin_service: PluginService | None = None

    def _get_plugin_service(self) -> PluginService:
        if self._plugin_service is None:
            from app.services.system.plugin_service import PluginService

            self._plugin_service = PluginService(self._db)
        return self._plugin_service

    async def _get_plugin_or_raise(self, plugin_id: int) -> PluginModel:
        plugin = await self._get_plugin_service().get_by_id(plugin_id)
        if plugin is None:
            raise NotFoundException(
                message=_("plugin.error.not_found_by_id").format(plugin_id=plugin_id)
            )
        return plugin

    async def remove_relational_records(self, plugin_id: int) -> None:
        """Remove plugin-related relational rows (versions, assignments, licenses)."""
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

    async def remove_plugin_row(self, plugin_id: int) -> None:
        """Remove plugin primary row."""
        await self._db.execute(delete(PluginModel).where(PluginModel.id == plugin_id))

    async def purge_alembic_versions_by_plugin_name(self, plugin_name: str) -> None:
        """Purge plugin-owned alembic version rows by plugin name prefix."""
        raw_prefix = plugin_name.replace("-", "_") + "_"
        await self._db.execute(
            text(
                "DELETE FROM alembic_version "
                "WHERE version_num LIKE :prefix ESCAPE '\\'"
            ),
            {"prefix": f"{_escape_like_pattern(raw_prefix)}%"},
        )

    async def force_cleanup_orphan(self, plugin_id: int) -> None:
        plugin = await self._get_plugin_or_raise(plugin_id)

        plugin_dir = PLUGINS_DIR / plugin.name
        if plugin_dir.exists():
            raise BusinessException(
                message=_("plugin.error.force_cleanup_files_exist"),
            )

        await self.remove_relational_records(plugin_id)
        await self.remove_plugin_row(plugin_id)
        await self.purge_alembic_versions_by_plugin_name(plugin.name)

    async def save_plugin_icon(
        self,
        plugin_id: int,
        *,
        filename: str | None,
        content: bytes,
    ) -> str:
        """Persist canonical plugin icon file and update the plugin row."""
        from app.exceptions.base import ValidationException

        plugin = await self._get_plugin_or_raise(plugin_id)

        allowed_suffixes = {".png", ".svg", ".jpg", ".jpeg", ".webp"}
        suffix = Path(filename).suffix.lower() if filename else ".png"
        if suffix not in allowed_suffixes:
            raise ValidationException(message=_("plugin.error.invalid_icon_type"))

        icon_max_size = 2 * 1024 * 1024
        if len(content) > icon_max_size:
            raise ValidationException(
                message=_("plugin.error.icon_too_large").format(size=len(content)),
            )

        icon_filename = f"icon{suffix}"
        icon_path = PLUGINS_DIR / plugin.name / icon_filename
        with open(icon_path, "wb") as file:
            file.write(content)

        plugin.icon = icon_filename
        await self._db.flush()
        return icon_filename

    async def delete_backup(self, plugin_id: int, backup_name: str) -> None:
        """Delete a validated plugin backup directory."""
        import re as _re
        import shutil as _shutil

        from app.exceptions.base import ValidationException
        from app.plugins.backup import BACKUPS_DIR

        if not _re.match(r"^[a-zA-Z0-9._-]+$", backup_name) or ".." in backup_name:
            raise ValidationException(message=_("plugin.error.invalid_backup_name"))

        plugin = await self._get_plugin_or_raise(plugin_id)
        backup_path = BACKUPS_DIR / plugin.name / backup_name
        if not backup_path.is_dir():
            raise NotFoundException(message=_("plugin.error.backup_not_found"))

        _shutil.rmtree(backup_path)

        plugin_backup_dir = BACKUPS_DIR / plugin.name
        if plugin_backup_dir.is_dir() and not any(plugin_backup_dir.iterdir()):
            plugin_backup_dir.rmdir()

    async def deactivate_plugin_skill_records(self, plugin_name: str) -> None:
        """Disable plugin-created skill package and skills."""
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

        await self._db.execute(
            update(SkillPackage)
            .where(SkillPackage.id == package_id)
            .values(is_active=False)
        )
        await self._db.execute(
            update(Skill)
            .where(
                Skill.package_id == package_id,
                Skill.is_deleted.is_(False),
            )
            .values(is_active=False)
        )
        await self._db.flush()
        logger.info("Deactivated skill records for plugin {}", plugin_name)

    async def delete_plugin_skill_records(self, plugin_name: str) -> None:
        """Hard-delete plugin-created skill package and child skills."""
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

        await self._db.execute(delete(Skill).where(Skill.package_id == package_id))
        await self._db.execute(delete(SkillPackage).where(SkillPackage.id == package_id))
        await self._db.flush()
        logger.info("Deleted skill records for plugin {}", plugin_name)

    async def delete_plugin_permissions_from_db(self, plugin_name: str) -> None:
        """Hard-delete plugin permission rows on uninstall."""
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
                plugin_name,
                result.rowcount,
            )

    async def ensure_plugin_ai_features(
        self,
        plugin_name: str,
        features: list[Any],
    ) -> None:
        """Ensure global assignment records for plugin AI features."""
        created = 0
        for feature in features:
            feature_code = f"plugin.{plugin_name}.{feature.feature_code}"
            feature_name = feature.display_name.get(
                "zh-CN",
                feature.display_name.get("en", feature.feature_code),
            )
            feature_desc = feature.description.get("zh-CN", feature.description.get("en", ""))
            existing = await self._db.execute(
                select(SystemAgentAssignment.id).where(
                    SystemAgentAssignment.feature_code == feature_code,
                    SystemAgentAssignment.tenant_id.is_(None),
                    SystemAgentAssignment.is_deleted.is_(False),
                )
            )
            if existing.scalar_one_or_none():
                continue

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
            created += 1

        if created:
            await self._db.flush()
            logger.info(
                "Plugin {}: ensured {} AI feature assignment(s) in DB",
                plugin_name,
                created,
            )

    async def sync_plugin_notification_templates(
        self,
        plugin_name: str,
        notifications: list[Any],
    ) -> None:
        """Upsert plugin notification templates."""
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
            result = await self._db.execute(
                select(NotificationTemplate).where(
                    NotificationTemplate.code == full_code,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.is_deleted = False
                existing.deleted_at = None
                existing.channels = channels
                existing.category = category
                existing.title_template = title
                existing.updated_at = utc_now()
            else:
                self._db.add(
                    NotificationTemplate(
                        code=full_code,
                        category=category,
                        title_template=title,
                        channels=channels,
                        priority="normal",
                        is_system=True,
                    )
                )
            synced += 1

        if synced:
            await self._db.flush()
            logger.info(
                "Plugin {}: synced {} notification template(s) to DB",
                plugin_name,
                synced,
            )

    async def delete_plugin_notification_templates(self, plugin_name: str) -> None:
        """Delete plugin notification templates on uninstall."""
        escaped_name = plugin_name.replace("_", "\\_").replace("%", "\\%")
        result = await self._db.execute(
            delete(NotificationTemplate).where(
                NotificationTemplate.code.like(
                    f"plugin.{escaped_name}.%",
                    escape="\\",
                ),
            )
        )
        if result.rowcount:
            await self._db.flush()
            logger.info(
                "Plugin {}: deleted {} notification template(s) from DB",
                plugin_name,
                result.rowcount,
            )

    async def sync_plugin_task_definitions(
        self,
        plugin_name: str,
        tasks: list[Any],
    ) -> None:
        """Upsert plugin task definitions and refresh scheduler."""
        from app.enums.common import ResourceScopeEnum
        from app.enums.task import ScheduleTypeEnum
        from app.models.system.task_definition import TaskDefinition
        from app.plugins.scheduler_refresh import refresh_plugin_schedule_or_raise

        synced = 0
        for task_ext in tasks:
            task_code = f"plugin.{plugin_name}.{task_ext.name}"
            handler_path = task_code
            result = await self._db.execute(
                select(TaskDefinition)
                .where(
                    TaskDefinition.is_deleted.is_(False),
                    (
                        (TaskDefinition.code == task_code)
                        | (TaskDefinition.handler_path == handler_path)
                    ),
                )
                .order_by(TaskDefinition.id.asc())
            )
            matched = list(result.scalars().all())
            existing = next((item for item in matched if item.code == task_code), None)
            if existing is None and matched:
                existing = matched[0]

            duplicate_rows = [
                item for item in matched if existing is not None and item.id != existing.id
            ]
            schedule_type = task_ext.schedule_type or ScheduleTypeEnum.INTERVAL.value
            description_text = resolve_i18n(task_ext.description, "zh-CN")
            if existing:
                existing.is_deleted = False
                existing.deleted_at = None
                existing.is_enabled = True
                existing.name = task_code
                existing.handler_path = handler_path
                existing.definition_type = "plugin"
                existing.category = "plugin"
                existing.scope = ResourceScopeEnum.ADMIN_ONLY.value
                existing.code = task_code
                existing.default_schedule_type = schedule_type
                existing.default_cron_expression = task_ext.cron_expression
                existing.default_interval_seconds = task_ext.interval_seconds
                existing.default_queue = "scheduled"
                existing.is_system_builtin = True
                existing.is_editable = False
                existing.is_deletable = False
                if description_text:
                    existing.description = description_text
            else:
                self._db.add(
                    TaskDefinition(
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
                        description=description_text or "",
                    )
                )

            deleted_at = utc_now()
            for duplicate in duplicate_rows:
                duplicate.is_deleted = True
                duplicate.deleted_at = deleted_at
                duplicate.is_enabled = False
            synced += 1

        if synced:
            await self._db.flush()
            refresh_plugin_schedule_or_raise(plugin_name, action="enable")
            logger.info(
                "Plugin {}: synced {} task definition(s) to DB",
                plugin_name,
                synced,
            )

    async def deactivate_plugin_task_definitions(self, plugin_name: str) -> None:
        """Disable plugin task definitions."""
        from app.models.system.task_definition import TaskDefinition
        from app.plugins.scheduler_refresh import refresh_plugin_schedule_or_raise

        escaped_name = plugin_name.replace("_", "\\_").replace("%", "\\%")
        result = await self._db.execute(
            update(TaskDefinition)
            .where(
                TaskDefinition.code.like(
                    f"plugin.{escaped_name}.%",
                    escape="\\",
                ),
                TaskDefinition.is_deleted.is_(False),
            )
            .values(is_enabled=False)
        )
        if result.rowcount:
            await self._db.flush()
            refresh_plugin_schedule_or_raise(plugin_name, action="disable")
            logger.info(
                "Plugin {}: deactivated {} task definition(s)",
                plugin_name,
                result.rowcount,
            )

    async def delete_plugin_task_definitions(self, plugin_name: str) -> None:
        """Delete plugin task definitions on uninstall."""
        from app.models.system.task_definition import TaskDefinition
        from app.plugins.scheduler_refresh import refresh_plugin_schedule_or_raise

        escaped_name = plugin_name.replace("_", "\\_").replace("%", "\\%")
        result = await self._db.execute(
            delete(TaskDefinition).where(
                TaskDefinition.code.like(
                    f"plugin.{escaped_name}.%",
                    escape="\\",
                )
            )
        )
        if result.rowcount:
            await self._db.flush()
            refresh_plugin_schedule_or_raise(plugin_name, action="uninstall")
            logger.info(
                "Plugin {}: deleted {} task definition(s) from DB",
                plugin_name,
                result.rowcount,
            )

__all__ = ["PluginCleanupService", "_escape_like_pattern"]
