"""
# DEPRECATED: Use `novusai plugin <create|validate|pack|list>` instead.
# 已弃用：请使用 `novusai plugin <create|validate|pack|list>` 替代。

NovusAI 插件开发 CLI 工具

用法:
    python scripts/plugin_cli.py create <name> [--template=minimal|skill|full-module]
    python scripts/plugin_cli.py validate <dir>
    python scripts/plugin_cli.py pack <dir> [--output=output.zip]
    python scripts/plugin_cli.py publish <zip> [--token=GITHUB_TOKEN]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# create — 生成插件骨架
# ============================================================

_MINIMAL_PLUGIN_YAML = """name: {name}
version: "1.0.0"
display_name:
  zh-CN: "{display_name}"
  en: "{display_name_en}"
description:
  zh-CN: "{description}"
  en: "{description_en}"
author: ""
icon: "lucide:puzzle"
scope: all_tenants

capabilities: []

extensions: {{}}

dependencies:
  python: []

pricing:
  type: free
"""

_MINIMAL_MAIN_PY = '''"""
{display_name} 插件
"""

from app.plugins.base import PluginBase


class {class_name}Plugin(PluginBase):
    """{display_name}"""

    async def on_install(self, ctx) -> None:
        ctx.get_logger().info("{name} installed")

    async def on_enable(self, ctx) -> None:
        ctx.get_logger().info("{name} enabled")
'''

_SKILL_RESOLVER_PY = '''"""
{display_name} 技能解析器
"""

from app.ai.tools.types import ToolDefinition, ToolParameter


def resolve(skill, config: dict) -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="{name}_query",
            description="TODO: describe your tool",
            tool_type="{name}",
            parameters=[
                ToolParameter(
                    name="input",
                    type="string",
                    description="Input parameter",
                    required=True,
                ),
            ],
            config=config,
            enabled=True,
        ),
    ]
'''

_SKILL_EXECUTOR_PY = '''"""
{display_name} 工具执行器
"""

from __future__ import annotations

import time
from typing import Any, TYPE_CHECKING

from app.ai.tools.executors.base import BaseToolExecutor
from app.ai.tools.types import ToolDefinition, ToolResult

if TYPE_CHECKING:
    from app.ai.tools.types import ExecutionContext


class {class_name}Executor(BaseToolExecutor):
    """{display_name} 执行器"""

    async def validate(self, definition: ToolDefinition, arguments: dict[str, Any]) -> bool:
        return bool(arguments.get("input"))

    async def execute(
        self,
        definition: ToolDefinition,
        tool_call_id: str,
        arguments: dict[str, Any],
        context: ExecutionContext | None = None,
    ) -> ToolResult:
        start = time.perf_counter()
        # TODO: implement your tool logic
        output = f"Result for: {{arguments.get('input', '')}}"
        duration_ms = int((time.perf_counter() - start) * 1000)
        return ToolResult(
            tool_call_id=tool_call_id,
            name=definition.name,
            success=True,
            output=output,
            duration_ms=duration_ms,
        )
'''

_SKILL_PLUGIN_YAML_EXT = """
extensions:
  skills:
    - name: {name}-query
      type: {name}
      display_name:
        zh-CN: "{display_name}"
        en: "{display_name_en}"
      entry_point: "skills.{name_underscore}_resolver"
"""

_FULLMOD_YAML_FRONTEND_EXT = """
  frontend:
    header_widgets:
      - name: {name}-widget
        component: "{class_name}Widget"
        sort_order: 90
