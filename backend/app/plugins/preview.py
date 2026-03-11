"""
Plugin installation preview.
/ 插件安装预览

Parse manifest → collect extension declarations → check dependencies → detect conflicts → return preview info.
/ 解析 manifest → 收集扩展点声明 → 检查依赖 → 检测冲突 → 返回预览信息。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
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


# Capability description mapping / 能力说明映射
_CAPABILITY_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "db:read": {"zh-CN": "读取数据库", "en": "Read database"},
    "db:write": {"zh-CN": "写入数据库", "en": "Write to database"},
    "db:own_tables": {"zh-CN": "操作自有数据表", "en": "Operate own tables"},
    "http:outbound": {"zh-CN": "发送外部 HTTP 请求", "en": "Send outbound HTTP requests"},
    "storage:read": {"zh-CN": "读取存储文件", "en": "Read storage files"},
    "storage:write": {"zh-CN": "写入存储文件", "en": "Write storage files"},
    "ai:call": {"zh-CN": "调用 AI 功能", "en": "Call AI features"},
    "config:write": {"zh-CN": "修改插件配置", "en": "Modify plugin config"},
    "notifications:send": {"zh-CN": "发送通知", "en": "Send notifications"},
}


def resolve_i18n(text: dict[str, str] | str, locale: str = "zh-CN") -> str:
    """Resolve multilingual text to a single-language string / 将多语言文本解析为单语言字符串"""
    if isinstance(text, str):
        return text
    return text.get(locale, text.get("zh-CN", text.get("en", next(iter(text.values()), ""))))


async def generate_preview(
    plugin_path: Path,
    loader: PluginLoader | None = None,
) -> InstallPreview:
    """
    Generate installation preview.
    / 生成安装预览。

    Args:
        plugin_path: Plugin directory path (already extracted) / 插件目录路径（已解压）
        loader: PluginLoader instance (optional) / PluginLoader 实例（可选）
    """
    loader = loader or PluginLoader()

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
        "display_name": resolve_i18n(manifest.display_name),
        "description": resolve_i18n(manifest.description) if manifest.description else "",
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
        "skills_details": [resolve_i18n(s.display_name) or s.name for s in ext.skills],
        "adapters": len(ext.adapters),
        "adapters_details": [resolve_i18n(a.display_name) or a.provider_code for a in ext.adapters],
        "storage_drivers": len(ext.storage_drivers),
        "storage_drivers_details": [resolve_i18n(s.display_name) or s.code for s in ext.storage_drivers],
        "hooks": len(ext.hooks),
        "hooks_details": [h.point for h in ext.hooks],
        "events": len(ext.events),
        "events_details": [e.event for e in ext.events],
        "webhooks": len(ext.webhooks),
        "webhooks_details": [f"{w.method} {w.path}" for w in ext.webhooks],
        "tasks": len(ext.tasks),
        "tasks_details": [t.name for t in ext.tasks],
        "notifications": len(ext.notifications),
        "notifications_details": [n.code for n in ext.notifications],
        "permissions": len(ext.permissions),
        "permissions_details": [p.code for p in ext.permissions],
        "api_routes": len(ext.api.admin_routes) + len(ext.api.tenant_routes) + len(ext.api.public_routes),
        "api_routes_details": [
            f"{r.method} /{r.path}" for r in
            [*ext.api.admin_routes, *ext.api.tenant_routes, *ext.api.public_routes]
        ],
        "frontend_menus": len(ext.frontend.menus),
        "frontend_menus_details": [m.title for m in ext.frontend.menus] if ext.frontend.menus else [],
    }

    # Dependencies / 依赖
    dependencies = {
        "python": manifest.dependencies.python,
        "plugins": manifest.dependencies.plugins,
        "system": manifest.dependencies.system,
    }

    # Conflict detection / 冲突检测
    from app.plugins.registry import ExtensionRegistry

    conflicts = ExtensionRegistry.get_instance().get_conflicts(manifest)

    # Capability declarations / 能力声明
    capabilities = []
    for cap in manifest.capabilities:
        desc = _CAPABILITY_DESCRIPTIONS.get(cap, {})
        capabilities.append({
            "code": cap,
            "description": resolve_i18n(desc) if desc else cap,
        })

    # Compatibility / 兼容性
    compatibility: dict[str, Any] = {}
    if manifest.compatibility:
        compatibility = {
            "platform_version": manifest.compatibility.platform_version,
            "conflicts_count": len(manifest.compatibility.conflicts),
            "requires_count": len(manifest.compatibility.requires),
        }

    # Security scan / 安全扫描
    from app.plugins.security_scan import scan_plugin_directory

    scan_result = scan_plugin_directory(plugin_path)

    # Warnings / 警告
    warnings: list[str] = []
    if conflicts:
        warnings.append(f"Detected {len(conflicts)} conflict(s) with existing extensions")
    if manifest.dependencies.python:
        # Actually check which packages are installed and which need pip install, avoiding false positives
        # / 实际检查哪些包已安装、哪些需要 pip install
        try:
            import importlib.metadata as _imeta

            from packaging.requirements import Requirement
            from packaging.version import Version

            to_install: list[str] = []
            for req_str in manifest.dependencies.python:
                try:
                    req_obj = Requirement(req_str.strip())
                    dist = _imeta.distribution(req_obj.name)
                    if req_obj.specifier and Version(dist.version) not in req_obj.specifier:
                        to_install.append(req_str)
                    # Already satisfied → not counted in to_install / 已满足
                except _imeta.PackageNotFoundError:
                    to_install.append(req_str)
                except Exception:
                    to_install.append(req_str)

            if to_install:
                warnings.append(f"Will install {len(to_install)} Python package(s)")
            else:
                warnings.append(
                    f"Python dependencies already satisfied ({len(manifest.dependencies.python)} package(s))"
                )
        except ImportError:
            # Degrade to static hint when packaging is not installed / packaging 未安装时降级为原静态提示
            warnings.append(f"Will install {len(manifest.dependencies.python)} Python package(s)")
    if manifest.pricing.type == "paid" and not manifest.pricing.price:
        warnings.append("Paid plugin but no price specified")
    if scan_result.has_warnings:
        warnings.append(f"Security scan found {len(scan_result.warnings)} warning(s)")
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
