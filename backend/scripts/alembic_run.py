"""
Alembic wrapper that dynamically discovers plugin migration paths.

Usage (replaces `python -m alembic`):
    python scripts/alembic_run.py heads
    python scripts/alembic_run.py upgrade head
    python scripts/alembic_run.py current

This avoids hardcoding plugin names in alembic.ini.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _discover_plugin_migration_paths() -> list[str]:
    """Scan plugins/*/backend/migrations/versions/ directories."""
    plugins_dir = PROJECT_ROOT / "plugins"
    paths: list[str] = []
    if plugins_dir.exists():
        for plugin_dir in sorted(plugins_dir.iterdir()):
            versions_dir = plugin_dir / "backend" / "migrations" / "versions"
            if versions_dir.is_dir():
                paths.append(str(versions_dir))
    return paths


def main() -> None:
    from alembic.config import CommandLine, Config

    cli = CommandLine(prog="alembic")
    options = cli.parser.parse_args(sys.argv[1:])

    cfg = Config(
        file_=str(PROJECT_ROOT / "alembic.ini"),
        cmd_opts=options,
    )

    # Inject plugin migration paths into version_locations BEFORE ScriptDirectory is built
    base_locations = cfg.get_main_option("version_locations") or ""
    plugin_paths = _discover_plugin_migration_paths()
    if plugin_paths:
        all_locations = f"{base_locations} {' '.join(plugin_paths)}"
        cfg.set_main_option("version_locations", all_locations)

    cli.run_cmd(cfg, options)


if __name__ == "__main__":
    main()
