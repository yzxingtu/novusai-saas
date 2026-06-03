"""Alembic/database cleanup helpers extracted from PluginLifecycle."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.core.response import resolve_public_error_message
from app.plugins.exceptions import PluginError, PluginInstallError
from app.plugins.lifecycle_support import (
    escape_like_pattern,
    is_safe_plugin_table_name,
    run_subprocess_async,
)
from app.plugins.loader import PLUGINS_DIR, PluginLoader
from app.plugins.migration_paths import build_migration_version_locations

if TYPE_CHECKING:
    pass


logger = get_logger(__name__)


def _collect_plugin_revision_ids(plugin_name: str) -> list[str]:
    """中文: 从插件迁移目录收集显式 Alembic revision ID。

    EN: Collect explicit Alembic revision IDs from a plugin migration directory.
    """
    import re as _re

    migrations_dir = PLUGINS_DIR / plugin_name / "backend" / "migrations" / "versions"
    if not migrations_dir.is_dir():
        return []

    revision_ids: list[str] = []
    for migration_file in sorted(migrations_dir.iterdir()):
        if migration_file.suffix != ".py" or migration_file.name == "__init__.py":
            continue
        try:
            source = migration_file.read_text(encoding="utf-8")
        except Exception as exc:
            raise PluginInstallError(
                message=(
                    f"Cannot read migration file '{migration_file.name}' for "
                    f"plugin '{plugin_name}'"
                ),
            ) from exc
        match = _re.search(
            r'^revision\s*(?::[^=]*)?=\s*["\']([^"\']+)["\']',
            source,
            _re.MULTILINE,
        )
        if not match:
            raise PluginInstallError(
                message=(
                    f"Migration file '{migration_file.name}' for plugin "
                    f"'{plugin_name}' does not declare a revision"
                ),
            )
        revision_ids.append(match.group(1))
    return revision_ids


class LifecycleMigrationMixin:
    """Alembic/database cleanup helpers extracted from PluginLifecycle."""

    def _resolve_plugin_table_prefixes_strict(self, plugin_name: str) -> list[str]:
        """中文: 仅从有效 manifest 解析插件 DB 表前缀，不做猜测。

        EN: Resolve plugin DB table prefixes from a valid manifest, without guessing.
        """
        own_prefix = f"px_{plugin_name.replace('-', '_')}_"
        prefixes: list[str] = [own_prefix]
        loader = getattr(self, "_loader", None) or PluginLoader()
        try:
            manifest = loader.load_manifest(plugin_name)
        except Exception as exc:
            raise PluginError(
                message=(
                    f"Cannot resolve DB table prefixes for plugin '{plugin_name}'. "
                    "Fix plugin.yaml before database cleanup."
                ),
            ) from exc

        extra_prefixes = getattr(manifest, "db_table_prefixes", None) or []
        for prefix in extra_prefixes:
            normalized = (prefix or "").strip()
            if normalized:
                prefixes.append(normalized)
        return list(dict.fromkeys(prefixes))

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

        branch_label = f"plugin_{plugin_name.replace('-', '_')}"

        version_locations = build_migration_version_locations(
            backend_dir=PLUGINS_DIR.parent,
            include_plugin_names=[plugin_name],
        )

        # Run via sys.executable -c to use Alembic Python API in a subprocess,
        # keeping sync Alembic isolated from the async event loop.
        # alembic.ini only has 'migrations/versions' (main app); plugin paths are injected here.
        script = f"""
from alembic.config import Config
from alembic import command
import os

cfg = Config('alembic.ini')
version_locations = {version_locations!r}
target = {f"{branch_label}@head"!r}

