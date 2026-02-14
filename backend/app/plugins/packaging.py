"""
插件打包与导入/导出工具

定义 .nap (NovusAI Plugin) 包格式，提供打包、校验、导入、导出功能。

.nap 包结构（zip 格式）：
├── manifest.json      # 插件元数据（必须）
├── plugin.py          # 插件入口文件（必须）
├── README.md          # 说明文档（可选）
├── CHANGELOG.md       # 变更日志（可选）
├── requirements.txt   # Python 依赖（可选）
└── src/               # 额外源码目录（可选）
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from app.core.logging import LogManager

logger = LogManager.get_logger("app")

# manifest.json 必需字段
MANIFEST_REQUIRED_FIELDS = {"name", "display_name", "version", "entry_point"}

# 允许的顶层文件/目录
ALLOWED_TOP_ENTRIES = {
    "manifest.json",
    "plugin.py",
    "README.md",
    "CHANGELOG.md",
    "requirements.txt",
    "src",
    "__init__.py",
}

# 语义化版本正则
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

# 插件名称正则（小写字母、数字、连字符）
PLUGIN_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")

# .nap 文件扩展名
NAP_EXTENSION = ".nap"

# 允许上传的插件包扩展名
ALLOWED_PACKAGE_EXTENSIONS = {".nap", ".zip"}


class PackageError(Exception):
    """打包/校验错误"""


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    """
    校验 manifest.json 内容

    Args:
        manifest: manifest 字典

    Returns:
        错误列表（空列表表示通过）
    """
    errors: list[str] = []

    # 必需字段
    for field in MANIFEST_REQUIRED_FIELDS:
        if field not in manifest or not manifest[field]:
            errors.append(f"Missing required field: {field}")

    if errors:
        return errors

    # 名称格式
    name = manifest.get("name", "")
    if not PLUGIN_NAME_RE.match(name):
        errors.append(
            f"Invalid plugin name: '{name}'. "
            "Must be lowercase letters, digits, hyphens, "
            "start with letter, end with letter or digit."
        )

    # 版本号格式
    version = manifest.get("version", "")
    if not SEMVER_RE.match(version):
        errors.append(f"Invalid version: '{version}'. Must follow semver (e.g. 1.0.0).")

    # entry_point 格式
    entry_point = manifest.get("entry_point", "")
    if entry_point and "." not in entry_point:
        errors.append(
            f"Invalid entry_point: '{entry_point}'. "
            "Must be a dotted Python path (e.g. plugin.MyPlugin)."
        )

    # config_schema 如果存在必须是 dict
    config_schema = manifest.get("config_schema")
    if config_schema is not None and not isinstance(config_schema, dict):
        errors.append("config_schema must be a JSON object (dict).")

    # dependencies 如果存在必须是 dict
    dependencies = manifest.get("dependencies")
    if dependencies is not None and not isinstance(dependencies, dict):
        errors.append("dependencies must be a JSON object (dict).")

    # conflicts 如果存在必须是 list
    conflicts = manifest.get("conflicts")
    if conflicts is not None and not isinstance(conflicts, list):
        errors.append("conflicts must be a JSON array (list).")

    # provides 如果存在必须是 list
    provides = manifest.get("provides")
    if provides is not None and not isinstance(provides, list):
        errors.append("provides must be a JSON array (list).")

    # Skill 声明校验：如果 provides 包含 "skill"，则 skill_type 必须存在
    if isinstance(provides, list) and "skill" in provides:
        skill_type = manifest.get("skill_type")
        if not skill_type or not isinstance(skill_type, str):
            errors.append(
                "skill_type is required when provides contains 'skill'."
            )
        skill_config_schema = manifest.get("skill_config_schema")
        if skill_config_schema is not None and not isinstance(
            skill_config_schema, dict
        ):
            errors.append("skill_config_schema must be a JSON object (dict).")

    return errors


def _find_manifest_in_zip(zf: zipfile.ZipFile) -> str | None:
    """
    在 zip 中查找 manifest.json 路径。

    支持两种结构：
    1. manifest.json 在根目录
    2. manifest.json 在唯一的顶层子目录中（常见于 GitHub zip 下载）

    Returns:
        manifest.json 在 zip 中的路径，如 "manifest.json" 或 "my-plugin/manifest.json"。
        未找到返回 None。
    """
    names = zf.namelist()

    # 情况 1：根目录
    if "manifest.json" in names:
        return "manifest.json"

    # 情况 2：唯一子目录
    candidates = [n for n in names if n.endswith("/manifest.json") and n.count("/") == 1]
    if len(candidates) == 1:
        return candidates[0]

    return None


def _get_zip_prefix(manifest_zip_path: str) -> str:
    """
    从 manifest.json 的 zip 路径推导出前缀。

    "manifest.json"              -> ""
    "my-plugin/manifest.json"    -> "my-plugin/"
    """
    idx = manifest_zip_path.rfind("/")
    return manifest_zip_path[: idx + 1] if idx >= 0 else ""


def validate_package(nap_path: str | Path) -> list[str]:
    """
    校验插件包完整性（.nap 或 .zip）

    支持 manifest.json 在 zip 根目录或唯一子目录中。

    Args:
        nap_path: 插件包文件路径

    Returns:
        错误列表（空列表表示通过）
    """
    nap_path = Path(nap_path)
    errors: list[str] = []

    if not nap_path.exists():
        return [f"File not found: {nap_path}"]

    if nap_path.suffix not in ALLOWED_PACKAGE_EXTENSIONS:
        errors.append(
            f"File extension must be one of {ALLOWED_PACKAGE_EXTENSIONS}, "
            f"got '{nap_path.suffix}'"
        )

    # 尝试作为 zip 打开
    try:
        with zipfile.ZipFile(nap_path, "r") as zf:
            manifest_zip_path = _find_manifest_in_zip(zf)
            if not manifest_zip_path:
                errors.append(
                    "Missing manifest.json in package root "
                    "(also checked single subdirectory)"
                )
                return errors

            # 读取并校验 manifest
            manifest_data = zf.read(manifest_zip_path)
            try:
                manifest = json.loads(manifest_data)
            except json.JSONDecodeError as e:
                errors.append(f"Invalid manifest.json: {e}")
                return errors

            manifest_errors = validate_manifest(manifest)
            errors.extend(manifest_errors)

            # 检查是否有路径遍历攻击
            for name in zf.namelist():
                normalized = os.path.normpath(name)
                if (
                    normalized.startswith("..")
                    or normalized.startswith("/")
                    or normalized.startswith("\\")
                    or os.path.isabs(normalized)
                ):
                    errors.append(f"Suspicious path in archive: {name}")

    except zipfile.BadZipFile:
        errors.append("File is not a valid zip archive")

    return errors


def pack_plugin(
    source_dir: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """
    将插件目录打包为 .nap 文件

    Args:
        source_dir: 插件源码目录
        output_path: 输出文件路径（默认为 source_dir 同级目录下的 {name}-{version}.nap）

    Returns:
        生成的 .nap 文件路径

    Raises:
        PackageError: 校验失败
    """
    source_dir = Path(source_dir).resolve()

    if not source_dir.is_dir():
        raise PackageError(f"Source directory not found: {source_dir}")

    manifest_path = source_dir / "manifest.json"
    if not manifest_path.exists():
        raise PackageError(f"Missing manifest.json in {source_dir}")

    # 读取并校验 manifest
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    errors = validate_manifest(manifest)
    if errors:
        raise PackageError("Manifest validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    plugin_name = manifest["name"]
    plugin_version = manifest["version"]

    # 确定输出路径
    if output_path is None:
        output_path = source_dir.parent / f"{plugin_name}-{plugin_version}{NAP_EXTENSION}"
    else:
        output_path = Path(output_path)

    # 创建 .nap (zip) 文件
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            # 跳过 __pycache__ 和隐藏目录
            dirs[:] = [
                d for d in dirs
                if d != "__pycache__" and not d.startswith(".")
            ]
            for file_name in files:
                if file_name.startswith(".") or file_name.endswith(".pyc"):
                    continue
                file_path = Path(root) / file_name
                arcname = file_path.relative_to(source_dir).as_posix()
                zf.write(file_path, arcname)

    logger.info(
        "Plugin packed: %s -> %s",
        source_dir, output_path,
    )
    return output_path


def extract_package(
    nap_path: str | Path,
    target_dir: str | Path,
) -> dict[str, Any]:
    """
    解压插件包到目标目录

    支持 manifest.json 在 zip 根目录或唯一子目录中。
    如果 manifest.json 在子目录中，会自动去除前缀，将文件平铺到 target_dir。

    Args:
        nap_path: 插件包文件路径（.nap 或 .zip）
        target_dir: 解压目标目录

    Returns:
        manifest 字典

    Raises:
        PackageError: 校验失败或解压错误
    """
    nap_path = Path(nap_path)
    target_dir = Path(target_dir)

    # 校验包
    errors = validate_package(nap_path)
    if errors:
        raise PackageError(
            "Package validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    # 安全解压：逐文件检查路径，防止 zip slip 攻击
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(nap_path, "r") as zf:
        manifest_zip_path = _find_manifest_in_zip(zf)
        prefix = _get_zip_prefix(manifest_zip_path or "manifest.json")

        for member in zf.infolist():
            # 跳过不在当前前缀范围内的文件（多余的顶层目录条目）
            if prefix and not member.filename.startswith(prefix):
                continue

            # 去除前缀，得到相对于插件根目录的路径
            relative = member.filename[len(prefix):]
            if not relative:
                continue

            out_path = (target_dir / relative).resolve()
            if not str(out_path).startswith(str(target_dir.resolve())):
                raise PackageError(
                    f"Unsafe path in archive: {member.filename}"
                )

            if member.is_dir():
                out_path.mkdir(parents=True, exist_ok=True)
            else:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(out_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    # 读取 manifest
    manifest_path = target_dir / "manifest.json"
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    logger.info(
        "Plugin extracted: %s -> %s (%s v%s, prefix='%s')",
        nap_path, target_dir,
        manifest.get("name"), manifest.get("version"),
        prefix,
    )
    return manifest


def export_plugin(
    plugin_dir: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """
    导出已安装的插件为 .nap 文件

    与 pack_plugin 相同，但语义上用于导出已安装的插件。

    Args:
        plugin_dir: 已安装插件的目录
        output_path: 输出文件路径

    Returns:
        生成的 .nap 文件路径
    """
    return pack_plugin(plugin_dir, output_path)


def generate_manifest(
    name: str,
    display_name: str,
    version: str = "0.1.0",
    description: str = "",
    author: str = "",
    plugin_type: str = "composite",
    entry_point: str | None = None,
    skill_type: str | None = None,
    skill_display_name: str | None = None,
    skill_icon: str | None = None,
    skill_config_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    生成标准 manifest.json 内容

    Args:
        name: 插件唯一标识
        display_name: 显示名称
        version: 版本号
        description: 描述
        author: 作者
        plugin_type: 插件类型
        entry_point: 入口点（默认 plugin.{PascalCase}Plugin）
        skill_type: Skill 类型标识（仅 skill 类型插件）
        skill_display_name: Skill 显示名称
        skill_icon: Skill 图标
        skill_config_schema: Skill 配置 JSON Schema

    Returns:
        manifest 字典
    """
    if entry_point is None:
        # my-plugin -> MyPlugin
        class_name = "".join(
            part.capitalize() for part in name.replace("-", "_").split("_")
        ) + "Plugin"
        entry_point = f"plugin.{class_name}"

    manifest: dict[str, Any] = {
        "name": name,
        "display_name": display_name,
        "version": version,
        "description": description,
        "author": author,
        "plugin_type": plugin_type,
        "entry_point": entry_point,
        "icon": "lucide:plug",
        "homepage": "",
        "config_schema": None,
        "default_config": {},
        "required_permissions": [],
        "dependencies": {},
        "conflicts": [],
        "platform_version": None,
    }

    # Skill 声明
    if plugin_type == "skill" or skill_type:
        manifest["provides"] = ["skill"]
        manifest["skill_type"] = skill_type or name
        manifest["skill_display_name"] = skill_display_name or display_name
        manifest["skill_icon"] = skill_icon or "lucide:zap"
        manifest["skill_config_schema"] = skill_config_schema

    return manifest