"""

# ── Frontend templates for full-module ──

_FE_INDEX_TS = '''/**
 * {display_name} 插件前端入口
 */
import type {{ NovusPluginSharedAPI }} from './types';

import {class_name}Widget from './{class_name}Widget.vue';
import {{ zhCN, enUS }} from './locales';
import {{ {prefix_upper}_STYLES }} from './styles';

export function setup(): void {{
  const shared = (window as unknown as Record<string, unknown>)
    .NovusPluginShared as NovusPluginSharedAPI | undefined;

  if (shared?.registerLocale) {{
    shared.registerLocale('zh-CN', 'plugin.{name}', zhCN);
    shared.registerLocale('zh', 'plugin.{name}', zhCN);
    shared.registerLocale('en-US', 'plugin.{name}', enUS);
    shared.registerLocale('en', 'plugin.{name}', enUS);
  }}

  if (!document.getElementById('{prefix}-plugin-styles')) {{
    const style = document.createElement('style');
    style.id = '{prefix}-plugin-styles';
    style.textContent = {prefix_upper}_STYLES;
    document.head.appendChild(style);
  }}
}}

export {{ {class_name}Widget }};
'''

_FE_STYLES_TS = '''/**
 * {display_name} 插件样式
 *
 * 通过 setup() JS 注入到 <head>，避免 scoped CSS 在 portal 中失效。
 * 以 .{prefix}- 前缀避免全局冲突。
 */
export const {prefix_upper}_STYLES = `
/* {display_name} plugin styles */
.{prefix}-widget {{
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}}
`;
'''

_FE_LOCALES_TS = '''/**
 * {display_name} 插件 i18n
 */
export const zhCN: Record<string, string> = {{
  title: "{display_name}",
  description: "{display_name}插件",
}};

export const enUS: Record<string, string> = {{
  title: "{display_name_en}",
  description: "{display_name_en} plugin",
}};
'''

_FE_TYPES_TS = '''/**
 * 宿主共享 API 类型声明（仅用于类型提示，不打入 bundle）
 */
export interface NovusPluginSharedAPI {{
  requestClient: {{
    get: <T = unknown>(url: string, config?: Record<string, unknown>) => Promise<T>;
    post: <T = unknown>(url: string, data?: unknown, config?: Record<string, unknown>) => Promise<T>;
  }};
  $t: (key: string, ...args: unknown[]) => string;
  IconifyIcon: unknown;
  usePluginSlotsStore: () => unknown;
  registerLocale: (locale: string, prefix: string, messages: Record<string, unknown>) => void;
}}
'''

_FE_WIDGET_VUE = '''<script lang="ts" setup>
import {{ $t, IconifyIcon }} from '@novus/plugin-shared';
</script>

<template>
  <div class="{prefix}-widget">
    <IconifyIcon icon="lucide:puzzle" class="size-4" />
    <span>{{{{ $t('plugin.{name}.title') }}}}</span>
  </div>
</template>

<!-- 所有样式通过 setup() JS 注入（scoped CSS 在 Popover portal 中不生效） -->
'''

_FE_PACKAGE_JSON = '''{{
  "name": "@novus-plugin/{name}",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {{
    "build": "vite build"
  }},
  "devDependencies": {{
    "@vitejs/plugin-vue": "^5.2.0",
    "typescript": "~5.7.0",
    "vite": "^6.0.0",
    "vue": "^3.5.0"
  }}
}}
'''

_FE_VITE_CONFIG_TS = '''/**
 * 插件前端 UMD 构建配置
 */
import {{ defineConfig }} from 'vite';
import vue from '@vitejs/plugin-vue';
import {{ resolve }} from 'node:path';

export default defineConfig({{
  plugins: [vue()],
  build: {{
    outDir: 'dist',
    emptyOutDir: true,
    lib: {{
      entry: resolve(__dirname, 'src/index.ts'),
      name: 'NovusPlugin_{name_underscore}',
      formats: ['umd'],
      fileName: () => 'index.js',
    }},
    rollupOptions: {{
      external: ['vue', 'vue-router', 'ant-design-vue', '@novus/plugin-shared'],
      output: {{
        globals: {{
          vue: 'Vue',
          'vue-router': 'VueRouter',
          'ant-design-vue': 'AntDesignVue',
          '@novus/plugin-shared': 'NovusPluginShared',
        }},
        assetFileNames: '[name][extname]',
      }},
    }},
    cssCodeSplit: false,
    minify: 'esbuild',
  }},
}});
'''

_FE_GITIGNORE = """node_modules/
dist/
"""

# ── Storage driver template ──

_STORAGE_YAML_EXT = """
extensions:
  storage_drivers:
    - code: {name}
      display_name:
        zh-CN: "{display_name}存储"
        en: "{display_name_en} Storage"
      entry_point: "backend.driver.{class_name}Driver"

