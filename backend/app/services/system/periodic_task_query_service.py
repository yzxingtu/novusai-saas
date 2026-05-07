"""Periodic-task read models used by admin controllers."""

from __future__ import annotations

from sqlalchemy import select

from app.enums.common import ResourceScopeEnum
from app.enums.plugin import PluginStatusEnum
from app.models.system.plugin import Plugin
from app.plugins.loader import PluginLoader
from app.plugins.preview import resolve_i18n
from app.schemas.system import PeriodicTaskResponse


class PeriodicTaskPluginStateService:
    """Resolve plugin enabled state for periodic-task rows."""

    def __init__(self, db):
        self._db = db

    async def resolve_enabled_map(
        self,
        *,
        plugin_names: list[str],
    ) -> dict[str, bool]:
        if not plugin_names:
            return {}

        result = await self._db.execute(
            select(Plugin.name, Plugin.status).where(
                Plugin.name.in_(plugin_names),
                Plugin.is_deleted.is_(False),
            )
        )
        return {
            name: status == PluginStatusEnum.ENABLED.value
            for name, status in result.all()
        }


class PeriodicTaskPresentationService:
    """Serialize periodic-task rows and keep controller-level view logic thin."""

    @staticmethod
    def extract_plugin_name(definition) -> str | None:
        for raw in (
            getattr(definition, "code", None),
            getattr(definition, "handler_path", None),
            getattr(definition, "name", None),
        ):
            value = str(raw or "").strip()
            if not value.startswith("plugin."):
                continue
            parts = value.split(".")
            if len(parts) >= 3:
                return parts[1]
        return None

    def collect_plugin_names(self, definitions: list) -> list[str]:
        return sorted(
            {
                plugin_name
                for item in definitions
                if (plugin_name := self.extract_plugin_name(item))
            }
        )

    @staticmethod
    def resolve_plugin_task_i18n(
        definition,
        manifest_cache: dict[str, object] | None = None,
    ) -> tuple[str | None, str]:
        task_code = str(
            getattr(definition, "code", "") or getattr(definition, "name", "")
        )
        handler_path = str(getattr(definition, "handler_path", "") or "")
        is_plugin_like = (
            getattr(definition, "definition_type", None) == "plugin"
            or task_code.startswith("plugin.")
            or handler_path.startswith("plugin.")
        )
        if not is_plugin_like:
            return definition.description, definition.name

        if not task_code.startswith("plugin.") and handler_path.startswith("plugin."):
            task_code = handler_path
        parts = task_code.split(".")
        if len(parts) < 3 or parts[0] != "plugin":
            return definition.description, definition.name

        plugin_name = parts[1]
        task_name = ".".join(parts[2:])
        manifest_map = manifest_cache if manifest_cache is not None else {}
        manifest = manifest_map.get(plugin_name)

        if manifest is None:
            try:
                manifest = PluginLoader().load_manifest(plugin_name)
            except Exception:
                manifest = False
            manifest_map[plugin_name] = manifest

        if not manifest:
            return definition.description, definition.name

        locale = getattr(definition, "_locale", None)
        if not locale:
            from app.core.i18n import get_locale

            locale = get_locale()

        task_ext = next(
            (item for item in manifest.extensions.tasks if item.name == task_name),
            None,
        )
        if task_ext is None:
            return definition.description, definition.name

        display_name = resolve_i18n(task_ext.display_name, locale) or definition.name
        description = (
            resolve_i18n(task_ext.description, locale) or definition.description
        )
        return description, display_name

    @staticmethod
    def binding_semantics(
        scope: str | None, binding_count: int
    ) -> dict[str, bool | str]:
        selected_scopes = {
            ResourceScopeEnum.SELECTED_TENANTS.value,
            ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
        }
        if scope in selected_scopes:
            return {
                "binding_required": True,
                "binding_configured": binding_count > 0,
                "tenant_access_mode": "selected",
            }
        if scope in (
            ResourceScopeEnum.ALL_TENANTS.value,
            ResourceScopeEnum.GLOBAL_SHARED.value,
        ):
            return {
                "binding_required": False,
                "binding_configured": True,
                "tenant_access_mode": "all",
            }
        return {
            "binding_required": False,
            "binding_configured": True,
            "tenant_access_mode": "none",
        }

    @staticmethod
    def resolve_binding_target_scope(
        *,
        current_scope: str | None,
        requested_scope: str | None,
        tenant_ids: list[int],
    ) -> str:
        explicit_scopes = {
            ResourceScopeEnum.SELECTED_TENANTS.value,
            ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value,
        }
        if requested_scope:
            return requested_scope
        if current_scope in explicit_scopes:
            return str(current_scope)
        if tenant_ids:
            return ResourceScopeEnum.ADMIN_AND_SELECTED_TENANTS.value
        return current_scope or ResourceScopeEnum.ADMIN_ONLY.value

    def serialize_definition(
        self,
        definition,
        *,
        assigned_tenant_names: list[str] | None = None,
        assigned_tenant_ids: list[int] | None = None,
        binding_count: int = 0,
        binding_summary: str | None = None,
        manifest_cache: dict[str, object] | None = None,
        plugin_enabled_map: dict[str, bool] | None = None,
    ) -> dict:
        semantics = self.binding_semantics(definition.scope, binding_count)
        plugin_name = self.extract_plugin_name(definition)
        description, display_name = self.resolve_plugin_task_i18n(
            definition,
            manifest_cache=manifest_cache,
        )
        return PeriodicTaskResponse(
            id=definition.id,
            name=display_name,
            definition_type=definition.definition_type,
            task_path=definition.handler_path,
            schedule_type=definition.default_schedule_type,
            cron_expression=definition.default_cron_expression,
            interval_seconds=definition.default_interval_seconds,
            is_active=definition.is_enabled,
            last_run_at=definition.last_run_at,
            next_run_at=definition.next_run_at,
            description=description,
            plugin_name=plugin_name,
            plugin_enabled=(
                plugin_enabled_map.get(plugin_name, True)
                if plugin_name and plugin_enabled_map is not None
                else True
            ),
            scope=definition.scope,
            owner_tenant_id=definition.owner_tenant_id,
            assigned_tenant_ids=assigned_tenant_ids or [],
            assigned_tenant_names=assigned_tenant_names or [],
            binding_count=binding_count,
            binding_summary=binding_summary,
            binding_required=bool(semantics["binding_required"]),
            binding_configured=bool(semantics["binding_configured"]),
            tenant_access_mode=str(semantics["tenant_access_mode"]),
            is_locked=not definition.is_deletable,
            is_editable=definition.is_editable,
            max_retries=definition.max_retries,
            retry_delay=definition.retry_delay,
            timeout=definition.timeout,
            notify_on_failure=definition.notify_on_failure,
            notify_emails=definition.notify_emails,
            created_at=definition.created_at,
        ).model_dump()

    @staticmethod
    def patch_missing_next_run(
        definitions: list,
        *,
        compute_next_run,
    ) -> None:
        for definition in definitions:
            if definition.next_run_at is None and definition.is_enabled:
                next_run = compute_next_run(
                    definition.default_schedule_type,
                    definition.default_cron_expression,
                    definition.default_interval_seconds,
                )
                if next_run:
                    definition.next_run_at = next_run


__all__ = ["PeriodicTaskPluginStateService", "PeriodicTaskPresentationService"]
