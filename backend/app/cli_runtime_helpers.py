"""Runtime helper functions shared by CLI command handlers."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit


def get_venv_python(backend_dir: Path) -> str:
    """中文: 解析 backend/.venv 的 Python；缺失时显式失败。

    EN: Resolve backend/.venv Python and fail explicitly when it is missing.
    """
    venv_dir = backend_dir / ".venv" / ("Scripts" if os.name == "nt" else "bin")
    venv_py = venv_dir / ("python.exe" if os.name == "nt" else "python")
    if venv_py.exists():
        return str(venv_py)
    raise RuntimeError(
        f"Backend virtualenv Python not found at {venv_py}. "
        "Create backend/.venv before running runtime CLI commands."
    )


def run_celery(backend_dir: Path, celery_app: str, args: list[str]) -> None:
    os.chdir(backend_dir)
    python_exe = get_venv_python(backend_dir)
    cmd = [python_exe, "-m", "celery", "-A", celery_app] + args
    subprocess.run(cmd, check=True)


def redact_url(url: str) -> str:
    """Return a CLI-safe URL with passwords hidden."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if not parts.password:
        return url

    hostname = parts.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    username = parts.username or ""
    netloc = f"{username}:***@{hostname}"
    if parts.port:
        netloc = f"{netloc}:{parts.port}"

    return urlunsplit(
        SplitResult(
            scheme=parts.scheme,
            netloc=netloc,
            path=parts.path,
            query=parts.query,
            fragment=parts.fragment,
        )
    )


def check_celery_broker_url(
    broker_url: str,
    logger: Any,
    *,
    connect_timeout: float = 1.0,
) -> bool:
    """Check the configured Celery broker without importing the task app."""
    try:
        from kombu import Connection

        with Connection(
            broker_url,
            connect_timeout=connect_timeout,
            transport_options={
                "socket_connect_timeout": connect_timeout,
                "socket_timeout": connect_timeout,
            },
        ) as connection:
            connection.ensure_connection(
                max_retries=0,
                interval_start=0,
                interval_step=0,
                interval_max=0,
            )
        return True
    except Exception as e:
        logger.debug("Celery broker URL check failed: {}", e)
        return False


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

    for path in (
        cfg.get_version_locations_list() or []
    ) + discover_plugin_migration_paths(backend_dir):
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
