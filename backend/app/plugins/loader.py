"""
Plugin loader. / 插件加载器。

Responsible for plugin discovery, manifest parsing, main class dynamic import, README and i18n loading.
/ 负责插件发现、清单解析、主类动态导入、README 和 i18n 加载。
"""

from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path

import yaml

from app.core.logging import get_logger
from app.core.response import resolve_public_error_message
from app.plugins.base import PluginBase
from app.plugins.exceptions import (
    PluginError,
    PluginManifestError,
    PluginNotFoundError,
)
from app.plugins.manifest import PluginManifest

logger = get_logger(__name__)

# Root directory for installed plugins / 已安装插件的存放根目录
PLUGINS_DIR = Path(__file__).parent.parent.parent / "plugins"


class PluginLoader:
    """Plugin discovery and loading / 插件发现与加载"""

    def __init__(self, plugins_dir: Path | None = None) -> None:
        self.plugins_dir = plugins_dir or PLUGINS_DIR

    # ── 1. Discovery / 发现 ──

    def discover_plugins(self) -> list[str]:
        """
        Scan plugins directory, return all subdirectory names containing plugin.yaml.
        / 扫描插件目录，返回所有包含 plugin.yaml 的子目录名。

        Skips hidden directories and __pycache__.
        / 跳过隐藏目录和 __pycache__。
        """
        if not self.plugins_dir.exists():
            return []

        names: list[str] = []
        for child in sorted(self.plugins_dir.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith(".") or child.name == "__pycache__":
                continue
            if (child / "plugin.yaml").is_file():
                names.append(child.name)
        return names

    # ── 2. Manifest parsing / 清单解析 ──

    def _load_manifest_from_yaml(
        self,
        yaml_path: Path,
        plugin_name: str,
    ) -> PluginManifest:
        """
        Parse PluginManifest from the specified plugin.yaml path.
        / 从指定 plugin.yaml 路径解析 PluginManifest。

        Raises:
            PluginNotFoundError: plugin.yaml does not exist / plugin.yaml 不存在
            PluginManifestError: YAML parse or schema validation failed / YAML 解析或 Schema 校验失败
        """
        if not yaml_path.is_file():
            raise PluginNotFoundError(
                message=f"Plugin '{plugin_name}' not found: {yaml_path} does not exist",
            )

        _MAX_MANIFEST_SIZE = 1 * 1024 * 1024  # 1 MB / manifest 单文件大小上限
        file_size = yaml_path.stat().st_size
        if file_size > _MAX_MANIFEST_SIZE:
            raise PluginManifestError(
                message=f"plugin.yaml for '{plugin_name}' too large: {file_size} bytes (limit {_MAX_MANIFEST_SIZE})",
            )

        try:
            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise PluginManifestError(
                message=f"Failed to parse plugin.yaml for '{plugin_name}': {exc}",
            ) from exc

        if not isinstance(data, dict):
            raise PluginManifestError(
                message=f"plugin.yaml for '{plugin_name}' is not a valid mapping",
            )

        try:
            manifest = PluginManifest.model_validate(data)
        except Exception as exc:
            raise PluginManifestError(
                message=f"Manifest validation failed for '{plugin_name}': {exc}",
            ) from exc
        manifest.icon = self._resolve_plugin_metadata_icon(
            yaml_path.parent,
            manifest.icon,
        )
        return manifest

    @staticmethod
    def _resolve_plugin_metadata_icon(
        plugin_dir: Path,
        declared_icon: str,
    ) -> str:
        raw = (declared_icon or "").strip()
        if raw == "icon.png":
            return raw

        return "icon.png" if (plugin_dir / "icon.png").is_file() else ""

    def load_manifest(self, plugin_name: str) -> PluginManifest:
        """
        Read and parse plugin.yaml → PluginManifest.
        / 读取并解析 plugin.yaml → PluginManifest。

        Raises:
            PluginNotFoundError: plugin.yaml does not exist / plugin.yaml 不存在
            PluginManifestError: YAML parse or schema validation failed / YAML 解析或 Schema 校验失败
        """
        yaml_path = self.plugins_dir / plugin_name / "plugin.yaml"
        return self._load_manifest_from_yaml(yaml_path, plugin_name)

    def load_manifest_from_path(self, plugin_dir: Path) -> PluginManifest:
        """
        Read and parse plugin.yaml from any plugin directory.
        / 从任意插件目录读取并解析 plugin.yaml。

        Used for temp extraction dirs, upgrade source dirs, etc. not under the default PLUGINS_DIR.
        / 用于临时解压目录、升级源目录等不在默认 PLUGINS_DIR 下的场景。
        """
        plugin_name = plugin_dir.name
        yaml_path = plugin_dir / "plugin.yaml"
        return self._load_manifest_from_yaml(yaml_path, plugin_name)

    # ── 3. Main class loading / 主类加载 ──

    def load_plugin_class(self, plugin_name: str) -> type[PluginBase]:
        """
        Dynamically import the plugin main class (PluginBase subclass).
        / 动态导入插件主类（PluginBase 子类）。

        Convention path: backend/plugins/{name}/backend/main.py
        / 约定路径: backend/plugins/{name}/backend/main.py

        Raises:
            PluginNotFoundError: main.py does not exist / main.py 不存在
            PluginError: Import failed or no PluginBase subclass found / 导入失败或找不到 PluginBase 子类
        """
        main_path = self.plugins_dir / plugin_name / "backend" / "main.py"
        if not main_path.is_file():
            raise PluginNotFoundError(
                message=f"Plugin entry point not found: {main_path}",
            )

        module_name = f"plugins.{plugin_name}.backend.main"
        try:
            # Prefer using cached module / 优先使用已缓存的模块
            import sys

            if module_name in sys.modules:
                module = sys.modules[module_name]
            else:
                spec = importlib.util.spec_from_file_location(module_name, main_path)
                if spec is None or spec.loader is None:
                    raise PluginError(
                        message=f"Cannot create module spec for '{plugin_name}'",
                    )
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                try:
                    spec.loader.exec_module(module)
                except Exception:
                    # Clear failed module entry to prevent subsequent calls from getting corrupted cache
                    # / 清除失败的模块条目，防止后续调用取到破损缓存
                    sys.modules.pop(module_name, None)
                    raise
        except Exception as exc:
            if isinstance(exc, (PluginError, PluginNotFoundError)):
                raise
            raise PluginError(
                message=resolve_public_error_message(
                    exc,
                    fallback_message=f"Failed to import plugin '{plugin_name}'",
                ),
            ) from exc

        # Find PluginBase subclass / 查找 PluginBase 子类
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, PluginBase) and obj is not PluginBase:
                return obj

        raise PluginError(
            message=f"No PluginBase subclass found in '{main_path}'",
        )

    # ── 4. README / README 加载 ──

    def load_readme(self, plugin_name: str, locale: str = "zh-CN") -> str | None:
        """
        Find README by priority:
        README.{locale}.md → README.md → None
        / 按优先级查找 README
        """
        plugin_dir = self.plugins_dir / plugin_name
        candidates = [
            plugin_dir / f"README.{locale}.md",
            plugin_dir / "README.md",
        ]
        for path in candidates:
            if path.is_file():
                return path.read_text(encoding="utf-8")
        return None

    # ── 5. i18n (locales) / 国际化 ──

    def load_locales(self, plugin_name: str) -> dict[str, dict]:
        """
        Scan locales/ directory, load all .json translation files.
        / 扫描 locales/ 目录，加载所有 .json 翻译文件。

        Returns: {"zh-CN": {...}, "en": {...}}
        / 返回: {"zh-CN": {...}, "en": {...}}
        """
        locales_dir = self.plugins_dir / plugin_name / "locales"
        if not locales_dir.is_dir():
            return {}

        result: dict[str, dict] = {}
        for json_file in sorted(locales_dir.glob("*.json")):
            lang_code = (
                json_file.stem
            )  # "zh-CN" from "zh-CN.json" / 语言码取文件名 stem
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    result[lang_code] = data
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(
                    "Failed to load locale file {} for plugin {}: {}",
                    json_file.name,
                    plugin_name,
                    exc,
                )
        return result
