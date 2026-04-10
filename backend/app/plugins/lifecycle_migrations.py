"""Alembic/database cleanup helpers extracted from PluginLifecycle."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.core.response import resolve_public_error_message
from app.plugins.exceptions import PluginInstallError
from app.plugins.lifecycle_support import (
    escape_like_pattern,
    is_safe_plugin_table_name,
    run_subprocess_async,
)
from app.plugins.loader import PLUGINS_DIR
from app.plugins.migration_paths import build_migration_version_locations

if TYPE_CHECKING:
    pass


logger = get_logger(__name__)


class LifecycleMigrationMixin:
    """Alembic/database cleanup helpers extracted from PluginLifecycle."""
    async def _purge_orphaned_alembic_stamps(self) -> None:
        """Purge orphaned version stamps in alembic_version that no longer have corresponding migration files.
        / 升级前清除 alembic_version 中已无对应迁移文件的孤立版本戳。

        Background: if downgrade fails during plugin uninstall, or revision ID prefix doesn't
        match plugin name (e.g. some plugins use custom prefix like ncc_001),
        the version stamp remains in alembic_version, causing subsequent upgrades to fail:
          "Can't locate revision identified by 'xxx'"
        This method scans all currently installed migration files to get valid revision IDs,
        then deletes stamps that don't belong to any known migration.
        / 背景：插件卸载时若 downgrade 失败或 revision ID 前缀与插件名不一致，
        其版本戳会残留在 alembic_version，导致后续任何 upgrade 均报错。
        此方法通过扫描所有当前安装的迁移文件获取合法 revision ID，
        然后删除不属于任何已知迁移的孤立戳。
        """
        import re as _re

        from sqlalchemy import text

        # 1. Collect valid revision IDs from main project + DB-registered plugins
        # / 1. 收集主项目 + 数据库已注册插件的合法 revision ID
        known_revisions: set[str] = set()
        dirs_to_scan = [
            Path(path)
            for path in build_migration_version_locations(
                backend_dir=PLUGINS_DIR.parent,
            )
        ]

        for vdir in dirs_to_scan:
            if not vdir.is_dir():
                continue
            for f in vdir.iterdir():
                if f.suffix == ".py" and f.name != "__init__.py":
                    try:
                        source = f.read_text(encoding="utf-8")
                        m = _re.search(
                            r'^revision\s*(?::[^=]*)?=\s*["\']([^"\']+)["\']',
                            source,
                            _re.MULTILINE,
                        )
                        if m:
                            known_revisions.add(m.group(1))
                    except Exception:
                        pass

        # 2. Query all version stamps in alembic_version / 查询 alembic_version 中的全部版本戳
        try:
            result = await self._db.execute(
                text("SELECT version_num FROM alembic_version")
            )
            all_stamps = [row[0] for row in result.fetchall()]
        except Exception:
            return

        # 3. Delete orphaned stamps (not in any known migration file)
        # / 3. 删除孤立戳（不在任何已知迁移文件中）
        orphaned = [s for s in all_stamps if s not in known_revisions]
        for stamp in orphaned:
            logger.warning(
                "Purging orphaned alembic stamp '{}' (no migration file found for it)",
                stamp,
            )
            await self._db.execute(
                text("DELETE FROM alembic_version WHERE version_num = :vid"),
                {"vid": stamp},
            )
        if orphaned:
            await self._db.flush()
            logger.info(
                "Purged {} orphaned alembic stamp(s): {}", len(orphaned), orphaned
            )

    async def run_alembic_upgrade(self, plugin_name: str) -> None:
        """Run plugin Alembic migration (public interface, called by version_manager etc.).
        / 执行插件 Alembic 迁移（公共接口，供 version_manager 等调用）

        Uses Alembic Python API (not CLI) to dynamically inject version_locations.
        Alembic CLI reads version_locations from alembic.ini at ScriptDirectory.from_config(),
        before env.py runs, so dynamic paths won't take effect.
        Using Python API to set Config then call command.upgrade() solves this.
        / 使用 Alembic Python API（而非 CLI）来动态注入 version_locations。

        Important: must add ALL installed plugins' migration paths to version_locations,
        otherwise other plugins' revision stamps in alembic_version can't be resolved,
        causing "Can't locate revision identified by 'xxx'" errors.
        / 重要：必须把所有已安装插件的迁移路径都加入 version_locations。
        """

        # Purge orphaned version stamps before upgrade (prevent uninstalled plugins' stamps from blocking upgrade)
        # / 升级前清除孤立版本戳（防止已卸载插件的 stamp 阻断升级）
        await self._purge_orphaned_alembic_stamps()

        branch_label = f"plugin_{plugin_name.replace('-', '_')}"

        version_locations = build_migration_version_locations(
            backend_dir=PLUGINS_DIR.parent,
            include_plugin_names=[plugin_name],
        )

        # Run via sys.executable -c to use Alembic Python API in a subprocess,
        # keeping sync Alembic isolated from the async event loop.
        # alembic.ini only has 'migrations/versions' (main app); plugin paths are injected here.
        #
        # Compat scenario: plugin tables exist but version stamp is missing (common in historical data/manual fixes);
        # upgrade may fail with DuplicateTable. In that case stamp the plugin branch to head
        # to clear duplicate warnings and restore migration state consistency.
        # / 兼容场景：插件表已存在但版本戳缺失时，
        # upgrade 可能因 DuplicateTable 失败。此时对插件分支执行 stamp 到 head。
        script = f"""
