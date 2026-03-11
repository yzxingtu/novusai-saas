"""
Pre-operation plugin backup / 插件操作前备份

Automatically backs up plugin data tables, files, and config snapshots before upgrade/uninstall.
Supports restoring from backup and data export.
/
升级/卸载前自动备份插件数据表、文件和配置快照。
支持从备份恢复和数据导出。
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.base_model import utc_now
from app.core.logging import get_logger
from app.plugins.loader import PLUGINS_DIR, PluginLoader

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

BACKUPS_DIR = PLUGINS_DIR / ".backups"

_SAFE_TABLE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _is_safe_plugin_table(
    table_name: str,
    expected_prefix: str | tuple[str, ...] | list[str],
) -> bool:
    """Validate table name safety: must match safe characters + must start with plugin prefix / 校验表名安全性：必须匹配安全字符 + 必须以插件前缀开头"""
    if not _SAFE_TABLE_RE.match(table_name):
        return False
    if isinstance(expected_prefix, str):
        prefixes = (expected_prefix,)
    else:
        prefixes = tuple(expected_prefix)
    return any(table_name.startswith(prefix) for prefix in prefixes)


def _get_plugin_table_prefixes(plugin_name: str) -> tuple[str, ...]:
    """Get plugin table prefixes (default px_{plugin}_* + manifest's db_table_prefixes). / 获取插件表前缀（默认 px_{plugin}_* + manifest 的 db_table_prefixes）。"""
    own_prefix = f"px_{plugin_name.replace('-', '_')}_"
    prefixes: list[str] = [own_prefix]
    try:
        manifest = PluginLoader().load_manifest(plugin_name)
        extra_prefixes = getattr(manifest, "db_table_prefixes", None) or []
        for prefix in extra_prefixes:
            normalized = (prefix or "").strip()
            if normalized:
                prefixes.append(normalized)
    except Exception as exc:
        logger.warning(
            "Failed to resolve custom table prefixes for %s, fallback to default: %s",
            plugin_name,
            exc,
        )
    return tuple(dict.fromkeys(prefixes))


async def backup_plugin_data(
    plugin_name: str,
    version: str,
    db: AsyncSession,
) -> Path:
    """
    Back up plugin data (table data + files + config snapshot).
    / 备份插件数据（表数据 + 文件 + 配置快照）。

    Returns:
        Backup directory path / 备份目录路径
    """
    timestamp = utc_now().strftime("%Y%m%d_%H%M%S")
    backup_dir = BACKUPS_DIR / plugin_name / f"{version}_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)

    # 1. Back up plugin files / 备份插件文件
    plugin_dir = PLUGINS_DIR / plugin_name
    if plugin_dir.is_dir():
        files_dir = backup_dir / "files"
        shutil.copytree(plugin_dir, files_dir)
        logger.info("Backed up plugin files: %s", files_dir)

    # 2. Back up config snapshot / 备份配置快照
    try:
        from sqlalchemy import select

        from app.models.system.plugin import Plugin

        # Read operations in savepoint to avoid SQL exceptions polluting outer transaction state
        # / 读操作放在 savepoint 内，避免 SQL 异常污染外层事务状态
        async with db.begin_nested():
            result = await db.execute(
                select(Plugin.config, Plugin.manifest, Plugin.granted_capabilities).where(
                    Plugin.name == plugin_name,
                    Plugin.is_deleted.is_(False),
                )
            )
            row = result.one_or_none()
            if row:
                config_snapshot = {
                    "config": row[0] or {},
                    "manifest": row[1] or {},
                    "granted_capabilities": row[2] or [],
                    "backed_up_at": utc_now().isoformat(),
                }
                config_path = backup_dir / "config_snapshot.json"
                config_path.write_text(json.dumps(config_snapshot, ensure_ascii=False, indent=2))
                logger.info("Backed up config snapshot: %s", config_path)
    except Exception as exc:
        logger.warning("Failed to backup config for %s: %s", plugin_name, exc)

    # 3. Back up plugin data tables (default px_{name}_*, supports manifest extended prefixes)
    # / 备份插件数据表（默认 px_{name}_*，支持 manifest 扩展前缀）
    table_prefixes = _get_plugin_table_prefixes(plugin_name)
    try:
        from sqlalchemy import text

        # Read operations in savepoint; exceptions only roll back to savepoint, not outer transaction
        # / 读操作放在 savepoint 内，异常仅回滚到 savepoint，不影响外层事务
        async with db.begin_nested():
            # No ESCAPE clause (asyncpg doesn't accept multi-byte ESCAPE params);
            # Minor false-positives filtered by _is_safe_plugin_table second pass.
            # / 不使用 ESCAPE 子句（asyncpg 不接受多字节 ESCAPE 参数）；
            # 轻微 false-positive 由 _is_safe_plugin_table 二次过滤兜底。
            table_names: set[str] = set()
            for prefix in table_prefixes:
                tables_result = await db.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_name LIKE :prefix"
                    ),
                    {"prefix": f"{prefix}%"},
                )
                table_names.update(row[0] for row in tables_result)

            if table_names:
                data_dir = backup_dir / "data"
                data_dir.mkdir(exist_ok=True)

                for table_name in sorted(table_names):
                    if not _is_safe_plugin_table(table_name, table_prefixes):
                        logger.warning("Skipping unsafe table name: %s", table_name)
                        continue
                    rows_result = await db.execute(text(f'SELECT * FROM "{table_name}"'))
                    columns = list(rows_result.keys())
                    rows = [
                        dict(zip(columns, row, strict=False))
                        for row in rows_result.fetchall()
                    ]

                    # Serialize (handle datetime and other special types) / 序列化（处理 datetime 等特殊类型）
                    table_path = data_dir / f"{table_name}.json"
                    table_path.write_text(
                        json.dumps(rows, ensure_ascii=False, indent=2, default=str)
                    )
                    logger.info(
                        "Backed up table %s: %d rows", table_name, len(rows)
                    )
    except Exception as exc:
        logger.warning("Failed to backup data tables for %s: %s", plugin_name, exc)

    logger.info("Plugin %s v%s backup complete: %s", plugin_name, version, backup_dir)
    return backup_dir


