"""Plugin edition and tenant exposure policy helpers. / 插件版本与企业暴露策略辅助。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.core.scope import ScopeChecker
from app.enums.common import ResourceScopeEnum

CURRENT_PLUGIN_HOST_EDITION = "saas"
PLUGIN_EDITION_SAAS = "saas"
PLUGIN_EDITION_SINGLE_MANAGEMENT = "single_management"
TENANT_EXPOSURE_SCOPE_DEFAULT = "scope_default"
TENANT_EXPOSURE_ALL_TENANTS = "all_tenants"
TENANT_EXPOSURE_SELECTED_TENANTS = "selected_tenants"
TENANT_EXPOSURE_NONE = "none"

_VALID_EDITIONS = frozenset({PLUGIN_EDITION_SAAS, PLUGIN_EDITION_SINGLE_MANAGEMENT})
_EDITION_ALIASES = {
    "single": PLUGIN_EDITION_SINGLE_MANAGEMENT,
    "single_management": PLUGIN_EDITION_SINGLE_MANAGEMENT,
    "singlemanagement": PLUGIN_EDITION_SINGLE_MANAGEMENT,
    "single_mgmt": PLUGIN_EDITION_SINGLE_MANAGEMENT,
}
_VALID_SURFACES = frozenset({"admin", "tenant", "user", "platform", "global"})
_SURFACE_ALIASES = {
    "tenant_scoped": "tenant",
    "tenant_admin": "tenant",
    "platform_admin": "admin",
}
_TENANT_RUNTIME_SURFACES = frozenset({"tenant", "global"})
_TENANT_EXPOSURE_ALIASES = {
    "default": TENANT_EXPOSURE_SCOPE_DEFAULT,
    "scope": TENANT_EXPOSURE_SCOPE_DEFAULT,
    "all": TENANT_EXPOSURE_ALL_TENANTS,
    "global": TENANT_EXPOSURE_ALL_TENANTS,
    "selected": TENANT_EXPOSURE_SELECTED_TENANTS,
    "assigned": TENANT_EXPOSURE_SELECTED_TENANTS,
    "assignment_required": TENANT_EXPOSURE_SELECTED_TENANTS,
    "tenant_scoped": TENANT_EXPOSURE_SELECTED_TENANTS,
    "disabled": TENANT_EXPOSURE_NONE,
    "admin_only": TENANT_EXPOSURE_NONE,
}
_VALID_TENANT_EXPOSURE = frozenset(
    {
        TENANT_EXPOSURE_SCOPE_DEFAULT,
        TENANT_EXPOSURE_ALL_TENANTS,
        TENANT_EXPOSURE_SELECTED_TENANTS,
        TENANT_EXPOSURE_NONE,
    }
)
_TENANT_POSSIBLE_SCOPES = frozenset(ScopeChecker.get_tenant_possible_scopes())
_TENANT_ASSIGNMENT_REQUIRED_SCOPES = frozenset(
    ScopeChecker.get_assignment_required_scopes()
)


@dataclass(frozen=True)
class PluginExposureProfile:
    """中文: 插件在当前 SaaS 宿主中的版本和企业暴露投影。

    EN: Edition and tenant-exposure projection for the current SaaS host.
    """

    current_edition: str
    declared_editions: list[str]
    surfaces: list[str]
    is_saas_compatible: bool
    is_single_management_compatible: bool
    tenant_exposure: str
    tenant_assignment_required: bool
    tenant_runtime_scope: str | None
    tenant_runtime_denial_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_edition": self.current_edition,
            "editions": list(self.declared_editions),
            "declared_editions": list(self.declared_editions),
            "surfaces": list(self.surfaces),
            "is_saas_compatible": self.is_saas_compatible,
            "is_single_management_compatible": (self.is_single_management_compatible),
            "tenant_exposure": self.tenant_exposure,
            "tenant_assignment_required": self.tenant_assignment_required,
            "tenant_runtime_scope": self.tenant_runtime_scope,
            "tenant_runtime_denial_reason": self.tenant_runtime_denial_reason,
        }


def build_plugin_exposure_profile(
    manifest_or_data: object,
    *,
    scope: str | None = None,
) -> PluginExposureProfile:
    """中文: 从 manifest 派生兼容 profile，旧 manifest 默认保持 SaaS 行为。

    EN: Derive a compatibility profile from a manifest; legacy manifests keep
    the existing SaaS behavior by default.
    """
    manifest_data = _as_mapping(manifest_or_data)
    raw_scope = _normalize_scope(scope or _read_value(manifest_or_data, "scope"))
    compatibility = _read_compatibility(manifest_or_data, manifest_data)

    declared_editions = _normalize_list(
        compatibility.get("editions"),
        allowed=_VALID_EDITIONS,
        aliases=_EDITION_ALIASES,
        default=[PLUGIN_EDITION_SAAS],
    )
    surfaces = _normalize_list(
        compatibility.get("surfaces"),
        allowed=_VALID_SURFACES,
        aliases=_SURFACE_ALIASES,
        default=_derive_surfaces_from_scope(raw_scope),
    )
    tenant_exposure = _normalize_tenant_exposure(compatibility.get("tenant_exposure"))

    is_saas_compatible = PLUGIN_EDITION_SAAS in declared_editions
    is_single_management_compatible = (
        PLUGIN_EDITION_SINGLE_MANAGEMENT in declared_editions
    )
    tenant_runtime_scope, denial_reason = _resolve_tenant_runtime_scope(
        raw_scope,
        is_saas_compatible=is_saas_compatible,
        surfaces=surfaces,
        tenant_exposure=tenant_exposure,
    )
    tenant_assignment_required = (
        tenant_runtime_scope in _TENANT_ASSIGNMENT_REQUIRED_SCOPES
    )

    return PluginExposureProfile(
        current_edition=CURRENT_PLUGIN_HOST_EDITION,
        declared_editions=declared_editions,
        surfaces=surfaces,
        is_saas_compatible=is_saas_compatible,
        is_single_management_compatible=is_single_management_compatible,
        tenant_exposure=tenant_exposure,
        tenant_assignment_required=tenant_assignment_required,
        tenant_runtime_scope=tenant_runtime_scope,
        tenant_runtime_denial_reason=denial_reason,
    )


def _as_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, Mapping):
            return dumped
    return {}


def _read_value(source: object, field_name: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(field_name)
    return getattr(source, field_name, None)


def _read_compatibility(
    source: object,
    manifest_data: Mapping[str, Any],
) -> Mapping[str, Any]:
    compatibility = _read_value(source, "compatibility")
    if compatibility is None:
        compatibility = manifest_data.get("compatibility")
    if compatibility is None:
        return {}
    return _as_mapping(compatibility)


def _normalize_list(
    value: object,
    *,
    allowed: frozenset[str],
    aliases: dict[str, str],
    default: list[str],
) -> list[str]:
    if value is None:
        return list(default)
    if isinstance(value, str):
        raw_items: list[object] = [value]
    elif isinstance(value, list):
        raw_items = value
    else:
        return []
    if not raw_items:
        return list(default)

    normalized: list[str] = []
    for item in raw_items:
        text = str(item or "").strip().lower().replace("-", "_")
        if not text:
            continue
        text = aliases.get(text, text)
        if text not in allowed:
            continue
        if text not in normalized:
            normalized.append(text)
    return normalized


def _normalize_tenant_exposure(value: object) -> str:
    if value is None:
        return TENANT_EXPOSURE_SCOPE_DEFAULT
    text = str(value or "").strip().lower().replace("-", "_")
    if not text:
        return TENANT_EXPOSURE_SCOPE_DEFAULT
    text = _TENANT_EXPOSURE_ALIASES.get(text, text)
    if text not in _VALID_TENANT_EXPOSURE:
        return TENANT_EXPOSURE_NONE
    return text


def _normalize_scope(value: object) -> str:
    return str(value or "").strip()


def _derive_surfaces_from_scope(scope: str) -> list[str]:
    surfaces: list[str] = []
    if ScopeChecker.is_visible_to_admin(scope):
        surfaces.append("admin")
    if scope in _TENANT_POSSIBLE_SCOPES:
        surfaces.append("tenant")
    return surfaces


def _resolve_tenant_runtime_scope(
    scope: str,
    *,
    is_saas_compatible: bool,
    surfaces: list[str],
    tenant_exposure: str,
) -> tuple[str | None, str | None]:
    if scope not in _TENANT_POSSIBLE_SCOPES:
        return None, "scope_denied"
    if not is_saas_compatible:
        return None, "edition_denied"
    if not (_TENANT_RUNTIME_SURFACES & set(surfaces)):
        return None, "surface_denied"
    if tenant_exposure == TENANT_EXPOSURE_NONE:
        return None, "tenant_exposure_denied"
    if tenant_exposure == TENANT_EXPOSURE_SELECTED_TENANTS:
        return ResourceScopeEnum.SELECTED_TENANTS.value, None
    return scope, None


__all__ = [
    "CURRENT_PLUGIN_HOST_EDITION",
    "PLUGIN_EDITION_SAAS",
    "PLUGIN_EDITION_SINGLE_MANAGEMENT",
    "PluginExposureProfile",
    "TENANT_EXPOSURE_ALL_TENANTS",
    "TENANT_EXPOSURE_NONE",
    "TENANT_EXPOSURE_SCOPE_DEFAULT",
    "TENANT_EXPOSURE_SELECTED_TENANTS",
    "build_plugin_exposure_profile",
]
