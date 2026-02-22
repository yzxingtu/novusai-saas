"""
插件数据库迁移运行器

负责检测、执行和回滚插件的数据库迁移文件。
插件可在 ``{plugin_dir}/migrations/`` 目录中放置编号 SQL 迁移文件：
- ``001_create_tables.sql`` — 升级脚本
- ``001_create_tables.down.sql`` — 降级脚本（可选，用于回滚）

迁移按文件名排序依次执行，已执行的迁移记录在 ``plugin_migrations`` 表中。
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import _
from app.core.logging import LogManager
from app.exceptions import BusinessException
from app.core.base_model import utc_now

logger = LogManager.get_logger("plugin")

_MIGRATION_PATTERN = re.compile(r"^(\d{3,})_.+\.sql$")
_DOWN_SUFFIX = ".down.sql"


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _parse_version(filename: str) -> str:
    """从文件名中提取版本号前缀（如 001）"""
    m = _MIGRATION_PATTERN.match(filename)
    if m:
        return m.group(1)
    return filename


def _to_module_name(plugin_name: str) -> str:
    """将插件名（如 rich-editor）转为模块目录名（如 rich_editor）"""
    return plugin_name.replace("-", "_")


def discover_migrations(plugin_name: str) -> list[Path]:
    """发现插件迁移文件

    扫描 ``app/plugins/{module_name}/migrations/`` 目录中匹配
    ``NNN_description.sql`` 格式的文件（排除 ``.down.sql``），按名称排序。

    Args:
        plugin_name: 插件名称

    Returns:
        升级迁移文件路径列表（已排序）
    """
    plugins_base = Path(__file__).resolve().parent.parent / "plugins"
    migrations_dir = plugins_base / _to_module_name(plugin_name) / "migrations"

    if not migrations_dir.is_dir():
        return []

    files = []
    for f in sorted(migrations_dir.iterdir()):
        if f.is_file() and _MIGRATION_PATTERN.match(f.name) and not f.name.endswith(_DOWN_SUFFIX):
            files.append(f)
    return files


async def get_applied_versions(
    db: AsyncSession, plugin_name: str,
) -> set[str]:
    """获取已执行的迁移版本集合"""
    from sqlalchemy import select
    from app.models.system.plugin_migration import PluginMigration

    stmt = select(PluginMigration.version).where(
        PluginMigration.plugin_name == plugin_name,
        PluginMigration.is_deleted == False,  # noqa: E712
    )
    result = await db.execute(stmt)
    return {row[0] for row in result.all()}


async def run_migrations(
    db: AsyncSession, plugin_name: str,
) -> list[str]:
    """执行插件的待执行迁移

    按序号顺序执行所有未执行的迁移文件，并将记录写入
    ``plugin_migrations`` 表。

    Args:
        db: 数据库会话
        plugin_name: 插件名称

    Returns:
        已执行的迁移文件名列表

    Raises:
        BusinessException: 迁移执行失败
    """
    from sqlalchemy import text
    from app.models.system.plugin_migration import PluginMigration

    migration_files = discover_migrations(plugin_name)
    if not migration_files:
        return []

    applied = await get_applied_versions(db, plugin_name)
    executed: list[str] = []

    for mf in migration_files:
        version = _parse_version(mf.name)
        if version in applied:
            logger.debug(
                "Plugin migration already applied: %s/%s",
                plugin_name, mf.name,
            )
            continue

        sql_content = mf.read_text(encoding="utf-8").strip()
        if not sql_content:
            continue

        logger.info(
            "Applying plugin migration: %s/%s",
            plugin_name, mf.name,
        )

        try:
            # 逐条执行 SQL 语句（以分号分隔）
            for stmt_text in _split_sql(sql_content):
                await db.execute(text(stmt_text))

            record = PluginMigration(
                plugin_name=plugin_name,
                version=version,
                filename=mf.name,
                checksum=_sha256(sql_content),
                description=mf.stem.split("_", 1)[1] if "_" in mf.stem else None,
                applied_at=utc_now(),
            )
            db.add(record)
            await db.flush()
            executed.append(mf.name)
        except Exception as exc:
            logger.error(
                "Plugin migration failed: %s/%s — %s",
                plugin_name, mf.name, exc, exc_info=True,
            )
            raise BusinessException(
                _("plugin.migration_failed")
            ) from exc

    if executed:
        from app.plugins.security import log_plugin_action
        log_plugin_action(
            action="run_migrations",
            plugin_name=plugin_name,
            details={"applied": executed},
        )
        logger.info(
            "Plugin migrations applied: %s — %s",
            plugin_name, executed,
        )

    return executed


async def rollback_migrations(
    db: AsyncSession, plugin_name: str,
) -> dict[str, list[str]]:
    """回滚插件的所有已执行迁移

    按版本号倒序查找 ``.down.sql`` 文件并执行。如果 down 文件不存在则跳过。
    回滚后删除对应的 ``plugin_migrations`` 记录。

    Args:
        db: 数据库会话
        plugin_name: 插件名称

    Returns:
        结构化结果：{"rolled_back": [...], "skipped": [...], "warnings": [...]}
    """
    from sqlalchemy import select, delete
    from app.models.system.plugin_migration import PluginMigration

    stmt = (
        select(PluginMigration)
        .where(
            PluginMigration.plugin_name == plugin_name,
            PluginMigration.is_deleted == False,  # noqa: E712
        )
        .order_by(PluginMigration.version.desc())
    )
    result = await db.execute(stmt)
    records = list(result.scalars().all())

    if not records:
        return {"rolled_back": [], "skipped": [], "warnings": []}

    plugins_base = Path(__file__).resolve().parent.parent / "plugins"
    migrations_dir = plugins_base / _to_module_name(plugin_name) / "migrations"
    rolled_back: list[str] = []
    skipped: list[str] = []
    warnings: list[str] = []

    for record in records:
        down_file = migrations_dir / record.filename.replace(".sql", _DOWN_SUFFIX)
        if not down_file.exists():
            skipped.append(record.filename)
            warn_msg = f"No down migration for {record.filename} — tables/data may remain"
            warnings.append(warn_msg)
            logger.warning(
                "No down migration for %s/%s — skipping rollback",
                plugin_name, record.filename,
            )
            continue

        sql_content = down_file.read_text(encoding="utf-8").strip()
        if not sql_content:
            continue

        logger.info(
            "Rolling back plugin migration: %s/%s",
            plugin_name, record.filename,
        )

        try:
            from sqlalchemy import text
            for stmt_text in _split_sql(sql_content):
                await db.execute(text(stmt_text))
            rolled_back.append(record.version)
        except Exception as exc:
            warn_msg = f"Rollback failed for {record.filename}: {exc}"
            warnings.append(warn_msg)
            logger.warning(
                "Plugin migration rollback failed: %s/%s — %s (continuing)",
                plugin_name, record.filename, exc, exc_info=True,
            )

    # 删除迁移记录
    if records:
        del_stmt = delete(PluginMigration).where(
            PluginMigration.plugin_name == plugin_name,
        )
        await db.execute(del_stmt)

    rollback_result = {
        "rolled_back": rolled_back,
        "skipped": skipped,
        "warnings": warnings,
    }

    from app.plugins.security import log_plugin_action
    log_plugin_action(
        action="rollback_migrations",
        plugin_name=plugin_name,
        details=rollback_result,
    )
    if rolled_back or skipped:
        logger.info(
            "Plugin migrations rollback: %s — rolled_back=%s skipped=%s",
            plugin_name, rolled_back, skipped,
        )

    return rollback_result


def _split_sql(content: str) -> list[str]:
    """将 SQL 文本按分号拆分为独立语句

    正确处理：
    - 单引号字符串内的分号（如 ``'a;b'``）
    - ``$$`` 引用的函数体（PostgreSQL 函数/匿名块）
    - 空语句跳过
    """
    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_dollar_quote = False
    i = 0
    chars = content

    while i < len(chars):
        ch = chars[i]

        # $$ 引用块（PostgreSQL 函数体/匿名块）
        if chars[i:i + 2] == "$$" and not in_single_quote:
            in_dollar_quote = not in_dollar_quote
            current.append("$$")
            i += 2
            continue

        # 单引号字符串
        if ch == "'" and not in_dollar_quote:
            # 处理转义的单引号 ''
            if i + 1 < len(chars) and chars[i + 1] == "'":
                current.append("''")
                i += 2
                continue
            in_single_quote = not in_single_quote
            current.append(ch)
            i += 1
            continue

        # 分号分隔符（仅在引用外）
        if ch == ";" and not in_single_quote and not in_dollar_quote:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue

        current.append(ch)
        i += 1

    # 最后一条语句（可能没有尾部分号）
    stmt = "".join(current).strip()
    if stmt:
        statements.append(stmt)

    return statements
