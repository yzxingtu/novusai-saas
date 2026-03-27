"""
迁移文件元数据注入 / Migration Helper

为生成的迁移文件注入 codegen 元数据变量
Injects codegen metadata variables into generated migration files.

Web/CLI 回滚时执行 alembic downgrade、删除迁移文件、并自动 DROP 数据表
Run alembic downgrade, delete migration file, and auto DROP table on web/CLI rollback.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_table_name(resource: str) -> str:
    """从 resource 推断表名，与 model 模板一致。Infer table name from resource."""
    from app.codegen.config_parser import _infer_plural
    return _infer_plural(resource.replace("-", "_")) if resource else ""


def _extract_revision(path: Path) -> str | None:
    """从迁移文件中提取 revision ID。Extract revision ID from migration file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^revision[^=]*=\s*['\"]([^'\"]+)['\"]", text, re.MULTILINE)
        return m.group(1).strip() if m else None
    except Exception:
        return None


def _get_current_heads(backend_dir: Path) -> tuple[list[str], str | None]:
    """
    获取当前 alembic head 列表。
    Get list of current alembic head revisions.
    Returns (heads, error_message). heads 非空且 len==1 时表示单 head 安全。
    """
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=str(backend_dir), capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return [], proc.stderr or "alembic current failed"
    heads = re.findall(r"([a-zA-Z0-9_-]+)\s+\(head\)", proc.stdout or "")
    heads = [h.strip() for h in heads if h.strip()]
    return heads, None


def _has_fk_references(table: str) -> list[tuple[str, str]]:
    """
    检查是否有其他表的 FK 引用目标表。
    Check if other tables have FK constraints referencing target table.
    Returns list of (table_name, constraint_name).
    """
    try:
        from sqlalchemy import text

        from app.core.database import sync_session_factory
        with sync_session_factory() as session:
            result = session.execute(text("""
                SELECT tc.table_name, tc.constraint_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu
                    ON tc.constraint_name = ccu.constraint_name
                    AND tc.table_schema = ccu.table_schema
                WHERE ccu.table_name = :tbl
                    AND tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_name != :tbl
            """), {"tbl": table})
            return [(r[0], r[1]) for r in result.fetchall()]
    except Exception as e:
        logger.warning("Cannot check FK references for table %s: %s", table, e)
        return []


def _drop_table_if_exists(resource: str, force_cascade: bool = False) -> bool:
    """
    回滚时删除数据表。
    Drop table on rollback. Checks for FK references before using CASCADE.
    """
    table = _get_table_name(resource)
    if not table:
        return False
    try:
        from sqlalchemy import text

        from app.core.database import sync_session_factory

        fk_refs = _has_fk_references(table)
        if fk_refs and not force_cascade:
            ref_info = ", ".join(f"{t}.{c}" for t, c in fk_refs)
            logger.warning(
                "Table %s is referenced by FK constraints: %s. "
                "Dropping without CASCADE to preserve referential integrity. "
                "You may need to manually clean up FK constraints.",
                table, ref_info,
            )

        cascade = " CASCADE" if (force_cascade or not fk_refs) else ""
        with sync_session_factory() as session:
            session.execute(text(f'DROP TABLE IF EXISTS "{table}"{cascade}'))
            session.commit()
        logger.info("Dropped table %s%s", table, cascade)
        return True
    except Exception as e:
        logger.error("Failed to drop table %s: %s", table, e)
        return False


