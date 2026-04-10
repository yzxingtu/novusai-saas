"""Runtime helper functions shared by CLI command handlers."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def get_venv_python(backend_dir: Path) -> str:
    """Resolve backend .venv Python executable with fallback to current Python."""
    venv_dir = backend_dir / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    venv_py = venv_dir / ("python.exe" if os.name == "nt" else "python")
    return str(venv_py) if venv_py.exists() else sys.executable


def run_celery(backend_dir: Path, celery_app: str, args: list[str]) -> None:
    os.chdir(backend_dir)
    python_exe = get_venv_python(backend_dir)
    cmd = [python_exe, "-m", "celery", "-A", celery_app] + args
    subprocess.run(cmd, check=True)


def discover_plugin_migration_paths(backend_dir: Path) -> list[str]:
    """Resolve plugin migration paths from DB-registered plugins."""
    from app.plugins.migration_paths import build_migration_version_locations

    version_locations = build_migration_version_locations(backend_dir=backend_dir)
    return version_locations[1:]


def get_alembic_config(backend_dir: Path):
    """Build Alembic config with plugin migration paths injected."""
    from alembic.config import Config

    cfg = Config(str(backend_dir / "alembic.ini"))
    merged_paths: list[str] = []
    seen_paths: set[str] = set()

    for path in (cfg.get_version_locations_list() or []) + discover_plugin_migration_paths(
        backend_dir
    ):
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen_paths:
            continue
        seen_paths.add(normalized)
        merged_paths.append(path)

    if merged_paths:
        cfg.set_main_option("version_locations", "\n".join(merged_paths))
    return cfg


def load_plugin_cli(backend_dir: Path) -> None:
    """Ensure scripts dir on sys.path for dynamic plugin CLI module import."""
    scripts_dir = str(backend_dir / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, str(backend_dir))
        sys.path.insert(0, scripts_dir)


def run_plugin_operator_action(
    backend_dir: Path,
    plugin_name: str,
    action,
    *,
    init_redis: bool = False,
    run_async,
):
    """Run plugin operator action in managed DB/Redis runtime context."""

    async def _do():
        from app.core.database import get_db_context
        from app.core.redis import RedisManager
        from app.services.system.plugin_service import PluginService

        if init_redis:
            await RedisManager.init()
        try:
            async with get_db_context() as db:
                service = PluginService(db)
                plugin = await service.get_by_name(plugin_name)
                if not plugin:
                    raise SystemExit(f"Plugin '{plugin_name}' not found")
                return await action(service, plugin)
        finally:
            if init_redis:
                await RedisManager.close()

    os.chdir(backend_dir)
    return run_async(_do())


def check_db(logger: Any) -> bool:
    try:
        from sqlalchemy import text

        from app.core.database import sync_session_factory

        session = sync_session_factory()
        session.execute(text("SELECT 1"))
        session.close()
        return True
    except Exception as e:
        logger.debug("DB check failed: {}", e)
        return False


def check_redis(logger: Any) -> bool:
    try:
        from redis import Redis

        from app.core.config import settings

        r = Redis.from_url(settings.REDIS_URL)
        r.ping()
        return True
    except Exception as e:
        logger.debug("Redis check failed: {}", e)
        return False


def check_celery(logger: Any) -> bool:
    try:
        from app.celery_app import celery_app

        celery_app.connection().connect()
        return True
    except Exception as e:
        logger.debug("Celery check failed: {}", e)
        return False