from alembic.config import Config
from alembic import command
import os

cfg = Config('alembic.ini')
version_locations = {version_locations!r}
target = {f"{branch_label}@head"!r}

cfg.set_main_option('version_locations', '\\n'.join(version_locations))

try:
    command.upgrade(cfg, target)
except Exception as exc:
    err = str(exc)
    if 'already exists' in err or 'DuplicateTable' in type(exc).__name__:
        command.stamp(cfg, target)
    else:
        raise
"""
        result = await run_subprocess_async(
            sys.executable,
            "-c",
            script,
            timeout=120,
            cwd=str(PLUGINS_DIR.parent),
            shell=False,
        )
        if result.returncode != 0:
            err_output = (
                result.stderr.strip() or result.stdout.strip() or "unknown error"
            )
            raise PluginInstallError(
                message=resolve_public_error_message(
                    err_output,
                    fallback_message=f"Alembic upgrade failed for '{plugin_name}'",
                ),
            )

    def _plugin_has_migrations(self, plugin_name: str) -> bool:
        """Check if plugin has Alembic migration files / 检查插件是否有 Alembic 迁移文件"""
        migrations_dir = (
            PLUGINS_DIR / plugin_name / "backend" / "migrations" / "versions"
        )
        if not migrations_dir.is_dir():
            return False
        return any(
            f.suffix == ".py" and f.name != "__init__.py"
            for f in migrations_dir.iterdir()
        )

    async def run_alembic_downgrade(self, plugin_name: str) -> None:
        """Downgrade plugin Alembic migration (public interface, called by version_manager etc.).
        / 回退插件 Alembic 迁移（公共接口，供 version_manager 等调用）

        Safety checks:
        - Plugin must have migration files, otherwise skip (prevent accidentally downgrading main project migrations)
        - Uses plugin's revision ID prefix matching, not branch_label (plugin migrations may not declare branch_labels)
        / 安全检查：
        - 插件必须有迁移文件，否则跳过（防止误回退主项目迁移）
        - 使用插件的 revision ID 前缀匹配，而非 branch_label
        """
        if not self._plugin_has_migrations(plugin_name):
            logger.info(
                "Plugin {} has no migration files, skipping alembic downgrade",
                plugin_name,
            )
            return

        import re as _re

        from sqlalchemy import text as _text

        branch_label = f"plugin_{plugin_name.replace('-', '_')}"
        version_locations = build_migration_version_locations(
            backend_dir=PLUGINS_DIR.parent,
            include_plugin_names=[plugin_name],
        )

        # Scan migration files to get actual revision IDs, then query DB directly.
        # More reliable than alembic command.current(): the latter depends on version_locations containing plugin paths,
        # and assumes revision ID contains plugin name prefix (e.g. ncc_001 doesn't contain novus_crud_code prefix).
        # / 扫描迁移文件获取实际 revision ID，然后直接查询 DB。
        migrations_dir = (
            PLUGINS_DIR / plugin_name / "backend" / "migrations" / "versions"
        )
        plugin_revision_ids: list[str] = []
        for _f in migrations_dir.iterdir():
            if _f.suffix == ".py" and _f.name != "__init__.py":
                try:
                    _src = _f.read_text(encoding="utf-8")
                    _m = _re.search(
                        r'^revision\s*(?::[^=]*)?=\s*["\']([^"\']+)["\']',
                        _src,
                        _re.MULTILINE,
                    )
                    if _m:
                        plugin_revision_ids.append(_m.group(1))
                except Exception:
                    pass

        if not plugin_revision_ids:
            logger.info(
                "Plugin {}: no revision IDs found in migration files, skipping downgrade",
                plugin_name,
            )
            return

        # Directly query alembic_version table, no alembic subprocess needed
        # / 直接查询 alembic_version 表，无需 alembic subprocess
        has_stamp = False
        for _rev_id in plugin_revision_ids:
            _row = await self._db.execute(
                _text("SELECT 1 FROM alembic_version WHERE version_num = :vid"),
                {"vid": _rev_id},
            )
            if _row.scalar():
                has_stamp = True
                break

        if not has_stamp:
            logger.info(
                "Plugin {} has no alembic version stamp, skipping downgrade",
                plugin_name,
            )
            return

        downgrade_script = f"""
