"""Resolve the absolute path of a plugin static asset, ensuring security. / 解析插件静态资源的绝对路径，确保安全。"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

_PLUGIN_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")

# Plugin metadata icon is fixed to root icon.png / 插件元数据图标固定为根目录 icon.png
_PLUGIN_METADATA_ICON_NAME = "icon.png"


def resolve_plugin_icon_file(
    plugins_root: Path,
    plugin_name: str,
    file_path: str,
) -> Path | None:
    """
    Resolve admin-visible plugin metadata icon file.
    / 解析管理态可见的插件元数据图标文件。

    Only top-level icon files are allowed from the plugin root.
    / 仅允许读取插件根目录下的顶层图标文件。
    """
    if not _PLUGIN_NAME_PATTERN.match(plugin_name or ""):
        return None

    normalized = PurePosixPath(file_path.replace("\\", "/").lstrip("/"))
    if (
        str(normalized) in {"", "."}
        or ".." in normalized.parts
        or len(normalized.parts) != 1
        or normalized.name.lower() != _PLUGIN_METADATA_ICON_NAME
    ):
        return None

    plugin_root = (plugins_root / plugin_name).resolve()
    icon_file = (plugin_root / normalized).resolve()
    if (
        plugin_root in icon_file.parents or plugin_root == icon_file.parent
    ) and icon_file.is_file():
        return icon_file
    return None


def resolve_plugin_asset_file(
    plugins_root: Path,
    plugin_name: str,
    file_path: str,
) -> Path | None:
    """
    Plugin frontend static asset path resolver / 插件前端静态资源路径解析器

    Security constraints / 安全约束：
    - Plugin name must be a valid kebab-case / 插件名必须是合法 kebab-case
    - Plugin metadata icon only allows root icon.png / 插件元数据图标只允许根目录 icon.png
    - Other files only allowed from plugins/{name}/frontend/dist / 其他文件仅允许从 frontend/dist 目录读取
    - Path traversal forbidden (../ or absolute paths) / 禁止路径穿越（../ 或绝对路径）
    - Empty paths, directory paths, and path traversal forbidden / 禁止空路径、目录路径、路径穿越
    """
    if not _PLUGIN_NAME_PATTERN.match(plugin_name or ""):
        return None

    normalized = PurePosixPath(file_path.replace("\\", "/").lstrip("/"))
    if str(normalized) in {"", "."} or ".." in normalized.parts:
        return None

    # Top-level icon files (e.g. icon.png) can be read from plugin root / 顶层图标文件（如 icon.png）可从插件根目录直接读取
    icon_file = resolve_plugin_icon_file(plugins_root, plugin_name, file_path)
    if icon_file is not None:
        return icon_file

    # Other files only allowed from frontend/dist directory / 其他文件仅允许从 frontend/dist 目录读取
    dist_root = (plugins_root / plugin_name / "frontend" / "dist").resolve()
    asset_file = (dist_root / normalized).resolve()

    if dist_root not in asset_file.parents:
        return None
    if not asset_file.is_file():
        return None

    return asset_file
