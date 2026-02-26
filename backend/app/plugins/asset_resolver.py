"""插件前端静态资源路径解析器。"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

_PLUGIN_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")

# 允许从插件根目录直接读取的图标文件扩展名
_ICON_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".svg", ".webp", ".ico"})


def resolve_plugin_asset_file(
    plugins_root: Path,
    plugin_name: str,
    file_path: str,
) -> Path | None:
    """
    解析并校验插件静态资源文件路径。

    安全约束：
    - 插件名必须是合法 kebab-case
    - 图标文件（png/jpg/jpeg/svg/webp/ico）允许从插件根目录读取
    - 其他文件仅允许读取 plugins/{name}/frontend/dist 下
    - 拒绝绝对路径、空路径、目录路径、路径穿越
    """
    if not _PLUGIN_NAME_PATTERN.match(plugin_name or ""):
        return None

    normalized = PurePosixPath(file_path.replace("\\", "/").lstrip("/"))
    if str(normalized) in {"", "."} or ".." in normalized.parts:
        return None

    # 插件根目录下的顶层图标文件（如 icon.png）
    if len(normalized.parts) == 1 and normalized.suffix.lower() in _ICON_EXTENSIONS:
        plugin_root = (plugins_root / plugin_name).resolve()
        icon_file = (plugin_root / normalized).resolve()
        if plugin_root in icon_file.parents or plugin_root == icon_file.parent:
            if icon_file.is_file():
                return icon_file

    # frontend/dist 下的常规资源文件
    dist_root = (plugins_root / plugin_name / "frontend" / "dist").resolve()
    asset_file = (dist_root / normalized).resolve()

    if dist_root not in asset_file.parents:
        return None
    if not asset_file.is_file():
        return None

    return asset_file
