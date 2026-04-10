"""Admin plugin controller contracts and helper seams."""

from __future__ import annotations

import importlib
from typing import Any

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field

from app.core.deps import DbSession
from app.core.i18n import _
from app.exceptions import ServiceUnavailableException


def _is_missing_module(exc: ModuleNotFoundError, module_path: str) -> bool:
    return bool(exc.name) and (
        exc.name == module_path or exc.name.startswith(f"{module_path}.")
    )


def resolve_plugin_audit_service(db: DbSession) -> Any:
    candidates = [
        ("app.services.system.plugin_audit_service", "PluginAuditService"),
        ("app.services.system.extension_audit_service", "PluginAuditService"),
    ]
    for module_path, class_name in candidates:
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError as exc:
            if _is_missing_module(exc, module_path):
                continue
            raise
        service_cls = getattr(module, class_name, None)
        if service_cls is not None:
            return service_cls(db)
    raise ServiceUnavailableException(
        message=_("plugin.error.audit_service_unavailable")
    )


class PluginConfigBody(PydanticBaseModel):
    config: dict = Field(default_factory=dict, max_length=65536)


class PluginInstallConfirmBody(PydanticBaseModel):
    config: dict = Field(default_factory=dict, max_length=65536)
    preview_token: str = Field(default="", max_length=4096)


class PluginCapabilitiesBody(PydanticBaseModel):
    capabilities: list[str] = Field(default_factory=list)


class PluginAssignTenantsBody(PydanticBaseModel):
    tenant_ids: list[int] = Field(default_factory=list, max_length=500)


class PluginActivateLicenseBody(PydanticBaseModel):
    license_key: str = Field(default="", max_length=500)


class PluginRollbackBody(PydanticBaseModel):
    target_version: str = Field(
        default="",
        pattern=r"^\d+\.\d+\.\d+(?:-[\w.]+)?(?:\+[\w.]+)?$",
    )


class MenuOverrideItem(PydanticBaseModel):
    """Single menu override contract."""

    name: str = Field(..., max_length=100, description="Menu name from plugin.yaml")
    parent: str = Field(
        ...,
        max_length=100,
        pattern=r"^[a-z0-9_-]+$",
        description="Admin parent menu code (e.g. system_mgmt)",
    )
    tenant_parent: str | None = Field(
        None,
        max_length=100,
        pattern=r"^[a-z0-9_-]+$",
        description="Tenant parent menu code (when menu scope is both)",
    )


class PluginMenuConfigBody(PydanticBaseModel):
    """Admin-configurable menu placement overrides."""

    menu_overrides: list[MenuOverrideItem] = Field(default_factory=list)


class PluginEnableBody(PydanticBaseModel):
    """Optional enable-body contract with menu configuration."""

    menu_overrides: list[MenuOverrideItem] = Field(default_factory=list)


class PluginDependencyActionBody(PydanticBaseModel):
    """Install/uninstall dependency switches."""

    model_config = ConfigDict(extra="forbid")

    python: bool = True


def build_menu_overrides_payload(
    menu_overrides: list[MenuOverrideItem],
) -> dict[str, dict[str, str]]:
    payload: dict[str, dict[str, str]] = {}
    for item in menu_overrides:
        if item.tenant_parent:
            payload[item.name] = {
                "parent": item.parent,
                "tenant_parent": item.tenant_parent,
            }
        else:
            payload[item.name] = {"parent": item.parent}
    return payload


__all__ = [
    "MenuOverrideItem",
    "PluginActivateLicenseBody",
    "PluginAssignTenantsBody",
    "PluginCapabilitiesBody",
    "PluginConfigBody",
    "PluginDependencyActionBody",
    "PluginEnableBody",
    "PluginInstallConfirmBody",
    "PluginMenuConfigBody",
    "PluginRollbackBody",
    "build_menu_overrides_payload",
    "resolve_plugin_audit_service",
]
