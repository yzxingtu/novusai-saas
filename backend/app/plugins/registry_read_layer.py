"""Read-model and conflict helpers for ExtensionRegistry."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.plugins.registry import ExtensionRegistry


class RegistryReadLayer:
    """Split read/composition concerns from ExtensionRegistry core mutators."""

    def __init__(
        self,
        registry: ExtensionRegistry,
        *,
        select_i18n_value: Callable[[dict[str, Any], str], str | None],
    ) -> None:
        self._registry = registry
        self._select_i18n_value = select_i18n_value

    def resolve_plugin_menu_title(self, i18n_key: str) -> str | None:
        from app.core.i18n import get_locale

        locale = get_locale()
        for titles_map in self._registry._plugin_menu_titles.values():
            if i18n_key in titles_map:
                locale_titles = titles_map[i18n_key]
                return self._select_i18n_value(locale_titles, locale)
        return None

    def resolve_plugin_permission_title(self, i18n_key: str) -> str | None:
        from app.core.i18n import _, get_locale

        locale = get_locale()
        if ".permission." not in i18n_key:
            return None

        parts = i18n_key.split(".")
        if len(parts) < 4 or parts[1] != "permission":
            return None

        base_key = ".".join(parts[:-1])
        action = parts[-1]

        for titles_map in self._registry._plugin_permission_titles.values():
            if base_key not in titles_map:
                continue
            base_title = self._select_i18n_value(titles_map[base_key], locale)
            if not base_title:
                return None
            action_key = f"rbac.action.{action}"
            action_title = _(action_key)
            if action_title == action_key:
                action_title = (
                    action.replace("_", " ").replace("-", " ").strip().title()
                )
            return f"{base_title} - {action_title}"
        return None

    def get_plugin_tenant_menu_policy(self, plugin_name: str) -> dict[str, Any]:
        default_policy: dict[str, Any] = {
            "plugin_name": plugin_name,
            "grant_mode": "auto_all_active_plans",
            "source": "default",
            "extension_name": "",
        }
        extensions = self._registry.get_custom_extensions(
            ext_type="tenant_menu_policy",
            plugin_name=plugin_name,
        )
        if not extensions:
            return default_policy

        for ext in extensions:
            data = ext.get("data") if isinstance(ext.get("data"), dict) else {}
            raw_mode = str(data.get("grant_mode") or "").strip().lower()
            if raw_mode in {"auto_all_active_plans", "manual_entitlement"}:
                return {
                    "plugin_name": plugin_name,
                    "grant_mode": raw_mode,
                    "source": "custom_extension",
                    "extension_name": str(ext.get("name") or ""),
                }
        return default_policy

    def get_frontend_slots_grouped(
        self,
        scope: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        from app.enums.plugin import FrontendSlotTypeEnum

        type_to_key: dict[str, str] = {
            FrontendSlotTypeEnum.HEADER_WIDGET.value: "header_widgets",
            FrontendSlotTypeEnum.DASHBOARD_WIDGET.value: "dashboard_widgets",
            FrontendSlotTypeEnum.SETTINGS_TAB.value: "settings_tabs",
            FrontendSlotTypeEnum.FLOATING_PANEL.value: "floating_panels",
            FrontendSlotTypeEnum.STANDALONE_PAGE.value: "pages",
            FrontendSlotTypeEnum.NOTIFICATION_UI.value: "notification_ui",
        }

        result: dict[str, list[dict[str, Any]]] = {key: [] for key in type_to_key.values()}

        for slot in self._registry.get_frontend_slots(scope=scope):
            key = type_to_key.get(slot.get("slot_type", ""))
            if key:
                result[key].append(slot)

        for slots in result.values():
            slots.sort(key=lambda x: x.get("sort_order", 100))
        return result

    def get_conflicts(self, manifest: Any) -> list[dict[str, str]]:
        conflicts: list[dict[str, str]] = []
        extensions = getattr(manifest, "extensions", None)
        if not extensions:
            return conflicts

        for adapter in getattr(extensions, "adapters", []):
            from app.ai.adapters import AdapterRegistry

            if AdapterRegistry.get_adapter(adapter.provider_code):
                owner = self.find_owner("adapter", adapter.provider_code)
                conflicts.append(
                    {
                        "type": "adapter",
                        "key": adapter.provider_code,
                        "owner": owner or "system",
                    }
                )

        plugin_name = getattr(manifest, "name", "")
        if plugin_name and plugin_name in self._registry._plugin_skill_resolvers:
            owner = self.find_owner("skill", plugin_name)
            if owner and owner != plugin_name:
                conflicts.append(
                    {
                        "type": "skill",
                        "key": plugin_name,
                        "owner": owner,
                    }
                )

        for driver in getattr(extensions, "storage_drivers", []):
            from app.storage.manager import storage_manager

            if storage_manager.has_driver(driver.code):
                owner = self.find_owner("storage", driver.code)
                conflicts.append(
                    {
                        "type": "storage",
                        "key": driver.code,
                        "owner": owner or "system",
                    }
                )

        return conflicts

    def find_owner(self, ext_type: str, key: str) -> str | None:
        for plugin_name, extensions in self._registry._registry.items():
            for ext in extensions:
                if ext.ext_type == ext_type and ext.key == key:
                    return plugin_name
        return None