def scaffold_plugin(
    output_dir: str | Path,
    name: str,
    plugin_type: str = "composite",
    display_name: str | None = None,
    author: str = "",
) -> Path:
    """
    生成插件脚手架目录

    Args:
        output_dir: 输出父目录
        name: 插件名称
        plugin_type: 插件类型 (adapter/tool/hook/api/skill/composite)
        display_name: 显示名称
        author: 作者

    Returns:
        生成的插件目录路径
    """
    output_dir = Path(output_dir)
    plugin_dir = output_dir / name
    plugin_dir.mkdir(parents=True, exist_ok=True)

    if display_name is None:
        display_name = name.replace("-", " ").title()

    # 确定基类和导入
    type_map = {
        "adapter": ("AdapterPlugin", "app.plugins.extensions.adapter_plugin"),
        "tool": ("ToolPlugin", "app.plugins.extensions.tool_plugin"),
        "hook": ("HookPlugin", "app.plugins.extensions.hook_plugin"),
        "api": ("ApiPlugin", "app.plugins.extensions.api_plugin"),
        "skill": ("SkillPlugin", "app.plugins.extensions.skill_plugin"),
        "composite": ("BasePlugin", "app.plugins.base"),
    }
    base_class, base_import = type_map.get(plugin_type, type_map["composite"])

    # 生成类名
    class_name = "".join(
        part.capitalize() for part in name.replace("-", "_").split("_")
    ) + "Plugin"

    # manifest.json
    manifest = generate_manifest(
        name=name,
        display_name=display_name,
        plugin_type=plugin_type,
        author=author,
        entry_point=f"plugin.{class_name}",
    )
    with open(plugin_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # plugin.py
    plugin_py = f'''"""
{display_name} Plugin
"""

from __future__ import annotations

from typing import Any

from {base_import} import {base_class}
from app.plugins.context import PluginContext


class {class_name}({base_class}):
    """
    {display_name}
    """

    @property
    def name(self) -> str:
        return "{name}"

    @property
    def display_name(self) -> str:
        return "{display_name}"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def description(self) -> str:
        return ""

    @property
    def author(self) -> str:
        return "{author}"

    async def on_enable(self, ctx: PluginContext) -> None:
        if ctx.logger:
            ctx.logger.info("{class_name} enabled")

    async def on_disable(self, ctx: PluginContext) -> None:
        if ctx.logger:
            ctx.logger.info("{class_name} disabled")
'''

    # Skill 类型追加必要的抽象方法实现
    if plugin_type == "skill":
        skill_extra = f'''
    # ========================================
    # SkillPlugin interface
    # ========================================

    def get_skill_type(self) -> str:
        return "{name}"

    def get_skill_config_schema(self) -> dict[str, Any]:
        return {{
            "type": "object",
            "properties": {{}},
        }}

    def resolve(
        self,
        skill_config: dict[str, Any],
    ) -> list:
        # TODO: Return ToolDefinition list based on skill_config
        return []

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: "PluginContext",
    ) -> dict[str, Any] | str:
        # TODO: Implement tool execution logic
        return {{"error": f"Not implemented: {{tool_name}}"}}
'''
        plugin_py += skill_extra
    with open(plugin_dir / "plugin.py", "w", encoding="utf-8") as f:
        f.write(plugin_py)

    # __init__.py
    with open(plugin_dir / "__init__.py", "w", encoding="utf-8") as f:
        f.write(f'"""{display_name} Plugin"""\n')

    # README.md
    readme = f"""# {display_name}

## Description

A NovusAI {plugin_type} plugin.

## Installation

```bash
novusai-plugin pack .
# Upload the generated .nap file via admin panel
```

## Configuration

No configuration required.
"""
    with open(plugin_dir / "README.md", "w", encoding="utf-8") as f:
        f.write(readme)

    # CHANGELOG.md
    changelog = f"""# Changelog

## 0.1.0

- Initial release
"""
    with open(plugin_dir / "CHANGELOG.md", "w", encoding="utf-8") as f:
        f.write(changelog)

    logger.info("Plugin scaffolded: %s at %s", name, plugin_dir)
    return plugin_dir


__all__ = [
    "NAP_EXTENSION",
    "PackageError",
    "export_plugin",
    "extract_package",
    "generate_manifest",
    "pack_plugin",
    "scaffold_plugin",
    "validate_manifest",
    "validate_package",
]