config_schema:
  type: object
  properties:
    access_key:
      type: string
      x-encrypted: true
      title: Access Key
    secret_key:
      type: string
      x-encrypted: true
      title: Secret Key
    bucket:
      type: string
      title: Bucket Name
  required: [access_key, secret_key, bucket]
"""

_STORAGE_DRIVER_PY = '''"""\n{display_name} 存储驱动\n"""
from __future__ import annotations
from typing import Any

from app.storage.base import StorageDriver


class {class_name}Driver(StorageDriver):
    name = "{name}"

    def __init__(self, config: dict[str, Any]) -> None:
        self._access_key = config.get("access_key", "")
        self._secret_key = config.get("secret_key", "")
        self._bucket = config.get("bucket", "")

    async def put(self, path: str, content: Any, mime_type: str | None = None, **kwargs: Any) -> Any:
        raise NotImplementedError

    async def get(self, path: str) -> Any:
        raise NotImplementedError

    async def delete(self, path: str) -> bool:
        raise NotImplementedError

    async def exists(self, path: str) -> bool:
        raise NotImplementedError

    async def get_url(self, path: str, expires: int = 3600, **kwargs: Any) -> str:
        raise NotImplementedError
'''


def _is_truthy_or_falsy_bool_str(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"1", "0", "true", "false", "yes", "no", "on", "off"}


def _normalize_debug_env_for_cli(warnings: list[str]) -> None:
    """
    CLI 健壮性保护：
    当 DEBUG 被设置为非布尔字符串（例如 release）时，
    app.core.config 会在 import 阶段抛 ValidationError，导致 validate 中断。
    """
    raw = os.getenv("DEBUG")
    if raw is None:
        return
    if _is_truthy_or_falsy_bool_str(raw):
        return
    os.environ["DEBUG"] = "false"
    warnings.append(
        f"Environment DEBUG='{raw}' is not a valid boolean; fallback to DEBUG=false for CLI validation"
    )


def _manifest_has_frontend_extensions(manifest_data: dict) -> bool:
    frontend = (manifest_data.get("extensions") or {}).get("frontend") or {}
    return bool(
        frontend.get("menus")
        or frontend.get("header_widgets")
        or frontend.get("floating_panels")
        or frontend.get("dashboard_widgets")
        or frontend.get("settings_tabs")
        or frontend.get("standalone_pages")
        or frontend.get("notification_ui")
        or (frontend.get("admin") or {}).get("entry")
        or (frontend.get("tenant") or {}).get("entry")
    )


def cmd_create(args: argparse.Namespace) -> None:
    """创建插件骨架"""
    name = args.name
    template = args.template or "minimal"

    if not re.match(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$", name):
        print(f"Error: Plugin name must be lowercase kebab-case, got '{name}'")
        sys.exit(1)

    name_underscore = name.replace("-", "_")
    class_name = "".join(word.capitalize() for word in name.split("-"))
    display_name = name.replace("-", " ").title()

    output_dir = Path(args.output) if args.output else Path.cwd() / name
    if output_dir.exists():
        print(f"Error: Directory already exists: {output_dir}")
        sys.exit(1)

    # 创建目录
    (output_dir / "backend").mkdir(parents=True)
    (output_dir / "locales").mkdir()

    # plugin.yaml
    yaml_content = _MINIMAL_PLUGIN_YAML.format(
        name=name, display_name=display_name,
        display_name_en=display_name, description=f"{display_name} plugin",
        description_en=f"{display_name} plugin",
    )

    if template in ("skill", "full-module"):
        yaml_content += _SKILL_PLUGIN_YAML_EXT.format(
            name=name, display_name=display_name,
            display_name_en=display_name, name_underscore=name_underscore,
        )

    if template == "storage":
        yaml_content = _MINIMAL_PLUGIN_YAML.format(
            name=name, display_name=display_name,
            display_name_en=display_name, description=f"{display_name} storage driver",
            description_en=f"{display_name} storage driver",
        ).replace("scope: all_tenants", "scope: admin_only")
        yaml_content += _STORAGE_YAML_EXT.format(
            name=name, display_name=display_name,
            display_name_en=display_name, class_name=class_name,
        )

    (output_dir / "plugin.yaml").write_text(yaml_content, encoding="utf-8")

    # backend/main.py
    (output_dir / "backend" / "__init__.py").touch()
    (output_dir / "backend" / "main.py").write_text(
        _MINIMAL_MAIN_PY.format(
            name=name, display_name=display_name, class_name=class_name,
        ),
        encoding="utf-8",
    )

    # skill template extras
    if template in ("skill", "full-module"):
        (output_dir / "backend" / "skills").mkdir()
        (output_dir / "backend" / "skills" / "__init__.py").touch()
        (output_dir / "backend" / "skills" / f"{name_underscore}_resolver.py").write_text(
            _SKILL_RESOLVER_PY.format(name=name, display_name=display_name),
            encoding="utf-8",
        )

        (output_dir / "backend" / "executors").mkdir()
        (output_dir / "backend" / "executors" / "__init__.py").touch()
        (output_dir / "backend" / "executors" / f"{name_underscore}_executor.py").write_text(
            _SKILL_EXECUTOR_PY.format(
                name=name, display_name=display_name, class_name=class_name,
            ),
            encoding="utf-8",
        )

    # storage extras
    if template == "storage":
        (output_dir / "backend" / "driver.py").write_text(
            _STORAGE_DRIVER_PY.format(
                name=name, display_name=display_name, class_name=class_name,
            ),
            encoding="utf-8",
        )

    # full-module extras
    if template == "full-module":
        (output_dir / "backend" / "migrations").mkdir()
        (output_dir / "backend" / "migrations" / "versions").mkdir()
        (output_dir / "backend" / "api").mkdir()
        (output_dir / "backend" / "api" / "__init__.py").touch()

        # Derive CSS prefix (first 2 letters of each word, e.g. my-plugin -> mp)
        prefix = "".join(w[0] for w in name.split("-"))
        prefix_upper = prefix.upper()
        fe_vars = {
            "name": name, "name_underscore": name_underscore, "class_name": class_name,
            "display_name": display_name, "display_name_en": display_name,
            "prefix": prefix, "prefix_upper": prefix_upper,
        }

        # Append frontend extension to yaml
        yaml_content += _FULLMOD_YAML_FRONTEND_EXT.format(**fe_vars)
        (output_dir / "plugin.yaml").write_text(yaml_content, encoding="utf-8")

        # frontend/src/
        fe_src = output_dir / "frontend" / "src"
        fe_src.mkdir(parents=True)
        (fe_src / "index.ts").write_text(_FE_INDEX_TS.format(**fe_vars), encoding="utf-8")
        (fe_src / "styles.ts").write_text(_FE_STYLES_TS.format(**fe_vars), encoding="utf-8")
        (fe_src / "locales.ts").write_text(_FE_LOCALES_TS.format(**fe_vars), encoding="utf-8")
        (fe_src / "types.ts").write_text(_FE_TYPES_TS.format(**fe_vars), encoding="utf-8")
        (fe_src / f"{class_name}Widget.vue").write_text(_FE_WIDGET_VUE.format(**fe_vars), encoding="utf-8")

        # frontend/ config files
        fe_dir = output_dir / "frontend"
        (fe_dir / "package.json").write_text(_FE_PACKAGE_JSON.format(**fe_vars), encoding="utf-8")
        (fe_dir / "vite.config.ts").write_text(_FE_VITE_CONFIG_TS.format(**fe_vars), encoding="utf-8")
        (fe_dir / ".gitignore").write_text(_FE_GITIGNORE, encoding="utf-8")

    # locales
    for lang, label in [("zh-CN", display_name), ("en", display_name)]:
        locale_data = {
            f"plugin.{name}.name": label,
            f"plugin.{name}.description": f"{label} plugin",
        }
        (output_dir / "locales" / f"{lang}.json").write_text(
            json.dumps(locale_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # README
    (output_dir / "README.md").write_text(
        f"# {display_name}\n\nA NovusAI plugin.\n",
        encoding="utf-8",
    )

    print(f"Created plugin '{name}' with template '{template}' at: {output_dir}")


# ============================================================
# validate — 校验插件
# ============================================================

def cmd_validate(args: argparse.Namespace) -> None:
    """校验插件"""
    plugin_dir = Path(args.dir)
    if not plugin_dir.is_dir():
        print(f"Error: Not a directory: {plugin_dir}")
        sys.exit(1)

    errors: list[str] = []
    warnings: list[str] = []

    # 1. plugin.yaml
    yaml_path = plugin_dir / "plugin.yaml"
    if not yaml_path.is_file():
        errors.append("Missing plugin.yaml")
    else:
        try:
            import yaml

            from app.plugins.manifest import PluginManifest

            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            manifest = PluginManifest.model_validate(data)
            print(f"  [OK] plugin.yaml valid: {manifest.name} v{manifest.version}")

            # Check i18n key prefix
            locales_dir = plugin_dir / "locales"
            if locales_dir.is_dir():
                prefix = f"plugin.{manifest.name}."
                for json_file in locales_dir.glob("*.json"):
                    locale_data = json.loads(json_file.read_text(encoding="utf-8"))
                    for key in locale_data:
                        if not key.startswith(prefix):
                            warnings.append(f"i18n key '{key}' in {json_file.name} should start with '{prefix}'")

            # Check DB table prefix
            # (scan Python files for table names)

        except Exception as exc:
            errors.append(f"plugin.yaml validation failed: {exc}")

    # 2. backend/main.py
    main_path = plugin_dir / "backend" / "main.py"
    if not main_path.is_file():
        errors.append("Missing backend/main.py")
    else:
        print("  [OK] backend/main.py exists")

    # 3. Frontend checks (if frontend extensions declared)
    try:
        import yaml as _yaml
        with open(yaml_path, encoding="utf-8") as _yf:
            _ydata = _yaml.safe_load(_yf)
        _has_fe = _manifest_has_frontend_extensions(_ydata or {})
    except Exception:
        _has_fe = False

    if _has_fe:
        dist_js = plugin_dir / "frontend" / "dist" / "index.js"
        if dist_js.is_file():
            dist_size = sum(f.stat().st_size for f in (plugin_dir / "frontend" / "dist").rglob("*") if f.is_file())
            if dist_size > 5 * 1024 * 1024:
                warnings.append(f"frontend/dist/ is {dist_size / 1024 / 1024:.1f} MB (> 5MB recommended limit)")
            print(f"  [OK] frontend/dist/index.js exists ({dist_size / 1024:.1f} KB)")
        else:
            errors.append("frontend/dist/index.js missing - run: cd frontend && npm install && npx vite build")

        # Scan .vue files for forbidden <style scoped>
        vue_files = list((plugin_dir / "frontend").rglob("*.vue"))
        for vue_file in vue_files:
            content = vue_file.read_text(encoding="utf-8", errors="ignore")
            if "<style scoped" in content or "<style scoped>" in content:
                errors.append(f"{vue_file.relative_to(plugin_dir)}: <style scoped> forbidden - use styles.ts JS injection")
            elif "<style>" in content or "<style " in content:
                warnings.append(f"{vue_file.relative_to(plugin_dir)}: <style> block found - recommend styles.ts JS injection instead")

        if not vue_files:
            pass  # No Vue files = no frontend component check needed
        elif not errors:
            print(f"  [OK] {len(vue_files)} .vue file(s) - no <style scoped>")
    else:
        print("  [INFO] No frontend extensions declared")

    # 4. Capabilities consistency check
    try:
        import yaml as _yaml2
        with open(yaml_path, encoding="utf-8") as _yf2:
            _ydata2 = _yaml2.safe_load(_yf2)
        from app.plugins.manifest import PluginManifest
        _manifest2 = PluginManifest.model_validate(_ydata2)
        _caps = set(_manifest2.capabilities)
        _ext2 = _manifest2.extensions
        if _manifest2.ai_requirements and _manifest2.ai_requirements.features and "ai:call" not in _caps:
            warnings.append("ai_requirements.features declared but 'ai:call' not in capabilities")
        if (
            any(r.handler for r in [*_ext2.api.admin_routes, *_ext2.api.tenant_routes, *_ext2.api.public_routes])
            and not _caps
        ):
            pass  # API routes don't require specific capability
        _encrypted_fields = []
        if _manifest2.config_schema:
            for _k, _v in (_manifest2.config_schema.get("properties") or {}).items():
                if isinstance(_v, dict) and _v.get("x-encrypted"):
                    _encrypted_fields.append(_k)
        if _encrypted_fields:
            print(f"  [INFO] x-encrypted fields: {', '.join(_encrypted_fields)} (will be Fernet-encrypted)")
    except Exception:
        pass

    # 5. Security scan
    _normalize_debug_env_for_cli(warnings)
    from app.plugins.security_scan import scan_plugin_directory

    scan_result = scan_plugin_directory(plugin_dir)
    if scan_result.has_warnings:
        for w in scan_result.warnings:
            warnings.append(f"Security: {w}")
    else:
        print(f"  [OK] Security scan clean ({scan_result.files_scanned} files)")

    # Report
    print(f"\n{'='*40}")
    if errors:
        print(f"  [ERROR] {len(errors)} error(s):")
        for e in errors:
            print(f"     - {e}")
    if warnings:
        print(f"  [WARN] {len(warnings)} warning(s):")
        for w in warnings:
            print(f"     - {w}")
    if not errors and not warnings:
        print("  [OK] All checks passed!")

    sys.exit(1 if errors else 0)


# ============================================================
# pack — 打包
# ============================================================

_PACK_EXCLUDE_DIRS = {"node_modules", "__pycache__", ".git", ".venv"}
_PACK_EXCLUDE_EXTS = {".pyc", ".pyo"}


def cmd_pack(args: argparse.Namespace) -> None:
    """打包插件为 .zip"""
    plugin_dir = Path(args.dir)
    if not (plugin_dir / "plugin.yaml").is_file():
        print(f"Error: No plugin.yaml in {plugin_dir}")
        sys.exit(1)

    import yaml

    with open(plugin_dir / "plugin.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    name = data.get("name", plugin_dir.name)
    version = data.get("version", "1.0.0")

    # Check if frontend extensions declared but dist/ not built
    has_frontend = _manifest_has_frontend_extensions(data or {})
    if has_frontend:
        dist_js = plugin_dir / "frontend" / "dist" / "index.js"
        if not dist_js.is_file():
            print("  \u26a0\ufe0f  Warning: frontend/dist/index.js not found.")
            print(f"     Please run: cd {plugin_dir}/frontend && npm install && npx vite build")

    output_path = Path(args.output) if args.output else Path.cwd() / f"{name}-{version}.zip"

    file_count = 0
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in plugin_dir.rglob("*"):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(plugin_dir)
            # Skip excluded dirs
            if any(part in _PACK_EXCLUDE_DIRS for part in rel.parts):
                continue
            # Skip hidden files/dirs
            if any(p.startswith(".") for p in rel.parts):
                continue
            # Skip compiled Python
            if file_path.suffix in _PACK_EXCLUDE_EXTS:
                continue
            zf.write(file_path, f"{name}/{rel}")
            file_count += 1

    size_kb = output_path.stat().st_size / 1024
    print(f"Packed: {output_path}")
    print(f"  {file_count} files, {size_kb:.1f} KB")


# ============================================================
# main
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="NovusAI Plugin CLI",
        prog="novusai-plugin",
    )
    subparsers = parser.add_subparsers(dest="command")

    # create
    p_create = subparsers.add_parser("create", help="Create plugin skeleton")
    p_create.add_argument("name", help="Plugin name (kebab-case)")
    p_create.add_argument("--template", choices=["minimal", "skill", "full-module", "storage"], default="minimal")
    p_create.add_argument("--output", help="Output directory")

    # validate
    p_validate = subparsers.add_parser("validate", help="Validate plugin")
    p_validate.add_argument("dir", help="Plugin directory")

    # pack
    p_pack = subparsers.add_parser("pack", help="Pack plugin to .zip")
    p_pack.add_argument("dir", help="Plugin directory")
    p_pack.add_argument("--output", help="Output .zip path")

    args = parser.parse_args()

    if args.command == "create":
        cmd_create(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "pack":
        cmd_pack(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