async def restore_plugin_data(
    plugin_name: str,
    backup_path: Path,
    db: AsyncSession,
) -> None:
    """Restore plugin data and files from backup / 从备份恢复插件数据和文件"""
    # Restore files / 恢复文件
    files_dir = backup_path / "files"
    if files_dir.is_dir():
        target_dir = PLUGINS_DIR / plugin_name
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(files_dir, target_dir)
        logger.info("Restored plugin files from %s", files_dir)

    # Restore config / 恢复配置
    config_path = backup_path / "config_snapshot.json"
    if config_path.is_file():
        try:
            from sqlalchemy import update

            from app.models.system.plugin import Plugin

            snapshot = json.loads(config_path.read_text())
            await db.execute(
                update(Plugin).where(
                    Plugin.name == plugin_name,
                    Plugin.is_deleted.is_(False),
                ).values(
                    config=snapshot.get("config", {}),
                    granted_capabilities=snapshot.get("granted_capabilities", []),
                )
            )
            await db.flush()
            logger.info("Restored config from snapshot")
        except Exception as exc:
            logger.warning("Failed to restore config for %s: %s", plugin_name, exc)

    logger.info("Plugin %s restore complete from %s", plugin_name, backup_path)


async def export_plugin_data(
    plugin_name: str,
    db: AsyncSession,
    fmt: str = "json",
) -> dict[str, str]:
    """
    Export plugin data as downloadable files.
    / 导出插件数据为下载文件。

    Returns:
        {table_name: file_content_string, ...}
    """
    table_prefixes = _get_plugin_table_prefixes(plugin_name)
    exports: dict[str, str] = {}

    try:
        from sqlalchemy import text

        table_names: set[str] = set()
        for prefix in table_prefixes:
            tables_result = await db.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name LIKE :prefix"
                ),
                {"prefix": f"{prefix}%"},
            )
            table_names.update(row[0] for row in tables_result)

        for table_name in sorted(table_names):
            if not _is_safe_plugin_table(table_name, table_prefixes):
                logger.warning("Skipping unsafe table name in export: %s", table_name)
                continue
            rows_result = await db.execute(text(f'SELECT * FROM "{table_name}"'))
            columns = list(rows_result.keys())
            rows = [
                dict(zip(columns, row, strict=False))
                for row in rows_result.fetchall()
            ]

            if fmt == "csv":
                import csv
                import io

                output = io.StringIO()
                if rows:
                    writer = csv.DictWriter(output, fieldnames=columns)
                    writer.writeheader()
                    for row in rows:
                        writer.writerow({k: str(v) for k, v in row.items()})
                exports[table_name] = output.getvalue()
            else:
                exports[table_name] = json.dumps(rows, ensure_ascii=False, indent=2, default=str)

    except Exception as exc:
        logger.warning("Failed to export data for %s: %s", plugin_name, exc)

    return exports


def list_backups(plugin_name: str) -> list[dict]:
    """List all backups for a plugin / 列出插件的所有备份"""
    plugin_backup_dir = BACKUPS_DIR / plugin_name
    if not plugin_backup_dir.is_dir():
        return []

    backups = []
    for child in sorted(plugin_backup_dir.iterdir(), reverse=True):
        if child.is_dir():
            parts = child.name.split("_", 1)
            backups.append({
                "path": str(child),
                "name": child.name,
                "version": parts[0] if parts else "",
                "has_data": (child / "data").is_dir(),
                "has_files": (child / "files").is_dir(),
                "has_config": (child / "config_snapshot.json").is_file(),
            })
    return backups