cfg.set_main_option('version_locations', '\\n'.join(version_locations))
command.upgrade(cfg, target)
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
        plugin_revision_ids = _collect_plugin_revision_ids(plugin_name)

        if not plugin_revision_ids:
            raise PluginInstallError(
                message=f"Plugin '{plugin_name}' has migration files but no revisions",
            )

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
            err_output = (
                result.stderr.strip() or result.stdout.strip() or "unknown error"
            )
            raise PluginInstallError(
                message=resolve_public_error_message(
                    err_output,
                    fallback_message=f"Alembic downgrade failed for '{plugin_name}'",
                ),
            )

    async def _cleanup_plugin_database(self, plugin_name: str) -> None:
        """Clean up plugin database resources: DROP plugin tables + clean alembic version stamps.
        / 清理插件数据库资源：DROP 插件表 + 清理 alembic 版本戳

        Strategy:
        1. Try alembic downgrade when migrations exist; failures block cleanup.
        2. Plugins without migrations may drop only manifest-owned safe table prefixes.
        3. Clean alembic_version by exact revision IDs only.
        / 策略：
        1. 存在迁移时先执行 alembic downgrade；失败则阻断清理。
        2. 无迁移插件仅允许按 manifest 声明的安全表前缀清理。
        3. 仅按精确 revision ID 清理 alembic_version。
        """
        from sqlalchemy import text

        table_prefixes = self._resolve_plugin_table_prefixes_strict(plugin_name)
        escaped_table_prefixes = [
            escape_like_pattern(prefix) for prefix in table_prefixes
        ]

        # Step 1: Try alembic downgrade (only when plugin has migration files)
        # / Step 1: 尝试 alembic downgrade（仅当插件有迁移文件时）
        has_migrations = self._plugin_has_migrations(plugin_name)
        if has_migrations:
            try:
                await self.run_alembic_downgrade(plugin_name)
            except Exception as exc:
                raise PluginInstallError(
                    message=(
                        f"Plugin '{plugin_name}' database cleanup blocked: "
                        "alembic downgrade failed"
                    ),
                ) from exc
        else:
            logger.info(
                "Plugin {} has no migrations, skipping alembic downgrade", plugin_name
            )

        # Step 2: Check for remaining tables. If migrations exist, residual tables
        # indicate a broken migration contract and must not be hidden by direct DROP.
        # / Step 2: 检查残留表；有迁移仍残留说明迁移契约错误，不能用直接 DROP 掩盖。
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
                    if has_migrations:
                        safe_remaining = [
                            tbl
                            for tbl in sorted(remaining_tables)
                            if is_safe_plugin_table_name(tbl, table_prefixes)
                        ]
                        raise PluginInstallError(
                            message=(
                                f"Plugin '{plugin_name}' database cleanup blocked: "
                                "alembic downgrade left plugin tables behind"
                            ),
                            data={"tables": safe_remaining},
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
                            raise PluginInstallError(
                                message=(
                                    f"Plugin '{plugin_name}' database cleanup blocked: "
                                    "residual table cleanup failed"
                                ),
                                data={"table": tbl},
                            ) from exc
                    await self._db.flush()
        except Exception as exc:
            if isinstance(exc, PluginInstallError):
                raise
            logger.error(
                "Plugin {}: failed to query/drop residual tables: {}", plugin_name, exc
            )
            raise PluginInstallError(
                message=(
                    f"Plugin '{plugin_name}' database cleanup blocked: "
                    "residual table cleanup failed"
                ),
            ) from exc

        # Step 3: Clean alembic_version plugin version stamps
        # Prefer scanning migration files for actual revision IDs (avoid short prefix like ncc_ not matching plugin name)
        # / Step 3: 清理 alembic_version 中的插件版本戳
        # 优先通过扫描迁移文件获取实际 revision ID
        revision_ids_from_files = _collect_plugin_revision_ids(plugin_name)

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
                    logger.info(
                        "Plugin {}: no migration revisions found; skipping alembic_version cleanup",
                        plugin_name,
                    )
                await self._db.flush()
        except Exception as exc:
            raise PluginInstallError(
                message=(
                    f"Plugin '{plugin_name}' database cleanup blocked: "
                    "alembic_version cleanup failed"
                ),
            ) from exc