from alembic.config import Config
from alembic import command
import os

cfg = Config('alembic.ini')
version_locations = {version_locations!r}
cfg.set_main_option('version_locations', '\\n'.join(version_locations))
command.downgrade(cfg, {f"{branch_label}@base"!r})
"""
        result = await run_subprocess_async(
            sys.executable,
            "-c",
            downgrade_script,
            timeout=120,
            cwd=str(PLUGINS_DIR.parent),
            shell=False,
        )
        if result.returncode != 0:
            logger.warning(
                "Alembic downgrade for {}: {}", plugin_name, result.stderr.strip()
            )

    async def _cleanup_plugin_database(self, plugin_name: str) -> None:
        """Clean up plugin database resources: DROP plugin tables + clean alembic version stamps.
        / 清理插件数据库资源：DROP 插件表 + 清理 alembic 版本戳

        Strategy:
        1. Try alembic downgrade (graceful rollback, preserves data integrity)
        2. If alembic fails, directly DROP all plugin-prefixed tables (fallback)
        3. Always clean alembic_version plugin version stamps
        / 策略：
        1. 尝试 alembic downgrade（优雅回退）
        2. 若 alembic 失败，直接 DROP 所有插件前缀表（兜底）
        3. 无论如何，清理 alembic_version 中的插件版本戳
        """
        from sqlalchemy import text

        table_prefixes = self._resolve_plugin_table_prefixes(plugin_name)
        escaped_table_prefixes = [
            escape_like_pattern(prefix) for prefix in table_prefixes
        ]

        # Step 1: Try alembic downgrade (only when plugin has migration files)
        # / Step 1: 尝试 alembic downgrade（仅当插件有迁移文件时）
        alembic_ok = False
        if self._plugin_has_migrations(plugin_name):
            try:
                await self.run_alembic_downgrade(plugin_name)
                alembic_ok = True
            except Exception as exc:
                logger.warning(
                    "Plugin {} alembic downgrade failed: {}", plugin_name, exc
                )
        else:
            logger.info(
                "Plugin {} has no migrations, skipping alembic downgrade", plugin_name
            )

        # Step 2: Check for remaining tables, DROP directly if found
        # / Step 2: 检查是否还有残留表，若有则直接 DROP
        try:
            # Critical cleanup SQL uses savepoint to prevent local exceptions from polluting outer transaction
            # / 关键清理 SQL 使用 savepoint，避免局部异常污染外层事务
            async with self._db.begin_nested():
                remaining_tables: set[str] = set()
                for escaped_prefix in escaped_table_prefixes:
                    result = await self._db.execute(
                        text(
                            "SELECT tablename FROM pg_tables "
                            "WHERE schemaname = 'public' AND tablename LIKE :prefix ESCAPE '\\'"
                        ),
                        {"prefix": f"{escaped_prefix}%"},
                    )
                    remaining_tables.update(row[0] for row in result.fetchall())

                if remaining_tables:
                    if alembic_ok:
                        logger.warning(
                            "Plugin {}: alembic downgrade succeeded but {} tables remain, dropping directly",
                            plugin_name,
                            len(remaining_tables),
                        )
                    for tbl in sorted(remaining_tables):
                        if not is_safe_plugin_table_name(tbl, table_prefixes):
                            logger.warning(
                                "Plugin {}: skip dropping unsafe table name '{}'",
                                plugin_name,
                                tbl,
                            )
                            continue
                        try:
                            await self._db.execute(
                                text(f'DROP TABLE IF EXISTS "{tbl}" CASCADE')
                            )
                            logger.info("Plugin {}: dropped table {}", plugin_name, tbl)
                        except Exception as exc:
                            logger.error(
                                "Plugin {}: failed to drop table {}: {}",
                                plugin_name,
                                tbl,
                                exc,
                            )
                    await self._db.flush()
        except Exception as exc:
            logger.error(
                "Plugin {}: failed to query/drop residual tables: {}", plugin_name, exc
            )

        # Step 3: Clean alembic_version plugin version stamps
        # Prefer scanning migration files for actual revision IDs (avoid short prefix like ncc_ not matching plugin name)
        # / Step 3: 清理 alembic_version 中的插件版本戳
        # 优先通过扫描迁移文件获取实际 revision ID
        import re as _re

        revision_ids_from_files: list[str] = []
        migrations_dir = (
            PLUGINS_DIR / plugin_name / "backend" / "migrations" / "versions"
        )
        if migrations_dir.is_dir():
            for f in migrations_dir.iterdir():
                if f.suffix == ".py" and f.name != "__init__.py":
                    try:
                        source = f.read_text(encoding="utf-8")
                        m = _re.search(
                            r'^revision\s*(?::[^=]*)?=\s*["\']([^"\']+)["\']',
                            source,
                            _re.MULTILINE,
                        )
                        if m:
                            revision_ids_from_files.append(m.group(1))
                    except Exception:
                        pass

        try:
            # Critical cleanup SQL uses savepoint to prevent local exceptions from polluting outer transaction
            # / 关键清理 SQL 使用 savepoint，避免局部异常污染外层事务
            async with self._db.begin_nested():
                if revision_ids_from_files:
                    # Exact match: delete by revision IDs read from files
                    # / 精确匹配：用文件中读到的 revision ID 删除
                    deleted_count = 0
                    for vid in revision_ids_from_files:
                        result = await self._db.execute(
                            text(
                                "DELETE FROM alembic_version WHERE version_num = :vid"
                            ),
                            {"vid": vid},
                        )
                        deleted_count += result.rowcount
                    if deleted_count:
                        logger.info(
                            "Plugin {}: cleaned {} alembic_version stamp(s) by revision ID",
                            plugin_name,
                            deleted_count,
                        )
                else:
                    # Fallback: match by plugin name prefix, escaping LIKE wildcards
                    # / 兜底：按插件名前缀匹配，并转义 LIKE 通配符
                    version_prefix = plugin_name.replace("-", "_") + "_"
                    escaped_version_prefix = escape_like_pattern(version_prefix)
                    result = await self._db.execute(
                        text(
                            "DELETE FROM alembic_version WHERE version_num LIKE :prefix ESCAPE '\\'"
                        ),
                        {"prefix": f"{escaped_version_prefix}%"},
                    )
                    if result.rowcount:
                        logger.info(
                            "Plugin {}: cleaned {} alembic_version stamp(s) by prefix fallback",
                            plugin_name,
                            result.rowcount,
                        )
                await self._db.flush()
        except Exception as exc:
            logger.warning(
                "Plugin {}: failed to clean alembic_version: {}", plugin_name, exc
            )
