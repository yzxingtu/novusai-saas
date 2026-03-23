"""
Plugin-aware Alembic migration path helpers.
/ 插件感知的 Alembic 迁移路径辅助函数。
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


def resolve_backend_dir(backend_dir: Path | None = None) -> Path:
    """Resolve backend root directory. / 解析 backend 根目录。"""
    return backend_dir or Path(__file__).resolve().parents[2]


def resolve_main_versions_dir(backend_dir: Path | None = None) -> Path:
    """Resolve main app Alembic versions dir. / 解析主应用迁移目录。"""
    return resolve_backend_dir(backend_dir) / "migrations" / "versions"


def resolve_plugin_versions_dir(
    plugin_name: str,
    *,
    backend_dir: Path | None = None,
) -> Path:
    """Resolve one plugin versions dir. / 解析单个插件的迁移目录。"""
    return (
        resolve_backend_dir(backend_dir)
        / "plugins"
        / plugin_name
        / "backend"
        / "migrations"
        / "versions"
    )


def get_db_registered_plugin_names(*, db_url: str | None = None) -> list[str]:
    """
    Load plugin names from DB plugin records.
    / 从数据库插件记录读取插件名。

    A non-deleted plugin row is treated as "installed enough" for migration graph
    resolution, regardless of enabled/disabled/error runtime status.
    / 只要插件记录未软删除，就视为迁移图里需要解析；不再按 enabled/disabled/error 细分。
    """
    target_db_url = (db_url or _get_default_db_url() or "").replace("\\", "/")
    if not target_db_url:
        return []

    engine = create_engine(target_db_url, echo=False)
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT name "
                    "FROM plugins "
                    "WHERE COALESCE(is_deleted, FALSE) = FALSE"
                )
            ).fetchall()
        names = {
            str(row[0]).strip()
            for row in rows
            if row and str(row[0] or "").strip()
        }
        return sorted(names)
    except Exception as exc:
        logger.debug("Cannot resolve DB-registered plugins for migrations: %s", exc)
        return []
    finally:
        engine.dispose()


def _get_default_db_url() -> str:
    """Resolve DATABASE_URL_SYNC lazily to avoid core import cycles. / 惰性读取数据库 URL，避免 core 循环导入。"""
    from app.core.config import settings

    return str(settings.DATABASE_URL_SYNC or "")


def get_migration_plugin_names(
    *,
    backend_dir: Path | None = None,
    db_url: str | None = None,
    include_plugin_names: Iterable[str] | None = None,
) -> list[str]:
    """Resolve plugin names participating in migration graph. / 解析参与迁移图的插件名。"""
    plugin_names = set(get_db_registered_plugin_names(db_url=db_url))
    for plugin_name in include_plugin_names or ():
        normalized = str(plugin_name or "").strip()
        if normalized:
            plugin_names.add(normalized)

    backend = resolve_backend_dir(backend_dir)
    filtered_names: list[str] = []
    for plugin_name in sorted(plugin_names):
        plugin_root = backend / "plugins" / plugin_name
        if plugin_root.is_dir():
            filtered_names.append(plugin_name)
    return filtered_names


def build_migration_version_locations(
    *,
    backend_dir: Path | None = None,
    db_url: str | None = None,
    include_plugin_names: Iterable[str] | None = None,
) -> list[str]:
    """
    Build version_locations for Alembic.
    / 构建 Alembic 的 version_locations。
    """
    backend = resolve_backend_dir(backend_dir)
    seen_paths: set[str] = set()
    version_locations: list[str] = []

    def _add_path(path: Path) -> None:
        if not path.is_dir():
            return
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen_paths:
            return
        seen_paths.add(normalized)
        version_locations.append(str(path).replace("\\", "/"))

    _add_path(resolve_main_versions_dir(backend))

    for plugin_name in get_migration_plugin_names(
        backend_dir=backend,
        db_url=db_url,
        include_plugin_names=include_plugin_names,
    ):
        _add_path(resolve_plugin_versions_dir(plugin_name, backend_dir=backend))

    return version_locations


def purge_migration_bytecode(
    version_locations: Iterable[str | os.PathLike[str]],
) -> list[str]:
    """
    Remove cached migration bytecode files.
    / 删除迁移目录下缓存的字节码文件。

    This avoids Alembic picking up stale revision metadata from old ``.pyc``
    files after a migration script was edited in place.
    / 避免迁移脚本被原地修改后，Alembic 继续读取旧 ``.pyc`` 中的 revision 元数据。
    """
    removed_paths: list[str] = []

    for version_location in version_locations:
        pycache_dir = Path(version_location) / "__pycache__"
        if not pycache_dir.is_dir():
            continue

        for cached_file in pycache_dir.iterdir():
            if cached_file.suffix not in {".pyc", ".pyo"}:
                continue
            try:
                cached_file.unlink()
                removed_paths.append(str(cached_file).replace("\\", "/"))
            except FileNotFoundError:
                continue
            except Exception as exc:
                logger.debug(
                    "Cannot remove migration bytecode %s: %s",
                    cached_file,
                    exc,
                )

    return removed_paths


def should_purge_migration_bytecode_for_startup(*, debug: bool) -> bool:
    """
    Decide whether startup should purge migration bytecode.
    / 判断启动阶段是否应清理迁移字节码。

    In local DEBUG mode this app starts with reload enabled. Deleting ``.pyc``
    files under migration directories can trigger a file-watch reload and
    interrupt the Alembic subprocess mid-startup on Windows. To keep startup
    stable, DEBUG startup skips the purge and only keeps the purge for
    non-debug paths such as production boot or explicit CLI migration runs.
    / 本项目本地 DEBUG 启动默认开启 reload。若在启动阶段删除迁移目录下的
    ``.pyc``，可能触发文件监听重载，在 Windows 开发环境中打断 Alembic
    子进程。为保证启动稳定，DEBUG 启动跳过该清理；非 DEBUG 路径（如生产启
    动或显式 CLI 迁移）仍保留清理能力。
    """
    return not debug
