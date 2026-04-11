"""Create command for plugin_cli. / plugin_cli create 命令。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from plugin_cli_shared import _PLUGIN_NAME_PATTERN
from plugin_cli_templates import (
    _FE_GITIGNORE,
    _FE_INDEX_TS,
    _FE_LOCALES_TS,
    _FE_PACKAGE_JSON,
    _FE_PAGE_VUE,
    _FE_TYPES_TS,
    _FE_VITE_CONFIG_TS,
    _FULLMOD_YAML_FRONTEND_EXT,
    _MINIMAL_MAIN_PY,
    _MINIMAL_PLUGIN_YAML,
    _SKILL_EXECUTOR_PY,
    _SKILL_PLUGIN_YAML_EXT,
    _SKILL_RESOLVER_PY,
    _STORAGE_DRIVER_PY,
    _STORAGE_YAML_EXT,
)


def cmd_create(args: argparse.Namespace) -> None:
    """创建插件骨架"""

    name = args.name
    template = args.template or "minimal"

    if not _PLUGIN_NAME_PATTERN.match(name):
        print(f"Error: Plugin name must be lowercase kebab-case, got '{name}'")
        sys.exit(1)

    name_underscore = name.replace("-", "_")
    class_name = "".join(word.capitalize() for word in name.split("-"))
    display_name = name.replace("-", " ").title()

    output_dir = Path(args.output) if args.output else Path.cwd() / name
    if output_dir.exists():
        print(f"Error: Directory already exists: {output_dir}")
        sys.exit(1)

    (output_dir / "backend").mkdir(parents=True)
    (output_dir / "locales").mkdir()

    yaml_content = _MINIMAL_PLUGIN_YAML.format(
        name=name,
        display_name=display_name,
        display_name_en=display_name,
        description=f"{display_name} plugin",
        description_en=f"{display_name} plugin",
    )

    if template in ("skill", "full-module"):
        yaml_content += _SKILL_PLUGIN_YAML_EXT.format(
            name=name,
            display_name=display_name,
            display_name_en=display_name,
            name_underscore=name_underscore,
        )

    if template == "storage":
        yaml_content = _MINIMAL_PLUGIN_YAML.format(
            name=name,
            display_name=display_name,
            display_name_en=display_name,
            description=f"{display_name} storage driver",
            description_en=f"{display_name} storage driver",
        ).replace("scope: all_tenants", "scope: admin_only")
        yaml_content += _STORAGE_YAML_EXT.format(
            name=name,
            display_name=display_name,
            display_name_en=display_name,
            class_name=class_name,
        )

    (output_dir / "plugin.yaml").write_text(yaml_content, encoding="utf-8")

    (output_dir / "backend" / "__init__.py").touch()
    (output_dir / "backend" / "main.py").write_text(
        _MINIMAL_MAIN_PY.format(
            name=name,
            display_name=display_name,
            class_name=class_name,
        ),
        encoding="utf-8",
    )

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
                name=name,
                display_name=display_name,
                class_name=class_name,
            ),
            encoding="utf-8",
        )

    if template == "storage":
        (output_dir / "backend" / "driver.py").write_text(
            _STORAGE_DRIVER_PY.format(
                name=name,
                display_name=display_name,
                class_name=class_name,
            ),
            encoding="utf-8",
        )

    if template == "full-module":
        (output_dir / "backend" / "migrations").mkdir()
        (output_dir / "backend" / "migrations" / "versions").mkdir()
        (output_dir / "backend" / "api").mkdir()
        (output_dir / "backend" / "api" / "__init__.py").touch()

        prefix = "".join(word[0] for word in name.split("-"))
        fe_vars = {
            "name": name,
            "name_underscore": name_underscore,
            "class_name": class_name,
            "display_name": display_name,
            "display_name_en": display_name,
            "prefix": prefix,
        }

        yaml_content += _FULLMOD_YAML_FRONTEND_EXT.format(**fe_vars)
        (output_dir / "plugin.yaml").write_text(yaml_content, encoding="utf-8")

        fe_src = output_dir / "frontend" / "src"
        fe_src.mkdir(parents=True)
        (fe_src / "index.ts").write_text(_FE_INDEX_TS.format(**fe_vars), encoding="utf-8")
        (fe_src / "locales.ts").write_text(_FE_LOCALES_TS.format(**fe_vars), encoding="utf-8")
        (fe_src / "types.ts").write_text(_FE_TYPES_TS.format(**fe_vars), encoding="utf-8")
        (fe_src / f"{class_name}Page.vue").write_text(
            _FE_PAGE_VUE.format(**fe_vars),
            encoding="utf-8",
        )

        fe_dir = output_dir / "frontend"
        (fe_dir / "package.json").write_text(_FE_PACKAGE_JSON.format(**fe_vars), encoding="utf-8")
        (fe_dir / "vite.config.ts").write_text(
            _FE_VITE_CONFIG_TS.format(**fe_vars),
            encoding="utf-8",
        )
        (fe_dir / ".gitignore").write_text(_FE_GITIGNORE, encoding="utf-8")

    for lang, label in [("zh-CN", display_name), ("en", display_name)]:
        locale_data = {
            f"plugin.{name}.name": label,
            f"plugin.{name}.description": f"{label} plugin",
        }
        (output_dir / "locales" / f"{lang}.json").write_text(
            json.dumps(locale_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    (output_dir / "README.md").write_text(
        f"# {display_name}\n\nA NovusAI plugin.\n",
        encoding="utf-8",
    )

    print(f"Created plugin '{name}' with template '{template}' at: {output_dir}")