def run_rollback_migration_cleanup(
    resource: str,
    migration_file: str | None,
    project_root: Path,
    backend_dir: Path | None = None,
    *,
    force_drop: bool = False,
) -> bool:
    """
    回滚后清理迁移：purge 孤立 stamp、downgrade、删除迁移文件。
    After rollback: purge orphaned stamps, downgrade, delete migration file.

    Safety: only downgrades if the codegen migration is the current head.
    If later migrations exist on top, refuses to downgrade to prevent chain breakage.

    Returns:
        True 若成功执行 downgrade 并删除迁移文件
    """
    _backend = backend_dir or (project_root / "backend")
    _backend = Path(_backend)
    if not _backend.exists():
        return False

    _mp = _locate_migration_file(migration_file, resource, _backend)

    from app.core.database import purge_orphaned_alembic_stamps
    purge_orphaned_alembic_stamps(_backend)

    if not _mp or not _mp.exists():
        logger.warning(
            "Migration file not found for resource %s, skipping downgrade. "
            "Refusing DROP TABLE without migration file (use force_drop to override).",
            resource,
        )
        if force_drop and resource:
            _drop_table_if_exists(resource)
        return False

    target_rev = _extract_revision(_mp)
    if not target_rev:
        logger.warning("Cannot extract revision from %s, skipping downgrade.", _mp)
        if force_drop and resource:
            _drop_table_if_exists(resource)
        return False

    heads, head_err = _get_current_heads(_backend)
    if head_err:
        logger.error("Cannot get alembic current: %s — refusing downgrade.", head_err)
        if force_drop and resource:
            _drop_table_if_exists(resource)
        return False
    if len(heads) == 0:
        logger.error(
            "No alembic head found — cannot safely determine if %s is current. "
            "Refusing downgrade. Run 'alembic current' to inspect.",
            target_rev,
        )
        if force_drop and resource:
            _drop_table_if_exists(resource)
        return False
    if len(heads) > 1:
        logger.error(
            "Multiple heads detected: %s. Refusing downgrade to prevent chain breakage. "
            "Run 'alembic merge' or 'novusai db merge' first.",
            heads,
        )
        if force_drop and resource:
            _drop_table_if_exists(resource)
        return False
    if heads[0] != target_rev:
        logger.error(
            "Codegen migration %s is NOT the current head (head=%s). "
            "Later migrations depend on it — refusing to downgrade. "
            "Please manually roll back later migrations first.",
            target_rev, heads[0],
        )
        if force_drop and resource:
            _drop_table_if_exists(resource)
        return False

    _down_rev = None
    _txt = _mp.read_text(encoding="utf-8", errors="replace")
    _m = re.search(r"down_revision[^=]*=\s*['\"]([^'\"]+)['\"]", _txt)
    if _m:
        _down_rev = _m.group(1).strip()

    _proc = None
    if _down_rev:
        _proc = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", _down_rev],
            cwd=str(_backend), capture_output=True, text=True,
        )
    else:
        _proc = subprocess.run(
            [sys.executable, "-m", "alembic", "downgrade", "-1"],
            cwd=str(_backend), capture_output=True, text=True,
        )

    migration_cleaned = False
    if _proc is not None and _proc.returncode == 0:
        if _mp.exists():
            _mp.unlink()
            migration_cleaned = True
            logger.info("Downgraded and removed migration %s", _mp.name)
        if resource:
            _drop_table_if_exists(resource)
    else:
        stderr = _proc.stderr if _proc else "no process"
        logger.error("Downgrade failed for %s: %s", target_rev, stderr)

    return migration_cleaned


def _locate_migration_file(
    migration_file: str | None,
    resource: str,
    backend_dir: Path,
) -> Path | None:
    """Locate the migration file from manifest path, fallback to scan by table/codegen_resource."""
    _mp = None
    if migration_file:
        _mp = Path(migration_file)
        if not _mp.is_absolute():
            _mp = backend_dir / migration_file.replace("backend/", "").replace("backend\\", "")
        if not _mp.exists():
            _mp = backend_dir / "migrations" / "versions" / Path(migration_file).name

    _table = _get_table_name(resource)
    _vers = backend_dir / "migrations" / "versions" if _table else None

    if (not _mp or not _mp.exists()) and _vers and _vers.exists():
        for _f in _vers.glob("*.py"):
            if _f.name.startswith(".") or _f.name == "__init__.py":
                continue
            try:
                _t = _f.read_text(encoding="utf-8", errors="replace")
                if (f"'{_table}'" in _t or f'"{_table}"' in _t) and "codegen_resource" in _t:
                    _mp = _f
                    break
            except Exception:
                pass
        if not _mp or not _mp.exists():
            for _f in _vers.glob("*.py"):
                if _f.name.startswith(".") or _f.name == "__init__.py":
                    continue
                try:
                    _t = _f.read_text(encoding="utf-8", errors="replace")
                    if (f"'{_table}'" in _t or f'"{_table}"' in _t):
                        _mp = _f
                        logger.info("Located legacy codegen migration (no metadata) for %s: %s", resource, _f.name)
                        break
                except Exception:
                    pass
    return _mp


def inject_migration_metadata(
    content: str,
    resource: str,
    source: str = "codegen",
    version: str = "1",
) -> str:
    """
    为迁移文件内容注入元数据变量 / Inject metadata variables into migration content.

    Args:
        content: 迁移文件原始内容
        resource: 资源名
        source: 来源标识，默认 codegen
        version: 版本号

    Returns:
        注入元数据后的内容
    """
    meta = f"""
# Codegen metadata / 代码生成器元数据
codegen_source = {repr(source)}
codegen_resource = {repr(resource)}
codegen_version = {repr(version)}
"""
    if "revision" in content and "codegen_source" not in content:
        lines = content.split("\n")
        insert_at = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("revision") and "=" in line:
                insert_at = i + 1
                break
        lines.insert(insert_at, meta)
        return "\n".join(lines)
    return content


__all__ = ["inject_migration_metadata", "run_rollback_migration_cleanup"]
