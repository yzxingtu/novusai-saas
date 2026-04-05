"""
Plugin installation preview. / 插件安装预览。

Parse manifest → collect extension declarations → check dependencies → detect conflicts → return preview info.
/ 解析 manifest → 收集扩展点声明 → 检查依赖 → 检测冲突 → 返回预览信息。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.i18n import _, get_locale
from app.core.logging import get_logger
from app.plugins.dependencies import (
    build_plugin_dependency_states,
    build_python_dependency_states,
    detect_direct_python_dependency_conflicts,
    get_installed_distribution_version,
    iter_effective_python_requirements,
    normalize_plugin_dependencies,
    normalize_python_package_name,
)
from app.plugins.frontend_contract_checks import collect_frontend_i18n_warnings
from app.plugins.loader import PluginLoader

logger = get_logger(__name__)


class InstallPreview(BaseModel):
    """Installation preview information / 安装预览信息"""

    plugin_info: dict = Field(default_factory=dict)
    install_manifest: dict = Field(default_factory=dict)
    dependencies: dict = Field(default_factory=dict)
    conflicts: list[dict] = Field(default_factory=list)
    capabilities: list[dict] = Field(default_factory=list)
    compatibility: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    preview_token: str = ""


# Capability description mapping / 能力说明映射
_CAPABILITY_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "db:read": {"zh-CN": "读取数据库", "en": "Read database"},
    "db:write": {"zh-CN": "写入数据库", "en": "Write to database"},
    "db:own_tables": {"zh-CN": "操作自有数据表", "en": "Operate own tables"},
    "platform:read": {
        "zh-CN": "读取宿主平台快照",
        "en": "Read host platform snapshots",
    },
    "http:outbound": {
        "zh-CN": "发送外部 HTTP 请求",
        "en": "Send outbound HTTP requests",
    },
    "storage:read": {"zh-CN": "读取存储文件", "en": "Read storage files"},
    "storage:write": {"zh-CN": "写入存储文件", "en": "Write storage files"},
    "ai:call": {"zh-CN": "调用 AI 功能", "en": "Call AI features"},
    "config:write": {"zh-CN": "修改插件配置", "en": "Modify plugin config"},
    "notifications:send": {"zh-CN": "发送通知", "en": "Send notifications"},
}


def _canonical_locale(locale: str) -> str:
    normalized = (locale or "").strip().replace("_", "-")
    lowered = normalized.lower()
    if lowered.startswith("zh"):
        return "zh-CN"
    if lowered.startswith("en"):
        return "en"
    return normalized


def _iter_locale_candidates(locale: str | None) -> list[str]:
    candidates: list[str] = []

    def _push(value: str | None) -> None:
        if value and value not in candidates:
            candidates.append(value)

    locale_text = (locale or "").strip()
    if locale_text:
        normalized = locale_text.replace("_", "-")
        base = normalized.split("-", 1)[0]
        _push(locale_text)
        _push(normalized)
        _push(locale_text.replace("-", "_"))
        _push(base)
        if base == "zh":
            _push("zh-CN")
            _push("zh_CN")
            _push("zh")
        elif base == "en":
            _push("en")
            _push("en-US")
            _push("en_US")

    for fallback in ("zh-CN", "zh_CN", "zh", "en", "en-US", "en_US"):
        _push(fallback)

    return candidates


def resolve_i18n(text: dict[str, str] | str, locale: str | None = None) -> str:
    """Resolve multilingual text to a single-language string / 将多语言文本解析为单语言字符串"""
    if isinstance(text, str):
        return text
    if not isinstance(text, dict):
        return ""
    for candidate in _iter_locale_candidates(locale):
        value = text.get(candidate)
        if isinstance(value, str) and value:
            return value
    return next((value for value in text.values() if isinstance(value, str)), "")


def _localize_conflict_reason(conflict: dict[str, Any]) -> str:
    conflict_type = str(conflict.get("type") or "").strip().lower()
    key = str(conflict.get("key") or "").strip()
    owner = str(conflict.get("owner") or "system").strip() or "system"
    owner_label = (
        _("plugin.preview.conflict.system_owner") if owner == "system" else owner
    )
    template_key = {
        "adapter": "plugin.preview.conflict.adapter",
        "skill": "plugin.preview.conflict.skill",
        "storage": "plugin.preview.conflict.storage",
    }.get(conflict_type, "plugin.preview.conflict.generic")
    return _(
        template_key,
        conflict_key=key,
        owner=owner_label,
        type=conflict_type or _("plugin.preview.conflict.generic_type"),
    )


def _localize_conflicts(conflicts: list[dict[str, str]]) -> list[dict[str, str]]:
    localized_conflicts: list[dict[str, str]] = []
    for conflict in conflicts:
        localized_conflict = dict(conflict)
        localized_conflict["reason"] = _localize_conflict_reason(conflict)
        localized_conflicts.append(localized_conflict)
    return localized_conflicts


async def generate_preview(
    plugin_path: Path,
    loader: PluginLoader | None = None,
    db=None,
) -> InstallPreview:
    """
    Generate installation preview.
    / 生成安装预览。

    Args:
        plugin_path: Plugin directory path (already extracted) / 插件目录路径（已解压）
        loader: PluginLoader instance (optional) / PluginLoader 实例（可选）
    """
    loader = loader or PluginLoader()
    locale = get_locale()

    # Parse manifest
    # Read directly by path, supporting staging/temp directory preview without requiring plugin to be in PLUGINS_DIR
    # / 解析 manifest。直接按路径读取，支持 staging/temp 目录预览
    manifest = loader.load_manifest_from_path(plugin_path)

    # Basic info / 基本信息
    icon_value = manifest.icon
    # If it's an image file, convert to base64 data URL (plugin not yet installed during preview, cannot access via /plugin-assets/)
    # / 如果是图片文件，转为 base64 data URL
    if icon_value and not icon_value.startswith("http") and ":" not in icon_value:
        icon_file = (plugin_path / icon_value).resolve()
        # Prevent path traversal: ensure icon file is within plugin directory
        # / 防止路径遍历
        if icon_file.is_file() and plugin_path.resolve() in icon_file.parents:
            import base64
            import mimetypes

            mime = mimetypes.guess_type(str(icon_file))[0] or "image/png"
            icon_b64 = base64.b64encode(icon_file.read_bytes()).decode()
            icon_value = f"data:{mime};base64,{icon_b64}"

    plugin_info = {
        "name": manifest.name,
        "version": manifest.version,
        "display_name": resolve_i18n(manifest.display_name, locale),
        "description": resolve_i18n(manifest.description, locale)
        if manifest.description
        else "",
        "icon": icon_value,
        "scope": manifest.scope,
        "author": manifest.author,
        "tags": manifest.tags,
        "pricing_type": manifest.pricing.type,
    }

    # Extension points summary (count + details list) / 扩展点汇总（含数量 + 详情列表）
    ext = manifest.extensions
    install_manifest = {
        "skills": len(ext.skills),
        "skills_details": [
            resolve_i18n(s.display_name, locale) or s.name for s in ext.skills
        ],
        "adapters": len(ext.adapters),
        "adapters_details": [
            resolve_i18n(a.display_name, locale) or a.provider_code
            for a in ext.adapters
        ],
        "storage_drivers": len(ext.storage_drivers),
        "storage_drivers_details": [
            resolve_i18n(s.display_name, locale) or s.code for s in ext.storage_drivers
        ],
        "hooks": len(ext.hooks),
        "hooks_details": [h.point for h in ext.hooks],
        "events": len(ext.events),
        "events_details": [e.event for e in ext.events],
        "webhooks": len(ext.webhooks),
        "webhooks_details": [f"{w.method} {w.path}" for w in ext.webhooks],
        "tasks": len(ext.tasks),
        "tasks_details": [
            resolve_i18n(t.display_name, locale) or t.name for t in ext.tasks
        ],
        "notifications": len(ext.notifications),
        "notifications_details": [n.code for n in ext.notifications],
        "permissions": len(ext.permissions),
        "permissions_details": [p.code for p in ext.permissions],
        "api_routes": len(ext.api.admin_routes)
        + len(ext.api.tenant_routes)
        + len(ext.api.public_routes),
        "api_routes_details": [
            f"{r.method} /{r.path}"
            for r in [
                *ext.api.admin_routes,
                *ext.api.tenant_routes,
                *ext.api.public_routes,
            ]
        ],
        "frontend_pages": len(ext.frontend.pages),
        "frontend_pages_details": [
            resolve_i18n(p.title, locale) for p in ext.frontend.pages
        ]
        if ext.frontend.pages
        else [],
        "page_menus": len([p for p in ext.frontend.pages if p.menu is not None]),
        "page_menus_details": [
            resolve_i18n(p.menu.title or p.title, locale)
            for p in ext.frontend.pages
            if p.menu is not None
        ],
        "header_widgets": len(ext.frontend.header_widgets),
        "header_widgets_details": [w.name for w in ext.frontend.header_widgets],
        "floating_panels": len(ext.frontend.floating_panels),
        "floating_panels_details": [p.name for p in ext.frontend.floating_panels],
        "notification_ui": len(ext.frontend.notification_ui),
        "notification_ui_details": [n.event for n in ext.frontend.notification_ui],
        "dashboard_widgets": len(ext.frontend.dashboard_widgets),
        "dashboard_widgets_details": [
            resolve_i18n(w.title, locale) or w.name
            for w in ext.frontend.dashboard_widgets
        ],
        "settings_tabs": len(ext.frontend.settings_tabs),
        "settings_tabs_details": [
            resolve_i18n(t.title, locale) or t.name for t in ext.frontend.settings_tabs
        ],
    }

    # Dependencies / 依赖
    plugin_dependency_requirements = normalize_plugin_dependencies(manifest)
    plugin_dependency_states: list[dict[str, object]] = []
    if db is not None and plugin_dependency_requirements:
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel

        dependency_names = sorted(
            {item.plugin for item in plugin_dependency_requirements}
        )
        result = await db.execute(
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
        plugin_dependency_states = [
            state.to_dict()
            for state in build_plugin_dependency_states(
                plugin_dependency_requirements,
                plugin_rows,
                require_enabled=False,
            )
        ]
    else:
        plugin_dependency_states = [
            {
                "plugin": item.plugin,
                "version": item.version,
                "source": item.source,
                "installed": False,
                "enabled": False,
                "installed_version": None,
                "state": "unknown",
                "message": _(
                    "plugin.preview.dependency.plugin_db_context_missing",
                    plugin=item.plugin,
                    source=item.source,
                ),
            }
            for item in plugin_dependency_requirements
        ]

    python_dependency_states = build_python_dependency_states(
        manifest.dependencies.python
    )
    dependencies = {
        "python": python_dependency_states,
        "plugins": plugin_dependency_states,
    }

    # Conflict detection / 冲突检测
    from app.plugins.registry import ExtensionRegistry

    conflicts = _localize_conflicts(
        ExtensionRegistry.get_instance().get_conflicts(manifest)
    )

    # Capability declarations / 能力声明
    capabilities = []
    for cap in manifest.capabilities:
        desc = _CAPABILITY_DESCRIPTIONS.get(cap, {})
        capabilities.append(
            {
                "code": cap,
                "description": resolve_i18n(desc, locale) if desc else cap,
            }
        )

    # Compatibility / 兼容性
    compatibility: dict[str, Any] = {}
    if manifest.compatibility:
        compatibility = {
            "platform_version": manifest.compatibility.platform_version,
            "conflicts_count": len(manifest.compatibility.conflicts),
        }

    # Security scan / 安全扫描
    from app.plugins.security_scan import scan_plugin_directory

    scan_result = scan_plugin_directory(plugin_path)

    # Warnings / 警告
    warnings: list[str] = []
    warnings.extend(collect_frontend_i18n_warnings(manifest))
    if conflicts:
        warnings.append(
            _("plugin.preview.warning.conflicts_detected", count=len(conflicts))
        )
    if python_dependency_states:
        missing_python = [
            state["requirement"]
            for state in python_dependency_states
            if not state["satisfied"]
        ]
        if missing_python:
            warnings.append(
                _(
                    "plugin.preview.warning.python_dependencies_missing",
                    requirements=", ".join(str(item) for item in missing_python),
                )
            )
        else:
            warnings.append(
                _(
                    "plugin.preview.warning.python_dependencies_ready",
                    count=len(python_dependency_states),
                )
            )

    dependency_warnings = [
        str(state["message"])
        for state in plugin_dependency_states
        if state["state"] not in {"ready", "unknown"}
    ]
    if dependency_warnings:
        warnings.append(
            _(
                "plugin.preview.warning.plugin_dependency_issues",
                details="; ".join(dependency_warnings),
            )
        )

    if db is not None and manifest.dependencies.python:
        from sqlalchemy import select

        from app.models.system.plugin import Plugin as PluginModel

        host_requirements: list[str] = []
        pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"
        if pyproject_path.is_file():
            try:
                raw = pyproject_path.read_bytes()
                import sys as _sys

                if _sys.version_info >= (3, 11):
                    import tomllib

                    cfg = tomllib.loads(raw.decode(encoding="utf-8"))
                else:
                    import tomli

                    cfg = tomli.loads(raw.decode(encoding="utf-8"))
                project_cfg = cfg.get("project") or {}
                host_requirements.extend(
                    item
                    for item in project_cfg.get("dependencies") or []
                    if isinstance(item, str)
                )
                optional = project_cfg.get("optional-dependencies") or {}
                for deps in optional.values():
                    if isinstance(deps, list):
                        host_requirements.extend(
                            item for item in deps if isinstance(item, str)
                        )
            except Exception as exc:
                logger.warning("Preview: failed to parse host pyproject.toml: {}", exc)

        requirement_groups: dict[str, list[tuple[str, str]]] = {}
        for requirement_text in host_requirements:
            for requirement in iter_effective_python_requirements([requirement_text]):
                package = normalize_python_package_name(requirement.name)
                requirement_groups.setdefault(package, []).append(
                    ("host", str(requirement))
                )

        other_plugins_result = await db.execute(
            select(PluginModel.name, PluginModel.manifest).where(
                PluginModel.is_deleted.is_(False),
                PluginModel.name != manifest.name,
            )
        )
        for owner, manifest_data in other_plugins_result.all():
            if not manifest_data or not isinstance(manifest_data, dict):
                continue
            deps = manifest_data.get("dependencies") or {}
            raw_python = deps.get("python") if isinstance(deps, dict) else None
            if not isinstance(raw_python, list):
                continue
            for requirement in iter_effective_python_requirements(raw_python):
                package = normalize_python_package_name(requirement.name)
                requirement_groups.setdefault(package, []).append(
                    (f"plugin:{owner}", str(requirement))
                )

        for requirement in iter_effective_python_requirements(
            manifest.dependencies.python
        ):
            package = normalize_python_package_name(requirement.name)
            requirement_groups.setdefault(package, []).append(
                (f"plugin:{manifest.name}", str(requirement))
            )

        installed_versions = {
            package: get_installed_distribution_version(package)
            for package in requirement_groups
        }
        direct_conflicts = detect_direct_python_dependency_conflicts(
            requirement_groups,
            installed_versions=installed_versions,
        )
        if direct_conflicts:
            warnings.append(
                _(
                    "plugin.preview.warning.python_shared_env_conflicts",
                    details="; ".join(
                        f"{conflict.package}: {conflict.reason}"
                        for conflict in direct_conflicts
                    ),
                )
            )
    if manifest.pricing.type == "paid" and not manifest.pricing.price:
        warnings.append(_("plugin.preview.warning.paid_plugin_missing_price"))
    if scan_result.has_warnings:
        warnings.append(
            _(
                "plugin.preview.warning.security_scan_found",
                count=len(scan_result.warnings),
            )
        )
        warnings.extend(scan_result.warnings)

    return InstallPreview(
        plugin_info=plugin_info,
        install_manifest=install_manifest,
        dependencies=dependencies,
        conflicts=conflicts,
        capabilities=capabilities,
        compatibility=compatibility,
        warnings=warnings,
    )
